const statusEl = document.querySelector("#status");
const connectBtn = document.querySelector("#connectBtn");
const ledOnBtn = document.querySelector("#ledOnBtn");
const ledOffBtn = document.querySelector("#ledOffBtn");
const logEl = document.querySelector("#log");

let port;
let reader;
let writer;
let readBuffer = "";
let keepReading = false;

function log(message) {
  const row = document.createElement("div");
  row.className = "log-entry";
  row.textContent = message;
  logEl.appendChild(row);
  logEl.scrollTop = logEl.scrollHeight;
}

function setConnected(connected) {
  statusEl.textContent = connected ? "Connected" : "Disconnected";
  statusEl.className = `status ${connected ? "connected" : "disconnected"}`;
  connectBtn.textContent = connected ? "Disconnect" : "Connect ESP32";
  ledOnBtn.disabled = !connected;
  ledOffBtn.disabled = !connected;
}

function handleLine(line) {
  const message = line.trim();
  if (!message) return;

  if (message === "BUTTON_PRESSED") {
    log(`Button pressed - ${new Date().toLocaleTimeString()}`);
  } else if (message === "LED_ON_OK") {
    log("ESP32 acknowledged LED ON");
  } else if (message === "LED_OFF_OK") {
    log("ESP32 acknowledged LED OFF");
  } else {
    log(`< ${message}`);
  }
}

async function readLoop() {
  const decoder = new TextDecoder();
  keepReading = true;

  try {
    while (port?.readable && keepReading) {
      reader = port.readable.getReader();
      try {
        while (keepReading) {
          const { value, done } = await reader.read();
          if (done) break;
          readBuffer += decoder.decode(value, { stream: true });
          const lines = readBuffer.split(/\r?\n/);
          readBuffer = lines.pop() ?? "";
          lines.forEach(handleLine);
        }
      } finally {
        reader.releaseLock();
        reader = undefined;
      }
    }
  } catch (error) {
    log(`Read stopped: ${error.message}`);
  } finally {
    if (port) {
      await disconnect();
    }
  }
}

async function connect() {
  if (!("serial" in navigator)) {
    log("Web Serial is not available. Use Chrome or Edge on localhost.");
    return;
  }

  try {
    port = await navigator.serial.requestPort();
    await port.open({ baudRate: 115200 });
    writer = port.writable.getWriter();
    setConnected(true);
    log("Connected to ESP32");
    readLoop();
  } catch (error) {
    log(`Connect failed: ${error.message}`);
    await disconnect();
  }
}

async function disconnect() {
  keepReading = false;

  try {
    if (reader) {
      await reader.cancel();
    }
  } catch (_) {
  }

  try {
    if (writer) {
      writer.releaseLock();
      writer = undefined;
    }
    if (port) {
      await port.close();
    }
  } catch (error) {
    log(`Disconnect cleanup: ${error.message}`);
  } finally {
    port = undefined;
    readBuffer = "";
    setConnected(false);
  }
}

async function sendCommand(command) {
  if (!writer) {
    log("Not connected");
    return;
  }

  const encoder = new TextEncoder();
  await writer.write(encoder.encode(`${command}\n`));
  log(`> ${command}`);
}

connectBtn.addEventListener("click", () => {
  if (port) {
    disconnect();
  } else {
    connect();
  }
});

ledOnBtn.addEventListener("click", () => sendCommand("LED_ON"));
ledOffBtn.addEventListener("click", () => sendCommand("LED_OFF"));

navigator.serial?.addEventListener("disconnect", () => {
  log("ESP32 disconnected");
  disconnect();
});

setConnected(false);
log("Open this page in Chrome or Edge, then click Connect ESP32.");
