const form = document.querySelector("#upload-form");
const input = document.querySelector("#file-input");
const dropzone = document.querySelector("#dropzone");
const selection = document.querySelector("#file-selection");
const apiKeyInput = document.querySelector("#api-key");
const submitButton = document.querySelector("#submit-button");
const notice = document.querySelector("#notice");
const jobPanel = document.querySelector("#job-panel");
const jobTitle = document.querySelector("#job-title");
const jobState = document.querySelector("#job-state");
const progressBar = document.querySelector("#progress-bar");
const progressCopy = document.querySelector("#progress-copy");
const results = document.querySelector("#results");
const filePanel = document.querySelector("#file-panel");
const cameraPanel = document.querySelector("#camera-panel");
const modeTabs = [...document.querySelectorAll(".mode-tab")];

const cameraSelect = document.querySelector("#camera-select");
const cameraVideo = document.querySelector("#camera-video");
const cameraCanvas = document.querySelector("#camera-canvas");
const cameraOutput = document.querySelector("#camera-output");
const cameraPlaceholder = document.querySelector("#camera-placeholder");
const analysisPlaceholder = document.querySelector("#analysis-placeholder");
const cameraStartButton = document.querySelector("#camera-start");
const analysisStartButton = document.querySelector("#analysis-start");
const cameraStopButton = document.querySelector("#camera-stop");
const cameraStateLabel = document.querySelector("#camera-state");
const analysisDot = document.querySelector("#analysis-dot");

let selectedFile = null;
let currentJobId = null;
let previewUrl = null;
let fileResultReady = false;
let cameraStream = null;
let cameraSessionId = null;
let analysisActive = false;
let analysisTimer = null;
const liveReadings = new Map();

try {
  apiKeyInput.value = sessionStorage.getItem("anpr-api-key") || "";
} catch (_) { /* armazenamento indisponível */ }

apiKeyInput.addEventListener("change", () => {
  try { sessionStorage.setItem("anpr-api-key", apiKeyInput.value); } catch (_) { /* aba privada */ }
});

function authHeaders() {
  return apiKeyInput.value ? { "X-API-Key": apiKeyInput.value } : {};
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / (1024 ** index)).toFixed(index ? 1 : 0)} ${units[index]}`;
}

function setNotice(message, kind = "error") {
  notice.textContent = message;
  notice.className = `notice ${kind}`;
  notice.hidden = !message;
}

function showError(message) {
  setNotice(message, "error");
  submitButton.disabled = false;
}

function setFile(file) {
  selectedFile = file || null;
  selection.textContent = file ? `${file.name} • ${formatBytes(file.size)}` : "Nenhum arquivo selecionado";
  setNotice("");
}

input.addEventListener("change", () => setFile(input.files[0]));
["dragenter", "dragover"].forEach((name) => dropzone.addEventListener(name, (event) => {
  event.preventDefault();
  dropzone.classList.add("dragging");
}));
["dragleave", "drop"].forEach((name) => dropzone.addEventListener(name, (event) => {
  event.preventDefault();
  dropzone.classList.remove("dragging");
}));
dropzone.addEventListener("drop", (event) => setFile(event.dataTransfer.files[0]));

async function apiFetch(url, options = {}) {
  const response = await fetch(url, { ...options, headers: { ...authHeaders(), ...(options.headers || {}) } });
  if (!response.ok) {
    let message = `Falha na solicitação (${response.status}).`;
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch (_) { /* resposta sem JSON */ }
    throw new Error(message);
  }
  return response;
}

async function selectMode(mode) {
  const useCamera = mode === "camera";
  modeTabs.forEach((tab) => {
    const active = tab.dataset.mode === mode;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", String(active));
    tab.tabIndex = active ? 0 : -1;
  });
  filePanel.hidden = useCamera;
  cameraPanel.hidden = !useCamera;
  results.hidden = useCamera || !fileResultReady;
  setNotice("");
  if (!useCamera && cameraStream) await stopCamera();
}

modeTabs.forEach((tab) => tab.addEventListener("click", () => selectMode(tab.dataset.mode)));
document.querySelectorAll("[data-open-camera]").forEach((link) => link.addEventListener("click", async (event) => {
  event.preventDefault();
  await selectMode("camera");
  document.querySelector("#processar").scrollIntoView({ behavior: "smooth", block: "start" });
}));

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!selectedFile) return showError("Selecione uma imagem ou vídeo antes de continuar.");
  submitButton.disabled = true;
  setNotice("");
  fileResultReady = false;
  results.hidden = true;
  jobPanel.hidden = false;
  jobTitle.textContent = selectedFile.name;
  jobState.textContent = "Enviando";
  progressCopy.textContent = "Enviando arquivo para o processamento local.";
  progressBar.className = "indeterminate";
  progressBar.style.width = "35%";

  const data = new FormData();
  data.append("file", selectedFile);
  try {
    const response = await apiFetch("/api/v1/jobs", { method: "POST", body: data });
    const job = await response.json();
    currentJobId = job.id;
    await pollJob(job.id);
  } catch (error) {
    jobPanel.hidden = true;
    showError(error.message);
  }
});

async function pollJob(jobId) {
  try {
    const response = await apiFetch(`/api/v1/jobs/${jobId}`);
    const job = await response.json();
    renderJob(job);
    if (job.status === "completed") {
      const resultResponse = await apiFetch(job.result_url);
      renderResult(await resultResponse.json());
      submitButton.disabled = false;
      return;
    }
    if (job.status === "failed") throw new Error(job.error || "O processamento falhou.");
    window.setTimeout(() => pollJob(jobId), 900);
  } catch (error) {
    showError(error.message);
  }
}

function renderJob(job) {
  const labels = { queued: "Na fila", running: "Processando", completed: "Concluído", failed: "Falhou" };
  jobState.textContent = labels[job.status] || job.status;
  if (job.progress == null) {
    progressBar.className = "indeterminate";
    progressBar.style.width = "35%";
    progressCopy.textContent = `${job.frames_processed} frames processados.`;
  } else {
    progressBar.className = "";
    progressBar.style.width = `${job.progress}%`;
    progressCopy.textContent = job.status === "completed"
      ? "Arquivos e resultados estruturados estão prontos."
      : `${job.progress.toFixed(1)}% concluído • ${job.frames_processed} de ${job.total_frames || "?"} frames`;
  }
}

function renderResult(result) {
  fileResultReady = true;
  results.hidden = false;
  const summaries = [
    ["Frames processados", result.frames_processed],
    ["Placas consolidadas", result.vehicles.length],
    ["Tempo total", `${(result.duration_ms / 1000).toFixed(2)} s`],
    ["Schema", result.schema_version],
  ];
  document.querySelector("#summary-list").innerHTML = summaries
    .map(([label, value]) => `<div><dt>${label}</dt><dd>${value}</dd></div>`).join("");

  const rows = document.querySelector("#result-rows");
  rows.innerHTML = result.vehicles.map((vehicle) => `
    <tr>
      <td>${vehicle.track_id == null ? "—" : `#${vehicle.track_id}`}</td>
      <td class="plate">${escapeHtml(vehicle.plate)}</td>
      <td>${vehicle.confidence.toFixed(1)}%</td>
      <td>${vehicle.first_frame === vehicle.last_frame ? vehicle.first_frame : `${vehicle.first_frame}–${vehicle.last_frame}`}</td>
      <td>${vehicle.occurrences}</td>
    </tr>`).join("");
  document.querySelector("#plate-count").textContent = `${result.vehicles.length} ${result.vehicles.length === 1 ? "resultado" : "resultados"}`;
  document.querySelector("#empty-table").hidden = result.vehicles.length > 0;
  renderDownloads(result);
  loadPreview(result);
  results.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderDownloads(result) {
  const labels = { media: "Baixar mídia", json: "Baixar JSON", csv: "Baixar CSV", text: "Baixar log" };
  const container = document.querySelector("#download-actions");
  container.innerHTML = "";
  Object.keys(result.artifacts).forEach((artifact) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = artifact === "media" ? "button primary" : "button secondary";
    button.textContent = labels[artifact] || `Baixar ${artifact}`;
    button.addEventListener("click", () => downloadArtifact(artifact, result.artifacts[artifact]));
    container.appendChild(button);
  });
}

async function artifactBlob(kind) {
  const response = await apiFetch(`/api/v1/jobs/${currentJobId}/artifacts/${kind}`);
  return response.blob();
}

async function downloadArtifact(kind, filename) {
  try {
    const blob = await artifactBlob(kind);
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    showError(error.message);
  }
}

async function loadPreview(result) {
  const surface = document.querySelector("#preview-surface");
  try {
    const blob = await artifactBlob("media");
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = URL.createObjectURL(blob);
    const isImage = result.source_type === "image";
    surface.innerHTML = isImage
      ? `<img src="${previewUrl}" alt="Resultado anotado da análise">`
      : `<video src="${previewUrl}" controls aria-label="Resultado anotado da análise"></video>`;
  } catch (_) {
    surface.innerHTML = "<p>A prévia não pôde ser carregada. Use o botão de download.</p>";
  }
}

function cameraErrorMessage(error) {
  if (error?.name === "NotAllowedError") return "Permissão da câmera negada. Autorize o acesso nas configurações do navegador.";
  if (error?.name === "NotFoundError") return "Nenhuma câmera foi encontrada nesta máquina.";
  if (error?.name === "NotReadableError") return "A câmera está sendo usada por outro aplicativo.";
  return error?.message || "Não foi possível acessar a câmera.";
}

async function activateCamera(deviceId = "") {
  if (!navigator.mediaDevices?.getUserMedia) {
    showError("Este navegador não oferece acesso à câmera. Use localhost em um navegador atualizado.");
    return;
  }
  cameraStartButton.disabled = true;
  setNotice("");
  cameraStateLabel.textContent = "Solicitando acesso à câmera…";
  try {
    if (analysisActive) await stopAnalysis();
    if (cameraStream) cameraStream.getTracks().forEach((track) => track.stop());
    const video = deviceId
      ? { deviceId: { exact: deviceId }, width: { ideal: 1280 }, height: { ideal: 720 } }
      : { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } };
    cameraStream = await navigator.mediaDevices.getUserMedia({ video, audio: false });
    cameraVideo.srcObject = cameraStream;
    await cameraVideo.play();
    cameraPlaceholder.hidden = true;
    cameraStartButton.textContent = "Reiniciar câmera";
    analysisStartButton.disabled = false;
    cameraStopButton.disabled = false;
    cameraStateLabel.textContent = "Câmera pronta. Inicie a análise quando desejar.";
    await populateCameraDevices();
  } catch (error) {
    cameraStream = null;
    cameraPlaceholder.hidden = false;
    analysisStartButton.disabled = true;
    cameraStopButton.disabled = true;
    cameraStateLabel.textContent = "Câmera indisponível.";
    showError(cameraErrorMessage(error));
  } finally {
    cameraStartButton.disabled = false;
  }
}

async function populateCameraDevices() {
  const devices = (await navigator.mediaDevices.enumerateDevices()).filter((device) => device.kind === "videoinput");
  const activeDeviceId = cameraStream?.getVideoTracks()[0]?.getSettings().deviceId || "";
  cameraSelect.innerHTML = "";
  devices.forEach((device, index) => {
    const option = document.createElement("option");
    option.value = device.deviceId;
    option.textContent = device.label || `Câmera ${index + 1}`;
    cameraSelect.appendChild(option);
  });
  if (activeDeviceId) cameraSelect.value = activeDeviceId;
  cameraSelect.disabled = devices.length < 2;
}

function resetLiveSession() {
  liveReadings.clear();
  document.querySelector("#live-frame").textContent = "0";
  document.querySelector("#live-vehicles").textContent = "0";
  document.querySelector("#live-plates-count").textContent = "0";
  document.querySelector("#live-fps").textContent = "—";
  document.querySelector("#live-latency").textContent = "—";
  document.querySelector("#live-result-rows").innerHTML = "";
  document.querySelector("#live-reading-count").textContent = "0 placas";
  document.querySelector("#live-empty-table").hidden = false;
}

async function startAnalysis() {
  if (!cameraStream) await activateCamera();
  if (!cameraStream || analysisActive) return;

  analysisStartButton.disabled = true;
  cameraStartButton.disabled = true;
  setNotice("Preparando os modelos para a análise em tempo real…", "info");
  cameraStateLabel.textContent = "Preparando modelos…";
  resetLiveSession();
  try {
    const response = await apiFetch("/api/v1/realtime/sessions", { method: "POST" });
    const session = await response.json();
    cameraSessionId = session.id;
    analysisActive = true;
    analysisDot.classList.add("active");
    analysisStartButton.textContent = "Analisando";
    cameraStopButton.disabled = false;
    setNotice("Análise ativa. Nenhum frame da câmera será salvo no disco.", "success");
    cameraStateLabel.textContent = "Analisando frames sequencialmente…";
    analyzeNextFrame();
  } catch (error) {
    analysisStartButton.disabled = false;
    cameraStartButton.disabled = false;
    cameraStateLabel.textContent = "Não foi possível iniciar a análise.";
    showError(error.message);
  }
}

function captureCameraFrame() {
  return new Promise((resolve, reject) => {
    if (cameraVideo.readyState < HTMLMediaElement.HAVE_CURRENT_DATA || !cameraVideo.videoWidth) {
      reject(new Error("A câmera ainda não entregou um frame válido."));
      return;
    }
    const scale = Math.min(1, 1280 / Math.max(cameraVideo.videoWidth, cameraVideo.videoHeight));
    cameraCanvas.width = Math.max(1, Math.round(cameraVideo.videoWidth * scale));
    cameraCanvas.height = Math.max(1, Math.round(cameraVideo.videoHeight * scale));
    const context = cameraCanvas.getContext("2d", { alpha: false });
    context.drawImage(cameraVideo, 0, 0, cameraCanvas.width, cameraCanvas.height);
    cameraCanvas.toBlob((blob) => {
      if (blob) resolve(blob);
      else reject(new Error("Não foi possível capturar o frame da câmera."));
    }, "image/jpeg", 0.82);
  });
}

async function analyzeNextFrame() {
  if (!analysisActive || !cameraSessionId) return;
  try {
    const blob = await captureCameraFrame();
    const data = new FormData();
    data.append("file", blob, "camera-frame.jpg");
    const response = await apiFetch(`/api/v1/realtime/sessions/${cameraSessionId}/frames`, {
      method: "POST",
      body: data,
    });
    renderLiveFrame(await response.json());
  } catch (error) {
    if (analysisActive) {
      showError(error.message);
      await stopAnalysis();
    }
    return;
  }
  if (analysisActive) analysisTimer = window.setTimeout(analyzeNextFrame, 120);
}

function renderLiveFrame(payload) {
  cameraOutput.src = payload.annotated_image;
  cameraOutput.hidden = false;
  analysisPlaceholder.hidden = true;
  document.querySelector("#live-frame").textContent = payload.frame;
  document.querySelector("#live-vehicles").textContent = payload.vehicles;
  document.querySelector("#live-plates-count").textContent = payload.plates.length;
  document.querySelector("#live-fps").textContent = `${payload.inference_fps.toFixed(1)} FPS`;
  document.querySelector("#live-latency").textContent = `${payload.elapsed_ms.toFixed(0)} ms`;

  payload.plates.forEach((plate) => {
    const key = plate.text;
    const previous = liveReadings.get(key);
    liveReadings.set(key, {
      trackId: plate.track_id,
      text: key,
      confidence: Math.max(plate.confidence, previous?.confidence || 0),
      firstFrame: previous?.firstFrame || payload.frame,
      lastFrame: payload.frame,
      occurrences: (previous?.occurrences || 0) + 1,
    });
  });
  renderLiveReadings();

  const best = [...liveReadings.values()].sort((a, b) => b.occurrences - a.occurrences || b.confidence - a.confidence)[0];
  cameraStateLabel.textContent = best
    ? `Leitura atual: ${best.text} • ${best.confidence.toFixed(1)}%`
    : "Analisando — mantenha o veículo estável no enquadramento.";
}

function renderLiveReadings() {
  const readings = [...liveReadings.values()].sort((a, b) => b.lastFrame - a.lastFrame || b.confidence - a.confidence);
  document.querySelector("#live-result-rows").innerHTML = readings.map((reading) => `
    <tr>
      <td>${reading.trackId == null ? "—" : `#${reading.trackId}`}</td>
      <td class="plate">${escapeHtml(reading.text)}</td>
      <td>${reading.confidence.toFixed(1)}%</td>
      <td>${reading.firstFrame}</td>
      <td>${reading.lastFrame}</td>
      <td>${reading.occurrences}</td>
    </tr>`).join("");
  document.querySelector("#live-reading-count").textContent = `${readings.length} ${readings.length === 1 ? "placa" : "placas"}`;
  document.querySelector("#live-empty-table").hidden = readings.length > 0;
}

async function stopAnalysis(notifyServer = true) {
  analysisActive = false;
  if (analysisTimer) window.clearTimeout(analysisTimer);
  analysisTimer = null;
  const sessionId = cameraSessionId;
  cameraSessionId = null;
  analysisDot.classList.remove("active");
  analysisStartButton.textContent = "Iniciar análise";
  analysisStartButton.disabled = !cameraStream;
  cameraStartButton.disabled = false;
  if (notifyServer && sessionId) {
    try { await apiFetch(`/api/v1/realtime/sessions/${sessionId}`, { method: "DELETE" }); } catch (_) { /* sessão já expirada */ }
  }
  if (cameraStream) cameraStateLabel.textContent = "Análise pausada. A câmera continua disponível.";
}

async function stopCamera() {
  await stopAnalysis();
  if (cameraStream) cameraStream.getTracks().forEach((track) => track.stop());
  cameraStream = null;
  cameraVideo.srcObject = null;
  cameraPlaceholder.hidden = false;
  cameraOutput.hidden = true;
  cameraOutput.removeAttribute("src");
  analysisPlaceholder.hidden = false;
  cameraSelect.disabled = true;
  cameraSelect.innerHTML = '<option value="">Câmera padrão</option>';
  cameraStartButton.textContent = "Ativar câmera";
  analysisStartButton.disabled = true;
  cameraStopButton.disabled = true;
  cameraStateLabel.textContent = "Aguardando permissão da câmera.";
  resetLiveSession();
}

cameraStartButton.addEventListener("click", () => activateCamera(cameraSelect.value));
analysisStartButton.addEventListener("click", startAnalysis);
cameraStopButton.addEventListener("click", stopCamera);
cameraSelect.addEventListener("change", () => activateCamera(cameraSelect.value));

window.addEventListener("beforeunload", () => {
  if (cameraSessionId) {
    fetch(`/api/v1/realtime/sessions/${cameraSessionId}`, {
      method: "DELETE",
      headers: authHeaders(),
      keepalive: true,
    }).catch(() => {});
  }
  if (cameraStream) cameraStream.getTracks().forEach((track) => track.stop());
});

function escapeHtml(value) {
  const span = document.createElement("span");
  span.textContent = String(value);
  return span.innerHTML;
}

fetch("/version").then((response) => response.json()).then((data) => {
  document.querySelector("#app-version").textContent = `v${data.version}`;
}).catch(() => {});
