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

let selectedFile = null;
let currentJobId = null;
let previewUrl = null;

apiKeyInput.value = sessionStorage.getItem("anpr-api-key") || "";
apiKeyInput.addEventListener("change", () => sessionStorage.setItem("anpr-api-key", apiKeyInput.value));

function authHeaders() {
  return apiKeyInput.value ? { "X-API-Key": apiKeyInput.value } : {};
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / (1024 ** index)).toFixed(index ? 1 : 0)} ${units[index]}`;
}

function setFile(file) {
  selectedFile = file || null;
  selection.textContent = file ? `${file.name} • ${formatBytes(file.size)}` : "Nenhum arquivo selecionado";
  notice.hidden = true;
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

function showError(message) {
  notice.textContent = message;
  notice.hidden = false;
  submitButton.disabled = false;
}

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

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!selectedFile) return showError("Selecione uma imagem ou vídeo antes de continuar.");
  submitButton.disabled = true;
  notice.hidden = true;
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

function escapeHtml(value) {
  const span = document.createElement("span");
  span.textContent = String(value);
  return span.innerHTML;
}

fetch("/version").then((response) => response.json()).then((data) => {
  document.querySelector("#app-version").textContent = `v${data.version}`;
}).catch(() => {});
