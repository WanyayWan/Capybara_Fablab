"""Conversation sessions (test-plan: test_sessions.py)."""

from core.sessions import SessionManager
from core.steps import ProcedurePointer
from tests.fakes import FakeClock


def make_manager(clock: FakeClock, max_turns: int = 6) -> SessionManager:
    return SessionManager(timeout_s=120, max_turns=max_turns, clock=clock.now)


def test_S1_new_device_empty_history() -> None:
    """S1: new device -> empty history."""
    sessions = make_manager(FakeClock())
    assert sessions.get("fabai-01").history_messages() == []


def test_S2_two_turns_four_messages() -> None:
    """S2: add 2 turns -> history has 4 messages in order."""
    sessions = make_manager(FakeClock())
    session = sessions.get("fabai-01")
    session.add_turn("q1", "a1")
    session.add_turn("q2", "a2")
    assert sessions.get("fabai-01").history_messages() == [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "q2"},
        {"role": "assistant", "content": "a2"},
    ]


def test_S3_max_turns_kept() -> None:
    """S3: add 8 turns with max 6 -> only last 6 kept."""
    sessions = make_manager(FakeClock(), max_turns=6)
    session = sessions.get("fabai-01")
    for i in range(8):
        session.add_turn(f"q{i}", f"a{i}")
    history = session.history_messages()
    assert len(history) == 12
    assert [m["content"] for m in history if m["role"] == "user"] == [
        f"q{i}" for i in range(2, 8)
    ]


def test_S4_expires_after_timeout() -> None:
    """S4: advance clock 121 s -> get returns a fresh empty session."""
    clock = FakeClock()
    sessions = make_manager(clock)
    sessions.get("fabai-01").add_turn("q", "a")
    clock.advance(121)
    assert sessions.get("fabai-01").history_messages() == []


def test_S5_activity_refreshes_timeout() -> None:
    """S5: advance 60 s, add turn, advance 60 s -> still alive."""
    clock = FakeClock()
    sessions = make_manager(clock)
    sessions.get("fabai-01").add_turn("q1", "a1")
    clock.advance(60)
    sessions.get("fabai-01").add_turn("q2", "a2")
    clock.advance(60)
    assert sessions.get("fabai-01").last_user_messages(5) == ["q1", "q2"]


def test_S6_devices_independent() -> None:
    """S6: two devices -> histories independent."""
    sessions = make_manager(FakeClock())
    sessions.get("fabai-01").add_turn("printer?", "yes")
    sessions.get("fabai-02").add_turn("laser?", "no")
    assert sessions.get("fabai-01").last_user_messages(5) == ["printer?"]
    assert sessions.get("fabai-02").last_user_messages(5) == ["laser?"]


def test_S7_last_user_messages() -> None:
    """S7: last_user_messages(3) -> last 3 user texts, newest last."""
    sessions = make_manager(FakeClock())
    session = sessions.get("fabai-01")
    for i in range(5):
        session.add_turn(f"q{i}", f"a{i}")
    assert session.last_user_messages(3) == ["q2", "q3", "q4"]


def test_reset_starts_fresh() -> None:
    """reset(device_id) drops the session so the next get is empty."""
    sessions = make_manager(FakeClock())
    sessions.get("fabai-01").add_turn("q", "a")
    sessions.reset("fabai-01")
    sessions.reset("never-seen")
    assert sessions.get("fabai-01").history_messages() == []


def test_history_messages_last_turns() -> None:
    """Step mode sends only a short history: the last N turns."""
    clock = FakeClock()
    session = SessionManager(timeout_s=120, max_turns=6, clock=clock.now).get("d")
    for i in range(3):
        session.add_turn(f"q{i}", f"a{i}")
    assert [m["content"] for m in session.history_messages(last_turns=1)] == ["q2", "a2"]
    assert len(session.history_messages(last_turns=5)) == 6
    assert session.history_messages(last_turns=0) == []


def test_procedure_pointer_reset_on_expiry() -> None:
    clock = FakeClock()
    manager = SessionManager(timeout_s=120, max_turns=6, clock=clock.now)
    manager.get("d").procedure = ProcedurePointer("3d-printer", 2)
    assert manager.get("d").procedure == ProcedurePointer("3d-printer", 2)
    clock.advance(120)
    assert manager.get("d").procedure is None
