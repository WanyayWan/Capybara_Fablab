"""HTTP API with aiohttp test client and fakes (test-plan: test_api.py)."""

from __future__ import annotations

from typing import Any

import pytest
from aiohttp.test_utils import TestClient

from app import Container, build_app
from config import get_device
from tests.test_pipeline import DEVICE, SD_ANSWER, Rig, make_rig


@pytest.fixture
def rig() -> Rig:
    return make_rig()


@pytest.fixture
async def client(aiohttp_client: Any, rig: Rig) -> TestClient:
    container = Container(
        settings=rig.pipeline.settings,
        pipeline=rig.pipeline,
        states=rig.states,
        unanswered=rig.unanswered,
        devices=get_device,
        ollama_ok=lambda: True,
    )
    return await aiohttp_client(build_app(container))


async def event(client: TestClient, name: str, **extra: object) -> Any:
    return await client.post("/api/device/event", json={"device_id": DEVICE, "event": name, **extra})


async def test_API1_health(client: TestClient) -> None:
    """API1: GET /health -> 200, status ok."""
    response = await client.get("/health")
    assert response.status == 200
    assert await response.json() == {"status": "ok", "service": "fabai-backend", "ollama": True}


async def test_API2_register(client: TestClient) -> None:
    """API2: POST /api/device/register fabai-01 -> machine 3d-printer."""
    response = await client.post("/api/device/register", json={"device_id": DEVICE})
    assert response.status == 200
    assert await response.json() == {
        "device_id": DEVICE,
        "machine": "3d-printer",
        "location": "3D Printing Lab",
    }


async def test_API2b_heartbeat(client: TestClient) -> None:
    response = await client.post("/api/device/heartbeat", json={"device_id": DEVICE})
    assert await response.json() == {"device_id": DEVICE, "backend": "online"}
    assert (await client.post("/api/device/heartbeat", json={})).status == 400


async def test_API3_event_talk_pressed(client: TestClient, rig: Rig) -> None:
    """API3: POST /api/device/event talk_pressed -> 202, accepted."""
    response = await event(client, "talk_pressed")
    assert response.status == 202
    assert await response.json() == {"accepted": True}
    assert rig.recorder.is_recording


async def test_API3b_talk_released(client: TestClient, rig: Rig) -> None:
    await event(client, "talk_pressed")
    response = await event(client, "talk_released", held_ms=2000)
    assert response.status == 202
    assert await response.json() == {"accepted": True}
    await rig.pipeline.drain()
    assert rig.llm.calls == 1
    assert (await event(client, "talk_released", held_ms="long")).status == 400


async def test_API4_event_unknown(client: TestClient) -> None:
    """API4: unknown event -> 400."""
    response = await event(client, "talk_button_pressed")
    assert response.status == 400
    assert "error" in await response.json()


async def test_API5_event_invalid_json(client: TestClient) -> None:
    """API5: invalid JSON -> 400."""
    response = await client.post(
        "/api/device/event", data="{not json", headers={"Content-Type": "application/json"}
    )
    assert response.status == 400
    assert await response.json() == {"error": "invalid JSON"}
    assert (await client.post("/api/device/event", json=["a"])).status == 400


async def test_API6_state(client: TestClient) -> None:
    """API6: GET /api/device/state?device_id=fabai-01 -> activity, help, led."""
    response = await client.get("/api/device/state", params={"device_id": DEVICE})
    assert response.status == 200
    assert await response.json() == {"activity": "idle", "help": "none", "led": "off"}
    await event(client, "talk_pressed")
    state = await (await client.get("/api/device/state", params={"device_id": DEVICE})).json()
    assert state == {"activity": "listening", "help": "none", "led": "blue"}


async def test_API7_state_missing_device_id(client: TestClient) -> None:
    """API7: GET /api/device/state without device_id -> 400."""
    assert (await client.get("/api/device/state")).status == 400


async def test_API8_ask_valid(client: TestClient, rig: Rig) -> None:
    """API8: POST /api/ask -> 200 with text, intent, sources, refused."""
    response = await client.post(
        "/api/ask", json={"device_id": DEVICE, "question": "what is the maximum SD card size"}
    )
    assert response.status == 200
    body = await response.json()
    assert body["text"] == SD_ANSWER  # source prefix from the top chunk, no "Say next"
    assert body["intent"] == "question"
    assert body["refused"] is False
    assert body["sources"] and isinstance(body["sources"], list)
    assert all(set(source) == {"spoken_source", "origin"} for source in body["sources"])
    assert body["best_score"] >= 0.5
    assert rig.tts.spoken == []  # speak defaults to false


async def test_API8b_ask_without_device_uses_all(client: TestClient, rig: Rig) -> None:
    response = await client.post("/api/ask", json={"question": "what is the maximum SD card size"})
    assert response.status == 200
    assert rig.llm.last_messages is not None
    assert "(all)" in rig.llm.last_messages[0]["content"]


async def test_API8c_ask_llm_down(client: TestClient, rig: Rig) -> None:
    rig.llm.error = RuntimeError("ollama down")
    response = await client.post(
        "/api/ask", json={"device_id": DEVICE, "question": "what is the maximum SD card size"}
    )
    assert response.status == 503
    assert "error" in await response.json()


@pytest.mark.parametrize("question", ["", "   ", "x" * 2001, None, 42])
async def test_API9_ask_invalid_length(client: TestClient, question: object) -> None:
    """API9: empty or 2001 chars -> 400."""
    response = await client.post("/api/ask", json={"device_id": DEVICE, "question": question})
    assert response.status == 400


async def test_API9b_ask_2000_chars_ok(client: TestClient) -> None:
    response = await client.post("/api/ask", json={"device_id": DEVICE, "question": "x" * 2000})
    assert response.status == 200


async def test_API10_help_ack(client: TestClient, rig: Rig) -> None:
    """API10: POST /api/help/ack ack -> acknowledged."""
    await event(client, "help_requested")
    response = await client.post("/api/help/ack", json={"device_id": DEVICE, "action": "ack"})
    assert response.status == 200
    assert await response.json() == {"help": "acknowledged"}
    resolve = await client.post("/api/help/ack", json={"device_id": DEVICE, "action": "resolve"})
    assert await resolve.json() == {"help": "none"}
    bad = await client.post("/api/help/ack", json={"device_id": DEVICE, "action": "maybe"})
    assert bad.status == 400
    await rig.pipeline.drain()


async def test_API11_unanswered_after_refusal(client: TestClient) -> None:
    """API11: GET /api/unanswered after refusal -> 1 entry."""
    ask = await client.post("/api/ask", json={"device_id": DEVICE, "question": "best pizza"})
    assert (await ask.json())["refused"] is True
    response = await client.get("/api/unanswered")
    assert response.status == 200
    entries = await response.json()
    assert len(entries) == 1
    assert entries[0]["question"] == "best pizza"


async def test_API12_help_event_then_state(client: TestClient, rig: Rig) -> None:
    """API12: help_requested then state -> red_pulse."""
    response = await event(client, "help_requested")
    assert response.status == 202
    body = await response.json()
    assert body["accepted"] is True and body["help"] == "pending"
    state = await (await client.get("/api/device/state", params={"device_id": DEVICE})).json()
    assert state["led"] == "red_pulse"
    await rig.pipeline.drain()
    assert len(rig.notifier.requests) == 1
