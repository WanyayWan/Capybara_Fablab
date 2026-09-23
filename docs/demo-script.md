# FabAI demo script (3 minutes)

One unit, `fabai-01`, is the 3D printer unit. Every question below passed the RAG eval
or the rehearsal on 2026-09-24 (real Ollama, real knowledge files). Use the wording
exactly as written.

## Setup before the demo

Pre-demo checklist:

- [ ] **Close heavy apps** (Edge, Creative Cloud, Teams). Low RAM makes Windows page out the
      models, and the first answer then takes 5 to 30 s.
- [ ] **Mobile hotspot on**, 2.4 GHz, **power saving off** (Settings → Mobile hotspot).
- [ ] **One backend only.** Close any old `python app.py` window, then start the backend
      **5 minutes early**: `cd backend; python app.py`. Check the banner says
      `staff alerts: Telegram`.
- [ ] **One warm-up question**, asked from the laptop so the unit's conversation stays empty:
      ```powershell
      curl.exe -s -X POST http://127.0.0.1:8000/api/ask -H "Content-Type: application/json" -d '{\"question\":\"Where is the Fab Lab?\"}'
      ```
      If you rehearse on the unit itself, wait **2 minutes** before going live. The
      session resets after 120 s, and the step-mode opener must start in a fresh session.
- [ ] ESP32 powered, LED **off** (not blinking dim red). No help request pending: if the
      LED breathes red, tap **Resolved** in Telegram, or
      `curl.exe -s -X POST http://127.0.0.1:8000/api/help/ack -H "Content-Type: application/json" -d '{\"device_id\":\"fabai-01\",\"action\":\"resolve\"}'`.
- [ ] Headset connected and set as Windows default input **and** output; volume up.
- [ ] **Phone off FabAI-Setup** (it has no internet), on mobile data or venue Wi-Fi.
- [ ] **Telegram open on the phone** in the staff chat. Alerts from before a backend
      restart are no longer active, so use the new message.
- [ ] A second PowerShell window open in `backend/` with the PVC command below ready to
      paste.

## Script

| Time | Do / say | Expect |
|---|---|---|
| 0:00 | **Intro.** "Fab Lab users get stuck on small questions at machines where staff aren't standing. FabAI is a button at the machine: hold, ask, and it answers only from the lab's own guides. It runs offline on this laptop." | |
| 0:20 | **Step mode.** Hold the button: *"How do I use the 3D printer?"*, release. | LED blue → yellow → green → off. "According to the 3D printer guide, ... First, power on the printer. Next, load filament. Say next when you're ready." |
| 0:40 | Hold: *"Next"*, release. | "Step 1. Press the power button at the bottom right corner on the back of the machine. Say next when you're ready." |
| 0:50 | Hold: *"Next"*, release. | "Step 2. Open the AMS cover on top of the printer. ... The AMS will detect the filament and start loading automatically. Say next when you're ready." (About 15 s long.) Point out: steps are read word for word from the guide, not made up by the model. |
| 1:10 | **Out of scope.** Hold: *"What's the best pizza place near SUTD?"* | "Sorry, I don't have that in the Fab Lab guides. To get a staff member, double-press the button or say call staff." Say: "It refuses instead of guessing, and logs the question so staff know what the guides are missing." |
| 1:30 | **Laser cutter safety.** "Each unit knows its machine. Here's the laser cutter unit." In the second window, paste: `curl.exe -s -X POST http://127.0.0.1:8000/api/ask -H "Content-Type: application/json" -d '{\"device_id\":\"fabai-02\",\"question\":\"Can I cut PVC?\",\"speak\":true}'` | Spoken: "According to the laser cutter guide, no, you cannot cut PVC. It releases toxic chlorine gas." |
| 1:55 | **Call staff.** Double-press the button (two quick taps). | LED breathing red. Spoken: "I've called Fab Lab staff. Please stay by the machine." Phone buzzes: the alert shows the unit, machine, location, time and the last questions asked. |
| 2:15 | Show the phone and tap **On my way**. | LED purple, spoken: "A staff member is on the way." The Telegram message updates to "On my way: <name>". |
| 2:30 | Tap **Resolved**. | LED off. |
| 2:40 | **Close.** "Local models, answers only from the lab's guides, a one-gesture staff call, and a log of unanswered questions for staff. Next: a mic and speaker on each unit, and a staff dashboard." | |

**Wording rules:** say *"Can I cut PVC?"* exactly. *"Can I cut PVC on the laser cutter?"*
currently gets a wrong "yes" (the banned-materials section isn't retrieved for that
wording; see the test-plan results). Don't ask the PVC question on `fabai-01`: the 3D
printer unit refuses it.

## If something fails

| Step | Failure | Fallback |
|---|---|---|
| Any | LED blinks dim red every 2 s (offline) | Check the backend window is running and the laptop hotspot is on. Meanwhile, run the same questions from the laptop: `curl.exe ... /api/ask` with `\"device_id\":\"fabai-01\"` and `\"speak\":true`. |
| Any | Nothing heard | Headset not the default output: switch it in the Windows sound menu, or unplug and use the laptop speakers. |
| Any | "Sorry, I didn't catch that" | Hold the button for the whole sentence and speak after the LED turns blue. Repeat once. |
| Any | First answer is very slow | Models paged out. Keep talking; the next answers are fast. |
| Step mode | Overview refused, or "next" invents steps | The session wasn't fresh. Ask the eval questions directly instead: *"Where is the power button on the printer?"*, then *"How do I load filament?"* |
| Out of scope | Pizza gets an answer | Use *"What is the Wi-Fi password for the lab?"* (eval Q19). |
| PVC | Wrong or no answer | Paste the same command with `\"question\":\"Can I cut aluminium on the laser cutter?\"` (eval Q12: "no, ... can't cut metal"). If the backend is down, say the answer and move on. |
| Staff call | Double-press not detected (LED doesn't breathe red) | Hold the button and say *"Call staff"*. Same result. |
| Staff call | No Telegram message (laptop network dropped) | The poller retries every 5 s. Show the LED and the spoken confirmation, and drive the rest from the laptop: `curl.exe -s -X POST http://127.0.0.1:8000/api/help/ack -H "Content-Type: application/json" -d '{\"device_id\":\"fabai-01\",\"action\":\"ack\"}'`, then the same with `resolve`. |
| Staff call | Spoken "Sorry, I couldn't reach Fab Lab staff" | Telegram unreachable when sending (help goes back to none, so `/api/help/ack` does nothing). Say that's the designed fallback: the user is told to find staff in person. Move on to the close. |
| Staff call | "On my way" says "no longer active" | The backend restarted after that alert. Double-press again and use the new message. |
