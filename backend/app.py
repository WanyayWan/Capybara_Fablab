from __future__ import annotations

import asyncio
import socket
import ssl
import tempfile
import uuid
from pathlib import Path

from aiohttp import WSMsgType, web

from services.dev_tls import ensure_development_certificate
from services.llm_service import OllamaLLMService
from services.stt_service import WhisperSTTService

ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"
TMP_ROOT = ROOT / "tmp"
DEVICE_NAME = "FabAI Prototype"
LOCATION = "SUTD Fabrication Lab"


def lan_ip() -> str:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        return probe.getsockname()[0]
    except OSError:
        return ""
    finally:
        probe.close()


class PhoneClients:
    def __init__(self) -> None:
        self.clients: dict[str, web.WebSocketResponse] = {}
        self.active_client_id: str | None = None

    async def register(self, client_id: str, ws: web.WebSocketResponse) -> None:
        old = self.clients.get(client_id)
        if old and not old.closed:
            await old.close(code=1000, message=b"New phone session connected")
        self.clients[client_id] = ws
        self.active_client_id = client_id
        print(f"Phone client connected: {client_id}", flush=True)

    async def remove(self, client_id: str, ws: web.WebSocketResponse) -> None:
        if self.clients.get(client_id) is ws:
            self.clients.pop(client_id, None)
        if self.active_client_id == client_id:
            self.active_client_id = next(iter(self.clients), None)
        print(f"Phone client disconnected: {client_id}", flush=True)

    def active(self) -> tuple[str, web.WebSocketResponse] | None:
        if not self.active_client_id:
            return None
        ws = self.clients.get(self.active_client_id)
        return (self.active_client_id, ws) if ws and not ws.closed else None

    async def send(self, client_id: str, payload: dict[str, object]) -> bool:
        ws = self.clients.get(client_id)
        if not ws or ws.closed:
            return False
        await ws.send_json(payload)
        return True


phone_clients = PhoneClients()
stt_service = WhisperSTTService()
llm_service = OllamaLLMService()


async def root_handler(request: web.Request) -> web.FileResponse:
    if not request.secure:
        host = request.host.split(":")[0]
        raise web.HTTPTemporaryRedirect(location=f"https://{host}:8443/")
    return web.FileResponse(WEB_ROOT / "index.html")


async def health_handler(request: web.Request) -> web.Response:
    return web.json_response(
        {
            "status": "ok",
            "service": "fabai-backend",
            "phone_voice_client": "connected" if phone_clients.active() else "offline",
        }
    )


async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
    client_id = request.query.get("client_id") or f"phone-{uuid.uuid4().hex[:8]}"
    ws = web.WebSocketResponse(heartbeat=25)
    await ws.prepare(request)
    await phone_clients.register(client_id, ws)
    await phone_clients.send(client_id, {"type": "ready", "client_id": client_id})
    try:
        async for message in ws:
            if message.type == WSMsgType.ERROR:
                print(f"Phone WebSocket error: {ws.exception()}", flush=True)
    finally:
        await phone_clients.remove(client_id, ws)
    return ws


async def json_body(request: web.Request) -> dict[str, object]:
    try:
        return await request.json()
    except Exception:
        raise web.HTTPBadRequest(text="Expected JSON request body.")


async def device_register_handler(request: web.Request) -> web.Response:
    payload = await json_body(request)
    device_id = str(payload.get("device_id", "unknown"))
    return web.json_response({"device_id": device_id, "name": DEVICE_NAME, "location": LOCATION})


async def heartbeat_handler(request: web.Request) -> web.Response:
    payload = await json_body(request)
    return web.json_response({"device_id": str(payload.get("device_id", "unknown")), "backend": "online"})


async def device_event_handler(request: web.Request) -> web.Response:
    payload = await json_body(request)
    device_id = str(payload.get("device_id", "unknown"))
    if payload.get("event") != "talk_button_pressed":
        return web.json_response({"error": "unsupported event"}, status=400)
    active = phone_clients.active()
    if not active:
        print(f"BOOT event from {device_id}; no phone voice client is ready.", flush=True)
        return web.json_response({"accepted": False, "state": "phone_offline"}, status=202)
    client_id, _ = active
    session_id = uuid.uuid4().hex
    print(f"BOOT event received from {device_id}; notifying phone {client_id}.", flush=True)
    await phone_clients.send(
        client_id,
        {"type": "start_listening", "device_id": device_id, "client_id": client_id, "session_id": session_id},
    )
    return web.json_response({"accepted": True, "state": "listening", "session_id": session_id}, status=202)


async def phone_audio_handler(request: web.Request) -> web.Response:
    reader = await request.multipart()
    client_id = ""
    session_id = ""
    audio_path: Path | None = None
    try:
        while part := await reader.next():
            if part.name == "client_id":
                client_id = (await part.text()).strip()
            elif part.name == "session_id":
                session_id = (await part.text()).strip()
            elif part.name == "audio":
                TMP_ROOT.mkdir(exist_ok=True)
                with tempfile.NamedTemporaryFile(delete=False, dir=TMP_ROOT, suffix=".webm") as file:
                    audio_path = Path(file.name)
                    total = 0
                    while chunk := await part.read_chunk():
                        total += len(chunk)
                        if total > 12 * 1024 * 1024:
                            raise web.HTTPRequestEntityTooLarge(max_size=12 * 1024 * 1024, actual_size=total)
                        file.write(chunk)
        if not client_id or not session_id or not audio_path:
            raise web.HTTPBadRequest(text="Missing phone audio metadata.")
        await phone_clients.send(client_id, {"type": "state", "state": "TRANSCRIBING"})
        transcription = await asyncio.to_thread(stt_service.transcribe_file, str(audio_path))
        if not transcription:
            await phone_clients.send(client_id, {"type": "error", "message": "No speech was detected. Please try again."})
            return web.json_response({"accepted": False, "error": "empty transcription"}, status=422)
        print("\n" + "=" * 40)
        print("FabAI Phone Voice Session")
        print("Device: fabai-01")
        print(f"Client: {client_id}")
        print(f"Session: {session_id}")
        print(f'\nTranscription:\n"{transcription}"')
        print("=" * 40 + "\n", flush=True)
        await phone_clients.send(client_id, {"type": "transcription", "session_id": session_id, "text": transcription})
        return web.json_response({"accepted": True, "transcription": transcription})
    except web.HTTPException:
        raise
    except Exception as error:
        print(f"Phone audio processing failed: {error}", flush=True)
        if client_id:
            await phone_clients.send(client_id, {"type": "error", "message": "FabAI could not transcribe this recording."})
        return web.json_response({"accepted": False, "error": "transcription failed"}, status=500)
    finally:
        if audio_path:
            audio_path.unlink(missing_ok=True)


async def ask_handler(request: web.Request) -> web.Response:
    payload = await json_body(request)
    question = str(payload.get("question", "")).strip()
    if not question or len(question) > 2000:
        return web.json_response({"error": "Please enter a question."}, status=400)
    try:
        return web.json_response({"answer": await asyncio.to_thread(llm_service.answer, question)})
    except RuntimeError as error:
        return web.json_response({"error": str(error)}, status=503)


def build_app() -> web.Application:
    app = web.Application(client_max_size=12 * 1024 * 1024)
    app.router.add_get("/", root_handler)
    app.router.add_get("/health", health_handler)
    app.router.add_get("/ws", websocket_handler)
    app.router.add_post("/api/device/register", device_register_handler)
    app.router.add_post("/api/device/heartbeat", heartbeat_handler)
    app.router.add_post("/api/device/event", device_event_handler)
    app.router.add_post("/api/phone/audio", phone_audio_handler)
    app.router.add_post("/api/ask", ask_handler)
    app.router.add_static("/static/", WEB_ROOT)
    return app


async def serve() -> None:
    ip = lan_ip()
    ca_path, cert_path, key_path = ensure_development_certificate(ROOT / "certs", ip)
    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_context.load_cert_chain(certfile=cert_path, keyfile=key_path)
    print("\n" + "=" * 40)
    print("FabAI Backend Running")
    print("\nLaptop:\nhttps://localhost:8443")
    print(f"\nPhone:\nhttps://{ip}:8443" if ip else "\nLAN address unavailable")
    print("\nESP32 API:\nhttp://<laptop-ip>:8000")
    print("Phone Voice Client: Offline")
    print(f"\nDevelopment CA for phone trust:\n{ca_path}")
    print("=" * 40 + "\n", flush=True)
    app = build_app()
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", 8000).start()
    await web.TCPSite(runner, "0.0.0.0", 8443, ssl_context=ssl_context).start()
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(serve())
