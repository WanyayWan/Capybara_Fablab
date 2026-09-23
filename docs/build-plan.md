# FabAI build plan (branch `alh`)

## 1. Goal
Replace the phone client with an ESP32-only interaction. The ESP32 is the button and
status light. The laptop does audio (via a paired Bluetooth headset/speaker), speech to
text, retrieval, the LLM, text to speech, and staff notification.

## 2. User experience

| Gesture on the ESP32 BOOT button | Result |
|---|---|
| Hold, speak, release | One conversation turn (hold-to-talk) |
| Double-press (two short taps within 400 ms) | Call staff |
| Say "call staff" / "I need staff" | Call staff |
| Say an emergency word ("fire", "I'm hurt"...) | Instant fixed safety message + urgent staff alert |

- Conversation sessions: each device has a session. Follow-up questions use history.
  A session resets after 120 s with no activity.
- Step-by-step mode: for procedures, the assistant gives one step at a time and ends
  with "Say next when you're ready."
- Answers are 1 to 3 short spoken sentences, no lists or markdown, and mention the
  source guide naturally ("According to the 3D printer guide...").
- When the knowledge base has nothing relevant, the assistant refuses politely, tells
  the user how to call staff, and logs the question.

### LED (computed by the backend, rendered by the firmware)

| `led` value | Colour / pattern | Meaning |
|---|---|---|
| `off` | off | idle |
| `blue` | solid blue | listening |
| `yellow` | solid yellow | thinking |
| `green` | solid green | speaking |
| `red_pulse` | breathing red | staff called, waiting |
| `purple` | solid purple | staff acknowledged, on the way |
| `red_flash` | 3 quick red flashes then off | error |
| `offline` (firmware-local) | dim red blink every 2 s | backend unreachable |
| `white` (debug only) | solid dim white | serial `LED_ON` / portal LED On; overridden by the next state poll |

Priority: activity (listening/thinking/speaking/error) overrides help colours while it
is happening; when activity returns to idle, the help colour shows again.

### Staff help flow ("the assistant knows")
1. Trigger (double-press, voice phrase, or emergency) calls `pipeline.request_help()`.
2. Any in-progress recording is cancelled.
3. Help status becomes `pending` (LED `red_pulse`).
4. Notifier sends a Telegram message: device, machine, location, time, the last 3 user
   questions from the session, and `EMERGENCY` at the top if triggered by an emergency.
   Message has inline buttons **On my way** and **Resolved**.
5. The assistant speaks: "I've called Fab Lab staff. Please stay by the machine."
6. The help status is injected into the LLM system prompt, so if the user asks
   "is someone coming?" the assistant answers correctly.
7. Staff taps **On my way** → status `acknowledged` (LED `purple`), assistant speaks
   "A staff member is on the way."
8. Staff taps **Resolved**, or 10 minutes pass after acknowledgement → status `none`.
9. A second help request while `pending` does not send a duplicate message; it replies
   "Staff have already been called."
10. Without Telegram config, the notifier prints the message to the console and a
    `POST /api/help/ack` endpoint simulates the staff buttons (for demos and tests).

## 3. Target structure

```
Capybara_Fablab/
├── CLAUDE.md
├── README.md
├── docs/
│   ├── build-plan.md
│   ├── test-plan.md
│   ├── architecture.md
│   └── demo-script.md
├── firmware/
│   ├── main/
│   │   ├── main.c
│   │   ├── button_gesture.c/.h     # NEW pure logic, host-testable
│   │   ├── backend_client.c/.h     # events queue + state polling
│   │   ├── led_manager.c/.h        # NEW renders led values/patterns
│   │   ├── device_manager.c/.h
│   │   ├── wifi_manager.c/.h
│   │   ├── storage_manager.c/.h
│   │   └── web_server.c/.h         # fix portal JS bug
│   └── test/
│       ├── Makefile
│       └── test_button_gesture.c
└── backend/
    ├── app.py                      # build_app(container) + main()
    ├── config.py                   # Settings from env / .env
    ├── .env.example
    ├── requirements.txt
    ├── requirements-dev.txt
    ├── pytest.ini
    ├── core/                       # pure logic, no I/O
    │   ├── intents.py
    │   ├── sessions.py
    │   ├── device_state.py
    │   ├── prompts.py
    │   ├── speech_text.py          # sanitize text for TTS
    │   └── pipeline.py             # orchestration, depends on interfaces only
    ├── services/                   # I/O behind small classes
    │   ├── audio_service.py        # Recorder start()/stop()
    │   ├── stt_service.py          # WhisperSTT
    │   ├── embedder.py             # OllamaEmbedder
    │   ├── knowledge.py            # load + chunk + retrieve
    │   ├── llm_service.py          # OllamaChat
    │   ├── tts_service.py          # Windows / macOS / console
    │   ├── notify_service.py       # Telegram + console notifiers
    │   └── unanswered_log.py
    ├── knowledge/
    │   ├── general.md
    │   ├── 3d-printer.md
    │   ├── laser-cutter.md
    │   └── private/                # gitignored
    ├── scripts/
    │   └── run_eval.py
    ├── tests/
    │   ├── conftest.py
    │   ├── fakes.py                # FakeEmbedder, FakeSTT, FakeLLM, FakeTTS, ...
    │   ├── test_intents.py
    │   ├── test_sessions.py
    │   ├── test_device_state.py
    │   ├── test_prompts.py
    │   ├── test_speech_text.py
    │   ├── test_knowledge.py
    │   ├── test_audio_service.py
    │   ├── test_notify_service.py
    │   ├── test_unanswered_log.py
    │   ├── test_pipeline.py
    │   ├── test_api.py
    │   ├── test_integration_ollama.py   # marked integration
    │   └── eval/questions.yaml
    └── mic_diagnostic.py
```

**Delete:** `web/` (top level), `backend/web/`, `backend/services/dev_tls.py`,
`backend/PHONE_HTTPS.md`, the Vosk `STTService` class, all WebSocket/phone/HTTPS code.

## 4. Configuration (`config.py`, loaded from env and `.env`)

| Setting | Default |
|---|---|
| `OLLAMA_URL` | `http://127.0.0.1:11434` |
| `OLLAMA_MODEL` | `gemma3:4b` |
| `EMBED_MODEL` | `nomic-embed-text` |
| `WHISPER_MODEL` | `base.en` |
| `RAG_TOP_K` | `3` |
| `RAG_THRESHOLD` | `0.5` (tune with the eval script) |
| `RAG_MACHINE_BOOST` | `0.05` |
| `SESSION_TIMEOUT_S` | `120` |
| `SESSION_MAX_TURNS` | `6` |
| `MIN_RECORD_S` / `MAX_RECORD_S` | `0.5` / `15` |
| `PRE_ROLL_S` | `0.5` (audio kept from before the press, see section 9) |
| `HELP_ACK_CLEAR_S` | `600` |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | empty → console notifier |
| `PORT` | `8000` |

Device registry (in `config.py`, not env):
```python
DEVICES = {
    "fabai-01": {"machine": "3d-printer", "location": "3D Printing Lab"},
    "fabai-02": {"machine": "laser-cutter", "location": "Laser Lab"},
}
```
Unknown device ids fall back to `{"machine": "all", "location": "Fab Lab"}`.

## 5. Backend components

### core/intents.py
`detect_intent(text) -> Intent` where `Intent` is `EMERGENCY | HELP | QUESTION`.
Case-insensitive, word-boundary regex. EMERGENCY is checked first.
- EMERGENCY: fire, on fire, flames, smoke, burning, burnt myself, burned myself, injured,
  bleeding, cut myself, i'm hurt, i am hurt, emergency, electric shock
- HELP: call staff, call a staff, get staff, need staff, talk to staff, call someone,
  call for help, get a staff, staff please
- Everything else: QUESTION. "help me load filament" and "how do I cut acrylic" must be
  QUESTION.
`EMERGENCY_RESPONSE` constant: short fixed message ("Stop the machine if it is safe to
do so, and move away. I'm alerting Fab Lab staff now.").

### core/sessions.py
`SessionManager(timeout_s, max_turns, clock=time.monotonic)`
- `get(device_id) -> Session` (creates new if missing or expired)
- `Session.add_turn(user, assistant)`, keeps last `max_turns` turns
- `Session.last_user_messages(n)`, `Session.history_messages()` (chat format)
- `reset(device_id)`

### core/device_state.py
`Activity = idle | listening | thinking | speaking | error`
`HelpStatus = none | pending | acknowledged`
`DeviceStateStore(clock)`: `set_activity`, `set_help`, `get(device_id)`,
`led(device_id) -> str` implementing the LED table and priority rule. `error` reverts to
`idle` after 3 s (checked lazily in `get`/`led`). `acknowledged` reverts to `none` after
`HELP_ACK_CLEAR_S`.

### core/prompts.py
`build_messages(machine, location, chunks, history, question, help_status) -> list[dict]`
System prompt rules:
- You are FabAI, the voice assistant at the SUTD Fab Lab, at the `{location}` (`{machine}`).
- Answer ONLY from CONTEXT. If CONTEXT does not answer it, say you don't have that in the
  Fab Lab guides and suggest calling staff (double-press the button or say "call staff").
- 1 to 3 short sentences, spoken style, no lists, no markdown, no emoji.
- Mention the source guide name naturally.
- For procedures give ONE step at a time and end with "Say next when you're ready."
  When the user says "next", give the following step based on history.
- Never say someone is authorised to use a machine.
- Help status line: "Staff status: not called / called at HH:MM, waiting / on the way."
CONTEXT lists each chunk as `[source] heading: text`.

### core/speech_text.py
`to_speakable(text) -> str`: strip markdown (`*`, `#`, backticks, bullets), collapse
whitespace, expand "e.g." to "for example", keep numbers. Max 600 chars (cut at sentence).

### core/pipeline.py
`VoicePipeline(settings, recorder, stt, kb, llm, tts, notifier, states, sessions, unanswered, devices)`
- `async talk_pressed(device_id) -> dict`: if activity is thinking/speaking → return
  `{"accepted": False, "reason": "busy"}`. Else `recorder.start()`, activity `listening`.
- `async talk_released(device_id, held_ms) -> dict`: stop recorder. If duration <
  `MIN_RECORD_S` → discard, activity `idle`, return `{"accepted": False, "reason": "too_short"}`.
  Else activity `thinking` and schedule `_process_audio` as a background task.
- `async _process_audio(device_id, samples)`: transcribe (in thread). Empty → speak
  "Sorry, I didn't catch that." Then `await handle_text(device_id, text, speak=True)`.
- `async handle_text(device_id, text, speak) -> Answer` where
  `Answer = {text, intent, sources: list[str], refused: bool}`:
  - EMERGENCY → `EMERGENCY_RESPONSE`, `request_help(emergency=True, speak=False)`.
  - HELP → `request_help(...)`, answer is the help confirmation text.
  - QUESTION → retrieval query = previous user message + current text if the session has
    history, else current text. `kb.retrieve(query, machine)`. If no chunk ≥ threshold →
    refusal text, `unanswered.log(...)`, `refused=True`. Else `llm.chat(build_messages(...))`.
    Add the turn to the session.
  - If `speak`: activity `speaking`, `tts.speak(to_speakable(text))` in a thread, then `idle`.
- `async request_help(device_id, source, emergency=False, speak=True) -> str`:
  cancel recording, dedupe while pending, set `pending`, `notifier.send_help(HelpRequest)`,
  speak confirmation.
- `async help_update(device_id, action)`: `ack` → `acknowledged` + speak "A staff member is
  on the way."; `resolve` → `none`.
- Any exception in processing → activity `error`, speak "Sorry, something went wrong."
  (best effort), log the traceback.
- A per-device `asyncio.Lock` guards processing so a second press cannot start a
  parallel run.

### services/knowledge.py
- `load_chunks(dirs: list[Path]) -> list[Chunk]`: read `*.md`, parse YAML frontmatter
  (`machine`, `source`, `type`), split on `## ` headings. One chunk per heading.
  `Chunk(id, machine, source, heading, text)`. Skip files without frontmatter with a warning.
- `KnowledgeBase(chunks, embedder, top_k, threshold, machine_boost)`:
  `build()` embeds all chunks once (the embedder adds the `search_document: ` prefix, see section 9 Phase 2 decision 2);
  `retrieve(query, machine) -> list[ScoredChunk]` (embedder adds `search_query: `), cosine
  similarity, +boost for chunks whose machine equals the device machine or `all`,
  returns top-k sorted, each with `score`; callers compare to threshold via
  `kb.is_confident(results)`.
- Loads `knowledge/` and `knowledge/private/` if it exists.

### services/embedder.py
`OllamaEmbedder(url, model)`: `embed(texts) -> np.ndarray` (L2-normalised rows) via
`POST /api/embed`. Sync, called via `asyncio.to_thread`.

### services/llm_service.py
`OllamaChat(url, model)`: `chat(messages) -> str` via `POST /api/chat`,
`stream: false`, `options: {temperature: 0.2, num_ctx: 8192}`, timeout 120 s. Raise
`LLMUnavailable` on connection errors or empty response.

### services/stt_service.py
`WhisperSTT(model_name)`: lazy-load faster-whisper on first use (CPU, int8).
`transcribe(samples: np.ndarray) -> str` with `language="en"`, `beam_size=5`,
`vad_filter=True`, `initial_prompt=GLOSSARY`.
`GLOSSARY = "Fab Lab, SUTD, PLA, PETG, ABS, AMS, Bambu, P1S, X1E, SD card, filament, nozzle, build plate, laser cutter, acrylic, plywood, MDF, kerf, engrave, extraction"`

### services/audio_service.py
`Recorder(sample_rate=16000, max_seconds, stream_factory=sounddevice.InputStream)`:
`start()`, `stop() -> np.ndarray`, `cancel()`, `is_recording`, `_on_audio(chunk)` appends
until `max_seconds` then ignores. Mono float32.

### services/tts_service.py
`WindowsTTS` (existing SAPI code), `MacTTS` (`say`), `ConsoleTTS` (print).
`create_tts()` picks by platform. `speak(text)` is blocking.

### services/notify_service.py
- `HelpRequest(device_id, machine, location, time, recent_questions, emergency, help_id)`
- `format_help_message(req) -> str` (pure)
- `parse_callback(data) -> tuple[action, device_id, help_id] | None` (pure),
  callback data format `ack:<device_id>:<help_id>` / `resolve:<device_id>:<help_id>`
- `TelegramNotifier(token, chat_id, session)`: `send_help(req)` (sendMessage with
  inline keyboard), `run_ack_poller(on_update)` long-polls `getUpdates` with offset,
  calls `answerCallbackQuery`, edits the message to show who acknowledged, and calls
  `on_update(device_id, action)`. Ignore stale help ids.
- `ConsoleNotifier`: prints the formatted message.
- `create_notifier(settings, session)` picks one.

### services/unanswered_log.py
Append JSON lines to `data/unanswered.jsonl`: `ts, device_id, machine, question, best_score`.
`read_all()`.

### app.py routes

| Method | Path | Body / query | Response |
|---|---|---|---|
| GET | `/health` | | `{status, service, ollama: bool}` |
| POST | `/api/device/register` | `{device_id}` | `{device_id, machine, location}` |
| POST | `/api/device/heartbeat` | `{device_id}` | `{device_id, backend: "online"}` |
| POST | `/api/device/event` | `{device_id, event, held_ms?}` event ∈ `talk_pressed`, `talk_released`, `help_requested` | pipeline result, 202; 400 on unknown event |
| GET | `/api/device/state` | `?device_id=` | `{activity, help, led}` |
| POST | `/api/ask` | `{device_id?, question, speak?: false}` | `Answer` JSON; 400 if empty or > 2000 chars |
| POST | `/api/help/ack` | `{device_id, action: "ack"\|"resolve"}` | `{help}` (simulates staff) |
| GET | `/api/unanswered` | | list of logged questions |

`build_app(container)` takes all dependencies so tests use fakes. `main()` creates the
real services, builds the knowledge base, starts the Telegram poller if configured,
listens on `0.0.0.0:PORT` over plain HTTP, and prints the LAN URL for the ESP32 portal.

### Dependencies
`requirements.txt`: aiohttp, numpy, sounddevice, faster-whisper, pyyaml, python-dotenv
`requirements-dev.txt`: pytest, pytest-asyncio, pytest-aiohttp
`pytest.ini`: `asyncio_mode = auto`, marker `integration`, default `-m "not integration"`.

## 6. Firmware changes

### button_gesture.c/.h (no ESP-IDF includes)
```c
typedef enum { GESTURE_NONE, GESTURE_TALK_START, GESTURE_TALK_END, GESTURE_HELP } gesture_event_t;
typedef struct { /* internal */ } gesture_t;
void gesture_init(gesture_t *g);
gesture_event_t gesture_on_edge(gesture_t *g, bool pressed, uint32_t now_ms, uint32_t *held_ms_out);
```
Rules (input is already debounced):
- Press → if the previous press was a tap (held < 350 ms) and this press is within 400 ms
  of that release → `GESTURE_HELP`, and the matching release returns `GESTURE_NONE`.
  Otherwise → `GESTURE_TALK_START`.
- Release after a TALK_START → `GESTURE_TALK_END` with `held_ms`.
- The first tap of a double-press still sends TALK_START/TALK_END; the backend discards
  it as too short. This keeps hold-to-talk instant.

### backend_client.c
- FreeRTOS queue of events; a sender task POSTs `/api/device/event` so the button task
  never blocks on HTTP.
- `talk_pressed`, `talk_released` (with `held_ms`), `help_requested`.
- State poll task: `GET /api/device/state?device_id=fabai-01` every 400 ms while Wi-Fi
  and backend URL are set; passes `led` to `led_manager`. Three failed polls in a row →
  `offline` pattern. Keep the existing 15 s heartbeat.
- Register on boot (`/api/device/register`).

### led_manager.c
Owns the RGB LED (GPIO38) and a task that renders the current pattern at 20 Hz.
Low brightness (max ~40/255). `led_manager_set(const char *led)` parses the string.
On TALK_START the button task sets `blue` immediately (local feedback) before the next poll.

### main.c
Button task feeds debounced edges into `gesture_on_edge` and enqueues events. Keep the
ready banner and serial commands. `DEVICE_ID` stays `fabai-01` (a `#define` in one place).

### web_server.c
Fix the portal JS: `note` is a const function but is assigned strings in `api()` and
`scan()`. Replace those assignments with `note('...')` calls.

### test/Makefile + test_button_gesture.c
Compile `main/button_gesture.c` with host `gcc`, tiny assert-based runner, `make -C test`
builds and runs. Cases in `docs/test-plan.md`.

## 7. Phases

| Phase | Scope | Done when | Est. |
|---|---|---|---|
| 0 | Branch, delete phone code, new folder layout, requirements, pytest setup, config.py, .gitignore updates | `pytest` runs (0 tests OK), app imports | 30m |
| 1 | `core/`: intents, sessions, device_state, prompts, speech_text + tests | all core tests pass | 1h |
| 2 | `services/`: knowledge + embedder, llm, stt, audio, tts, notifier, unanswered + tests with fakes | service tests pass | 1.5h |
| 3 | `core/pipeline.py` + `app.py` routes + tests; manual check `/api/ask` with real Ollama | pipeline + API tests pass, real answer returned | 1.5h |
| 4 | Firmware: gesture module + host tests, event queue, state polling, led_manager, portal fix | `make -C test` passes, `idf.py build` succeeds | 1.5h |
| 5 | Integration: integration tests, `scripts/run_eval.py`, tune `RAG_THRESHOLD`, hardware checklist | eval ≥ 80% pass, hardware checklist done | 1h |
| 6 | Docs: README, architecture.md (Mermaid), demo-script.md, .env.example; push branch | docs complete, `git push -u origin alh` | 45m |

## 8. README sections (phase 6)
1. What FabAI is (one line) and the problem it solves
2. Demo photo/GIF placeholder
3. Architecture diagram (Mermaid)
4. Hardware: ESP32-S3 DevKit, laptop, Bluetooth headset/speaker
5. Setup: flash firmware, Python backend, `ollama pull gemma3:4b` and
   `ollama pull nomic-embed-text`, pair Bluetooth, create Telegram bot with BotFather and
   get the chat id
6. Configuration: ESP32 portal (FabAI-Setup AP → Wi-Fi + backend URL), `.env`, device map
7. Usage: hold to talk, double-press for staff, LED meanings table
8. Adding knowledge: markdown format, frontmatter, private folder
9. API reference
10. Testing: pytest, firmware host tests, eval script
11. Project structure
12. Limitations and roadmap: onboard I2S mic/speaker, multiple units, staff dashboard,
    unanswered-question insights
13. Team

## 9. Decisions (Step 2 review)

These override anything above that contradicts them.

1. **LED ownership.** `led_manager` owns the RGB LED (GPIO38) entirely, including
   `led_strip` init. `device_manager` keeps only the button (GPIO0) and uptime;
   `device_manager_set_led` is removed. Serial `LED_ON` / `LED_OFF` and the portal
   LED On / Off buttons call `led_manager_set("white")` / `led_manager_set("off")`.
   `white` is a debug-only LED value; the next state poll overrides it within ~400 ms,
   which is accepted.
2. **mic_diagnostic.py** is updated in Phase 2 to use `Recorder` and `WhisperSTT`.
3. **Always-open mic with pre-roll.** `Recorder` opens the input stream once at startup
   (`open()`), not per press, so Bluetooth headsets don't switch profile on every
   question. The stream callback keeps a ring buffer of the last `PRE_ROLL_S` seconds
   (default 0.5, configurable). `start()` seeds the recording with that pre-roll, then
   buffers until `stop()`. This covers button → HTTP latency and the first syllable.
   `max_seconds` applies to the total including pre-roll. TTS output stays on the
   system default device. Test A5 covers pre-roll.
4. **Too-short check.** `talk_released` measures the recorded sample duration
   (`len(samples) / sample_rate`, pre-roll excluded). If there is no audio at all, it
   falls back to `held_ms`.
5. **One DEVICE_ID.** A single `#define DEVICE_ID` (in `device_manager.h`) is used by
   the banner, all request bodies and the state poll URL. The portal HTML does not
   hardcode it; `/api/status` returns `"device_id"` and the page fills it in.
6. **Event name gap.** Between Phase 3 and Phase 4 the old firmware (`talk_button_pressed`)
   and new backend (`talk_pressed`) are incompatible. Accepted; don't demo the board in
   between.
7. **Python.** The venv is created with `py -3.12 -m venv backend/.venv`. Existing pins
   are kept (`sounddevice==0.5.6`, `faster-whisper==1.2.1`); new packages are pinned to
   the versions pip resolves (direct dependencies only).
8. **Thresholds in tests.** Tests that depend on the RAG threshold set their own value,
   never the config default (which is tuned for nomic embeddings).
9. **Small fixes.** `/health` checks Ollama with a 1 s timeout and caches the result for
   10 s. The firmware state poll reuses one keep-alive `esp_http_client`. The
   `backend/certs/` gitignore entry is removed.

### Phase 0 implementation notes

Accepted deviations from sections 3–5. Later phases follow these.

1. **`HelpRequest` lives in `core/pipeline.py`**, not `services/notify_service.py`, because
   the pipeline builds it and `core/` must not import `services/` (which pulls in aiohttp).
   `notify_service` imports and re-exports it, so `from services.notify_service import
   HelpRequest` also works.
2. **`build_messages()` takes an extra optional `help_called_at: datetime | None`** so the
   system prompt can say "called at HH:MM, waiting".
3. **`pytest.ini` also sets `testpaths = tests` and `pythonpath = .`** so tests can import
   `core.*`, `services.*` and `config` from `backend/`.
4. **`DeviceStateStore(clock, help_ack_clear_s=600.0)`** takes the ack timeout from config.
   `clock` is a zero-argument callable (tests pass `FakeClock().now`), as for
   `SessionManager`.
5. **The pipeline depends on Protocols defined in `core/pipeline.py`** (`RecorderLike`,
   `STTLike`, `KnowledgeBaseLike`, `LLMLike`, `TTSLike`, `NotifierLike`,
   `UnansweredLogLike`, `ScoredChunkLike`) and `devices` is a `Callable[[str], Mapping]`
   (`config.get_device`).
6. **Existing `audio_service.py`, `llm_service.py`, `tts_service.py` were left unchanged in
   Phase 0** (only Vosk was removed from `stt_service.py`); Phase 2 rewrites them to
   `Recorder`, `OllamaChat`, `create_tts()` and `WhisperSTT`, and updates `mic_diagnostic.py`.

### Phase 1 decisions

Override the EMERGENCY list in section 5 (`core/intents.py`) and extend `core/speech_text.py`.

1. **Two-tier emergency triggers**, so ordinary questions about smoke or burning do not
   page staff. Matching stays case-insensitive and whole-word.
   - STRONG (always EMERGENCY): i'm hurt, i am hurt, injured, bleeding, cut myself,
     burnt myself, burned myself, electric shock, emergency.
   - FIRE/SMOKE (EMERGENCY only in present-tense form): there's a fire, there is a fire,
     on fire, fire!, flames, there's smoke, there is smoke, smoke coming, lots of smoke,
     something is burning, it's burning, it is burning.
   - If the text contains a hypothetical/question marker (if, in case, is it normal, why,
     should i, how do i, what happens when) and no STRONG trigger, fire/smoke phrases do
     not trigger EMERGENCY; the text falls through to HELP / QUESTION.
   - Bare alarm words: if the transcript, after stripping punctuation and whitespace,
     consists only of the words fire, smoke, burning, flames, help (1 to 3 words total),
     it is EMERGENCY. Whisper usually transcribes a shouted word with a full stop
     ("Fire."). A sentence that merely contains one of these words ("the fire alarm test
     is today") is not.
   - "should I call staff if there is smoke" stays HELP (the hypothetical marker blocks
     the smoke phrase; "call staff" still matches HELP).
   Tests I12–I21 cover this; I1, I2, I3 and I10 still hold.
2. **Numbered list lines** ("1. ", "2) ") get the same sentence pause as bullets: they keep
   their number and end with a full stop when joined. Test T6.

### Phase 2 decisions

1. **Fake embedder tuned for low collisions; retrieval quality is judged by the real
   embedder in Phase 5 (IT3, eval Q9).** `FakeEmbedder` uses 4096 dims and drops a small
   stopword list before CRC32 hashing (see test-plan "Test fakes"). Knowledge files and
   thresholds are not changed to satisfy the fake.
2. **The embedder owns model-specific prefixes.** `OllamaEmbedder.embed_documents(texts)`
   and `embed_query(text)` add nomic's `search_document: ` / `search_query: ` internally;
   `KnowledgeBase` passes raw text (`heading
text`, the query) and no longer knows
   about prefixes. `FakeEmbedder` implements the same two methods without prefixes.
   This changes FakeEmbedder scores only (the prefix words used to add shared tokens).
   Top-1 score / heading before -> after:

   | Query (machine) | Before | After | Top heading (unchanged) |
   |---|---|---|---|
   | "what size SD card" (3d-printer) | 0.695 | 0.780 | What is the maximum SD card size? |
   | "can I cut PVC" (laser-cutter) | 0.362 | 0.390 | What materials are banned? |
   | "best pizza" (3d-printer) | 0.339 | 0.274 | What is the maximum SD card size? |
   | "what is the maximum SD card size" (3d-printer) | 0.757 | 0.841 | What is the maximum SD card size? |

   K1–K9 still pass; the 0.5 test threshold separates the queries more widely than before.

### Phase 3 decisions

1. **`Answer` has `best_score`** (top boosted retrieval score, `None` for help/emergency),
   returned by `/api/ask` so `run_eval.py` can print scores for threshold tuning.
2. **Refusal gate while staff are called (revised after review).** Below the threshold
   the LLM is never called. If help is `pending` or `acknowledged`, the reply is
   deterministic: "Sorry, I don't have that in the Fab Lab guides." plus "Staff were
   called at HH:MM and should be with you shortly." (pending) or "...and are on the
   way." (acknowledged). With no help, the normal refusal. Either way it is logged as
   unanswered and `refused=true`. Refused questions are still added to the session, so
   they appear in `recent_questions` for staff. Tests PL15, PL15b, PL15c.
3. **Event-triggered speech runs in the background** (help confirmation, "already been
   called", "on the way"), so `/api/device/event`, `/api/help/ack` and the Telegram poller
   return immediately. It does not set activity `speaking`: the LED shows `red_pulse` /
   `purple` straight away. A single speech lock stops utterances overlapping.
   `VoicePipeline.drain()` awaits background work (tests, shutdown).
4. **Notifier failure** sets help back to `none` and the user hears "Sorry, I couldn't
   reach Fab Lab staff. Please find a staff member in the lab." (appended to the
   emergency message for EMERGENCY).
5. **An emergency is never deduped**: it notifies even while a request is pending.
6. **`ack` is ignored unless help is `pending`**; `resolve` always clears.
7. **One mic, one recorder.** Only the device that started a recording can stop it; a press
   from another device while recording is `busy`. `talk_released` with no recording in
   progress (e.g. cancelled by a help request) returns `{"accepted": false, "reason":
   "not_recording"}` without touching activity.
8. **`VoicePipeline.ask()`** runs `handle_text` under the device lock and is what
   `/api/ask` calls. `/api/ask` without `device_id` uses `"api"` (machine `all`), returns
   503 `{error}` if the LLM or embedder fails. The pipeline takes an optional
   `now` callable for help timestamps.
9. **`OllamaHealth`** (`services/llm_service.py`) implements 9.9: `GET /api/tags`, 1 s
   timeout, result cached 10 s.
10. **Startup is tolerant**: no mic → warning (turns hear nothing); Ollama down → KB embeds
    on first question. Whisper preloads in the background.
11. **NEXT intent for step mode (after review).** `detect_intent` returns `NEXT` when the
    whole transcript, punctuation stripped and lowercased, is one of: next, next step,
    continue, go on, done, okay next, ok next ("what's next for the fab lab" stays
    QUESTION). Checked after EMERGENCY and HELP. In the pipeline:
    - With session history: the retrieval query is the last non-NEXT user question only,
      the threshold gate is skipped, the LLM gets history + the retrieved chunks, and
      the turn is stored with user text "next".
    - Without history: "What would you like help with?", no LLM call, nothing logged.
    Follow-up QUESTIONs also combine with the last non-NEXT question, never with "next".
    Tests I22, I23, PL7 (real knowledge files), PL7a, PL7b. This replaces the earlier
    PL7 one-chunk workaround.
12. **Demo latency.** At startup, if Ollama answers `/api/tags`, `warm_up()` embeds the
    knowledge base and sends one tiny chat ("Reply with OK.") to load the model, logging
    each duration; failures are logged and fall back to lazy loading. If Ollama is down,
    startup stays lazy. All chat and embed requests pass `keep_alive`
    (`OLLAMA_KEEP_ALIVE`, default `30m`) so the models stay in memory between questions.

### Smoke-test fixes (2026-09-24)

1. **Latency: diagnosed, not a reload.** The warm-up chat already used the same
   `OllamaChat.chat()` as real questions (same model, options, `keep_alive`), and the KB
   was already embedded in one `/api/embed` request. Ollama's own `load_duration` was
   ~0 on the slow requests. The laptop had ~0.9 GB of 16 GB RAM free, and the gemma
   runner's working set was 540 MB of 6 GB private (nomic: 93 MB of 1.4 GB), so Windows
   had paged the idle runners out. The first request to each model then waits seconds for
   page-ins (4–11 s measured; the 27 s first question fits Whisper + Edge etc. competing
   for RAM). **Before a demo, close Edge, Creative Cloud and other heavy apps.**
   Changes:
   - Every Ollama request logs its duration, Ollama's `load_duration`, the options and
     `keep_alive`; the pipeline logs retrieval and LLM time per turn, and the context
     headings sent to the LLM. A reload shows as `load N s`; paging shows as a slow
     request with `load 0.00 s`.
   - `OLLAMA_NUM_CTX` (default 4096, was a hard-coded 8192): prompts stay under ~600
     tokens, and a smaller KV cache means less memory. Warm-up and real chats share it.
   - KB embedding is sent in batches of 32 inputs.
   - Chunk vectors are cached in `data/kb_cache.npz`, keyed by a SHA-256 of every
     knowledge file (name + bytes) and the embed model name. A key or row-count mismatch
     or an unreadable file rebuilds it; writes are atomic.
   - Warm-up also runs one throwaway retrieval, so the embed model is loaded at startup
     even when the cache means nothing is embedded (without it the first question paid a
     2.7 s nomic load).

   | Startup / first question | Before | After |
   |---|---|---|
   | Cold (models unloaded), no cache: KB embed / LLM load | 6.6 s / 9.6 s | 4.8 s / 7.0 s (ready 13.4 s) |
   | Cold, with cache: KB / embed model / LLM | n/a | 0.0 s / 2.5 s / 6.0 s (ready 9.5 s) |
   | Warm restart (models in Ollama), with cache | KB 0.9 s, LLM 0.2 s | ready 1.7 s, KB 0.0 s |
   | First question after startup | 1.5 s cold, 2.0 s warm | 1.08 s cold, 0.57 s warm |

2. **Refusal is an LLM gate.** nomic scores bunch together ("best pizza" 0.69 vs real
   questions 0.68), so the threshold can't separate them. The system prompt now says: if
   CONTEXT doesn't answer, reply with exactly `NO_ANSWER` and nothing else. If the reply
   contains `NO_ANSWER`, the pipeline returns the normal refusal (or the staff-status
   version while help is pending/acknowledged), sets `refused=true`, logs the question as
   unanswered, and stores the refusal (never `NO_ANSWER`) in the session. `RAG_THRESHOLD`
   stays as a junk filter only, default lowered to 0.55. Tests PL5c, PL5d, P7.
3. **Step mode is deterministic.** `Session.procedure` is a `ProcedurePointer(file, step)`
   or None (`core/steps.py`). A procedure is a knowledge file with a "(full procedure)"
   overview chunk and "Step N:" chunks; `Chunk.file` is the file key (`3d-printer`).
   - QUESTION: clears the pointer. After a successful answer, if the retrieved chunks
     include an overview or a Step N chunk, the best-ranked one sets the pointer
     (overview → step 1, and the Step 1 chunk is added to CONTEXT).
   - NEXT with a pointer: `KnowledgeBase.step_chunk(file, N+1)` fetches the next step
     directly (no retrieval); the LLM gets only that chunk and the last 2 turns; the
     pointer advances. No step N+1 → "That was the last step. Anything else?" with no LLM
     call; the pointer stays, so a repeated "next" says the same. `NO_ANSWER` here
     refuses, logs with `best_score: null` and clears the pointer.
   - NEXT without a pointer but with history: unchanged (9.11).
   - New prompt rule: "State only facts from CONTEXT. Never add details that are not in
     CONTEXT."
   - Known trade-off: "include" means a lower-ranked step chunk can set the pointer (e.g.
     "what is the maximum SD card size" also retrieves "Step 4: Where do I insert the SD
     card?"), so a "next" after it continues from step 5.
   Tests PL7c (overview → next → next walks steps 1, 2, 3 of 3d-printer.md), PL7d, PL7e,
   PL7f, K15; PL7/PL7a now clear the pointer to test the no-pointer path.
4. **Spoken source names.** Knowledge frontmatter has `spoken_source` ("the Fab Lab
   website", "the 3D printer guide", "the laser cutter guide") and `origin` (the old
   `source` value). CONTEXT lines are `[spoken_source] heading: text`. `/api/ask`
   `sources` is a list of `{"spoken_source", "origin"}` objects. A file with only the old
   `source` key uses it for both. Tests K14, K14b, P1, API8.
5. **Small fixes.** `firmware/test/Makefile` sets `CC = gcc` (make's built-in `CC = cc`
   beat `CC ?= gcc`). `to_speakable` straightens curly quotes and apostrophes before TTS
   (T7). On this laptop the host tests run with MSYS2 (`C:\msys64\usr\bin\make.exe`, gcc
   from `C:\msys64\ucrt64\bin`) from PowerShell.

### Step-mode review (2026-09-24, after the smoke-test fixes)

Overrides the matching points of "Smoke-test fixes" item 3.

1. **"next" in step mode never calls the LLM.** With a pointer, the reply is the next
   step chunk spoken verbatim: "Step N. <chunk text> Say next when you're ready." (chunk
   whitespace collapsed; `core.steps.step_reply`), or "That was the last step. Anything
   else?". So steps are never trimmed or embellished, and the step-mode `NO_ANSWER` path
   and the 2-turn short history are gone. Tests PL7c, PL7d.
2. **First answer to a procedure question.** When the top chunk is a step or overview,
   the LLM is still used, but the length rule becomes "up to 5 sentences for step
   instructions, and include every action in the step" (`build_messages(step_answer=True)`)
   instead of "1 to 3 short sentences". Test P9.
3. **The pointer is set only from the TOP-ranked chunk** (overview -> step 1, "Step N" ->
   N). A step chunk lower in the results no longer sets it, which removes the "max SD card
   size" -> Step 4 trade-off. Test PL7f.
4. **Follow-up merging only after an answered question.** `Turn` records `refused`; a
   QUESTION is combined with the previous non-NEXT question only if that turn was not
   refused (threshold or `NO_ANSWER`), so an off-topic question no longer drags the next
   retrieval. NEXT without a pointer still uses the last question. Tests PL6c, PL6d.
5. **CLAUDE.md**: firmware host tests (`make -C firmware/test`) run from PowerShell, not
   Git Bash (MSYS2 temp-folder issue).
6. **Overview points at step 0 (after the re-run).** In the smoke re-run the LLM answered
   the overview question with the overview only, and the pointer (then step 1) made the
   first "next" skip to Step 2. Now an overview top chunk sets the pointer to step 0 and
   the Step 1 chunk is no longer added to CONTEXT: the LLM speaks the overview, and the
   first "next" reads Step 1 verbatim. A top "Step N" chunk still points at N. Tests PL7c,
   PL7g (overview -> next -> next -> next speaks steps 1, 2, 3 in order).

### Phase 4 firmware decisions

1. **Gestures.** A tap is a press held < 350 ms; a press within 400 ms of a tap's release
   is HELP. The HELP press never counts as a tap, so a triple tap gives one HELP and then
   a normal TALK_START (F5). Durations use unsigned subtraction, so the ms counter can wrap
   (F7). Repeated edges (press while pressed, release with no press) return NONE.
2. **LED rendering.** Colours at max 40/255: yellow (40, 28, 0), purple (28, 0, 40),
   debug white (16, 16, 16). `red_pulse` is a 2 s cosine breath from 2 to 40.
   `red_flash` is 3 × (150 ms on, 150 ms off), then off. `offline` is red 8/255 for 150 ms
   every 2 s. Setting the value the LED already shows keeps the animation phase, so the
   400 ms poll repeating `red_pulse` / `red_flash` does not restart it. Unknown strings
   are logged and ignored. The strip is written only when the colour changes.
3. **Offline.** Every poll that fails counts: no Wi-Fi, no backend URL, an HTTP error,
   non-2xx or a body without `led`. The 3rd failure in a row sets `offline` once, on the
   transition, and marks the backend offline for the portal. Consequences: in setup mode
   (no Wi-Fi) the LED blinks offline, and a debug `white` set while offline stays until
   the backend comes back. One successful poll clears the count and applies `led`.
   Poll timeout is 1 s (connection refused fails at once, so H4 shows within ~1.2 s).
   "Backend Connected" in the portal now comes from the state poll, not `/health`.
4. **Two keep-alive clients.** The poll task (GET) and the sender task (POST) each keep
   their own `esp_http_client` (a handle is not thread-safe), dropped on any transport
   error and rebuilt on the next request or when the backend URL changes. The URL is
   copied under a spinlock, with a generation counter bumped by `backend_client_set_url`,
   which also strips trailing `/`.
5. **Sender task.** It waits on the 8-entry queue with a 1 s timeout, sends the event
   first, then does housekeeping: register (once per backend URL, retried until it
   succeeds) and a 15 s heartbeat. Events are dropped (logged) when the queue is full or
   the network/URL isn't ready; they are not retried. Event timeout is 2 s.
6. **Button task.** Debounce is a 50 ms lockout after each accepted edge. Timestamps come
   from `esp_timer` in ms. Serial prints `EVENT=talk_pressed`,
   `EVENT=talk_released HELD_MS=<n>` and `EVENT=help_requested` (replacing
   `BUTTON_PRESSED`). Only TALK_START sets a local LED (`blue`); HELP waits for the poll
   (`red_pulse`).
7. **Portal.** `/api/status` has `"device_id"` (from `DEVICE_ID`), shown in the Device
   row. `note` is only called, never assigned (the assignment threw in `scan()`, so the
   Wi-Fi scan never ran).
8. **sdkconfig** gained defaults regenerated by ESP-IDF 5.5.5 (committed as-is). The
   Phase 4 commits "led_manager" and "event queue" don't build on their own; the branch
   tip does.
