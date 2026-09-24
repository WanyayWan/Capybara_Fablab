# FabAI setup guide: your own laptop to a working demo

For someone who has never seen the project, on **their own Windows or macOS laptop**. Read
[HANDOFF.md](HANDOFF.md) first for the short version. Follow the steps in order; each
ends with a check. Every problem we actually hit is in the
[troubleshooting table](#10-troubleshooting).

**You need:** a Windows 10/11 or macOS laptop (16 GB RAM recommended), the ESP32-S3 board
and its USB cable (from Aung, **already flashed**), and a phone with Telegram. On macOS the
phone also provides the hotspot.

**You do NOT need ESP-IDF or MSYS2** unless you re-flash the board (section 4, optional).

**Commands:** on Windows use **PowerShell** (not Git Bash, not cmd). On macOS use
**Terminal**. Where the two differ, both are shown.

---

## 1. Install the tools

Do every download on a normal internet connection, before the demo day.

| # | Tool | Windows | macOS | Notes |
|---|---|---|---|---|
| 1 | Git | https://git-scm.com/download/win | Run `git --version`; macOS offers to install it | Defaults are fine. |
| 2 | Python **3.12** | https://www.python.org/downloads/windows/ (latest 3.12.x, 64-bit installer) | https://www.python.org/downloads/macos/ (latest 3.12.x, universal2 installer) | **Not 3.13 or 3.14**: faster-whisper's dependencies don't install on 3.14. Windows: tick **"Add python.exe to PATH"**, keep the **py launcher**. |
| 3 | Ollama | https://ollama.com/download/windows | https://ollama.com/download/mac (drag to Applications, open it once) | Runs the local AI models. |
| 4 | VS Code | https://code.visualstudio.com/ | same | Optional. |

### 1.1 Check Python

```powershell
py -3.12 --version          # Windows: Python 3.12.x
```

```bash
python3.12 --version        # macOS: Python 3.12.x
```

### 1.2 Ollama models (about 3.6 GB)

Start Ollama (Windows: from the Start menu, it sits in the tray; macOS: open the app, it
sits in the menu bar), then:

```
ollama pull gemma3:4b             # 3.3 GB, answers questions
ollama pull nomic-embed-text      # 0.3 GB, searches the guides
ollama list                       # both models listed
```

If `ollama` is "not recognized" / "command not found", open a new terminal window.

### 1.3 Whisper (automatic)

The speech-to-text model (faster-whisper `base.en`, about 150 MB) downloads by itself the
first time you run `mic_diagnostic.py` or the backend. **That first run needs internet**:
do it once at home (section 6).

---

## 2. Get the code

Windows (PowerShell):

```powershell
cd $HOME\Documents
git clone https://github.com/WanyayWan/Capybara_Fablab.git
cd Capybara_Fablab
git checkout alh
cd backend
py -3.12 -m venv .venv
.venv\Scripts\activate            # prompt now starts with (.venv)
pip install -r requirements.txt -r requirements-dev.txt
copy .env.example .env
```

If `activate` is blocked ("running scripts is disabled"), run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then retry.

macOS (Terminal):

```bash
cd ~/Documents
git clone https://github.com/WanyayWan/Capybara_Fablab.git
cd Capybara_Fablab
git checkout alh
cd backend
python3.12 -m venv .venv
source .venv/bin/activate         # prompt now starts with (.venv)
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
```

In every new terminal, `cd` into `backend` and activate the venv again before running
`python`.

**Check:** `pytest` prints about 290 passed.

---

## 3. Telegram (staff alerts)

Aung sends you the two values **privately**. Put them in `backend/.env` (never commit this
file):

```
TELEGRAM_BOT_TOKEN=123456789:AAHfq3-example-token-XYZ
TELEGRAM_CHAT_ID=-1001234567890
```

Alerts go to the chat `TELEGRAM_CHAT_ID` names. So the team sees them, use a **group**:

1. In Telegram, create a group with your teammates and **add the bot** (search its
   username, which Aung sends with the token).
2. **Send any message in the group.** The bot only sees chats with a message in them.
3. **Make sure the FabAI backend is not running** (it reads and consumes these updates).
4. In a browser, open this URL with the token pasted straight after `bot`: **no angle
   brackets, no spaces**:

   ```
   https://api.telegram.org/bot123456789:AAHfq3-example-token-XYZ/getUpdates
   ```

5. Find the group in the reply: `"chat":{"id":-1001234567890,"title":"...","type":"group"}`.
   Group ids are **negative**: keep the minus sign. Put it in `TELEGRAM_CHAT_ID`.

   | You see | Meaning | Fix |
   |---|---|---|
   | `{"ok":true,"result":[]}` | No message yet, or a running backend already consumed it | Stop the backend, send another message in the group, reload |
   | `{"ok":false,"error_code":404}` | Token wrong or has `<` `>` / spaces in the URL | Copy the token again |
   | `{"ok":false,"error_code":401}` | Token revoked | Ask Aung for the current token |

For a one-person test, message the bot directly instead: your own chat id is positive.
Leaving both values empty prints alerts in the backend window instead of Telegram.

**Your own bot (optional):** in Telegram, open **@BotFather**, send `/newbot`, pick a name
and a username ending in `bot`; it replies with the token. Then steps 1 to 5 above.

---

## 4. Firmware (optional: only to re-flash the board)

**Skip this section.** The board arrives flashed with the current firmware. You only need
it if the board has to be rebuilt, which needs ESP-IDF 5.5 (and MSYS2 on Windows for the
firmware unit tests).

<details>
<summary>Re-flashing steps (Windows)</summary>

1. ESP-IDF 5.5: the **ESP-IDF Tools Installer** from https://dl.espressif.com/dl/esp-idf/
   (pick 5.5, then use its "ESP-IDF 5.5 PowerShell" shortcut), or from git:

   ```powershell
   mkdir $HOME\esp; cd $HOME\esp
   git clone -b release/v5.5 --recursive https://github.com/espressif/esp-idf.git
   cd esp-idf; .\install.ps1 esp32s3
   ```

   In every new PowerShell window where you build: `. $HOME\esp\esp-idf\export.ps1`
   (note the leading `. `), then `idf.py --version` shows v5.5.
2. Plug the board in with a **data** USB cable (the **UART/COM** port on boards with two).
   Find its port: `[System.IO.Ports.SerialPort]::GetPortNames()` (e.g. `COM5`), or Device
   Manager → Ports (COM & LPT).
3. Build and flash:

   ```powershell
   cd $HOME\Documents\Capybara_Fablab\firmware
   idf.py set-target esp32s3        # first time only
   idf.py build
   idf.py -p COM5 flash monitor     # your port; Ctrl+] quits the monitor
   ```

   **Check:** the monitor prints `FABAI_READY`, `DEVICE_ID=fabai-01`,
   `PORTAL_AP=http://192.168.4.1`. "Failed to connect": hold **BOOT**, tap **RESET**,
   release **BOOT**, flash again.
4. Firmware unit tests only: install MSYS2 (https://www.msys2.org/) to `C:\msys64`; in
   "MSYS2 UCRT64" run `pacman -Syu` then `pacman -S --needed make mingw-w64-ucrt-x86_64-gcc`;
   add `C:\msys64\usr\bin;C:\msys64\ucrt64\bin` to your user PATH; then from
   **PowerShell** (not Git Bash): `make -C firmware/test`.

On macOS, follow Espressif's macOS guide for ESP-IDF 5.5 and use `/dev/cu.usbserial-*` or
`/dev/cu.usbmodem*` as the port.

</details>

---

## 5. Wi-Fi

The board has no mic or speaker: it sends button presses to the backend on your laptop,
port 8000. Both must be on the **same 2.4 GHz network**. The board does **not** do 5 GHz.

| Your laptop | Network | Backend URL for the board |
|---|---|---|
| Windows, option 1 | Laptop Mobile Hotspot named **`ALH`** with Aung's password | `http://192.168.137.1:8000` (already saved on the board) |
| Windows, option 2 | Laptop Mobile Hotspot, any name and password | Your laptop's hotspot IP (`ipconfig`, usually `192.168.137.1`) |
| macOS | Phone hotspot at 2.4 GHz; the Mac and the board join it | The Mac's IP (`ipconfig getifaddr en0`) |

### 5.1 Why not the school Wi-Fi (SUTD)

| Problem | Why it matters |
|---|---|
| SUTD Wi-Fi is WPA2-**Enterprise** (username + password) | The FabAI portal only has a password field, so the board can't join. |
| It would need your personal login | Don't store personal passwords on the device (they are saved in its flash). |
| Campus networks block device-to-device traffic | Even connected, the board couldn't reach the laptop. |

### 5.2 Windows: turn on the Mobile Hotspot

1. Keep the laptop on its normal Wi-Fi (school or home): that is its internet. The laptop
   **is** the hotspot at the same time. **Never connect the laptop to its own hotspot.**
2. Settings → Network & internet → **Mobile hotspot**:
   - Share my internet connection from: **Wi-Fi**
   - Properties → **Edit**: name and password (option 1: name **`ALH`**, Aung's password;
     option 2: anything, letters and digits only is safest); **Network band: 2.4 GHz** if
     offered
   - **Power saving: Off** (otherwise it switches off when nothing is connected)
   - Turn **Mobile hotspot: On**
3. If the hotspot page says it shares over **5 GHz** (Windows follows the band of your
   current Wi-Fi connection), make the laptop's Wi-Fi prefer 2.4 GHz:
   1. Device Manager → **Network adapters** → your Wi-Fi adapter → **Advanced** tab.
   2. Find **Preferred Band** (Intel: "Prefer 2.4GHz band"; Realtek, e.g. 8922AE WiFi 7:
      "2.4G first") → OK. Leave other settings ("Wireless Mode", "Multi-Channel
      Concurrent") alone.
   3. Disconnect and reconnect the laptop's Wi-Fi, then turn the hotspot off and on.
   4. Still 5 GHz? Last resort: on the same tab, disable 5 GHz ("5G Wireless Mode" →
      Disabled on Realtek, or "Wireless Mode" without 802.11a/ac/ax on Intel). Undo it
      after the demo (5.8). Or use a phone hotspot at 2.4 GHz instead, as on macOS (5.5),
      with the backend URL set to the laptop's IP on that hotspot from `ipconfig`.
4. **Check:** the hotspot page shows the band as 2.4 GHz.

**Option 1 (`ALH`):** plug the board into USB power and go to 5.7: it connects on its own.
**Option 2:** configure the board in its portal (5.4).

### 5.3 Firewall

**Windows:** the first time the backend starts, Windows asks whether Python may accept
connections: tick **Private and Public** and click **Allow**. If you missed it, from an
**admin** PowerShell (adjust the path to your clone):

```powershell
New-NetFirewallRule -DisplayName "FabAI backend" -Direction Inbound -Action Allow `
  -Program "$HOME\Documents\Capybara_Fablab\backend\.venv\Scripts\python.exe" -Profile Private,Public
```

**macOS:** if the firewall is on (System Settings → Network → Firewall), macOS asks
whether "python" may accept incoming network connections: click **Allow**. Missed it?
Firewall → Options → allow Python, or turn the firewall off for the demo.

### 5.4 Configure the board in its portal

Needed for Windows option 2 and for macOS.

1. Power the board. If it can't find a saved network (it knows `ALH`), it retries for
   about 30 s and then opens an open Wi-Fi network **FabAI-Setup**.
2. On your phone (or laptop): Wi-Fi → join **FabAI-Setup**. A **"no internet"** warning is
   expected: choose to stay connected.
3. Open **http://192.168.4.1** in its browser. If it won't load, **turn off mobile
   data** (the phone is sending the request over 4G/5G) and retry.
4. **Backend URL** first: `http://<laptop IP>:8000` (Windows hotspot: usually
   `http://192.168.137.1:8000`, check with `ipconfig`, adapter "Local Area Connection\*";
   macOS: the address from `ipconfig getifaddr en0`), then **Save Backend**. The page says
   "Saved".
5. Tap **Scan Wi-Fi**, pick **your hotspot**, enter its password, **Save and Connect**. The
   board joins your hotspot, and the phone may drop off FabAI-Setup: that's fine.
6. On the phone, **forget FabAI-Setup** and switch back to normal Wi-Fi or mobile data.
   A phone left on FabAI-Setup has no internet, so **Telegram alerts won't arrive**.

If "Save Backend" says **"Request failed"**, check the URL starts with `http://` and has no
spaces, then see the curl fallback (5.6).

### 5.5 macOS: phone hotspot

A Mac can't share its Wi-Fi over Wi-Fi, so the phone is the hotspot.

1. **iPhone:** Settings → Personal Hotspot → **Allow Others to Join** on, and
   **Maximize Compatibility** on (that forces 2.4 GHz). Keep that settings page open while
   the board joins. **Android:** Hotspot → Advanced / AP band → **2.4 GHz**.
2. Join the **Mac** to the phone hotspot. Its internet now comes from the phone.
3. Get the Mac's IP on it:

   ```bash
   ipconfig getifaddr en0         # e.g. 172.20.10.2 (iPhone); empty? try en1
   ```

4. Configure the board in its portal (5.4) with backend URL `http://<that IP>:8000` and
   the phone hotspot's name and password. The phone running the hotspot can't join
   FabAI-Setup at the same time, so join FabAI-Setup from the **Mac** (or a second phone)
   and open http://192.168.4.1 there. Afterwards the Mac rejoins the phone hotspot; check
   its IP (step 3) is unchanged.
5. If the hotspot restarts, the Mac's IP can change. The LED then blinks dim red: run
   step 3 again and, if the IP changed, re-save the backend URL (5.4).

### 5.6 Fallback: set the board with curl

The board is flashed with the portal fix, so **Save Backend in the portal works**. Keep this
only as a fallback if the portal page won't save (for example a board with older
firmware). From a **laptop** joined to **FabAI-Setup**:

Windows (PowerShell):

```powershell
curl.exe -s -X POST http://192.168.4.1/api/backend -H "Content-Type: application/x-www-form-urlencoded" --data-binary "url=http://192.168.137.1:8000"
curl.exe -s -X POST http://192.168.4.1/api/wifi/connect -H "Content-Type: application/x-www-form-urlencoded" --data-binary "ssid=MyHotspot&password=MyPassword"
```

macOS: the same with `curl` instead of `curl.exe`, and your Mac's IP in the URL. Use a
hotspot name and password of letters and digits only here (`&`, `%`, `+` or spaces break
this command). Then rejoin your laptop to its normal network.

### 5.7 Check

- Windows: the hotspot page shows **1 device connected** (the board). iPhone: the
  Personal Hotspot page shows 1 connection.
- Once the backend runs (section 7), the LED **stops the dim red blink** within about
  30 s. Still blinking: press the board's **RESET** button once.

### 5.8 After the hackathon

- Wi-Fi adapter → Advanced → **Preferred Band** back to **No Preference** (and 5 GHz back
  to enabled if you disabled it).
- Hotspot power saving back on, if you like.

---

## 6. Audio

Use the **laptop's built-in speakers and mic**: the audience hears the answers, and they
are the most reliable.

- **Not AirPods or other Bluetooth earbuds:** the phone grabs them back, Windows switches
  them to low "call quality" audio when the mic is on, and Bluetooth shares 2.4 GHz with
  the hotspot.
- **Output:** the laptop speakers, not an external monitor (e.g. a Legion monitor's HDMI
  output). Windows: Settings → System → Sound. macOS: System Settings → Sound.
- **Restart the backend after changing the audio device**: it opens the mic at startup.
- **macOS:** the first run asks for **microphone access** for Terminal: allow it (System
  Settings → Privacy & Security → Microphone).

Test end to end (records 5 s, plays it back, transcribes it; first run downloads Whisper):

```
cd backend                        # venv activated
python mic_diagnostic.py
```

It prints **"Speak now"**: start talking only when you see it, close to the laptop.

---

## 7. Run it

1. Close heavy apps (browsers with many tabs, Teams, Creative Cloud): the models need RAM.
2. Hotspot on (section 5). Ollama running (tray / menu bar icon).
3. Start **one** backend:

   ```
   cd backend                     # venv activated (section 2)
   python app.py
   ```

   The banner shows `FabAI backend on http://...:8000` and `staff alerts: Telegram`.
4. Power the board. Within 30 s its LED goes **off** (connected). If it keeps blinking dim
   red, press **RESET** on the board.
5. Ask one warm-up question from a second terminal (loads the models, doesn't touch the
   button's conversation):

   ```powershell
   curl.exe -s -X POST http://127.0.0.1:8000/api/ask -H "Content-Type: application/json" -d '{\"question\":\"Where is the Fab Lab?\"}'
   ```

   ```bash
   curl -s -X POST http://127.0.0.1:8000/api/ask -H "Content-Type: application/json" -d '{"question":"Where is the Fab Lab?"}'
   ```

Speech on Windows uses the built-in SAPI voice; on macOS it uses `say`. Nothing to install.

### Speaking to it

- **Hold** the BOOT button the whole time you speak, and **release** right after.
- Wait for the **blue** LED before speaking, and speak close to the laptop.
- Known mishearings on the built-in mic: "load" → "love", "cut" → "cap". Repeat, closer.

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

- [ ] `curl -s http://127.0.0.1:8000/health` (Windows: `curl.exe`) → `"status": "ok"` and
      `"ollama": true`
- [ ] The hotspot shows 1 device; the board's LED is **off** (not blinking red)
- [ ] Hold the button, say *"Where is the power button on the printer?"*, release →
      blue → yellow → green, and you hear "According to the 3D printer guide, ..."
- [ ] Hold: *"How do I use the 3D printer?"*, then hold: *"Next"* → you hear "Step 1. Press
      the power button ..."
- [ ] **Double-press** → breathing red, "I've called Fab Lab staff", Telegram message in the
      group → tap **On my way** → purple, "A staff member is on the way" → tap
      **Resolved** → LED off

The 3-minute demo is in [demo-script.md](demo-script.md); the recording checklist is in
[HANDOFF.md](HANDOFF.md#recording-checklist).

---

## 9. Windows vs macOS at a glance

| Step | Windows | macOS |
|---|---|---|
| Python | `py -3.12` | `python3.12` |
| Activate venv | `.venv\Scripts\activate` | `source .venv/bin/activate` |
| Copy env file | `copy .env.example .env` | `cp .env.example .env` |
| Ollama | ollama.com/download/windows | ollama.com/download/mac |
| Hotspot | Laptop Mobile Hotspot | Phone hotspot, 2.4 GHz |
| Backend URL | `http://192.168.137.1:8000` (`ipconfig`) | `http://<ipconfig getifaddr en0>:8000` |
| Firewall | Allow Python, Private and Public | Allow "python" incoming connections |
| Speech | Windows SAPI | `say` |
| curl | `curl.exe` | `curl` |
| ESP-IDF / MSYS2 | Not needed (re-flashing only) | Not needed |

---

## 10. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `pip install` fails building `av` / `ctranslate2` | Wrong Python (3.13/3.14) | Delete `.venv`, recreate with Python 3.12 (section 2) |
| `.venv\Scripts\activate` "running scripts is disabled" | PowerShell execution policy | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `ollama` not recognized / command not found | PATH not refreshed | New terminal window; start Ollama from the Start menu / Applications |
| `/health` says `"ollama": false` | Ollama not running | Start Ollama; `ollama list` |
| First run hangs or fails downloading Whisper | No internet | Run `python mic_diagnostic.py` once on a normal connection (1.3) |
| First answer takes 5 to 30 s | Laptop low on RAM; the OS paged the models out | Close heavy apps; start the backend 5 min early; one warm-up question |
| getUpdates shows `"result":[]` | No message sent yet, or a running backend consumed it | Stop the backend, send a message in the group, reload |
| getUpdates 404 | Brackets or spaces around the token in the URL | Token straight after `bot`: `https://api.telegram.org/bot123456789:AAH.../getUpdates` |
| Alerts go to Aung, not the team | `TELEGRAM_CHAT_ID` is Aung's chat | Group id from getUpdates (section 3), starts with `-`; restart the backend |
| Board can't see the Windows hotspot | Hotspot on 5 GHz | Preferred Band 2.4 GHz (5.2); last resort disable 5 GHz, or a phone hotspot |
| Board can't see the iPhone hotspot | Maximize Compatibility off, or the hotspot page closed | Turn it on; keep Settings → Personal Hotspot open while the board joins |
| Board can't join SUTD Wi-Fi | Enterprise login, client isolation | Use a hotspot (5.1) |
| FabAI-Setup doesn't appear | The board is still retrying its saved network (`ALH`) | Wait 30 s; press RESET; if `ALH` is actually on, it connected instead |
| 192.168.4.1 won't load on the phone | Phone uses mobile data instead of FabAI-Setup | Turn off mobile data; stay connected despite "no internet" |
| Portal "Save Backend" says "Request failed" | URL typo (must start `http://`), or older firmware without the portal fix | Fix the URL; else the curl fallback (5.6) |
| LED blinks dim red every 2 s | Offline: 3 state polls in a row failed | Backend running? Board on the hotspot? Backend URL = laptop IP? Firewall (5.3)? Then RESET the board |
| Board doesn't register within 30 s of the backend starting | Board gave up or is on the wrong network | Press the board's RESET once |
| LED blinks red on macOS after it worked | Phone hotspot restarted and the Mac got a new IP | `ipconfig getifaddr en0`; re-save the backend URL (5.4) |
| Hotspot shows 0 devices after a while | Windows hotspot power saving | Power saving **Off** (5.2) |
| No Telegram alert on the phone | Phone still on FabAI-Setup | Forget FabAI-Setup (5.4 step 6) |
| Telegram buttons do nothing | Two backends running (they fight over port 8000 and Telegram updates) | Close every `python app.py` window, start one |
| "On my way" says "no longer active" | The backend restarted after that alert | Double-press again; use the new message |
| Log shows `Telegram poll failed ... getaddrinfo failed` or `WinError 1236` | The laptop's network dropped (seen twice on 2026-09-24) | Nothing: it retries every 5 s; presses made meanwhile arrive afterwards |
| `mic_diagnostic.py` records silence | Started talking before "Speak now", or the wrong input device | Wait for "Speak now"; set the built-in mic as input (6) |
| "Sorry, I didn't catch that" | Released too early, spoke too far away, or wrong input device | Hold for the whole sentence, speak close (7) |
| Nothing heard | Output is a monitor, Bluetooth device, or muted | Set the laptop speakers as output (6); volume up |
| Audio device changed but nothing changes | The backend opened the old device at startup | Restart the backend |
| No mic at all on macOS | Terminal has no microphone permission | Privacy & Security → Microphone → allow Terminal; restart the backend |
| Audio stutters / board drops | Bluetooth and the 2.4 GHz hotspot share the radio | Don't use Bluetooth audio (6) |
| `make -C firmware/test`: "Cannot create temporary file in C:\Windows\" | Ran from Git Bash (re-flashing only) | Run it from **PowerShell** |
