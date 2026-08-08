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
const progressTrack = document.querySelector("#progress-track");
const progressCopy = document.querySelector("#progress-copy");
const fileResults = document.querySelector("#file-results");
const historyResults = document.querySelector("#history-results");
const computeDevice = document.querySelector("#compute-device");
const computeSave = document.querySelector("#compute-save");
const computeTest = document.querySelector("#compute-test");
const computeDiagnostic = document.querySelector("#compute-diagnostic");
const computeStatusDot = document.querySelector("#compute-status-dot");
const computeDiagnosticTitle = document.querySelector("#compute-diagnostic-title");
const computeDiagnosticDetail = document.querySelector("#compute-diagnostic-detail");
const computeDiagnosticMeta = document.querySelector("#compute-diagnostic-meta");

const activityItems = [...document.querySelectorAll(".activity-item")];
const views = {
  file: document.querySelector("#view-file"),
  camera: document.querySelector("#view-camera"),
  history: document.querySelector("#view-history"),
  settings: document.querySelector("#view-settings"),
};
const titlebarTitle = document.querySelector("#titlebar-title");
const titlebarSubtitle = document.querySelector("#titlebar-subtitle");
const statusContext = document.querySelector("#status-context");
const healthDot = document.querySelector("#health-dot");
const healthLabel = document.querySelector("#health-label");
const statusVersion = document.querySelector("#status-version");

const historyRows = document.querySelector("#history-rows");
const historyEmpty = document.querySelector("#history-empty");
const historyRefresh = document.querySelector("#history-refresh");
const historyResultTitle = document.querySelector("#history-result-title");

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

const VIEW_META = {
  file: ["Nova análise", "Envie uma imagem ou vídeo para processamento local"],
  camera: ["Câmera ao vivo", "Análise em tempo real direto do navegador"],
  history: ["Histórico", "Análises processadas nesta máquina"],
  settings: ["Ajustes", "Configurações da interface local"],
};

let selectedFile = null;
let currentJobId = null;
let previewUrl = null;
let historyPreviewUrl = null;
let cameraStream = null;
let cameraSessionId = null;
let analysisActive = false;
let analysisTimer = null;
let activeView = "file";
let computeStatusLoaded = false;
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

function setStatus(text) {
  statusContext.textContent = text;
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

/* ── Navegação entre views ─────────────────────────────── */

async function selectView(view) {
  if (!views[view]) return;
  activeView = view;
  activityItems.forEach((item) => item.classList.toggle("active", item.dataset.view === view));
  Object.entries(views).forEach(([name, section]) => { section.hidden = name !== view; });
  const [title, subtitle] = VIEW_META[view];
  titlebarTitle.textContent = title;
  titlebarSubtitle.textContent = subtitle;
  setNotice("");
  if (view !== "camera" && cameraStream) await stopCamera();
  if (view === "history") await loadHistory();
  if (view === "settings" && !computeStatusLoaded) await loadComputeStatus();
}

activityItems.forEach((item) => item.addEventListener("click", () => selectView(item.dataset.view)));

/* ── Status bar ────────────────────────────────────────── */

async function checkHealth() {
  try {
    const response = await fetch("/health");
    if (!response.ok) throw new Error();
    healthDot.className = "status-dot-mini ok";
    healthLabel.textContent = "Serviço online";
  } catch (_) {
    healthDot.className = "status-dot-mini down";
    healthLabel.textContent = "Serviço offline";
  }
}

checkHealth();
window.setInterval(checkHealth, 30000);

fetch("/version").then((response) => response.json()).then((data) => {
  statusVersion.textContent = `v${data.version}`;
}).catch(() => {});

/* ── Dispositivo de processamento ─────────────────────── */

function renderComputeStatus(payload) {
  computeStatusLoaded = true;
  const nvidia = payload.nvidia || {};
  const nvidiaOption = computeDevice.querySelector('option[value="nvidia"]');
  nvidiaOption.disabled = !nvidia.available;
  computeDevice.value = payload.preference || "auto";
  if (computeDevice.value !== payload.preference) computeDevice.value = "auto";

  computeDiagnostic.classList.toggle("available", Boolean(nvidia.available));
  computeDiagnostic.classList.toggle("unavailable", !nvidia.available);
  computeStatusDot.className = `compute-status-dot ${nvidia.available ? "available" : "unavailable"}`;
  computeDiagnosticTitle.textContent = nvidia.available
    ? "NVIDIA pronta para processamento"
    : "NVIDIA indisponível nesta máquina";
  computeDiagnosticDetail.textContent = nvidia.reason || "O teste não retornou detalhes.";

  const details = [`Em uso: ${payload.resolved_label || "CPU"}`];
  if (nvidia.torch_version) details.push(`PyTorch ${nvidia.torch_version}`);
  if (nvidia.cuda_version) details.push(`CUDA ${nvidia.cuda_version}`);
  computeDiagnosticMeta.textContent = details.join(" • ");
  computeSave.disabled = Boolean(payload.busy);
  computeSave.title = payload.busy ? "Aguarde a análise atual terminar." : "";
}

async function loadComputeStatus(refresh = false) {
  computeTest.disabled = true;
  computeDiagnosticTitle.textContent = refresh ? "Executando novo teste…" : "Verificando o hardware…";
  computeDiagnosticDetail.textContent = "Consultando o suporte CUDA instalado nesta máquina.";
  try {
    const response = await apiFetch(refresh ? "/api/v1/system/compute/test" : "/api/v1/system/compute", {
      method: refresh ? "POST" : "GET",
    });
    renderComputeStatus(await response.json());
  } catch (error) {
    computeDiagnostic.className = "compute-diagnostic unavailable";
    computeStatusDot.className = "compute-status-dot unavailable";
    computeDiagnosticTitle.textContent = "Não foi possível testar o dispositivo";
    computeDiagnosticDetail.textContent = error.message;
  } finally {
    computeTest.disabled = false;
  }
}

computeTest.addEventListener("click", () => loadComputeStatus(true));
computeSave.addEventListener("click", async () => {
  computeSave.disabled = true;
  try {
    const response = await apiFetch("/api/v1/system/compute", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ preference: computeDevice.value }),
    });
    renderComputeStatus(await response.json());
    const selectedDevice = computeDiagnosticMeta.textContent.split(" • ")[0].replace("Em uso: ", "");
    setNotice(`Dispositivo atualizado: ${selectedDevice}.`, "success");
  } catch (error) {
    setNotice(error.message, "error");
    await loadComputeStatus();
  } finally {
    if (!computeSave.title) computeSave.disabled = false;
  }
});

/* ── Processamento de arquivo ──────────────────────────── */

function updateJobAnimation(state, { progress = null }) {
  const busy = ["uploading", "queued", "running"].includes(state);
  const numericProgress = Number.isFinite(progress) ? Math.min(100, Math.max(0, progress)) : null;
  jobPanel.dataset.state = state;
  jobPanel.setAttribute("aria-busy", String(busy));

  if (numericProgress == null) {
    progressBar.className = "progress-fill indeterminate";
    progressBar.style.width = "";
    progressTrack.removeAttribute("aria-valuenow");
  } else {
    progressBar.className = "progress-fill";
    progressBar.style.width = `${numericProgress}%`;
    progressTrack.setAttribute("aria-valuenow", numericProgress.toFixed(0));
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!selectedFile) return showError("Selecione uma imagem ou vídeo antes de continuar.");
  submitButton.disabled = true;
  setNotice("");
  fileResults.hidden = true;
  jobPanel.hidden = false;
  jobTitle.textContent = selectedFile.name;
  jobState.textContent = "Enviando";
  progressCopy.textContent = "Enviando arquivo para o processamento local.";
  updateJobAnimation("uploading", { stage: "Transferindo o arquivo com segurança", step: 0 });
  setStatus(`Enviando ${selectedFile.name}…`);

  const data = new FormData();
  data.append("file", selectedFile);
  try {
    const response = await apiFetch("/api/v1/jobs", { method: "POST", body: data });
    const job = await response.json();
    currentJobId = job.id;
    await pollJob(job.id);
  } catch (error) {
    jobPanel.hidden = true;
    setStatus("Pronto");
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
      renderResult(fileResults, await resultResponse.json(), jobId);
      jobPanel.hidden = true;
      submitButton.disabled = false;
      setStatus("Análise concluída");
      return;
    }
    if (job.status === "failed") throw new Error(job.error || "O processamento falhou.");
    window.setTimeout(() => pollJob(jobId), 900);
  } catch (error) {
    setStatus("Pronto");
    showError(error.message);
  }
}

function renderJob(job) {
  const labels = { queued: "Na fila", running: "Processando", completed: "Concluído", failed: "Falhou" };
  jobState.textContent = labels[job.status] || job.status;
  const progress = Number.isFinite(job.progress) ? job.progress : null;

  if (job.status === "queued") {
    updateJobAnimation("queued", { stage: "Aguardando o processador local", step: 1 });
    progressCopy.textContent = "Upload concluído. A análise começará assim que o pipeline estiver disponível.";
    setStatus(`${job.filename} está na fila…`);
    return;
  }

  if (job.status === "completed") {
    updateJobAnimation("completed", { progress: 100, stage: "Resultados prontos para consulta", step: 3 });
    progressCopy.textContent = "Análise concluída. Mídia e resultados estruturados estão disponíveis.";
    setStatus("Análise concluída");
    return;
  }

  if (job.status === "failed") {
    updateJobAnimation("failed", { progress, stage: "O processamento foi interrompido", step: 2 });
    progressCopy.textContent = job.error || "Não foi possível concluir a análise.";
    return;
  }

  const frameDescription = job.total_frames
    ? `Analisando frame ${job.frames_processed} de ${job.total_frames}`
    : `${job.frames_processed} frames analisados`;
  updateJobAnimation("running", { progress, stage: frameDescription, step: 2 });
  progressCopy.textContent = progress == null
    ? `${job.frames_processed} frames processados. Calculando o progresso total…`
    : `${progress.toFixed(1)}% concluído • ${job.frames_processed} de ${job.total_frames || "?"} frames`;
  setStatus(progress == null
    ? `Processando ${job.filename}…`
    : `Processando ${job.filename}… ${progress.toFixed(0)}%`);
}

/* ── Resultado (arquivo e histórico compartilham o bloco) ─ */

function renderResult(root, result, jobId) {
  root.hidden = false;
  const summaries = [
    ["Frames processados", result.frames_processed],
    ["Placas consolidadas", result.vehicles.length],
    ["Tempo total", `${(result.duration_ms / 1000).toFixed(2)} s`],
    ["Schema", result.schema_version],
  ];
  root.querySelector(".js-summary-list").innerHTML = summaries
    .map(([label, value]) => `<div><dt>${label}</dt><dd>${value}</dd></div>`).join("");

  root.querySelector(".js-result-rows").innerHTML = result.vehicles.map((vehicle) => `
    <tr>
      <td>${vehicle.track_id == null ? "—" : `#${vehicle.track_id}`}</td>
      <td class="plate">${escapeHtml(vehicle.plate)}</td>
      <td>${vehicle.confidence.toFixed(1)}%</td>
      <td>${vehicle.first_frame === vehicle.last_frame ? vehicle.first_frame : `${vehicle.first_frame}–${vehicle.last_frame}`}</td>
      <td>${vehicle.occurrences}</td>
    </tr>`).join("");
  root.querySelector(".js-plate-count").textContent = `${result.vehicles.length} ${result.vehicles.length === 1 ? "resultado" : "resultados"}`;
  root.querySelector(".js-empty-table").hidden = result.vehicles.length > 0;
  renderDownloads(root, result, jobId);
  loadPreview(root, result, jobId);
}

function renderDownloads(root, result, jobId) {
  const labels = { media: "Baixar mídia", json: "Baixar JSON", csv: "Baixar CSV", text: "Baixar log" };
  const container = root.querySelector(".js-download-actions");
  container.innerHTML = "";
  Object.keys(result.artifacts).forEach((artifact) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = artifact === "media" ? "button primary small" : "button secondary small";
    button.textContent = labels[artifact] || `Baixar ${artifact}`;
    button.addEventListener("click", () => downloadArtifact(jobId, artifact, result.artifacts[artifact]));
    container.appendChild(button);
  });
}

async function artifactBlob(jobId, kind) {
  const response = await apiFetch(`/api/v1/jobs/${jobId}/artifacts/${kind}`);
  return response.blob();
}

async function downloadArtifact(jobId, kind, filename) {
  try {
    const blob = await artifactBlob(jobId, kind);
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

async function loadPreview(root, result, jobId) {
  const surface = root.querySelector(".js-preview-surface");
  const isHistory = root === historyResults;
  try {
    const blob = await artifactBlob(jobId, "media");
    if (isHistory) {
      if (historyPreviewUrl) URL.revokeObjectURL(historyPreviewUrl);
      historyPreviewUrl = URL.createObjectURL(blob);
    } else {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      previewUrl = URL.createObjectURL(blob);
    }
    const url = isHistory ? historyPreviewUrl : previewUrl;
    const isImage = result.source_type === "image";
    if (isImage) {
      surface.innerHTML = `<img src="${url}" alt="Resultado anotado da análise">`;
      return;
    }

    surface.innerHTML = "";
    const video = document.createElement("video");
    video.src = url;
    video.controls = true;
    video.preload = "metadata";
    video.playsInline = true;
    video.setAttribute("aria-label", "Resultado anotado da análise");
    video.addEventListener("error", () => {
      surface.innerHTML = "<p>O navegador não conseguiu reproduzir esta mídia. Use o botão de download ou processe novamente para gerar H.264.</p>";
    }, { once: true });
    surface.appendChild(video);
  } catch (_) {
    surface.innerHTML = "<p>A prévia não pôde ser carregada. Use o botão de download.</p>";
  }
}

/* ── Histórico ─────────────────────────────────────────── */

const HISTORY_STATUS = { queued: "Na fila", running: "Processando", completed: "Concluído", failed: "Falhou" };

function formatJobDate(iso) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

async function loadHistory() {
  historyRows.innerHTML = "";
  historyEmpty.textContent = "Carregando…";
  historyEmpty.hidden = false;
  try {
    const response = await apiFetch("/api/v1/jobs");
    const jobs = await response.json();
    historyEmpty.hidden = jobs.length > 0;
    historyEmpty.textContent = "Nenhuma análise encontrada.";
    historyRows.innerHTML = jobs.map((job) => {
      const progress = job.status === "completed" ? "100%" : (job.progress == null ? "—" : `${job.progress.toFixed(0)}%`);
      const openButton = job.status === "completed"
        ? `<button class="button secondary small" type="button" data-open-job="${job.id}" data-filename="${escapeHtml(job.filename)}">Abrir</button>`
        : "";
      return `
        <tr>
          <td>${formatJobDate(job.created_at)}</td>
          <td>${escapeHtml(job.filename)}</td>
          <td data-status="${job.status}">${HISTORY_STATUS[job.status] || job.status}</td>
          <td>${progress}</td>
          <td>${openButton}</td>
        </tr>`;
    }).join("");
  } catch (error) {
    historyEmpty.textContent = error.message;
  }
}

historyRows.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-open-job]");
  if (!button) return;
  button.disabled = true;
  try {
    const response = await apiFetch(`/api/v1/jobs/${button.dataset.openJob}/result`);
    historyResultTitle.textContent = button.dataset.filename;
    renderResult(historyResults, await response.json(), button.dataset.openJob);
    setStatus(`Visualizando ${button.dataset.filename}`);
  } catch (error) {
    showError(error.message);
  } finally {
    button.disabled = false;
  }
});

historyRefresh.addEventListener("click", loadHistory);

/* ── Câmera ao vivo ────────────────────────────────────── */

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
    setStatus("Câmera ativa");
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
  setStatus("Preparando análise em tempo real…");
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
    setStatus("Análise de câmera ativa");
    analyzeNextFrame();
  } catch (error) {
    analysisStartButton.disabled = false;
    cameraStartButton.disabled = false;
    cameraStateLabel.textContent = "Não foi possível iniciar a análise.";
    setStatus("Pronto");
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
  if (activeView === "camera") setStatus(cameraStream ? "Câmera ativa" : "Pronto");
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
  if (activeView === "camera") setStatus("Pronto");
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
