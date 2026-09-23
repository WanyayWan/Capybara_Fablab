# FabAI: Claude Code prompts, step by step

Paste each prompt into Claude Code in order. Wait for each step to finish and check its
"Verify" list before moving on.

Tips:
- Start a fresh session (`/clear`) at the start of each phase. Every prompt below tells
  Claude Code to re-read the docs, so nothing is lost and context stays small.
- If Claude Code asks to run a command, read it before approving.
- Never paste your Telegram token into the chat. Put it in `backend/.env` yourself.

---

## Step 0: Before you start (manual)

1. Download `fabai-kickoff.zip` into your Downloads folder. Don't unzip it.
2. Open a terminal in the folder where you keep projects (not inside an existing repo).
3. Run `claude`.

---

## Step 1: Clone, branch, and place the kickoff files

```
I'm setting up a project. Do these steps in order and show me the output of each.

1. Clone https://github.com/WanyayWan/Capybara_Fablab.git into the current folder and
   cd into it.
2. Create and switch to a new branch called alh. Confirm with git branch.
3. Find fabai-kickoff.zip in my Downloads folder (on Windows this is
   C:\Users\<me>\Downloads, on macOS/Linux ~/Downloads). If you can't find it, stop and
   ask me for the path.
4. Unzip it to a temporary folder outside the repo.
5. Copy its contents into the repo root, keeping the folder structure. The zip contains
   a top-level folder fabai-kickoff/, so copy what is INSIDE it, so that these paths exist:
   - CLAUDE.md
   - docs/build-plan.md
   - docs/test-plan.md
   - docs/claude-code-prompts.md
   - backend/knowledge/general.md
   - backend/knowledge/3d-printer.md
   - backend/knowledge/laser-cutter.md
   - backend/tests/eval/questions.yaml
   Do not overwrite any existing file without asking me.
6. Delete the temporary folder.
7. Show me the full repo tree (excluding .git) and git status.
8. Commit only those 8 files with the message
   "docs: add build plan, test plan, prompts and knowledge base".

Do not change any other files yet.
```

**Verify:** you're on branch `alh`, the 8 files exist at the right paths, one commit.

---

## Step 2: Read and understand (no code changes)

```
Read CLAUDE.md, docs/build-plan.md and docs/test-plan.md fully. Then read every existing
file in the repo: backend/, firmware/main/, web/, and the .gitignore files.

Do not change anything. Give me:
1. A short summary of what the existing code does.
2. A table mapping each existing file to what happens to it in the plan: keep as is,
   modify, move, or delete.
3. Any conflicts between the plan and the existing code, or anything in the plan that is
   unclear or you think is wrong.
4. Anything I need to install on this machine (Python version, ESP-IDF, gcc, Ollama).
   Check what is already installed and report versions.
```

**Verify:** read the conflicts list. Answer any questions before continuing.

---

## Step 3: Structure the repo (Phase 0: skeleton only)

```
Read CLAUDE.md and docs/build-plan.md again. We're doing Phase 0: set up the full
structure. No real logic yet.

1. Delete the phone and old code listed under "Delete" in build-plan section 3:
   web/ (top level), backend/web/, backend/services/dev_tls.py, backend/PHONE_HTTPS.md.
   Remove the Vosk STTService class and all WebSocket/phone/HTTPS code from app.py
   (leave app.py minimal for now: /health only, plain HTTP on port 8000).
2. Create EVERY file in the build-plan section 3 tree that doesn't exist yet, as a stub:
   - Python: module docstring describing its job, the classes/functions from build-plan
     section 5 with full type-hinted signatures and docstrings, bodies raising
     NotImplementedError. Add empty __init__.py files for core/ and services/.
   - Tests: one file per test file in the tree, each test from docs/test-plan.md as a
     function named after its ID (for example test_I1_fire_in_laser_cutter) marked
     with @pytest.mark.skip(reason="not implemented").
   - tests/fakes.py: class stubs for every fake listed in docs/test-plan.md.
   - Firmware: button_gesture.h/.c and led_manager.h/.c with the declared functions and
     empty bodies; firmware/test/Makefile and test_button_gesture.c with the test case
     IDs as TODO comments. Add the new .c files to firmware/main/CMakeLists.txt.
   - docs/architecture.md, docs/demo-script.md, README.md: headings only (filled in
     Phase 6).
3. Create backend/requirements.txt, requirements-dev.txt and pytest.ini exactly as in
   build-plan section 5 "Dependencies".
4. Create backend/config.py fully (this one is real, not a stub): Settings dataclass
   loaded from env and .env with every setting in build-plan section 4, plus DEVICES
   and a get_device(device_id) helper with the fallback.
5. Create backend/.env.example with every setting, empty Telegram values.
6. Update .gitignore: backend/.env, backend/knowledge/private/, backend/data/,
   backend/.venv/, firmware/test/*.out, plus the existing entries. Create
   backend/knowledge/private/.gitkeep only if gitignore allows it; otherwise skip it.
7. Create a Python venv in backend/.venv, install both requirement files.
8. Run pytest from backend/. Everything should be collected and skipped, no errors.
9. Run make -C firmware/test. It should compile.
10. Show me the final tree (excluding .git, .venv, build folders) and the pytest output.
11. Commit: "chore: restructure repo for ESP32-only FabAI, add skeleton and config".

Stop and summarise.
```

**Verify:** the tree matches build-plan section 3, pytest shows all tests skipped with 0
errors, and `python -c "import app"` works from `backend/`.

---

## Step 4: Phase 1 (core logic)

```
/clear first if this session is long. Then:

Read CLAUDE.md, docs/build-plan.md sections 2 and 5 (core/ parts) and docs/test-plan.md
(unit tests for intents, sessions, device_state, prompts, speech_text).

Phase 1: implement backend/core/intents.py, sessions.py, device_state.py, prompts.py,
speech_text.py.
For each module: remove the skip markers and write the real test bodies for its test
IDs first, run them to see them fail, then implement until they pass. Fill in the fakes
in tests/fakes.py that these tests need (FakeClock at least).
Run the full pytest suite at the end, commit "feat: core logic for intents, sessions,
device state, prompts", then stop and summarise, including any test cases you had to
adjust and why.
```

**Verify:** tests I1–I11, S1–S7, D1–D8, P1–P6, T1–T5 pass.

---

## Step 5: Phase 2 (services)

```
/clear first if needed. Then:

Read CLAUDE.md, docs/build-plan.md section 5 (services/ parts) and docs/test-plan.md
(test_knowledge, test_audio_service, test_notify_service, test_unanswered_log, and the
fakes section).

Phase 2: implement everything in backend/services/: knowledge.py, embedder.py,
llm_service.py, stt_service.py, audio_service.py, tts_service.py, notify_service.py,
unanswered_log.py. Keep the existing Windows SAPI code in tts_service.py.
Tests first as before. Implement FakeEmbedder exactly as described in the test plan
(bag-of-words hashing, 256 dims, normalised). Mock all HTTP in tests; no test may call
Ollama, Telegram, or a real mic.
If K5 or K6 fail with the fake embedder because of wording, tell me before changing the
knowledge files.
Run full pytest, commit "feat: services for RAG, LLM, STT, audio, TTS, notifications",
stop and summarise.
```

**Verify:** K1–K9, A1–A4, N1–N7, U1–U2 pass. Nothing tries to reach the network.

---

## Step 6: Phase 3 (pipeline and API)

```
/clear first if needed. Then:

Read CLAUDE.md, docs/build-plan.md sections 2 and 5 (core/pipeline.py and app.py) and
docs/test-plan.md (pipeline tests PL1–PL18 and API tests API1–API12).

Phase 3: implement backend/core/pipeline.py and the full backend/app.py
(build_app(container) + main()). Tests first, all with fakes.
Then do a manual smoke test with the real services (Ollama must be running with
gemma3:4b and nomic-embed-text; check first and tell me if not):
1. Start python app.py.
2. POST /api/ask {"device_id":"fabai-01","question":"How do I load filament?"} and show
   the response.
3. POST /api/ask with "What's the best pizza near SUTD?" and show it is refused.
4. POST /api/device/event help_requested for fabai-01, then GET /api/device/state and
   show led is red_pulse. The console notifier should print the help message.
5. POST /api/help/ack with action ack, show led is purple.
Stop the server. Run full pytest, commit "feat: voice pipeline and API routes",
stop and summarise.
```

**Verify:** all PL and API tests pass, and the smoke test gives a real, sensible answer.

---

## Step 7: Phase 4 (firmware), can run in parallel with Steps 4–6

Run this in a **separate** Claude Code session (a teammate's laptop is ideal). Pull the
`alh` branch after Step 3 first.

```
Read CLAUDE.md, docs/build-plan.md section 6 and docs/test-plan.md (firmware host tests
F1–F7 and hardware checklist H1–H4). Read all of firmware/main/.

Phase 4: firmware changes.
1. button_gesture.c: write the F1–F7 host tests in firmware/test/test_button_gesture.c
   first, run make -C firmware/test, then implement until they pass.
2. led_manager.c: render the led values from the build-plan LED table, including
   red_pulse (breathing), red_flash, and offline. Max brightness ~40/255.
3. backend_client.c: FreeRTOS event queue + sender task, talk_pressed/talk_released
   (held_ms)/help_requested, register on boot, state polling every 400 ms, offline after
   3 failed polls. Keep the 15 s heartbeat.
4. main.c: feed debounced edges into gesture_on_edge, enqueue events, set LED blue
   locally on TALK_START.
5. web_server.c: fix the portal JS bug where the const note is assigned strings.
Only touch firmware/. Run idf.py build (ask me if ESP-IDF isn't set up in this terminal).
Commit "feat: firmware gestures, LED states, event queue, portal fix". Stop and
summarise, and list exactly what I should test on the real board.
```

**Verify:** `make -C firmware/test` passes and `idf.py build` succeeds. Flash the board
and run H1–H4.

---

## Step 8: Phase 5 (integration, eval, tuning)

```
/clear first. git pull to get the firmware changes if they were done elsewhere.

Read CLAUDE.md and docs/test-plan.md (integration tests, RAG eval, hardware checklist).

Phase 5:
1. Implement tests/test_integration_ollama.py (IT1–IT4, marked integration) and run
   pytest -m integration with Ollama running.
2. Implement scripts/run_eval.py as described in the test plan, start the backend, run
   it against tests/eval/questions.yaml, and show me the table.
3. If the pass rate is below 80%: show me the scores of passing vs failing questions and
   propose a RAG_THRESHOLD value or knowledge-file wording changes. Don't change the
   knowledge files without my OK.
4. Write the result into docs/test-plan.md under a new "Results" section (date, pass
   rate, threshold used).
Commit "test: integration tests and RAG eval", stop and summarise.
```

Then the team runs the hardware checklist H5–H15 with the real board, headset and
Telegram. Paste any failures back into Claude Code with the serial log and backend
console output.

---

## Step 9: Phase 6 (docs and push)

```
/clear first. Read CLAUDE.md, docs/build-plan.md section 8, and the current code.

Phase 6: documentation.
1. README.md with every section in build-plan section 8. Keep it scannable: short
   paragraphs, tables for LEDs, API, and configuration. Setup commands must work on
   Windows and macOS.
2. docs/architecture.md with a Mermaid flowchart of button → ESP32 → backend → STT →
   intents → RAG/LLM → TTS, plus the help flow as a Mermaid sequence diagram (ESP32,
   backend, Telegram, staff).
3. docs/demo-script.md: a 3-minute live demo script using questions that passed the
   eval, including the double-press staff call and the Telegram acknowledgement, plus a
   "if something fails" fallback for each step.
4. Check .env.example is complete and no secrets are in the repo
   (search for "bot" tokens and chat ids).
5. Run the full pytest suite and make -C firmware/test one last time.
Commit "docs: README, architecture, demo script", then git push -u origin alh and show
me the result. Do not merge into main.
```

**Verify:** the branch is on GitHub and the README renders correctly there.

---

## Helper prompts (use when needed)

**Tests failing and Claude Code is going in circles:**
```
Stop changing code. List the failing tests, the exact error for each, and your best
explanation of the root cause. Don't fix anything until I reply.
```

**Resume after a break or a new session:**
```
Read CLAUDE.md, docs/build-plan.md and docs/test-plan.md. Run git log --oneline -15 and
pytest. Tell me which phase we're in, what's done, and what's left in this phase.
```

**Hardware bug:**
```
On the real device, <what happened>. Expected: <what should happen per the checklist ID>.
Serial log:
<paste>
Backend console:
<paste>
Find the cause before changing anything and explain it to me first.
```

**Before the pitch:**
```
Run the full pytest suite, make -C firmware/test, and scripts/run_eval.py against the
running backend. Give me a one-screen status: what works, what's flaky, what to avoid
showing in the demo.
```
