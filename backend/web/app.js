const clientId = crypto.randomUUID();
const statusEl = document.querySelector("#status");
const messageEl = document.querySelector("#message");
const enableBtn = document.querySelector("#enable");
const speakBtn = document.querySelector("#speak");
const meter = document.querySelector("#meter span");
const meterWrap = document.querySelector("#meter");
const transcript = document.querySelector("#transcript");
const phone = document.querySelector("#phone");
const device = document.querySelector("#device");
let socket, stream, recorder, analyser, audioContext, sessionId;

function setState(state, text) {
  statusEl.textContent = state;
  statusEl.className = "status " + (state === "READY" ? "ready" : state === "LISTENING" ? "active" : "offline");
  messageEl.textContent = text;
}

function animateMeter() {
  if (!analyser) return;
  const data = new Uint8Array(analyser.fftSize);
  analyser.getByteTimeDomainData(data);
  const level = data.reduce((sum, value) => sum + Math.abs(value - 128), 0) / data.length;
  meter.style.width = Math.min(100, level * 4) + "%";
  if (recorder?.state === "recording") requestAnimationFrame(animateMeter);
}

async function enableVoice() {
  setState("CONNECTING", "Requesting microphone permission...");
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioContext = new AudioContext();
    analyser = audioContext.createAnalyser();
    audioContext.createMediaStreamSource(stream).connect(analyser);
    const scheme = location.protocol === "https:" ? "wss" : "ws";
    socket = new WebSocket(scheme + "://" + location.host + "/ws?client_id=" + encodeURIComponent(clientId));
    socket.onopen = () => socket.send(JSON.stringify({ type: "ready", client_id: clientId }));
    socket.onmessage = event => handleEvent(JSON.parse(event.data));
    socket.onclose = () => { phone.textContent = "Offline"; setState("DISCONNECTED", "Connection lost. Enable voice again."); };
    enableBtn.classList.add("hidden");
    speakBtn.classList.remove("hidden");
  } catch (error) {
    setState("ERROR", "Microphone unavailable: " + error.message);
  }
}

function handleEvent(event) {
  if (event.type === "ready") {
    phone.textContent = "Connected";
    setState("READY", "Ready to listen.");
  } else if (event.type === "start_listening") {
    device.textContent = event.device_id;
    sessionId = event.session_id;
    startRecording();
  } else if (event.type === "state" && event.state === "TRANSCRIBING") {
    setState("TRANSCRIBING", "Transcribing your request...");
  } else if (event.type === "transcription") {
    transcript.textContent = '"' + event.text + '"';
    setState("READY", "Ready to listen.");
  } else if (event.type === "error") {
    setState("ERROR", event.message);
  }
}

function startRecording() {
  if (!stream || recorder?.state === "recording") {
    speakBtn.classList.remove("hidden");
    setState("READY", "Tap to Speak when ready.");
    return;
  }
  const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "";
  recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
  const chunks = [];
  recorder.ondataavailable = event => { if (event.data.size) chunks.push(event.data); };
  recorder.onstop = async () => {
    meterWrap.classList.add("hidden");
    setState("UPLOADING", "Sending audio to FabAI...");
    const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
    const form = new FormData();
    form.append("audio", blob, "request.webm");
    form.append("client_id", clientId);
    form.append("session_id", sessionId || "");
    try {
      const response = await fetch("/api/phone/audio", { method: "POST", body: form });
      if (!response.ok) throw Error("Audio upload failed.");
    } catch (error) {
      setState("ERROR", error.message);
    }
  };
  setState("LISTENING", "Speak now...");
  meterWrap.classList.remove("hidden");
  recorder.start();
  animateMeter();
  setTimeout(() => recorder?.state === "recording" && recorder.stop(), 5000);
}

enableBtn.addEventListener("click", enableVoice);
speakBtn.addEventListener("click", startRecording);
