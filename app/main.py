from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from shutil import copy2, copyfileobj
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.schemas import ClipUpdateRequest, ProcessRequest, PublishRequest
from app.services.ffmpeg_service import FFmpegService
from app.services.packaging_service import PackagingService
from app.services.publish_service import PublishService
from app.services.scoring_service import ScoringService
from app.services.source_service import SourceService
from app.services.subtitle_service import SubtitleService
from app.storage import DEFAULT_COLUMNS, store, utc_now

VALID_COLUMNS = set(DEFAULT_COLUMNS)
executor = ThreadPoolExecutor(max_workers=2)

app = FastAPI(title=settings.app_name)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/data", StaticFiles(directory=str(settings.data_dir)), name="data")
templates = Jinja2Templates(directory="app/templates")

source = SourceService()
ffmpeg = FFmpegService()
scoring = ScoringService()
subtitles = SubtitleService()
packaging = PackagingService()
publisher = PublishService()


def get_transcript_service():
    try:
        from app.services.transcript_service import TranscriptService
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Dependencia ausente para transcricao. "
            "Instale os pacotes de requirements.txt antes de processar videos."
        ) from exc

    try:
        return TranscriptService()
    except Exception as exc:
        raise RuntimeError(f"Falha ao inicializar o modelo de transcricao: {exc}") from exc


def to_media_url(path_str: str | None) -> str | None:
    if not path_str:
        return None

    path = Path(path_str)
    if not path.is_absolute() and path.parts and path.parts[0] == settings.data_dir.name:
        path = Path(*path.parts[1:])
    elif path.is_absolute():
        try:
            path = path.relative_to(settings.data_dir.resolve())
        except ValueError:
            path = Path(path.name)

    return f"/data/{path.as_posix()}"


def serialize_clip(item: dict) -> dict:
    data = dict(item)
    data["include_subtitles"] = bool(data.get("include_subtitles", True))
    data["source_url"] = to_media_url(data.get("source_path"))
    data["clip_url"] = to_media_url(data.get("clip_path"))
    data["subtitle_url"] = to_media_url(data.get("subtitle_path"))
    data["thumbnail_url"] = to_media_url(data.get("thumbnail_path"))

    clip_id = data.get("id")
    if clip_id:
        data["source_download_url"] = f"/api/clips/{clip_id}/download?kind=source"
        data["clip_download_url"] = f"/api/clips/{clip_id}/download?kind=clip"
        data["subtitle_download_url"] = f"/api/clips/{clip_id}/download?kind=subtitle"
        data["thumbnail_download_url"] = f"/api/clips/{clip_id}/download?kind=thumbnail"
        data["delete_url"] = f"/api/clips/{clip_id}"
        data["edit_url"] = f"/api/clips/{clip_id}"

    return data


def serialize_job(item: dict) -> dict:
    data = dict(item)
    data["include_subtitles"] = bool(data.get("include_subtitles", True))
    data["source_url"] = to_media_url(data.get("source_path"))
    data["final_video_url"] = to_media_url(data.get("final_video_path"))
    data["final_thumbnail_url"] = to_media_url(data.get("final_thumbnail_path"))
    job_id = data.get("id")
    if job_id:
        data["job_url"] = f"/api/jobs/{job_id}"
        if data.get("source_path"):
            data["source_download_url"] = f"/api/jobs/{job_id}/download?kind=source"
        if data.get("final_video_path"):
            data["final_download_url"] = f"/api/jobs/{job_id}/download?kind=final"
        if data.get("final_thumbnail_path"):
            data["final_thumbnail_download_url"] = f"/api/jobs/{job_id}/download?kind=thumbnail"
    return data


def normalize_runtime_error(exc: Exception) -> str:
    if isinstance(exc, FileNotFoundError):
        message = str(exc)
        filename = (getattr(exc, "filename", "") or "").lower()
        if "ffmpeg" in filename or "ffmpeg" in message.lower():
            return "FFmpeg nao encontrado. Instale o FFmpeg e deixe o executavel no PATH."
        return message
    return str(exc)


def get_clip_or_404(clip_id: str) -> dict:
    clip = store.get_clip(clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip nao encontrado")
    return clip


def get_job_or_404(job_id: str) -> dict:
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job nao encontrado")
    return job


def safe_unlink(path_str: str | None) -> None:
    if not path_str:
        return

    path = Path(path_str)
    try:
        if path.exists() and path.is_file():
            path.unlink()
    except OSError:
        pass


def cleanup_clip_files(clip: dict) -> None:
    remaining_clips = store.list_clips()
    shared_source = any(
        item.get("source_path") == clip.get("source_path") and item.get("id") != clip.get("id")
        for item in remaining_clips
    )

    clip_path = Path(clip["clip_path"])
    raw_clip_path = clip_path.with_name(f"{clip_path.stem}_raw{clip_path.suffix}")

    safe_unlink(str(raw_clip_path))
    safe_unlink(clip.get("clip_path"))
    safe_unlink(clip.get("subtitle_path"))
    safe_unlink(clip.get("thumbnail_path"))

    if shared_source:
        return

    safe_unlink(clip.get("source_path"))
    source_stem = Path(clip["source_path"]).stem
    safe_unlink(str(settings.audio_dir / f"{source_stem}.mp3"))
    safe_unlink(str(settings.transcripts_dir / f"{source_stem}.json"))


def update_job_stage(
    job_id: str,
    *,
    status: str,
    stage: str,
    message: str,
    error_message: str | None = None,
    started: bool = False,
    finished: bool = False,
    **extra: object,
) -> None:
    fields: dict[str, object] = {
        "status": status,
        "stage": stage,
        "message": message,
        "error_message": error_message,
    }
    if started:
        fields["started_at"] = utc_now()
    if finished:
        fields["finished_at"] = utc_now()
    fields.update(extra)
    store.update_job(job_id, **fields)


def build_job_payload(
    *,
    creator_name: str,
    source_type: str,
    source_value: str,
    subtitle_font: str,
    subtitle_color: str,
    include_subtitles: bool,
    cut_style: str,
    top_n: int,
    min_clip_seconds: int,
    max_clip_seconds: int,
) -> dict:
    return {
        "id": uuid4().hex,
        "creator_name": creator_name,
        "source_type": source_type,
        "source_value": source_value,
        "source_title": None,
        "source_path": None,
        "include_subtitles": include_subtitles,
        "final_title": None,
        "final_video_path": None,
        "final_thumbnail_path": None,
        "final_duration_seconds": None,
        "subtitle_font": subtitle_font,
        "subtitle_color": subtitle_color,
        "cut_style": cut_style,
        "top_n": top_n,
        "min_clip_seconds": min_clip_seconds,
        "max_clip_seconds": max_clip_seconds,
        "status": "queued",
        "stage": "waiting",
        "message": "Aguardando processamento.",
        "error_message": None,
        "clips_count": 0,
    }


def queue_job(job: dict) -> dict:
    created = store.create_job(job)
    executor.submit(process_job_worker, created["id"])
    return created


def process_job_worker(job_id: str) -> None:
    job = store.get_job(job_id)
    if not job:
        return

    source_type = job["source_type"]
    effective_source_type = "local" if source_type in {"local", "upload"} else source_type

    try:
        initial_message = (
            "Baixando video..." if source_type == "url"
            else "Preparando upload..." if source_type == "upload"
            else "Preparando arquivo local..."
        )
        update_job_stage(
            job_id,
            status="running",
            stage="preparing_source",
            message=initial_message,
            started=True,
        )

        video_path, source_title = source.ingest(effective_source_type, job["source_value"])
        if source_type == "upload":
            safe_unlink(job["source_value"])
        store.update_job(job_id, source_title=source_title, source_path=video_path)

        video_name = Path(video_path).stem
        audio_path = settings.audio_dir / f"{video_name}.mp3"
        transcript_path = settings.transcripts_dir / f"{video_name}.json"

        update_job_stage(
            job_id,
            status="running",
            stage="extracting_audio",
            message="Extraindo audio...",
        )
        ffmpeg.extract_audio(video_path=video_path, audio_path=str(audio_path))

        update_job_stage(
            job_id,
            status="running",
            stage="transcribing",
            message="Transcrevendo com Whisper...",
        )
        transcript_service = get_transcript_service()
        transcript = transcript_service.transcribe(
            audio_path=str(audio_path),
            output_json_path=str(transcript_path),
        )

        update_job_stage(
            job_id,
            status="running",
            stage="analyzing_context",
            message=f"Analisando contexto com IA local para cortes do tipo {job['cut_style']}...",
        )
        scored_segments = scoring.score_segments(transcript, cut_style=job["cut_style"])
        moments = scoring.merge_top_segments(
            scored_segments=scored_segments,
            top_n=int(job["top_n"]),
            min_clip_seconds=int(job["min_clip_seconds"]),
            max_clip_seconds=int(job["max_clip_seconds"]),
        )

        if not moments:
            update_job_stage(
                job_id,
                status="completed",
                stage="done",
                message="Processamento concluido, mas nenhum corte foi selecionado.",
                finished=True,
            )
            return

        final_clip_paths: list[str] = []

        for index, moment in enumerate(moments, start=1):
            clip_id = uuid4().hex
            raw_clip_path = settings.clips_dir / f"{clip_id}_raw.mp4"
            final_clip_path = settings.clips_dir / f"{clip_id}.mp4"
            subtitle_path = settings.subtitles_dir / f"{clip_id}.srt"
            thumbnail_path = settings.thumbs_dir / f"{clip_id}.jpg"

            update_job_stage(
                job_id,
                status="running",
                stage="cutting",
                message=f"Gerando corte {index}/{len(moments)}...",
            )
            ffmpeg.cut_vertical_clip(
                input_path=video_path,
                output_path=str(raw_clip_path),
                start_sec=moment["start"],
                duration_sec=moment["duration"],
            )

            include_subtitles = bool(job.get("include_subtitles", 1))
            if include_subtitles:
                update_job_stage(
                    job_id,
                    status="running",
                    stage="subtitling",
                    message=f"Legendando corte {index}/{len(moments)}...",
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
                    subtitle_font=job["subtitle_font"],
                    subtitle_color=job["subtitle_color"],
                )
                item_subtitle_path = str(subtitle_path)
            else:
                copy2(raw_clip_path, final_clip_path)
                item_subtitle_path = None
            final_clip_paths.append(str(final_clip_path))

            update_job_stage(
                job_id,
                status="running",
                stage="thumbnail",
                message=f"Gerando thumbnail {index}/{len(moments)}...",
            )
            ffmpeg.make_thumbnail(
                input_path=str(final_clip_path),
                second=1,
                output_path=str(thumbnail_path),
            )

            title = packaging.make_title(job["creator_name"], moment["hook_text"])
            hashtags = packaging.make_hashtags(job["creator_name"])
            hashtags_text = " ".join(hashtags)
            caption = packaging.make_caption(title, hashtags)

            item = {
                "id": clip_id,
                "job_id": job_id,
                "creator_name": job["creator_name"],
                "source_type": source_type,
                "source_title": source_title,
                "source_path": video_path,
                "clip_path": str(final_clip_path),
                "subtitle_path": item_subtitle_path,
                "thumbnail_path": str(thumbnail_path),
                "start_seconds": moment["start"],
                "end_seconds": moment["end"],
                "duration_seconds": moment["duration"],
                "score": moment["score"],
                "title": title,
                "caption": caption,
                "hashtags_text": hashtags_text,
                "notes": moment.get("selection_reason", ""),
                "include_subtitles": include_subtitles,
                "subtitle_font": job["subtitle_font"],
                "subtitle_color": job["subtitle_color"],
                "cut_style": job["cut_style"],
                "board_column": "nao_postados",
                "publish_status": "draft",
            }
            store.add_clip(item)

        update_job_stage(
            job_id,
            status="running",
            stage="assembling_final_video",
            message="Montando video final com os melhores momentos...",
        )
        final_video_path = settings.exports_dir / f"{job_id}_tiktok.mp4"
        final_thumbnail_path = settings.thumbs_dir / f"{job_id}_final.jpg"
        ffmpeg.concat_clips(final_clip_paths, str(final_video_path))
        ffmpeg.make_thumbnail(
            input_path=str(final_video_path),
            second=1,
            output_path=str(final_thumbnail_path),
        )
        final_title = packaging.make_compilation_title(
            creator_name=job["creator_name"],
            source_title=source_title,
            cut_style=job["cut_style"],
            clip_count=len(moments),
        )
        store.update_job(
            job_id,
            final_title=final_title,
            final_video_path=str(final_video_path),
            final_thumbnail_path=str(final_thumbnail_path),
            final_duration_seconds=round(sum(float(moment["duration"]) for moment in moments), 2),
        )

        update_job_stage(
            job_id,
            status="completed",
            stage="done",
            message=f"Concluido com {len(moments)} momento(s) e video final pronto para TikTok.",
            finished=True,
        )
    except Exception as exc:
        update_job_stage(
            job_id,
            status="error",
            stage="error",
            message="Falha no processamento.",
            error_message=normalize_runtime_error(exc),
            finished=True,
        )


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "app_name": settings.app_name},
    )


@app.get("/health")
def health():
    return {"ok": True, "app_name": settings.app_name}


@app.get("/api/jobs")
def list_jobs():
    jobs = [serialize_job(job) for job in store.list_jobs()]
    return {"items": jobs}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = get_job_or_404(job_id)
    clips = [serialize_clip(item) for item in store.list_clips_for_job(job_id)]
    return {"job": serialize_job(job), "clips": clips}


@app.get("/api/jobs/{job_id}/download")
def download_job_asset(job_id: str, kind: str = Query("source")):
    job = get_job_or_404(job_id)
    asset_map = {
        "source": job.get("source_path"),
        "final": job.get("final_video_path"),
        "thumbnail": job.get("final_thumbnail_path"),
    }
    if kind not in asset_map:
        raise HTTPException(status_code=400, detail="Tipo de download invalido")
    path_str = asset_map[kind]
    if not path_str:
        raise HTTPException(status_code=404, detail="Arquivo nao encontrado")
    path = Path(path_str)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Arquivo nao encontrado")
    return FileResponse(path, filename=path.name, media_type="application/octet-stream")


@app.get("/api/board")
def get_board():
    board = store.board()
    columns = {
        column: [serialize_clip(item) for item in board.get(column, [])]
        for column in DEFAULT_COLUMNS
    }
    return {
        "columns": columns,
        "columns_order": DEFAULT_COLUMNS,
        "counts": {column: len(items) for column, items in columns.items()},
    }


@app.post("/api/process", status_code=202)
def process_video(payload: ProcessRequest):
    if payload.source_type not in {"url", "local"}:
        raise HTTPException(status_code=400, detail="Tipo de fonte invalido")
    job = build_job_payload(
        creator_name=payload.creator_name,
        source_type=payload.source_type,
        source_value=payload.source_value,
        include_subtitles=payload.include_subtitles,
        subtitle_font=payload.subtitle_font,
        subtitle_color=payload.subtitle_color,
        cut_style=payload.cut_style,
        top_n=payload.top_n,
        min_clip_seconds=payload.min_clip_seconds,
        max_clip_seconds=payload.max_clip_seconds,
    )
    created = queue_job(job)
    return {"job": serialize_job(created)}


@app.post("/api/process-upload", status_code=202)
def process_upload(
    creator_name: str = Form(...),
    include_subtitles: bool = Form(True),
    subtitle_font: str = Form("Arial"),
    subtitle_color: str = Form("yellow"),
    cut_style: str = Form("viral"),
    top_n: int = Form(5),
    min_clip_seconds: int = Form(20),
    max_clip_seconds: int = Form(50),
    upload_file: UploadFile = File(...),
):
    original_name = Path(upload_file.filename or "upload.mp4").name
    target_path = settings.uploads_dir / f"{uuid4().hex}_{original_name}"
    with target_path.open("wb") as handle:
        copyfileobj(upload_file.file, handle)

    job = build_job_payload(
        creator_name=creator_name,
        source_type="upload",
        source_value=str(target_path),
        include_subtitles=include_subtitles,
        subtitle_font=subtitle_font,
        subtitle_color=subtitle_color,
        cut_style=cut_style,
        top_n=top_n,
        min_clip_seconds=min_clip_seconds,
        max_clip_seconds=max_clip_seconds,
    )
    created = queue_job(job)
    return {"job": serialize_job(created)}


@app.patch("/api/clips/{clip_id}")
def update_clip(clip_id: str, payload: ClipUpdateRequest):
    existing = get_clip_or_404(clip_id)
    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        return serialize_clip(existing)

    if fields.get("publish_status") == "published":
        fields.setdefault("board_column", "postados")

    updated = store.update_clip(clip_id, **fields)
    if not updated:
        raise HTTPException(status_code=404, detail="Clip nao encontrado")
    return serialize_clip(updated)


@app.post("/api/clips/{clip_id}/move")
def move_clip(clip_id: str, column: str = Query(...)):
    if column not in VALID_COLUMNS:
        raise HTTPException(status_code=400, detail="Coluna invalida")

    updated = store.update_board_column(clip_id, column)
    if not updated:
        raise HTTPException(status_code=404, detail="Clip nao encontrado")

    return {"ok": True, "clip_id": clip_id, "column": column}


@app.delete("/api/clips/{clip_id}")
def delete_clip(clip_id: str):
    clip = store.delete_clip(clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip nao encontrado")

    cleanup_clip_files(clip)
    return {"ok": True, "clip_id": clip_id}


@app.get("/api/clips/{clip_id}/download")
def download_clip_asset(clip_id: str, kind: str = Query("clip")):
    clip = get_clip_or_404(clip_id)
    asset_map = {
        "clip": clip.get("clip_path"),
        "source": clip.get("source_path"),
        "subtitle": clip.get("subtitle_path"),
        "thumbnail": clip.get("thumbnail_path"),
    }
    if kind not in asset_map:
        raise HTTPException(status_code=400, detail="Tipo de download invalido")

    path_str = asset_map[kind]
    if not path_str:
        raise HTTPException(status_code=404, detail="Arquivo nao encontrado")

    path = Path(path_str)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Arquivo nao encontrado")

    return FileResponse(path, filename=path.name, media_type="application/octet-stream")


@app.post("/api/publish")
def publish_clip(payload: PublishRequest):
    clip = get_clip_or_404(payload.clip_id)

    result = publisher.publish(
        clip_path=clip["clip_path"],
        title=clip["title"],
        caption=clip["caption"],
        mode=payload.mode,
    )
    ok = result.get("ok", False)
    if ok and payload.mode == "publish":
        next_status = "published"
    elif ok:
        next_status = "draft"
    else:
        next_status = "failed"

    store.update_publish_status(payload.clip_id, next_status)
    return result
