from __future__ import annotations

import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.job_store import job_store
from app.schemas import ProcessRequest, PublishRequest
from app.services.ffmpeg_service import FFmpegService
from app.services.packaging_service import PackagingService
from app.services.publish_service import PublishService
from app.services.scoring_service import ScoringService
from app.services.source_service import SourceService
from app.services.subtitle_service import SubtitleService
from app.services.transcript_service import TranscriptService
from app.storage import store

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


def run_processing_job(job_id: str, payload: ProcessRequest) -> None:
    try:
        job_store.update(job_id, status="running", message="Baixando ou copiando video...")
        video_path, source_title = sources.ingest(payload.source_type, payload.source_value)

        audio_path = settings.audio_dir / f"{Path(video_path).stem}.mp3"
        transcript_path = settings.transcripts_dir / f"{Path(video_path).stem}.json"

        job_store.update(job_id, message="Extraindo audio...")
        ffmpeg.extract_audio(video_path, str(audio_path))

        job_store.update(job_id, message="Transcrevendo com Whisper...")
        transcript = transcriber.transcribe(str(audio_path), str(transcript_path))

        job_store.update(job_id, message="Analisando melhores momentos...")
        scored = scorer.score_segments(transcript)
        best_moments = scorer.merge_top_segments(
            scored_segments=scored,
            top_n=payload.top_n,
            min_clip_seconds=payload.min_clip_seconds,
            max_clip_seconds=payload.max_clip_seconds,
        )

        results = []

        for idx, moment in enumerate(best_moments, start=1):
            job_store.update(job_id, message=f"Gerando corte {idx} de {len(best_moments)}...")
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

        job_store.update(
            job_id,
            status="completed",
            message=f"{len(results)} cortes gerados com sucesso.",
            items=results,
            error=None,
        )
    except NotImplementedError as e:
        job_store.update(job_id, status="failed", message=str(e), error=str(e))
    except Exception as e:
        job_store.update(job_id, status="failed", message=str(e), error=str(e))


@app.post("/api/process")
def process_video(payload: ProcessRequest):
    job_id = str(uuid.uuid4())
    job_store.create(
        job_id,
        {
            "id": job_id,
            "status": "queued",
            "message": "Job criado. Preparando processamento...",
            "items": [],
            "error": None,
        },
    )
    threading.Thread(
        target=run_processing_job,
        args=(job_id, payload),
        daemon=True,
    ).start()
    return {"job_id": job_id, "status": "queued"}


@app.get("/api/process/{job_id}")
def get_process_job(job_id: str):
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job nao encontrado")
    return job


@app.post("/api/publish")
def publish_clip(payload: PublishRequest):
    clips = store.list_clips()
    clip = next((c for c in clips if c["id"] == payload.clip_id), None)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip nao encontrado")

    result = publisher.publish(
        clip_path=clip["clip_path"],
        title=clip["title"],
        caption=clip["caption"],
        mode=payload.mode,
    )
    ok = result.get("ok", False)
    store.update_publish_status(payload.clip_id, "published" if ok else "failed")
    return result
