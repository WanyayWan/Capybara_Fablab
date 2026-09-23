# FabAI — Claude Code guide

FabAI is a voice assistant for the SUTD Fabrication Lab. An ESP32-S3 provides one
physical button and one RGB LED. A laptop runs the Python backend, which records from
the laptop's default mic (a Bluetooth headset paired to the laptop), transcribes with
faster-whisper, answers with RAG + a local Ollama model, and speaks the answer back.

Full spec: `docs/build-plan.md`. Test cases: `docs/test-plan.md`.

## Working rules
- Work on branch `alh`. Never commit to or merge into `main`.
- Work one phase at a time from `docs/build-plan.md`. Stop after each phase, summarise
  what changed, and wait for review before starting the next.
- Write or update tests first for each phase, then implement until they pass.
- Run `pytest` from `backend/` before every commit. Do not commit failing tests.
- One commit per phase (more is fine), conventional messages: `feat:`, `fix:`, `test:`,
  `docs:`, `chore:`, `refactor:`.
- If the plan is ambiguous or wrong, ask instead of guessing.
- Before every phase, read docs/build-plan.md section 9 (Decisions and Phase 0
  implementation notes). It overrides anything earlier in the plan that conflicts with it.

## Code rules
- Python 3.11+, type hints everywhere, small functions, dataclasses for data.
- Pure logic lives in `backend/core/` and must not import hardware, network, or model
  libraries. Anything that touches audio, models, HTTP, or the OS lives in
  `backend/services/` behind a small class that tests can replace with a fake.
- Dependencies are injected (constructor arguments), never created at import time.
- Must run on Windows (the demo laptop). Use `pathlib`, no bash-only commands in code.
- No new dependencies beyond those listed in the build plan without asking.
- Firmware: ESP-IDF C for ESP32-S3. Keep pure logic (button gestures) in files with no
  ESP-IDF includes so it can be unit-tested on the host with gcc.

## Never commit
- `.env` or any secret (Telegram token, chat id)
- `backend/knowledge/private/` (internal SUTD documents)
- models, recordings, `data/`, build output

## Commands
```bash
# backend
cd backend
python -m venv .venv            # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
pytest                          # unit + API tests (no hardware, no Ollama needed)
pytest -m integration           # needs Ollama running
python app.py                   # start backend on :8000
python scripts/run_eval.py      # RAG eval against a running backend

# firmware
cd firmware
idf.py build
idf.py -p <PORT> flash monitor
make -C test                    # host unit tests for button gestures
```
