const FALLBACK_COLUMNS = ["nao_postados", "a_postar", "programados", "postados"];
const STAGE_LABELS = {
  waiting: "Na fila",
  preparing_source: "Preparando fonte",
  extracting_audio: "Extraindo áudio",
  transcribing: "Transcrevendo",
  analyzing_context: "Analisando contexto",
  cutting: "Gerando cortes",
  subtitling: "Legendando",
  thumbnail: "Criando thumbnail",
  assembling_final_video: "Montando vídeo final",
  done: "Concluído",
  error: "Erro"
};
const STAGE_ORDER = [
  "waiting",
  "preparing_source",
  "extracting_audio",
  "transcribing",
  "analyzing_context",
  "cutting",
  "subtitling",
  "thumbnail",
  "assembling_final_video",
  "done"
];

const clipCache = {};
let editingClipId = null;

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatSeconds(value) {
  const seconds = Number(value ?? 0);
  return `${seconds.toFixed(1)}s`;
}

function formatDate(value) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("pt-BR");
}

function truncateText(value, maxLength = 180) {
  const text = String(value ?? "");
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength - 1)}…`;
}

function stageLabel(stage) {
  return STAGE_LABELS[stage] || stage || "Na fila";
}

function statusClass(status) {
  if (status === "completed" || status === "published") {
    return "completed";
  }
  if (status === "error" || status === "failed") {
    return "error";
  }
  if (status === "running") {
    return "running";
  }
  return "neutral";
}

function columnLabel(column) {
  const labels = {
    nao_postados: "Não postados",
    a_postar: "A postar",
    programados: "Programados",
    postados: "Postados"
  };
  return labels[column] || column;
}

function cutStyleLabel(style) {
  const labels = {
    viral: "Viral",
    engracado: "Engraçado",
    chocante: "Chocante",
    informativo: "Informativo"
  };
  return labels[style] || style;
}

function progressPercent(stage, status) {
  if (status === "completed") {
    return 100;
  }
  if (status === "error") {
    return 100;
  }
  const stageIndex = STAGE_ORDER.indexOf(stage || "waiting");
  if (stageIndex === -1) {
    return 8;
  }
  return Math.max(8, Math.round(((stageIndex + 1) / STAGE_ORDER.length) * 100));
}

function jobCanBeDeleted(job) {
  return job.status !== "running";
}

function buildJobActions(job) {
  const actions = [];
  if (job.final_download_url) {
    actions.push(
      `<a class="inline-action" href="${job.final_download_url}">Baixar vídeo final</a>`
    );
  }
  if (job.source_download_url) {
    actions.push(
      `<a class="inline-action" href="${job.source_download_url}">Baixar original</a>`
    );
  }
  return actions.join("");
}

function renderJobCard(job) {
  const progress = progressPercent(job.stage, job.status);
  const error = job.error_message
    ? `<p class="error-text">${escapeHtml(job.error_message)}</p>`
    : "";
  const finalPreview = job.final_thumbnail_url
    ? `<img class="thumb" src="${job.final_thumbnail_url}" alt="Thumbnail do vídeo final ${escapeHtml(job.final_title || job.source_title || "job")}">`
    : "";
  const finalTitle = job.final_title
    ? `<p class="job-meta">Vídeo final: ${escapeHtml(job.final_title)}</p>`
    : "";

  return `
    <article class="job-card">
      ${finalPreview}
      <div class="clip-footer">
        <span class="status-pill ${statusClass(job.status)}">${escapeHtml(stageLabel(job.stage))}</span>
        <span class="pill neutral">${escapeHtml(cutStyleLabel(job.cut_style))}</span>
      </div>
      <h4 class="job-title">${escapeHtml(job.source_title || job.source_value || "Novo job")}</h4>
      <p class="job-meta">Criador: ${escapeHtml(job.creator_name)}</p>
      <p class="job-meta">Fonte: ${escapeHtml(job.source_type)} | Clips: ${escapeHtml(job.clips_count)}</p>
      ${finalTitle}
      <div class="progress-track">
        <div class="progress-fill" style="width:${progress}%"></div>
      </div>
      <p class="job-meta">${escapeHtml(job.message || "Aguardando processamento.")}</p>
      <p class="job-meta">Criado em ${escapeHtml(formatDate(job.created_at))}</p>
      ${error}
      <div class="clip-actions">
        ${buildJobActions(job)}
      </div>
    </article>
  `;
}

function buildCompactJobActions(job) {
  const actions = [];
  if (job.final_download_url) {
    actions.push(
      `<a class="inline-action" href="${job.final_download_url}">Video final</a>`
    );
  }
  if (job.source_download_url) {
    actions.push(
      `<a class="inline-action" href="${job.source_download_url}">Original</a>`
    );
  }
  return actions.join("");
}

function renderCompactJobCard(job) {
  const progress = progressPercent(job.stage, job.status);
  const canDelete = jobCanBeDeleted(job);
  const error = job.error_message
    ? `
      <details class="job-error-box">
        <summary>Ver erro</summary>
        <pre class="job-error-text">${escapeHtml(job.error_message)}</pre>
      </details>
    `
    : "";
  const finalPreview = job.final_thumbnail_url
    ? `
      <div class="job-media">
        <img class="job-thumb" src="${job.final_thumbnail_url}" alt="Thumbnail do video final ${escapeHtml(job.final_title || job.source_title || "job")}">
      </div>
    `
    : "";
  const finalTitle = job.final_title
    ? `<p class="job-meta">Video final: ${escapeHtml(job.final_title)}</p>`
    : "";
  const message = escapeHtml(job.message || "Aguardando processamento.");
  const deleteButtonLabel = canDelete ? "Remover" : "Em execucao";
  const deleteButtonAttr = canDelete ? "" : "disabled";

  return `
    <article class="job-card job-card-compact">
      <div class="job-topbar">
        <div class="job-badges">
          <span class="status-pill ${statusClass(job.status)}">${escapeHtml(stageLabel(job.stage))}</span>
          <span class="pill neutral">${escapeHtml(cutStyleLabel(job.cut_style))}</span>
        </div>
        <button class="job-remove-button" type="button" onclick="deleteJob('${job.id}')" ${deleteButtonAttr}>${deleteButtonLabel}</button>
      </div>
      <div class="job-body">
        ${finalPreview}
        <div class="job-content">
          <h4 class="job-title">${escapeHtml(job.source_title || job.source_value || "Novo job")}</h4>
          <p class="job-meta">Criador: ${escapeHtml(job.creator_name)}</p>
          <p class="job-meta">Fonte: ${escapeHtml(job.source_type)} | Clips: ${escapeHtml(job.clips_count)}</p>
          ${finalTitle}
          <div class="progress-track compact">
            <div class="progress-fill" style="width:${progress}%"></div>
          </div>
          <p class="job-message">${message}</p>
          <p class="job-meta">Criado em ${escapeHtml(formatDate(job.created_at))}</p>
          ${error}
        </div>
      </div>
      <div class="job-footer">
        <span class="job-chip">Job ${escapeHtml(job.id.slice(0, 8))}</span>
        <div class="job-actions">
          ${buildCompactJobActions(job)}
        </div>
      </div>
    </article>
  `;
}

function renderClipCard(item) {
  clipCache[item.id] = item;

  const thumbnail = item.thumbnail_url
    ? `<img class="thumb" src="${item.thumbnail_url}" alt="Thumbnail do corte ${escapeHtml(item.title)}">`
    : "";
  const noteBox = item.notes
    ? `<div class="note-box">${escapeHtml(truncateText(item.notes, 220))}</div>`
    : "";

  const actions = [];
  if (item.clip_url) {
    actions.push(`<a class="clip-action secondary" href="${item.clip_url}" target="_blank" rel="noreferrer">Ver vídeo</a>`);
  }
  if (item.clip_download_url) {
    actions.push(`<a class="clip-action secondary" href="${item.clip_download_url}">Baixar corte</a>`);
  }
  if (item.source_download_url) {
    actions.push(`<a class="clip-action secondary" href="${item.source_download_url}">Original HQ</a>`);
  }
  if (item.subtitle_download_url) {
    actions.push(`<a class="clip-action secondary" href="${item.subtitle_download_url}">Legenda</a>`);
  }

  return `
    <article class="clip-card" draggable="true" ondragstart="onDragStart(event, '${item.id}')">
      ${thumbnail}
      <div class="clip-footer">
        <span class="pill neutral">${escapeHtml(cutStyleLabel(item.cut_style || "viral"))}</span>
        <span class="status-pill ${statusClass(item.publish_status)}">${escapeHtml(item.publish_status)}</span>
      </div>
      <h4 class="clip-title">${escapeHtml(item.title)}</h4>
      <p class="clip-meta">Fonte: ${escapeHtml(item.source_title || "vídeo local")}</p>
      <p class="clip-meta">Duração: ${formatSeconds(item.duration_seconds)} | Score: ${escapeHtml(item.score)}</p>
      <div class="tag-row">
        <span class="tag">${item.include_subtitles ? "Com legenda" : "Sem legenda"}</span>
        ${item.include_subtitles ? `<span class="tag">${escapeHtml(item.subtitle_font || "Arial")}</span>` : ""}
        ${item.include_subtitles ? `<span class="tag">${escapeHtml(item.subtitle_color || "yellow")}</span>` : ""}
        <span class="tag">${escapeHtml(columnLabel(item.board_column || "nao_postados"))}</span>
      </div>
      ${noteBox}
      <div class="clip-actions">
        ${actions.join("")}
      </div>
      <div class="clip-actions">
        <button class="clip-action secondary" type="button" onclick="openEditModal('${item.id}')">Editar</button>
        <button class="clip-action danger" type="button" onclick="deleteClip('${item.id}')">Excluir</button>
      </div>
      <div class="clip-actions">
        <button class="clip-action secondary" type="button" onclick="publishClip('${item.id}', 'draft')">Rascunho</button>
        <button class="clip-action secondary" type="button" onclick="publishClip('${item.id}', 'publish')">Publicar</button>
      </div>
    </article>
  `;
}

function updateStats(jobs, boardCounts) {
  const runningJobs = jobs.filter((job) => job.status === "running" || job.status === "queued").length;
  const totalClips = Object.values(boardCounts || {}).reduce((sum, value) => sum + Number(value || 0), 0);

  document.getElementById("stat_total_jobs").textContent = String(jobs.length);
  document.getElementById("stat_running_jobs").textContent = String(runningJobs);
  document.getElementById("stat_total_clips").textContent = String(totalClips);
}

async function fetchJobs() {
  const res = await fetch("/api/jobs");
  if (!res.ok) {
    return [];
  }

  const data = await res.json();
  const jobs = data.items || [];
  const target = document.getElementById("jobs_list");
  document.getElementById("jobs_count").textContent = String(jobs.length);

  if (!jobs.length) {
    target.innerHTML = "";
    return jobs;
  }

  target.innerHTML = jobs.map(renderCompactJobCard).join("");
  return jobs;
}

async function fetchBoard() {
  const res = await fetch("/api/board");
  const status = document.getElementById("status");

  if (!res.ok) {
    status.textContent = "Não foi possível carregar o board.";
    return { counts: {}, columns: {} };
  }

  const data = await res.json();
  const columns = data.columns || {};
  const order = data.columns_order || FALLBACK_COLUMNS;

  for (const key of Object.keys(clipCache)) {
    delete clipCache[key];
  }

  for (const column of order) {
    const target = document.getElementById(`col-${column}`);
    const count = document.getElementById(`count-${column}`);
    const items = columns[column] || [];

    count.textContent = String(items.length);
    target.innerHTML = items.map(renderClipCard).join("");
  }

  return {
    counts: data.counts || {},
    columns
  };
}

async function refreshData() {
  const [jobs, board] = await Promise.all([fetchJobs(), fetchBoard()]);
  updateStats(jobs, board.counts);
}

function setCreateButtonBusy(isBusy) {
  const button = document.getElementById("create_job_button");
  button.disabled = isBusy;
  button.textContent = isBusy ? "Criando..." : "Criar job";
}

async function processVideo() {
  const sourceType = document.getElementById("source_type").value;
  const status = document.getElementById("status");
  const creatorName = document.getElementById("creator_name").value.trim();
  const includeSubtitles = document.getElementById("include_subtitles").value === "true";

  if (!creatorName) {
    status.textContent = "Preencha o nome do criador.";
    return;
  }

  setCreateButtonBusy(true);

  try {
    let res;

    if (sourceType === "upload") {
      const fileInput = document.getElementById("upload_file");
      if (!fileInput.files.length) {
        status.textContent = "Selecione um arquivo para upload.";
        return;
      }

      const formData = new FormData();
      formData.append("creator_name", creatorName);
      formData.append("include_subtitles", String(includeSubtitles));
      formData.append("subtitle_font", document.getElementById("subtitle_font").value);
      formData.append("subtitle_color", document.getElementById("subtitle_color").value);
      formData.append("cut_style", document.getElementById("cut_style").value);
      formData.append("top_n", document.getElementById("top_n").value);
      formData.append("min_clip_seconds", document.getElementById("min_clip_seconds").value);
      formData.append("max_clip_seconds", document.getElementById("max_clip_seconds").value);
      formData.append("upload_file", fileInput.files[0]);

      status.textContent = "Enviando arquivo e criando job em segundo plano...";
      res = await fetch("/api/process-upload", {
        method: "POST",
        body: formData
      });
    } else {
      const payload = {
        creator_name: creatorName,
        source_type: sourceType,
        source_value: document.getElementById("source_value").value.trim(),
        include_subtitles: includeSubtitles,
        subtitle_font: document.getElementById("subtitle_font").value,
        subtitle_color: document.getElementById("subtitle_color").value,
        cut_style: document.getElementById("cut_style").value,
        top_n: Number(document.getElementById("top_n").value),
        min_clip_seconds: Number(document.getElementById("min_clip_seconds").value),
        max_clip_seconds: Number(document.getElementById("max_clip_seconds").value)
      };

      if (!payload.source_value) {
        status.textContent = "Informe um caminho local ou URL.";
        return;
      }

      status.textContent = sourceType === "url"
        ? "Criando job de download e processamento..."
        : "Criando job de processamento...";

      res = await fetch("/api/process", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
    }

    const data = await res.json();
    if (!res.ok) {
      status.textContent = data.detail || "Erro ao iniciar processamento.";
      return;
    }

    status.textContent = `Job ${data.job.id.slice(0, 8)} criado com sucesso.`;
    await refreshData();
  } finally {
    setCreateButtonBusy(false);
  }
}

async function publishClip(clipId, mode) {
  const res = await fetch("/api/publish", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ clip_id: clipId, mode })
  });

  const data = await res.json();
  if (!res.ok) {
    window.alert(data.detail || "Erro ao publicar corte.");
    return;
  }

  window.alert(data.message || "Ação concluída.");
  await refreshData();
}

function openEditModal(clipId) {
  const item = clipCache[clipId];
  if (!item) {
    return;
  }

  editingClipId = clipId;
  document.getElementById("edit_title").value = item.title || "";
  document.getElementById("edit_caption").value = item.caption || "";
  document.getElementById("edit_hashtags").value = item.hashtags_text || "";
  document.getElementById("edit_notes").value = item.notes || "";
  document.getElementById("edit_publish_status").value = item.publish_status || "draft";
  document.getElementById("edit_board_column").value = item.board_column || "nao_postados";

  const modal = document.getElementById("edit_modal");
  modal.classList.remove("hidden");
  modal.setAttribute("aria-hidden", "false");
}

function closeEditModal() {
  editingClipId = null;
  const modal = document.getElementById("edit_modal");
  modal.classList.add("hidden");
  modal.setAttribute("aria-hidden", "true");
}

async function saveClipEdits(event) {
  event.preventDefault();
  if (!editingClipId) {
    return;
  }

  const payload = {
    title: document.getElementById("edit_title").value.trim(),
    caption: document.getElementById("edit_caption").value.trim(),
    hashtags_text: document.getElementById("edit_hashtags").value.trim(),
    notes: document.getElementById("edit_notes").value.trim(),
    publish_status: document.getElementById("edit_publish_status").value,
    board_column: document.getElementById("edit_board_column").value
  };

  const res = await fetch(`/api/clips/${editingClipId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  const data = await res.json();
  if (!res.ok) {
    window.alert(data.detail || "Erro ao editar corte.");
    return;
  }

  closeEditModal();
  await refreshData();
}

async function deleteClip(clipId) {
  const confirmed = window.confirm("Excluir este corte e limpar os arquivos relacionados?");
  if (!confirmed) {
    return;
  }

  const res = await fetch(`/api/clips/${clipId}`, {
    method: "DELETE"
  });

  const data = await res.json();
  if (!res.ok) {
    window.alert(data.detail || "Erro ao excluir corte.");
    return;
  }

  await refreshData();
}

async function deleteJob(jobId) {
  const confirmed = window.confirm("Remover este job e limpar os arquivos gerados por ele?");
  if (!confirmed) {
    return;
  }

  const res = await fetch(`/api/jobs/${jobId}`, {
    method: "DELETE"
  });

  const data = await res.json();
  if (!res.ok) {
    window.alert(data.detail || "Erro ao remover job.");
    return;
  }

  await refreshData();
}

function updateSubtitleControls() {
  const enabled = document.getElementById("include_subtitles").value === "true";
  const fontWrap = document.getElementById("subtitle_font_wrap");
  const colorWrap = document.getElementById("subtitle_color_wrap");
  const hint = document.getElementById("status");

  fontWrap.style.display = enabled ? "flex" : "none";
  colorWrap.style.display = enabled ? "flex" : "none";
  if (!enabled && !hint.textContent) {
    hint.textContent = "O video sera gerado sem legenda.";
  }
}

function updateSourceInput() {
  const sourceType = document.getElementById("source_type").value;
  const sourceValue = document.getElementById("source_value");
  const sourceHint = document.getElementById("source_hint");
  const sourceWrapper = document.getElementById("source_value_wrap");
  const uploadWrapper = document.getElementById("upload_wrap");

  if (sourceType === "url") {
    sourceWrapper.style.display = "flex";
    uploadWrapper.style.display = "none";
    sourceValue.placeholder = "Ex.: https://youtube.com/shorts/...";
    sourceHint.textContent = "A URL é baixada na melhor qualidade disponível, sem recompressão do arquivo original.";
    return;
  }

  if (sourceType === "upload") {
    sourceWrapper.style.display = "none";
    uploadWrapper.style.display = "flex";
    sourceHint.textContent = "Envie um vídeo direto pela página para criar um job em segundo plano.";
    return;
  }

  sourceWrapper.style.display = "flex";
  uploadWrapper.style.display = "none";
  sourceValue.placeholder = "Ex.: C:/videos/live.mp4";
  sourceHint.textContent = "Use um caminho local de vídeo ou troque para URL para baixar o original automaticamente.";
}

function onDragStart(event, clipId) {
  event.dataTransfer.setData("text/plain", clipId);
}

function allowDrop(event) {
  event.preventDefault();
}

async function onDrop(event, column) {
  event.preventDefault();
  const clipId = event.dataTransfer.getData("text/plain");

  const res = await fetch(`/api/clips/${clipId}/move?column=${column}`, {
    method: "POST"
  });

  if (!res.ok) {
    const data = await res.json();
    window.alert(data.detail || "Erro ao mover corte.");
    return;
  }

  await refreshData();
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("source_type").addEventListener("change", updateSourceInput);
  document.getElementById("include_subtitles").addEventListener("change", updateSubtitleControls);
  document.getElementById("edit_form").addEventListener("submit", saveClipEdits);
  updateSourceInput();
  updateSubtitleControls();
  refreshData();
  window.setInterval(refreshData, 3000);
});
