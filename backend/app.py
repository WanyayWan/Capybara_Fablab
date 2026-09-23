"""FabAI backend HTTP server.

`build_app(container)` wires the routes to already-built dependencies, so tests pass
fakes. `main()` builds the real services (mic, Whisper, Ollama, TTS, notifier), embeds
the knowledge base, starts the Telegram poller if configured, and serves plain HTTP on
`0.0.0.0:PORT`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import asdict, dataclass
from typing import Any, Protocol

import aiohttp
from aiohttp import web

from config import BACKEND_ROOT, Settings, get_device
from core.device_state import DeviceStateStore
from core.pipeline import HELP_ACTIONS, Answer, DeviceLookup, LLMLike, VoicePipeline
from core.sessions import SessionManager
from services.audio_service import Recorder
from services.embedder import OllamaEmbedder
from services.knowledge import (
    EmbeddingCache,
    KnowledgeBase,
    knowledge_dirs,
    knowledge_fingerprint,
    load_chunks,
)
from services.llm_service import OllamaChat, OllamaHealth
from services.notify_service import TelegramNotifier, create_notifier
from services.stt_service import WhisperSTT
from services.tts_service import create_tts
from services.unanswered_log import UnansweredLog

log = logging.getLogger("fabai")

SERVICE_NAME = "fabai-backend"
EVENTS = ("talk_pressed", "talk_released", "help_requested")
MAX_QUESTION_CHARS = 2000
MAX_DEVICE_ID_CHARS = 64
API_DEVICE_ID = "api"  # /api/ask without a device_id: machine "all"
KNOWLEDGE_ROOT = BACKEND_ROOT / "knowledge"
UNANSWERED_PATH = BACKEND_ROOT / "data" / "unanswered.jsonl"
KB_CACHE_PATH = BACKEND_ROOT / "data" / "kb_cache.npz"
WARM_UP_MESSAGES = [{"role": "user", "content": "Reply with OK."}]
WARM_UP_QUERY = "warm up"


class UnansweredReader(Protocol):
    def read_all(self) -> list[dict[str, object]]: ...


class Buildable(Protocol):
    def build(self) -> None: ...
    def retrieve(self, query: str, machine: str) -> object: ...


@dataclass
class Container:
    settings: Settings
    pipeline: VoicePipeline
    states: DeviceStateStore
    unanswered: UnansweredReader
    devices: DeviceLookup
    ollama_ok: Callable[[], bool]  # blocking, cached; run in a thread


CONTAINER = web.AppKey("container", Container)


# ---- request helpers ---------------------------------------------------------------


def _bad_request(message: str) -> web.HTTPBadRequest:
    return web.HTTPBadRequest(
        text=json.dumps({"error": message}), content_type="application/json"
    )


async def _json_body(request: web.Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise _bad_request("invalid JSON") from None
    if not isinstance(body, dict):
        raise _bad_request("body must be a JSON object")
    return body


def _device_id(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_DEVICE_ID_CHARS:
        raise _bad_request("device_id is required")
    return value.strip()


def _answer_json(answer: Answer) -> dict[str, object]:
    data = asdict(answer)
    data["intent"] = answer.intent.value
    return data


# ---- handlers ----------------------------------------------------------------------


async def health(request: web.Request) -> web.Response:
    container = request.app[CONTAINER]
    ollama = await asyncio.to_thread(container.ollama_ok)
    return web.json_response({"status": "ok", "service": SERVICE_NAME, "ollama": ollama})


async def register(request: web.Request) -> web.Response:
    device_id = _device_id((await _json_body(request)).get("device_id"))
    device = request.app[CONTAINER].devices(device_id)
    log.info("[%s] registered (%s)", device_id, device["machine"])
    return web.json_response(
        {"device_id": device_id, "machine": device["machine"], "location": device["location"]}
    )


async def heartbeat(request: web.Request) -> web.Response:
    device_id = _device_id((await _json_body(request)).get("device_id"))
    return web.json_response({"device_id": device_id, "backend": "online"})


async def device_event(request: web.Request) -> web.Response:
    body = await _json_body(request)
    device_id = _device_id(body.get("device_id"))
    event = body.get("event")
    if event not in EVENTS:
        raise _bad_request(f"event must be one of {', '.join(EVENTS)}")
    pipeline = request.app[CONTAINER].pipeline
    if event == "talk_pressed":
        result = await pipeline.talk_pressed(device_id)
    elif event == "talk_released":
        held_ms = body.get("held_ms", 0)
        if isinstance(held_ms, bool) or not isinstance(held_ms, int) or held_ms < 0:
            raise _bad_request("held_ms must be a non-negative integer")
        result = await pipeline.talk_released(device_id, held_ms)
    else:
        text = await pipeline.request_help(device_id, source="button")
        help_status = request.app[CONTAINER].states.get(device_id).help
        result = {"accepted": True, "help": help_status.value, "text": text}
    return web.json_response(result, status=202)


async def device_state(request: web.Request) -> web.Response:
    device_id = _device_id(request.query.get("device_id"))
    states = request.app[CONTAINER].states
    state = states.get(device_id)
    return web.json_response(
        {"activity": state.activity.value, "help": state.help.value, "led": states.led(device_id)}
    )


async def ask(request: web.Request) -> web.Response:
    body = await _json_body(request)
    question = body.get("question")
    if not isinstance(question, str) or not question.strip() or len(question) > MAX_QUESTION_CHARS:
        raise _bad_request(f"question must be 1 to {MAX_QUESTION_CHARS} characters")
    device_id = _device_id(body.get("device_id", API_DEVICE_ID))
    speak = body.get("speak", False) is True
    try:
        answer = await request.app[CONTAINER].pipeline.ask(device_id, question.strip(), speak)
    except Exception as error:
        log.exception("[%s] /api/ask failed", device_id)
        return web.json_response({"error": f"could not answer: {error}"}, status=503)
    return web.json_response(_answer_json(answer))


async def help_ack(request: web.Request) -> web.Response:
    body = await _json_body(request)
    device_id = _device_id(body.get("device_id"))
    action = body.get("action")
    if action not in HELP_ACTIONS:
        raise _bad_request(f"action must be one of {', '.join(HELP_ACTIONS)}")
    container = request.app[CONTAINER]
    await container.pipeline.help_update(device_id, action)
    return web.json_response({"help": container.states.get(device_id).help.value})


async def unanswered(request: web.Request) -> web.Response:
    entries = await asyncio.to_thread(request.app[CONTAINER].unanswered.read_all)
    return web.json_response(entries)


def build_app(container: Container) -> web.Application:
    app = web.Application()
    app[CONTAINER] = container
    app.router.add_get("/health", health)
    app.router.add_post("/api/device/register", register)
    app.router.add_post("/api/device/heartbeat", heartbeat)
    app.router.add_post("/api/device/event", device_event)
    app.router.add_get("/api/device/state", device_state)
    app.router.add_post("/api/ask", ask)
    app.router.add_post("/api/help/ack", help_ack)
    app.router.add_get("/api/unanswered", unanswered)
    return app


# ---- real wiring -------------------------------------------------------------------


def lan_ip() -> str:
    """Best guess at this laptop's LAN address (no packets are sent)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.connect(("10.255.255.255", 1))
            return str(probe.getsockname()[0])
        except OSError:
            return "127.0.0.1"


async def _log_failure(what: str, coro: Any) -> None:
    try:
        await coro
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("%s failed", what)


@dataclass
class WarmUpResult:
    embed_s: float | None  # None if embedding failed
    llm_s: float | None  # None if the warm-up chat failed


async def _timed(what: str, func: Callable[[], object]) -> float | None:
    started = time.perf_counter()
    try:
        await asyncio.to_thread(func)
    except Exception as error:
        log.warning("Warm-up: %s failed (%s)", what, error)
        return None
    elapsed = time.perf_counter() - started
    log.info("Warm-up: %s took %.1f s", what, elapsed)
    return elapsed


async def warm_up(kb: Buildable, llm: LLMLike, ollama_ok: Callable[[], bool]) -> WarmUpResult | None:
    """If Ollama is reachable, embed the knowledge base (or load it from the cache) and load
    the chat model now so the first question is fast. The warm-up chat goes through the
    same `llm.chat` as real questions, so model, options and keep_alive are identical.
    Returns None (lazy behaviour) if Ollama is down."""
    if not await asyncio.to_thread(ollama_ok):
        log.warning("Ollama not reachable at startup; knowledge base will embed on first question")
        return None
    embed_s = await _timed("knowledge base embedding (or cache load)", kb.build)
    # A cache hit embeds nothing, so load the embed model with one throwaway query.
    if await _timed("embed model load", lambda: kb.retrieve(WARM_UP_QUERY, "all")) is None:
        embed_s = None
    llm_s = await _timed("LLM load", lambda: llm.chat(WARM_UP_MESSAGES))
    return WarmUpResult(embed_s, llm_s)


async def create_app(settings: Settings) -> web.Application:
    """Build the real services and the app. Runs inside the server's event loop."""
    http = aiohttp.ClientSession()
    recorder = Recorder(max_seconds=settings.max_record_s, pre_roll_s=settings.pre_roll_s)
    try:
        recorder.open()
    except Exception:
        log.warning("Could not open the microphone; voice turns will hear nothing", exc_info=True)

    dirs = knowledge_dirs(KNOWLEDGE_ROOT)
    kb = KnowledgeBase(
        load_chunks(dirs),
        OllamaEmbedder(settings.ollama_url, settings.embed_model, keep_alive=settings.ollama_keep_alive),
        top_k=settings.rag_top_k,
        threshold=settings.rag_threshold,
        machine_boost=settings.rag_machine_boost,
        cache=EmbeddingCache(KB_CACHE_PATH),
        cache_key=knowledge_fingerprint(dirs, settings.embed_model),
    )
    llm = OllamaChat(
        settings.ollama_url,
        settings.ollama_model,
        keep_alive=settings.ollama_keep_alive,
        num_ctx=settings.ollama_num_ctx,
    )
    ollama_health = OllamaHealth(settings.ollama_url)
    await warm_up(kb, llm, ollama_health.check)

    stt = WhisperSTT(settings.whisper_model)
    notifier = create_notifier(settings, http)
    states = DeviceStateStore(time.monotonic, settings.help_ack_clear_s)
    unanswered_log = UnansweredLog(UNANSWERED_PATH)
    pipeline = VoicePipeline(
        settings=settings,
        recorder=recorder,
        stt=stt,
        kb=kb,
        llm=llm,
        tts=create_tts(),
        notifier=notifier,
        states=states,
        sessions=SessionManager(settings.session_timeout_s, settings.session_max_turns),
        unanswered=unanswered_log,
        devices=get_device,
    )
    container = Container(
        settings=settings,
        pipeline=pipeline,
        states=states,
        unanswered=unanswered_log,
        devices=get_device,
        ollama_ok=ollama_health.check,
    )
    app = build_app(container)

    async def lifecycle(app: web.Application) -> AsyncIterator[None]:
        tasks = [asyncio.create_task(_log_failure("Whisper preload", asyncio.to_thread(stt.load)))]
        if isinstance(notifier, TelegramNotifier):
            tasks.append(asyncio.create_task(notifier.run_ack_poller(pipeline.help_update)))
        staff = "Telegram" if isinstance(notifier, TelegramNotifier) else "console (POST /api/help/ack)"
        print(
            f"FabAI backend on http://{lan_ip()}:{settings.port}  "
            f"(enter this in the ESP32 portal; staff alerts: {staff})",
            flush=True,
        )
        yield
        for task in tasks:
            task.cancel()
        await pipeline.drain()
        recorder.close()
        await http.close()

    app.cleanup_ctx.append(lifecycle)
    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = Settings.load()
    web.run_app(create_app(settings), host="0.0.0.0", port=settings.port, print=None)


if __name__ == "__main__":
    main()
