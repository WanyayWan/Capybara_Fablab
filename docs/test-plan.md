# FabAI test plan

Four layers:

| Layer | Tool | Needs | When |
|---|---|---|---|
| Unit + API | pytest (fakes for all services) | nothing | every commit |
| Firmware logic | host gcc (`make -C firmware/test`) | gcc | phase 4 |
| Integration + eval | pytest `-m integration`, `scripts/run_eval.py` | Ollama | phase 5 |
| Hardware | manual checklist | ESP32, laptop, headset | phase 5 and before the pitch |

## Test fakes (`backend/tests/fakes.py`)
- `FakeEmbedder`: deterministic bag-of-words hashing vectors (lowercase words, minus a
  small stopword list: a, an, the, i, can, do, does, is, are, how, what, where, which,
  when, of, to, for, my, me, on, in, it, and, or, with; CRC32-hashed into 4096 dims,
  L2-normalised) so similar wording gives higher cosine. Tuned for low collisions;
  retrieval quality is judged by the real embedder in Phase 5 (IT3, eval Q9).
- `FakeSTT(text)`: returns fixed text; records calls.
- `FakeLLM(reply)`: returns fixed reply; stores the last messages it received.
- `FakeTTS`: records spoken strings, never blocks.
- `FakeNotifier`: records `HelpRequest`s.
- `FakeRecorder(samples)`: `start/stop/cancel` with controllable duration.
- `FakeClock`: `now()` and `advance(seconds)`.
- `FakeUnansweredLog`: in-memory list.

---

## Unit tests

### test_intents.py
| ID | Input | Expect |
|---|---|---|
| I1 | "There's a fire in the laser cutter" | EMERGENCY |
| I2 | "I cut myself" | EMERGENCY |
| I3 | "the material is on fire" | EMERGENCY |
| I4 | "please call staff" | HELP |
| I5 | "I need staff" | HELP |
| I6 | "CALL SOMEONE" (caps) | HELP |
| I7 | "can you help me load filament" | QUESTION |
| I8 | "how do I cut acrylic" | QUESTION (no "cut myself") |
| I9 | "what does the help button do" | QUESTION |
| I10 | "fire! call staff" | EMERGENCY (emergency wins) |
| I11 | "" | QUESTION |
| I12 | "is it normal for the laser cutter to smoke?" | QUESTION |
| I13 | "why is my print burning" | QUESTION |
| I14 | "what do I do if there's a fire" | QUESTION (hypothetical) |
| I15 | "there's smoke coming out of the laser cutter" | EMERGENCY |
| I16 | "something is burning" | EMERGENCY |
| I17 | "what if I cut myself" | EMERGENCY (strong triggers always win) |
| I18 | "Fire." | EMERGENCY (bare alarm word) |
| I19 | "fire fire" | EMERGENCY |
| I20 | "Smoke!" | EMERGENCY |
| I21 | "the fire alarm test is today" | QUESTION (not only alarm words) |

### test_sessions.py
| ID | Case | Expect |
|---|---|---|
| S1 | new device | empty history |
| S2 | add 2 turns | history has 4 messages in order |
| S3 | add 8 turns with max 6 | only last 6 kept |
| S4 | advance clock 121 s | `get` returns a fresh empty session |
| S5 | advance 60 s, add turn, advance 60 s | session still alive (activity refreshes) |
| S6 | two devices | histories independent |
| S7 | `last_user_messages(3)` | returns last 3 user texts, newest last |

### test_device_state.py
| ID | Case | Expect `led` |
|---|---|---|
| D1 | new device | `off` |
| D2 | activity listening / thinking / speaking | `blue` / `yellow` / `green` |
| D3 | help pending, activity idle | `red_pulse` |
| D4 | help pending, activity listening | `blue` (activity wins) |
| D5 | help acknowledged, idle | `purple` |
| D6 | activity error | `red_flash`; after 3 s → `off` |
| D7 | acknowledged, advance 601 s | help `none`, `off` |
| D8 | unknown device id | `off` without error |

### test_prompts.py
| ID | Case | Expect |
|---|---|---|
| P1 | chunks given | system message contains each `[source] heading` |
| P2 | history given | history messages appear between system and new question |
| P3 | help pending | system contains "called" and "waiting" |
| P4 | help acknowledged | system contains "on the way" |
| P5 | machine + location | both appear in system message |
| P6 | rules | system mentions one step at a time and never authorising |

### test_speech_text.py
| ID | Input | Expect |
|---|---|---|
| T1 | "**Press** the `button`" | "Press the button" |
| T2 | "- step one\n- step two" | no dashes, one line |
| T3 | "e.g. PLA" | "for example PLA" |
| T4 | 1,000-char text | ≤ 600 chars, ends at a sentence boundary |
| T5 | "32 GB" | numbers kept |
| T6 | "1. Heat the nozzle\n2) Load the filament" | "1. Heat the nozzle. 2) Load the filament." (numbered lines pause like bullets) |

### test_knowledge.py
| ID | Case | Expect |
|---|---|---|
| K1 | load real `knowledge/` | ≥ 30 chunks, every chunk has machine and source |
| K2 | file with 3 `##` headings | 3 chunks, headings correct, frontmatter not in text |
| K3 | file without frontmatter | skipped, no crash |
| K4 | `private/` missing | loads fine |
| K5 | retrieve "what size SD card" (FakeEmbedder, machine 3d-printer) | top chunk heading mentions SD card |
| K6 | retrieve "can I cut PVC" (machine laser-cutter) | top chunk is banned materials |
| K7 | machine boost | with two equally similar chunks, the device's machine ranks first |
| K8 | unrelated query "best pizza" | `is_confident` is False |
| K9 | top_k = 3 | at most 3 results, sorted by score desc |

### test_audio_service.py
| ID | Case | Expect |
|---|---|---|
| A1 | start, feed 1 s of chunks, stop | 16000 samples returned |
| A2 | feed beyond `max_seconds` | truncated at max |
| A3 | cancel | stop returns empty array, not recording |
| A4 | stop without start | empty array, no error |
| A5 | pre-roll: feed 1 s of chunks before `start()` (PRE_ROLL_S 0.5), then 1 s after, `stop()` | 24000 samples; the first 8000 equal the last 0.5 s fed before `start()` |

### test_notify_service.py
| ID | Case | Expect |
|---|---|---|
| N1 | `format_help_message` normal | contains device, machine, location, time, questions |
| N2 | emergency | message starts with EMERGENCY |
| N3 | no recent questions | says "no questions yet" (no crash) |
| N4 | `parse_callback("ack:fabai-01:abc")` | `("ack", "fabai-01", "abc")` |
| N5 | `parse_callback("garbage")` | None |
| N6 | `create_notifier` without token | ConsoleNotifier |
| N7 | Telegram `send_help` (mock HTTP) | posts to sendMessage with chat_id and 2 inline buttons |

### test_unanswered_log.py
| ID | Case | Expect |
|---|---|---|
| U1 | log twice to tmp path | 2 JSON lines with all fields |
| U2 | `read_all` on missing file | empty list |

---

## Pipeline tests (test_pipeline.py)
All with fakes and FakeClock.

| ID | Scenario | Expect |
|---|---|---|
| PL1 | press → release (2 s) → processing, STT "how do I load filament" | activity goes listening → thinking → speaking → idle; TTS spoke the LLM reply; session has 1 turn |
| PL2 | release after 0.2 s | `too_short`, activity idle, STT not called |
| PL3 | STT returns "" | TTS says "didn't catch that", no LLM call |
| PL4 | press while thinking | `accepted: False, reason: busy` |
| PL5 | question with no confident chunk | refusal text, `refused=True`, unanswered logged, LLM not called |
| PL6 | follow-up "what about the X1E" after an SD card question | retrieval query contains both questions |
| PL7 | "next" after a procedure answer | LLM receives history with the previous step |
| PL8 | help_requested event | notifier called once, help pending, TTS confirmation, led `red_pulse` |
| PL9 | help while recording | recorder cancelled |
| PL10 | second help while pending | notifier still called once, reply "already been called" |
| PL11 | voice "call staff" | same as PL8, no LLM call |
| PL12 | voice "there's a fire" | EMERGENCY_RESPONSE spoken, notifier called with emergency=True, no LLM call |
| PL13 | `help_update(ack)` | help acknowledged, TTS "on the way", led `purple` |
| PL14 | `help_update(resolve)` | help none |
| PL15 | ask "is someone coming" while pending | LLM system prompt contains the waiting status |
| PL16 | LLM raises | activity error, TTS "something went wrong", no crash |
| PL17 | unknown device id | uses machine `all`, still answers |
| PL18 | help request includes last 3 user questions | HelpRequest.recent_questions correct |

## API tests (test_api.py, aiohttp test client + fakes)

| ID | Request | Expect |
|---|---|---|
| API1 | GET /health | 200, status ok |
| API2 | POST /api/device/register fabai-01 | machine 3d-printer |
| API3 | POST /api/device/event talk_pressed | 202, accepted |
| API4 | POST /api/device/event unknown event | 400 |
| API5 | POST /api/device/event invalid JSON | 400 |
| API6 | GET /api/device/state?device_id=fabai-01 | 200 with activity, help, led |
| API7 | GET /api/device/state without device_id | 400 |
| API8 | POST /api/ask valid | 200 with text, intent, sources, refused |
| API9 | POST /api/ask empty / 2001 chars | 400 |
| API10 | POST /api/help/ack ack | help acknowledged |
| API11 | GET /api/unanswered after a refused question | 1 entry |
| API12 | help_requested event then state | led `red_pulse` |

---

## Firmware host tests (firmware/test/test_button_gesture.c)

| ID | Edge sequence (pressed, ms) | Expect events |
|---|---|---|
| F1 | down 0, up 2000 | TALK_START, TALK_END(held 2000) |
| F2 | down 0, up 100, down 300, up 400 | TALK_START, TALK_END(100), HELP, NONE |
| F3 | down 0, up 100, down 700, up 2700 | TALK_START, TALK_END, TALK_START, TALK_END (gap too long) |
| F4 | down 0, up 500, down 700 | third edge is TALK_START (first press was not a tap) |
| F5 | triple tap within 400 ms gaps | TALK_START, TALK_END, HELP, NONE, TALK_START, TALK_END (no double HELP) |
| F6 | up with no prior down | NONE |
| F7 | timer wrap (now_ms near UINT32_MAX) | same as F2 |

---

## Integration tests (`pytest -m integration`, Ollama running)

| ID | Case | Expect |
|---|---|---|
| IT1 | OllamaEmbedder on 2 texts | shape (2, dim), rows normalised |
| IT2 | OllamaChat simple message | non-empty string |
| IT3 | full KnowledgeBase with real embedder, "what is the max SD card size" | top chunk mentions 32 GB |
| IT4 | WhisperSTT on a short generated WAV (TTS or bundled fixture) | non-empty text |

## RAG eval (`scripts/run_eval.py`)
Reads `tests/eval/questions.yaml`, calls `POST /api/ask` on a running backend, checks:
- `expect: answer` → not refused, answer contains at least one `must_include` keyword
  (case-insensitive)
- `expect: refuse` → `refused=True`
- `expect: help` / `emergency` → matching intent

Prints a table (id, pass/fail, score, answer preview) and the pass rate. Target ≥ 80%.
Use the printed scores to tune `RAG_THRESHOLD`.

---

## Hardware checklist (manual)

| ID | Step | Expect |
|---|---|---|
| H1 | Power on, open serial monitor | `FABAI_READY` banner |
| H2 | Join FabAI-Setup AP, open 192.168.4.1, Scan Wi-Fi | network list shows (portal bug fixed) |
| H3 | Save Wi-Fi + backend URL `http://<laptop-ip>:8000` | portal shows Backend Connected |
| H4 | Stop backend | LED dim red blink within ~2 s |
| H5 | Hold button, ask "how do I load filament", release | blue → yellow → green → off, answer heard in headset |
| H6 | Say "next" (hold/release) | next step spoken |
| H7 | Double-press | pulsing red, Telegram message arrives, confirmation spoken |
| H8 | Tap **On my way** in Telegram | purple, "on the way" spoken |
| H9 | Tap **Resolved** | LED off |
| H10 | Say "call staff" | same as H7 |
| H11 | Say "there's a fire" | fixed safety message within ~1 s after transcription, Telegram marked EMERGENCY |
| H12 | Press during thinking | ignored, no crash |
| H13 | Ask "what's the best pizza nearby" | polite refusal, appears in /api/unanswered |
| H14 | 10 back-to-back questions | no memory growth or hangs |
| H15 | Wi-Fi router restart | device reconnects, resumes polling |
