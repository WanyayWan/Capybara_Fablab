# FabAI handoff: read this first

For the teammates who will set up and record the demo on **your own laptop and hotspot**,
without Aung. This page is the short version; every step in full, with a fix for every
problem we hit, is in [setup-guide.md](setup-guide.md).

## What you receive from Aung

| Item | How |
|---|---|
| The ESP32-S3 board (`fabai-01`) and its USB cable | In person. **It is already flashed**, so you don't build any firmware. |
| The repo: https://github.com/WanyayWan/Capybara_Fablab, branch **`alh`** | This link. |
| The `backend/.env` values: `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` | **Privately** (never commit them, never paste them in a group). |
| The hotspot password for the name **`ALH`** | **Privately.** Only needed for Windows option 1 below. |

**You do NOT need ESP-IDF or MSYS2.** They are only for re-flashing the board or running the
firmware unit tests. The board comes flashed with the current firmware, including the
portal fix (Save Backend works).

## What you install (any OS)

Git, Python **3.12** (not 3.13/3.14), Ollama plus two models (about 3.6 GB), and the repo's
Python packages. The Whisper speech model (about 150 MB) downloads itself on the first
run. **Do all downloads on a normal internet connection before the demo day.** Full steps:
[setup-guide.md, sections 1 and 2](setup-guide.md#1-install-the-tools).

## Your laptop: pick your OS

The board has no mic or speaker. It must reach the backend on your laptop at port 8000,
over a **2.4 GHz** Wi-Fi network that both of them join. School Wi-Fi (SUTD) doesn't work
(it needs a username login and blocks device-to-device traffic).

### Windows: your laptop's own Mobile Hotspot

Settings → Network & internet → **Mobile hotspot**: share from Wi-Fi, band **2.4 GHz**,
**power saving off**, then turn it on. Your laptop stays on its normal Wi-Fi for internet.

- **Option 1 (easiest): name the hotspot `ALH`** with Aung's password. The board already
  has that network and the backend URL `http://192.168.137.1:8000` saved (a Windows
  hotspot always gives the laptop `192.168.137.1`), so it **connects by itself**. No
  portal needed.
- **Option 2: any name and password.** The board won't find `ALH`, and after about 30 s it
  opens its setup network **FabAI-Setup**. Configure it from your phone:
  [setup-guide.md, section 5.4](setup-guide.md#54-configure-the-board-in-its-portal).
  **Save Backend** `http://<laptop IP>:8000`, then pick your hotspot and **Save and
  Connect**. For the laptop IP, run `ipconfig` and read the IPv4 address of the
  "Local Area Connection\*" adapter (almost always `192.168.137.1`).

If the hotspot page says it shares over **5 GHz**, the board can't see it: see
[setup-guide.md, section 5.2](setup-guide.md#52-windows-turn-on-the-mobile-hotspot).

### macOS: a phone hotspot

A Mac can't share Wi-Fi over Wi-Fi, so use a **phone hotspot** at **2.4 GHz** (iPhone:
Settings → Personal Hotspot → **Maximize Compatibility** on; Android: AP band 2.4 GHz).
The Mac and the board both join the phone's hotspot.

1. Join the Mac to the phone hotspot, then get its IP: `ipconfig getifaddr en0`
   (for example `172.20.10.2` on an iPhone hotspot).
2. Configure the board in its portal (it opens **FabAI-Setup** about 30 s after it fails to
   find `ALH`): Save Backend `http://<Mac IP>:8000`, then pick the phone's hotspot and
   Save and Connect. [setup-guide.md, section 5.5](setup-guide.md#55-macos-phone-hotspot).
3. If the phone hotspot is turned off and on, the Mac's IP can change: check it again and
   re-save the backend URL if the LED blinks dim red.

Mac differences: `source .venv/bin/activate` instead of `.venv\Scripts\activate`,
`cp` instead of `copy`, Ollama from https://ollama.com/download/mac, `curl` instead of
`curl.exe`, and speech comes from macOS `say` (nothing to install). Allow the Terminal
**microphone** access and Python **incoming connections** when macOS asks.

## Telegram (staff alerts)

Put Aung's two values in `backend/.env`. Alerts go to whatever chat `TELEGRAM_CHAT_ID`
names. **For the team to see them, use a Telegram group:**

1. Create a group, add the bot (its username comes with the token), and **send one message
   in the group**.
2. **With the backend stopped**, open
   `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser, with the token pasted
   straight after `bot` (no `<` `>`, no spaces).
3. Find `"chat":{"id":-100...` for the group. Group ids **start with `-`**: keep the minus.
   Put that in `TELEGRAM_CHAT_ID`.

`"result":[]` means no message reached the bot yet (or a running backend consumed it):
stop the backend, send another group message, reload. Leaving both values empty prints
alerts in the backend window instead.

## Demo day, in order

1. Close heavy apps (browsers with many tabs, Teams, Creative Cloud): the models need RAM.
2. Hotspot on (Windows: power saving off). Ollama running.
3. Start **one** backend, 5 minutes early:

   ```powershell
   cd backend
   .venv\Scripts\activate          # macOS: source .venv/bin/activate
   python app.py
   ```

   The banner should say `staff alerts: Telegram`.
4. Plug the board into USB power. Within 30 s its LED goes from blinking dim red to **off**
   (connected). Still blinking after 30 s: press the board's **RESET** button once.
5. One warm-up question from a second terminal (Windows; on macOS use `curl` and drop the
   backslashes before the quotes):

   ```powershell
   curl.exe -s -X POST http://127.0.0.1:8000/api/ask -H "Content-Type: application/json" -d '{\"question\":\"Where is the Fab Lab?\"}'
   ```

6. Audio: **the laptop's built-in speakers and mic** (the audience hears it). Not AirPods
   (the phone steals them, and their mic is call quality). Restart the backend after
   changing the audio device.
7. The phone is **off FabAI-Setup** and has Telegram open in the staff group.
8. Walk through the [demo-script.md](demo-script.md) pre-demo checklist.

## Recording checklist

- [ ] Film the whole [demo-script.md](demo-script.md) script: step mode (overview → next →
      next), the pizza refusal, PVC on the laser cutter, the double-press staff call,
      **On my way**, **Resolved**.
- [ ] Keep the **board's LED in frame** (blue listening, yellow thinking, green speaking,
      breathing red when staff is called, purple on "On my way").
- [ ] For the staff call, film the **phone's Telegram screen** as the alert arrives and as
      you tap the buttons (a second phone filming, or a screen recording cut in).
- [ ] Speak **close to the laptop mic**. Hold the button for the whole sentence, then
      release. Known mishearings: "load" → "love", "cut" → "cap": just repeat.
- [ ] Record the audio from the laptop speakers, not a monitor or Bluetooth output.
- [ ] If a take fails, wait 2 minutes before retrying step mode (the conversation resets
      after 120 s), or restart the backend.

Something wrong? The troubleshooting table in
[setup-guide.md](setup-guide.md#10-troubleshooting) has every problem we actually hit.

## Optional: Aung's laptop

If you borrow Aung's laptop instead, everything is installed and the board already knows
its hotspot. Turn on Mobile hotspot (`ALH`, power saving off), start Ollama, then follow
"Demo day, in order" from step 3, in `C:\Users\Public\SUTD\Term 1\MVP Hackathon\Capybara_Fablab\backend`.
