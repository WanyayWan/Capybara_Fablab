# FabAI setup guide: fresh Windows laptop to working demo

For someone who has never seen the project. Follow the steps in order; each ends with a
check. Every problem we actually hit is in the [troubleshooting table](#9-troubleshooting).

**You need:** a Windows 11 laptop (16 GB RAM), an ESP32-S3 DevKit and a USB cable, a
Bluetooth headset with a mic, and a phone with Telegram.

**Use PowerShell** for every command here (not Git Bash, not cmd), unless a step says
otherwise.

---

## 1. Downloads

| # | Tool | Download | Notes |
|---|---|---|---|
| 1 | Git | https://git-scm.com/download/win | Defaults are fine. |
| 2 | Python **3.12** | https://www.python.org/downloads/windows/ (latest **3.12.x**, "Windows installer (64-bit)") | **Not 3.13 or 3.14**: faster-whisper's dependencies don't install on 3.14. Tick **"Add python.exe to PATH"**; keep the **py launcher**. |
| 3 | VS Code | https://code.visualstudio.com/ | Optional but handy. |
| 4 | Claude Code | https://claude.com/claude-code | Optional. |
| 5 | Ollama | https://ollama.com/download/windows | Runs the local AI models. |
| 6 | ESP-IDF 5.5 | https://docs.espressif.com/projects/esp-idf/en/release-v5.5/esp32s3/get-started/windows-setup.html | Only needed to flash firmware. |
| 7 | MSYS2 | https://www.msys2.org/ | Only needed for the firmware unit tests (make + gcc). |

### 1.1 Check Python

```powershell
py -3.12 --version        # Python 3.12.x
```

### 1.2 Claude Code (optional)

```powershell
irm https://claude.ai/install.ps1 | iex
```

### 1.3 Ollama models

Install Ollama, start it from the Start menu (it sits in the tray), then:

```powershell
ollama pull gemma3:4b
ollama pull nomic-embed-text
ollama list               # both models listed
```

If `ollama` is "not recognized", open a new PowerShell window (the installer updates PATH).

### 1.4 ESP-IDF 5.5

Either use the **ESP-IDF Tools Installer** from https://dl.espressif.com/dl/esp-idf/
(pick 5.5, then use its "ESP-IDF 5.5 PowerShell" shortcut), or install from git as on the
demo laptop:

```powershell
mkdir $HOME\esp
cd $HOME\esp
git clone -b release/v5.5 --recursive https://github.com/espressif/esp-idf.git
cd esp-idf
.\install.ps1 esp32s3
```

**In every new PowerShell window** where you build firmware, run once:

```powershell
. $HOME\esp\esp-idf\export.ps1    # note the leading ". "
idf.py --version                  # ESP-IDF v5.5...
```

### 1.5 MSYS2 (make + gcc for firmware tests)

1. Install MSYS2 to `C:\msys64` (the default).
2. Open **"MSYS2 UCRT64"** from the Start menu and run:

   ```bash
   pacman -Syu                                            # may close the window; reopen and repeat
   pacman -S --needed make mingw-w64-ucrt-x86_64-gcc
   ```

3. Add both folders to your user PATH (PowerShell):

   ```powershell
   $add = "C:\msys64\usr\bin;C:\msys64\ucrt64\bin"
   [Environment]::SetEnvironmentVariable("Path", [Environment]::GetEnvironmentVariable("Path", "User") + ";" + $add, "User")
   ```

4. Open a **new** PowerShell window and check: `make --version` and `gcc --version`.

---

## 2. Get the code

```powershell
cd $HOME\Documents
git clone https://github.com/WanyayWan/Capybara_Fablab.git
cd Capybara_Fablab
git checkout alh
```

Create the Python environment and install dependencies:

```powershell
cd backend
py -3.12 -m venv .venv
.venv\Scripts\activate            # prompt now starts with (.venv)
pip install -r requirements.txt -r requirements-dev.txt
copy .env.example .env
```

If `activate` is blocked ("running scripts is disabled"), run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then retry.

**Check:** `pytest` prints about 290 passed.

---

## 3. Telegram bot (staff alerts)

1. In Telegram, open **@BotFather** and send `/newbot`. Choose a name and a username
   ending in `bot`. BotFather replies with a **token** like
   `123456789:AAHfq3-example-token-XYZ`.
2. Open a chat with **your new bot** (search its username) and **send it any message**,
   e.g. "hi". The bot can only see chats that have messaged it first. For a staff group,
   add the bot to the group and send a message in the group.
3. **Make sure the FabAI backend is not running** (it reads and consumes these updates).
4. In a browser, open this URL, with your token pasted straight after `bot`: **no angle
   brackets, no spaces**:

   ```
   https://api.telegram.org/bot123456789:AAHfq3-example-token-XYZ/getUpdates
   ```

5. Find the chat id in the reply: `"chat":{"id":123456789, ...}`. Group ids are negative
   (e.g. `-1001234567890`); keep the minus sign.

   | You see | Meaning | Fix |
   |---|---|---|
   | `{"ok":true,"result":[]}` | No message yet, or a running backend already consumed it | Stop the backend, send the bot another message, reload |
   | `{"ok":false,"error_code":404}` | Token wrong or has `<` `>` / spaces in the URL | Copy the token again from BotFather |
   | `{"ok":false,"error_code":401}` | Token revoked | `/token` in BotFather for a new one |

6. Edit `backend\.env` (never commit this file):

   ```
   TELEGRAM_BOT_TOKEN=123456789:AAHfq3-example-token-XYZ
   TELEGRAM_CHAT_ID=123456789
   ```

---

## 4. Firmware (flash the ESP32-S3)

1. Plug the board in with a **data** USB cable (the port labelled **UART/COM** on DevKits
   with two ports).
2. Find its COM port:

   ```powershell
   [System.IO.Ports.SerialPort]::GetPortNames()      # e.g. COM5
   ```

   Or Device Manager → **Ports (COM & LPT)**; unplug and replug to see which one appears.
3. Build and flash (in a PowerShell window where you ran `export.ps1`):

   ```powershell
   cd $HOME\Documents\Capybara_Fablab\firmware
   idf.py set-target esp32s3        # first time only
   idf.py build
   idf.py -p COM5 flash monitor     # use your port; Ctrl+] quits the monitor
   ```

4. **Check:** the monitor prints

   ```
   FABAI_READY
   DEVICE_ID=fabai-01
   ...
   PORTAL_AP=http://192.168.4.1
   ```

If flashing says "Failed to connect": hold **BOOT**, tap **RESET (EN)**, release **BOOT**,
and flash again.

---

## 5. Wi-Fi (the problems we actually hit)

The ESP32 must reach the laptop's backend on port 8000. The setup that works: **the laptop
shares a Windows Mobile Hotspot, and the ESP32 joins it.**

### 5.1 Why not the school Wi-Fi (SUTD)

| Problem | Why it matters |
|---|---|
| SUTD Wi-Fi is WPA2-**Enterprise** (username + password) | The FabAI portal only has a password field, so the ESP32 can't join. |
| It would need your personal login | Don't store personal passwords on the device (they are saved in its flash). |
| Campus networks block device-to-device traffic | Even connected, the ESP32 couldn't reach the laptop. |

### 5.2 Turn on the hotspot

1. Keep the laptop on the school Wi-Fi: that is its internet. The laptop **is** the
   hotspot at the same time; you don't "connect" the laptop to its own hotspot.
2. Settings → Network & internet → **Mobile hotspot**:
   - Share my internet connection from: **Wi-Fi**
   - Properties → **Edit**: set a name and password; **Network band: 2.4 GHz** if offered
   - **Power saving: Off** (otherwise it switches off when nothing is connected)
   - Turn **Mobile hotspot: On**
3. The ESP32-S3 only does **2.4 GHz**. If the hotspot page says it is sharing over
   **5 GHz** (Windows follows the band of your current Wi-Fi connection):
   1. Device Manager → **Network adapters** → **Realtek 8922AE WiFi 7** → **Advanced**
      tab → **Preferred Band** → **2.4G first** → OK.
      Don't change "2.4G Wireless Mode" or "Multi-Channel Concurrent".
   2. Disconnect and reconnect the laptop's Wi-Fi, then turn the hotspot off and on.
   3. Still 5 GHz? Same Advanced tab → **5G Wireless Mode** → **Disabled** (undo this
      after the hackathon, see 5.6).
4. **Check:** the hotspot page shows the band as 2.4 GHz.

### 5.3 Windows firewall

The first time the backend starts, Windows asks whether Python may accept connections:
tick **Private and Public** and click **Allow**. If you missed it, from an **admin**
PowerShell:

```powershell
New-NetFirewallRule -DisplayName "FabAI backend" -Direction Inbound -Action Allow `
  -Program "$HOME\Documents\Capybara_Fablab\backend\.venv\Scripts\python.exe" -Profile Private,Public
```

### 5.4 Configure the ESP32 in its portal

1. Power the ESP32. With no saved Wi-Fi it creates an open network **FabAI-Setup**.
2. On your phone: Wi-Fi → join **FabAI-Setup**. A **"no internet"** warning is expected:
   choose to stay connected.
3. Open **http://192.168.4.1** in the phone's browser. If it won't load, **turn off mobile
   data** (the phone is sending the request over 4G/5G) and retry.
4. Tap **Scan Wi-Fi**, pick **your hotspot**, enter its password, **Save and Connect**.
5. Backend URL: **`http://192.168.137.1:8000`** (on a Windows hotspot the laptop is always
   `192.168.137.1`), then **Save Backend**.
6. On the phone, **forget FabAI-Setup** and switch back to normal Wi-Fi or mobile data.
   A phone left on FabAI-Setup has no internet, so **Telegram alerts won't arrive**.

### 5.5 Check

- The hotspot page shows **1 device connected** (the ESP32).
- Once the backend runs (step 7), the LED **stops the dim red blink**.

### 5.6 After the hackathon

- Realtek adapter → Advanced → **Preferred Band** back to **No Preference** (and
  **5G Wireless Mode** back to enabled if you disabled it).
- Hotspot power saving back on, if you like.

---

## 6. Bluetooth headset

1. Settings → Bluetooth & devices → **Add device** → Bluetooth → pick the headset.
2. Settings → System → **Sound**: set the headset as the **Output** and the **Input**
   (choose the "Headset" / "Hands-Free" microphone entry).
3. Test it end to end (records 5 s, plays it back, transcribes it):

   ```powershell
   cd $HOME\Documents\Capybara_Fablab\backend
   .venv\Scripts\activate
   python mic_diagnostic.py
   ```

**2.4 GHz note:** Bluetooth and the 2.4 GHz hotspot share the same radio band. If audio
stutters or the ESP32 drops, keep the headset and the ESP32 close to the laptop and away
from other 2.4 GHz devices.

---

## 7. Run it

1. Close heavy apps (Edge, Creative Cloud, Teams): the models need the RAM.
2. Make sure Ollama is running (tray icon), then start **one** backend:

   ```powershell
   cd $HOME\Documents\Capybara_Fablab\backend
   .venv\Scripts\activate
   python app.py
   ```

   The banner shows `FabAI backend on http://...:8000` and `staff alerts: Telegram`.
3. After it says it is ready, ask one warm-up question from a second PowerShell window
   (loads the models, doesn't touch the button's conversation):

   ```powershell
   curl.exe -s -X POST http://127.0.0.1:8000/api/ask -H "Content-Type: application/json" -d '{\"question\":\"Where is the Fab Lab?\"}'
   ```

### LED colours

| LED | Meaning |
|---|---|
| off | idle |
| solid blue | listening (button held) |
| solid yellow | thinking |
| solid green | speaking |
| breathing red | staff called, waiting |
| solid purple | staff tapped "On my way" |
| 3 quick red flashes | error; try again |
| dim red blink every 2 s | offline: can't reach the backend |

---

## 8. Verify

- [ ] `curl.exe -s http://127.0.0.1:8000/health` → `"status": "ok"` and `"ollama": true`
- [ ] Hotspot shows 1 device; the ESP32 LED is **off** (not blinking red)
- [ ] Hold the BOOT button, say *"Where is the power button on the printer?"*, release →
      blue → yellow → green, and you hear "According to the 3D printer guide, ..."
- [ ] Hold: *"How do I use the 3D printer?"*, then hold: *"Next"* → you hear "Step 1. Press
      the power button ..."
- [ ] **Double-press** → breathing red, "I've called Fab Lab staff", Telegram message on the
      phone → tap **On my way** → purple, "A staff member is on the way" → tap
      **Resolved** → LED off

The 3-minute demo is in [demo-script.md](demo-script.md).

---

## 9. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `pip install` fails building `av` / `ctranslate2` | Wrong Python (3.13/3.14) | Delete `.venv`, recreate with `py -3.12 -m venv .venv` |
| `.venv\Scripts\activate` "running scripts is disabled" | PowerShell execution policy | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `ollama` not recognized | PATH not refreshed | New PowerShell window, or start Ollama from the Start menu |
| `/health` says `"ollama": false` | Ollama not running | Start Ollama from the Start menu; `ollama list` |
| First answer takes 5 to 30 s | Laptop low on RAM; Windows paged the models out | Close heavy apps; start the backend 5 min early; one warm-up question |
| `idf.py` not recognized | ESP-IDF environment not loaded in this window | `. $HOME\esp\esp-idf\export.ps1` |
| Flash: "Failed to connect to ESP32-S3" | Wrong port or board not in download mode | Check the COM port; hold BOOT, tap RESET, release BOOT |
| No COM port appears | Charge-only cable or other USB port | Use a data cable; try the board's UART port |
| getUpdates shows `"result":[]` | No message sent yet, or a running backend consumed it | Stop the backend, message the bot, reload |
| getUpdates 404 | Brackets or spaces around the token in the URL | Token straight after `bot`: `https://api.telegram.org/bot123456789:AAH.../getUpdates` |
| ESP32 can't see the hotspot | Hotspot on 5 GHz | Preferred Band "2.4G first" (5.2); last resort 5G Wireless Mode Disabled |
| ESP32 can't join SUTD Wi-Fi | Enterprise login, client isolation | Use the laptop hotspot (5.1) |
| 192.168.4.1 won't load on the phone | Phone uses mobile data instead of FabAI-Setup | Turn off mobile data; stay connected despite "no internet" |
| LED blinks dim red every 2 s | Offline: 3 state polls in a row failed | Backend running? ESP32 on the hotspot? URL `http://192.168.137.1:8000`? Firewall rule (5.3)? |
| Hotspot shows 0 devices after a while | Hotspot power saving | Power saving **Off** (5.2) |
| No Telegram alert on the phone | Phone still on FabAI-Setup | Forget FabAI-Setup (5.4 step 6) |
| Telegram buttons do nothing | Two backends running (they fight over port 8000 and Telegram updates) | Close every `python app.py` window, start one |
| "On my way" says "no longer active" | The backend restarted after that alert | Double-press again; use the new message |
| Log shows `Telegram poll failed ... getaddrinfo failed` or `WinError 1236` | The laptop's network dropped (seen at 02:10 and 02:24 on 2026-09-24) | Nothing: it retries every 5 s; presses made meanwhile arrive afterwards |
| "Sorry, I didn't catch that" | Released too early, or the wrong input device | Hold for the whole sentence; set the headset as input (6); `python mic_diagnostic.py` |
| Nothing heard | Headset not the default output | Settings → Sound → Output |
| Audio stutters / ESP32 drops | Bluetooth and the hotspot share 2.4 GHz | Keep devices close to the laptop (6) |
| `make -C firmware/test`: "Cannot create temporary file in C:\Windows\" | Ran from Git Bash | Run it from **PowerShell** |
| `make` or `gcc` not recognized | MSYS2 folders not on PATH | Step 1.5, then a new PowerShell window |
