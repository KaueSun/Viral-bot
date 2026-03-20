let activeJobId = null;
let activePollTimer = null;

async function fetchClips() {
  const res = await fetch('/api/clips');
  const data = await res.json();
  renderClips(data.items || []);
}

function renderClips(items) {
  const container = document.getElementById('clips');
  if (!items.length) {
    container.innerHTML = '<p class="muted">Nenhum corte gerado ainda.</p>';
    return;
  }

  container.innerHTML = items.slice().reverse().map(item => `
    <div class="card clip">
      <div>
        ${item.thumbnail_path ? `<img class="thumb" src="/${item.thumbnail_path}" alt="thumb" />` : ''}
      </div>
      <div class="meta">
        <p><strong>${item.title}</strong></p>
        <p class="muted">Criador: ${item.creator_name}</p>
        <p class="muted">Origem: ${item.source_title}</p>
        <p>Score: <strong>${item.score}</strong> · Duração: <strong>${item.duration_seconds}s</strong></p>
        <p>${item.caption}</p>
        <div class="row">
          <a href="/${item.clip_path}" target="_blank"><button>Ver vídeo</button></a>
          <button onclick="publishClip('${item.id}', 'draft')">Enviar como rascunho</button>
          <button onclick="publishClip('${item.id}', 'publish')">Publicar</button>
        </div>
        <p class="${item.publish_status === 'published' ? 'ok' : 'warn'}">Status: ${item.publish_status}</p>
      </div>
    </div>
  `).join('');
}

async function processVideo() {
  const payload = {
    creator_name: document.getElementById('creator_name').value,
    source_type: document.getElementById('source_type').value,
    source_value: document.getElementById('source_value').value,
    top_n: Number(document.getElementById('top_n').value),
    min_clip_seconds: Number(document.getElementById('min_clip_seconds').value),
    max_clip_seconds: Number(document.getElementById('max_clip_seconds').value)
  };

  const status = document.getElementById('status');
  const button = document.querySelector('button[onclick="processVideo()"]');

  if (activePollTimer) {
    clearTimeout(activePollTimer);
    activePollTimer = null;
  }

  status.textContent = 'Criando job de processamento...';
  button.disabled = true;

  const res = await fetch('/api/process', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  const data = await res.json();
  if (!res.ok) {
    status.textContent = data.detail || 'Erro ao processar vídeo.';
    button.disabled = false;
    return;
  }

  activeJobId = data.job_id;
  await pollJobStatus(button, status);
}

async function pollJobStatus(button, status) {
  if (!activeJobId) {
    button.disabled = false;
    return;
  }

  try {
    const res = await fetch(`/api/process/${activeJobId}`);
    const data = await res.json();

    if (!res.ok) {
      status.textContent = data.detail || 'Erro ao consultar o processamento.';
      button.disabled = false;
      activeJobId = null;
      return;
    }

    status.textContent = data.message || 'Processando...';

    if (data.status === 'completed') {
      button.disabled = false;
      activeJobId = null;
      if (activePollTimer) {
        clearTimeout(activePollTimer);
        activePollTimer = null;
      }
      await fetchClips();
      return;
    }

    if (data.status === 'failed') {
      status.textContent = data.error || data.message || 'Erro ao processar vídeo.';
      button.disabled = false;
      activeJobId = null;
      if (activePollTimer) {
        clearTimeout(activePollTimer);
        activePollTimer = null;
      }
      return;
    }
  } catch (error) {
    status.textContent = 'Falha ao consultar o progresso do processamento.';
    button.disabled = false;
    activeJobId = null;
    return;
  }

  activePollTimer = setTimeout(() => {
    pollJobStatus(button, status);
  }, 2000);
}

async function publishClip(clipId, mode) {
  const res = await fetch('/api/publish', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ clip_id: clipId, mode })
  });

  const data = await res.json();
  alert(data.message || 'Ação concluída.');
  await fetchClips();
}

fetchClips();
