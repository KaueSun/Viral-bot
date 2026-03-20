# Viral Cuts Bot v2

Projeto base com interface web simples para:

* cadastrar um criador
* colar URL ou apontar arquivo local
* processar vídeo
* listar cortes gerados
* aprovar/publicar

> Observação: esta base entrega a estrutura funcional do MVP com interface. As partes de download da plataforma e publicação real no TikTok ficam com adaptadores separados, porque dependem de credenciais, regras da plataforma e implementação específica.

---

## Estrutura

```text
viral_cuts_bot_v2/
├─ app/
│  ├─ main.py
│  ├─ config.py
│  ├─ schemas.py
│  ├─ storage.py
│  ├─ services/
│  │  ├─ ffmpeg_service.py
│  │  ├─ transcript_service.py
│  │  ├─ scoring_service.py
│  │  ├─ subtitle_service.py
│  │  ├─ packaging_service.py
│  │  ├─ source_service.py
│  │  └─ publish_service.py
│  ├─ templates/
│  │  └─ index.html
│  └─ static/
│     └─ app.js
├─ data/
│  ├─ downloads/
│  ├─ audio/
│  ├─ transcripts/
│  ├─ clips/
│  ├─ subtitles/
│  └─ thumbs/
├─ requirements.txt
└─ README.md
```

---

## requirements.txt

```
txt
fastapi
uvicorn
python-multipart
jinja2
pydantic
openai-whisper
python-dotenv
yt-dlp

```

---

## app/config.py

```python
from pathlib import Path
from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "Viral Cuts Bot v2"
    base_dir: Path = Path(".")
    data_dir: Path = base_dir / "data"
    downloads_dir: Path = data_dir / "downloads"
    audio_dir: Path = data_dir / "audio"
    transcripts_dir: Path = data_dir / "transcripts"
    clips_dir: Path = data_dir / "clips"
    subtitles_dir: Path = data_dir / "subtitles"
    thumbs_dir: Path = data_dir / "thumbs"
    whisper_model: str = "base"


settings = Settings()

for folder in [
    settings.data_dir,
    settings.downloads_dir,
    settings.audio_dir,
    settings.transcripts_dir,
    settings.clips_dir,
    settings.subtitles_dir,
    settings.thumbs_dir,
]:
    folder.mkdir(parents=True, exist_ok=True)
```

---

## app/schemas.py

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional


class ProcessRequest(BaseModel):
    creator_name: str = Field(min_length=2, max_length=100)
    source_type: Literal["url", "local"] = "url"
    source_value: str = Field(min_length=1)
    top_n: int = Field(default=5, ge=1, le=10)
    min_clip_seconds: int = Field(default=20, ge=10, le=120)
    max_clip_seconds: int = Field(default=50, ge=10, le=180)


class ClipItem(BaseModel):
    id: str
    creator_name: str
    source_title: str
    source_path: str
    clip_path: str
    subtitle_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    start_seconds: float
    end_seconds: float
    duration_seconds: float
    score: float
    title: str
    caption: str
    publish_status: Literal["draft", "published", "failed"] = "draft"


class PublishRequest(BaseModel):
    clip_id: str
    mode: Literal["draft", "publish"] = "draft"
```

---

## app/storage.py

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DB_PATH = Path("data/state.json")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


class JsonStore:
    def __init__(self, path: Path = DB_PATH):
        self.path = path
        if not self.path.exists():
            self._write({"clips": []})

    def _read(self) -> dict[str, Any]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def add_clip(self, item: dict[str, Any]) -> None:
        data = self._read()
        data["clips"].append(item)
        self._write(data)

    def list_clips(self) -> list[dict[str, Any]]:
        return self._read().get("clips", [])

    def update_publish_status(self, clip_id: str, status: str) -> bool:
        data = self._read()
        updated = False
        for clip in data.get("clips", []):
            if clip["id"] == clip_id:
                clip["publish_status"] = status
                updated = True
                break
        if updated:
            self._write(data)
        return updated


store = JsonStore()
```

---

## app/services/ffmpeg_service.py

```python
import subprocess
from pathlib import Path


class FFmpegService:
    @staticmethod
    def run(cmd: list[str]) -> None:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr)

    def extract_audio(self, video_path: str, audio_path: str) -> None:
        self.run([
            "ffmpeg", "-y",
            "-i", video_path,
            "-vn",
            "-acodec", "mp3",
            audio_path,
        ])

    def cut_vertical_clip(self, input_path: str, output_path: str, start_sec: float, duration_sec: float) -> None:
        vf = (
            "scale=-2:1920,"
            "crop=1080:1920,"
            "fps=30"
        )
        self.run([
            "ffmpeg", "-y",
            "-ss", str(start_sec),
            "-i", input_path,
            "-t", str(duration_sec),
            "-vf", vf,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-preset", "medium",
            "-movflags", "+faststart",
            output_path,
        ])

    def burn_subtitles(self, input_path: str, srt_path: str, output_path: str) -> None:
        subtitle_filter = f"subtitles={Path(srt_path).as_posix()}"
        self.run([
            "ffmpeg", "-y",
            "-i", input_path,
            "-vf", subtitle_filter,
            "-c:v", "libx264",
            "-c:a", "aac",
            output_path,
        ])

    def make_thumbnail(self, input_path: str, second: float, output_path: str) -> None:
        self.run([
            "ffmpeg", "-y",
            "-ss", str(second),
            "-i", input_path,
            "-vframes", "1",
            output_path,
        ])
```

---

## app/services/transcript_service.py

```python
import json
import whisper
from pathlib import Path
from app.config import settings


class TranscriptService:
    def __init__(self) -> None:
        self.model = whisper.load_model(settings.whisper_model)

    def transcribe(self, audio_path: str, output_json_path: str) -> dict:
        result = self.model.transcribe(audio_path, language="pt")
        Path(output_json_path).write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return result
```

---

## app/services/scoring_service.py

```python
from typing import Any

STRONG_KEYWORDS = [
    "não acredito", "meu deus", "caraca", "mentira", "polêmica",
    "olha isso", "sério", "absurdo", "vazou", "que isso"
]


class ScoringService:
    def score_segments(self, transcript: dict[str, Any]) -> list[dict]:
        segments = transcript.get("segments", [])
        scored = []

        for seg in segments:
            text = seg.get("text", "").strip().lower()
            start = float(seg.get("start", 0))
            end = float(seg.get("end", 0))
            duration = max(0.1, end - start)

            keyword_score = sum(1 for kw in STRONG_KEYWORDS if kw in text) * 2.0
            punctuation_score = text.count("!") * 0.8 + text.count("?") * 0.6
            density_score = min(len(text.split()) / 8.0, 2.0)
            duration_score = 1.0 if 4 <= duration <= 14 else 0.3
            score = keyword_score + punctuation_score + density_score + duration_score

            scored.append({
                "text": text,
                "start": start,
                "end": end,
                "duration": duration,
                "score": round(score, 2),
            })

        return sorted(scored, key=lambda x: x["score"], reverse=True)

    def merge_top_segments(
        self,
        scored_segments: list[dict],
        top_n: int,
        min_clip_seconds: int,
        max_clip_seconds: int,
    ) -> list[dict]:
        top = scored_segments[:top_n]
        merged = []
        for seg in top:
            desired = max(min_clip_seconds, min(max_clip_seconds, seg["duration"] + 8))
            start = max(0.0, seg["start"] - 3)
            end = start + desired
            merged.append({
                "start": round(start, 2),
                "end": round(end, 2),
                "duration": round(desired, 2),
                "score": seg["score"],
                "hook_text": seg["text"][:160],
            })
        return merged
```

---

## app/services/subtitle_service.py

```python
from pathlib import Path


def sec_to_srt(seconds: float) -> str:
    ms = int((seconds % 1) * 1000)
    total = int(seconds)
    s = total % 60
    m = (total // 60) % 60
    h = total // 3600
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


class SubtitleService:
    def clip_to_srt(self, transcript: dict, clip_start: float, clip_end: float, srt_path: str) -> None:
        lines: list[str] = []
        index = 1
        for seg in transcript.get("segments", []):
            seg_start = float(seg.get("start", 0))
            seg_end = float(seg.get("end", 0))
            if seg_end < clip_start or seg_start > clip_end:
                continue

            start = max(seg_start, clip_start) - clip_start
            end = min(seg_end, clip_end) - clip_start
            text = seg.get("text", "").strip()
            if not text:
                continue

            lines.append(
                f"{index}\n{sec_to_srt(start)} --> {sec_to_srt(end)}\n{text}\n"
            )
            index += 1

        Path(srt_path).write_text("\n".join(lines), encoding="utf-8")
```

---

## app/services/packaging_service.py

```python
class PackagingService:
    def make_title(self, creator_name: str, hook_text: str) -> str:
        base = hook_text.strip().capitalize()
        if len(base) > 70:
            base = base[:67] + "..."
        return f"{creator_name}: {base}"

    def make_hashtags(self, creator_name: str) -> list[str]:
        safe_name = creator_name.lower().replace(" ", "")
        return [
            f"#{safe_name}",
            "#cortes",
            "#viral",
            "#foryou",
            "#tiktokbr",
        ]

    def make_caption(self, title: str, hashtags: list[str]) -> str:
        return f"{title}\n\n" + " ".join(hashtags)
```

---

## app/services/source_service.py

```python
from pathlib import Path
from shutil import copy2
from urllib.parse import urlparse
from app.config import settings


class SourceService:
    def ingest(self, source_type: str, source_value: str) -> tuple[str, str]:
        """
        Retorna (video_path, source_title)

        source_type='local': copia o arquivo local para data/downloads
        source_type='url': placeholder para implementar o adaptador oficial da plataforma
        """
        if source_type == "local":
            src = Path(source_value)
            if not src.exists():
                raise FileNotFoundError(f"Arquivo não encontrado: {source_value}")
            dest = settings.downloads_dir / src.name
            copy2(src, dest)
            return str(dest), src.stem

        parsed = urlparse(source_value)
        if not parsed.scheme:
            raise ValueError("URL inválida")

        # Aqui entra o adaptador oficial/autorizado da plataforma.
        # Enquanto isso, deixamos explícito que precisa ser implementado.
        raise NotImplementedError(
            "A ingestão por URL precisa de um adaptador específico da plataforma/fonte autorizada."
        )
```

---

## app/services/publish_service.py

```python
class PublishService:
    def publish(self, clip_path: str, title: str, caption: str, mode: str = "draft") -> dict:
        """
        Placeholder para integração real com a API de publicação.
        mode='draft' simula envio como rascunho.
        mode='publish' simula publicação direta.
        """
        return {
            "ok": True,
            "mode": mode,
            "clip_path": clip_path,
            "title": title,
            "caption": caption,
            "message": "Integração simulada com sucesso. Substitua este método pela API real.",
        }
```

---

## app/main.py

```python
from __future__ import annotations

import uuid
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.schemas import ProcessRequest, PublishRequest
from app.storage import store
from app.services.ffmpeg_service import FFmpegService
from app.services.transcript_service import TranscriptService
from app.services.scoring_service import ScoringService
from app.services.subtitle_service import SubtitleService
from app.services.packaging_service import PackagingService
from app.services.source_service import SourceService
from app.services.publish_service import PublishService

app = FastAPI(title=settings.app_name)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/data", StaticFiles(directory="data"), name="data")
templates = Jinja2Templates(directory="app/templates")

ffmpeg = FFmpegService()
transcriber = TranscriptService()
scorer = ScoringService()
subtitles = SubtitleService()
packaging = PackagingService()
sources = SourceService()
publisher = PublishService()


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/clips")
def list_clips():
    return {"items": store.list_clips()}


@app.post("/api/process")
def process_video(payload: ProcessRequest):
    try:
        video_path, source_title = sources.ingest(payload.source_type, payload.source_value)
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    audio_path = settings.audio_dir / f"{Path(video_path).stem}.mp3"
    transcript_path = settings.transcripts_dir / f"{Path(video_path).stem}.json"

    ffmpeg.extract_audio(video_path, str(audio_path))
    transcript = transcriber.transcribe(str(audio_path), str(transcript_path))

    scored = scorer.score_segments(transcript)
    best_moments = scorer.merge_top_segments(
        scored_segments=scored,
        top_n=payload.top_n,
        min_clip_seconds=payload.min_clip_seconds,
        max_clip_seconds=payload.max_clip_seconds,
    )

    results = []

    for idx, moment in enumerate(best_moments, start=1):
        clip_id = str(uuid.uuid4())
        raw_clip_path = settings.clips_dir / f"{clip_id}_raw.mp4"
        final_clip_path = settings.clips_dir / f"{clip_id}.mp4"
        subtitle_path = settings.subtitles_dir / f"{clip_id}.srt"
        thumbnail_path = settings.thumbs_dir / f"{clip_id}.jpg"

        ffmpeg.cut_vertical_clip(
            input_path=video_path,
            output_path=str(raw_clip_path),
            start_sec=moment["start"],
            duration_sec=moment["duration"],
        )

        subtitles.clip_to_srt(
            transcript=transcript,
            clip_start=moment["start"],
            clip_end=moment["end"],
            srt_path=str(subtitle_path),
        )

        ffmpeg.burn_subtitles(
            input_path=str(raw_clip_path),
            srt_path=str(subtitle_path),
            output_path=str(final_clip_path),
        )

        ffmpeg.make_thumbnail(
            input_path=str(final_clip_path),
            second=1,
            output_path=str(thumbnail_path),
        )

        title = packaging.make_title(payload.creator_name, moment["hook_text"])
        hashtags = packaging.make_hashtags(payload.creator_name)
        caption = packaging.make_caption(title, hashtags)

        item = {
            "id": clip_id,
            "creator_name": payload.creator_name,
            "source_title": source_title,
            "source_path": video_path,
            "clip_path": str(final_clip_path),
            "subtitle_path": str(subtitle_path),
            "thumbnail_path": str(thumbnail_path),
            "start_seconds": moment["start"],
            "end_seconds": moment["end"],
            "duration_seconds": moment["duration"],
            "score": moment["score"],
            "title": title,
            "caption": caption,
            "publish_status": "draft",
        }
        store.add_clip(item)
        results.append(item)

    return {"items": results}


@app.post("/api/publish")
def publish_clip(payload: PublishRequest):
    clips = store.list_clips()
    clip = next((c for c in clips if c["id"] == payload.clip_id), None)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip não encontrado")

    result = publisher.publish(
        clip_path=clip["clip_path"],
        title=clip["title"],
        caption=clip["caption"],
        mode=payload.mode,
    )
    ok = result.get("ok", False)
    store.update_publish_status(payload.clip_id, "published" if ok else "failed")
    return result
```

---

## app/templates/index.html

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Viral Cuts Bot v2</title>
  <style>
    body { font-family: Arial, sans-serif; background: #0f1115; color: #f2f2f2; margin: 0; }
    .wrap { max-width: 1100px; margin: 0 auto; padding: 24px; }
    .card { background: #181c23; border: 1px solid #2a2f38; border-radius: 14px; padding: 18px; margin-bottom: 18px; }
    h1, h2 { margin-top: 0; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
    input, select, button, textarea {
      width: 100%; padding: 12px; border-radius: 10px; border: 1px solid #343a46;
      background: #0f1115; color: #f2f2f2; box-sizing: border-box;
    }
    button { cursor: pointer; font-weight: bold; }
    .clip { display: grid; grid-template-columns: 180px 1fr; gap: 16px; }
    .thumb { width: 180px; height: 320px; object-fit: cover; border-radius: 10px; background: #111; }
    .meta p { margin: 8px 0; }
    .row { display: flex; gap: 10px; }
    .row > button { flex: 1; }
    .muted { color: #b5bcc8; font-size: 14px; }
    .ok { color: #64d98b; }
    .warn { color: #ffd166; }
    @media (max-width: 800px) {
      .grid { grid-template-columns: 1fr; }
      .clip { grid-template-columns: 1fr; }
      .thumb { width: 100%; height: auto; aspect-ratio: 9/16; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>Viral Cuts Bot v2</h1>
      <p class="muted">Processa um vídeo local, encontra os melhores momentos, gera cortes com legenda e deixa pronto para publicar.</p>
    </div>

    <div class="card">
      <h2>Processar vídeo</h2>
      <div class="grid">
        <div>
          <label>Criador</label>
          <input id="creator_name" placeholder="Ex.: Paulinho o Loko" />
        </div>
        <div>
          <label>Tipo de fonte</label>
          <select id="source_type">
            <option value="local">Arquivo local</option>
            <option value="url">URL</option>
          </select>
        </div>
        <div>
          <label>Caminho do arquivo ou URL</label>
          <input id="source_value" placeholder="Ex.: C:/videos/live.mp4 ou https://..." />
        </div>
        <div>
          <label>Quantidade de cortes</label>
          <input id="top_n" type="number" value="5" min="1" max="10" />
        </div>
        <div>
          <label>Duração mínima</label>
          <input id="min_clip_seconds" type="number" value="20" min="10" max="120" />
        </div>
        <div>
          <label>Duração máxima</label>
          <input id="max_clip_seconds" type="number" value="50" min="10" max="180" />
        </div>
      </div>
      <div style="margin-top:14px;">
        <button onclick="processVideo()">Processar vídeo</button>
      </div>
      <p id="status" class="muted"></p>
    </div>

    <div class="card">
      <h2>Cortes gerados</h2>
      <div id="clips"></div>
    </div>
  </div>

  <script src="/static/app.js"></script>
</body>
</html>
```

---

## app/static/app.js

```javascript
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
  status.textContent = 'Processando... isso pode demorar dependendo do tamanho do vídeo.';

  const res = await fetch('/api/process', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  const data = await res.json();
  if (!res.ok) {
    status.textContent = data.detail || 'Erro ao processar vídeo.';
    return;
  }

  status.textContent = `${data.items.length} cortes gerados com sucesso.`;
  await fetchClips();
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
```

---

## README.md

````md
# Viral Cuts Bot v2

## 1. Instalação

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows
pip install -r requirements.txt
````

Também precisa ter o FFmpeg instalado e disponível no PATH.

## 2. Rodar

```bash
uvicorn app.main:app --reload
```

Abra no navegador:

```text
http://127.0.0.1:8000
```

## 3. Como testar

* escolha `Arquivo local`
* informe o caminho de um `.mp4`
* clique em `Processar vídeo`

## 4. O que já faz

* copia o vídeo para a pasta do projeto
* extrai áudio
* transcreve com Whisper
* escolhe os trechos com score maior
* cria cortes verticais
* gera `.srt`
* embute legenda no vídeo
* gera thumbnail
* cria título e caption
* lista tudo na interface

## 5. O que falta plugar

### Ingestão por URL

Implementar `SourceService.ingest()` para a fonte autorizada que você quiser usar.

### Publicação real

Implementar `PublishService.publish()` com a API/plataforma que você vai usar.

```

---

## Próximos upgrades que valem muito a pena

1. reenquadramento inteligente com detecção de rosto/jogo  
2. capa com texto grande automático  
3. painel com fila de jobs  
4. agendamento de postagem  
5. filtro para evitar cortes repetidos  
6. score mais inteligente com LLM

---

## Upgrade de interface: dashboard estilo Trello

A interface pode evoluir de uma página simples para um painel estilo Trello, com foco em organização visual e fluxo de produção.

### Estrutura visual sugerida

#### Colunas do board

1. **Entradas**
- vídeos enviados manualmente
- URLs pendentes
- novos vídeos detectados

2. **Processando**
- jobs em andamento
- progresso por etapa
- status como: baixando, transcrevendo, cortando, legendando

3. **Cortes Gerados**
- cards com thumbnail
- score do corte
- duração
- título gerado
- botão para pré-visualizar

4. **Aprovados**
- cortes selecionados para publicação
- edição final de título/caption
- escolha de capa

5. **Publicados**
- histórico de postagem
- data/hora
- status final

### Cada card deve exibir
- thumbnail vertical
- nome do criador
- título do vídeo original
- score
- duração
- status
- ações rápidas

### Interações estilo Trello
- arrastar e soltar cards entre colunas
- abrir modal lateral com detalhes do corte
- editar título, legenda e hashtags no card
- marcar card como favorito
- duplicar corte
- rejeitar corte
- selecionar múltiplos cards

### Área lateral de detalhes
Ao clicar em um card, abrir uma sidebar ou modal com:
- player de vídeo
- transcrição do trecho
- score detalhado
- título sugerido
- legenda sugerida
- hashtags
- botão de republicar
- botão de baixar
- botão de excluir

### Melhorias visuais
- layout escuro moderno
- cards com cantos arredondados
- animações suaves
- barra de progresso por job
- filtros por criador, status e score
- busca por título ou origem

### Organização recomendada do front-end
Se quiser manter simples:
- FastAPI + Jinja2 + HTML/CSS/JS puro

Se quiser algo mais profissional:
- FastAPI no backend
- React no frontend
- drag and drop com biblioteca específica
- componentes para board, cards, modal e filtros

### Fluxo ideal de uso
1. usuário faz upload do vídeo ou cola a URL  
2. job aparece em **Entradas**  
3. ao iniciar, vai para **Processando**  
4. após gerar cortes, cards aparecem em **Cortes Gerados**  
5. usuário arrasta os melhores para **Aprovados**  
6. ao publicar, o card vai para **Publicados**

### Próxima versão ideal
A próxima versão do projeto pode incluir:
- upload direto de arquivo pela página
- board estilo Trello
- preview em modal
- drag and drop entre colunas
- edição manual de título/caption antes de publicar
- status visual em tempo real

```
