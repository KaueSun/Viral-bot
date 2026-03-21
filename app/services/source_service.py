from __future__ import annotations

from pathlib import Path
from shutil import copy2
from urllib.parse import urlparse
from uuid import uuid4

from app.config import local_ffmpeg_bin, settings


class SourceService:
    def ingest(self, source_type: str, source_value: str) -> tuple[str, str]:
        """
        Retorna (video_path, source_title)

        source_type='local': copia o arquivo local para data/downloads
        source_type='url': baixa o video na melhor qualidade disponivel sem recompressao
        """
        if source_type == "local":
            return self._ingest_local(source_value)

        if source_type == "url":
            return self._ingest_url(source_value)

        raise ValueError("Tipo de fonte invalido")

    def _ingest_local(self, source_value: str) -> tuple[str, str]:
        src = Path(source_value)
        if not src.exists():
            raise FileNotFoundError(f"Arquivo nao encontrado: {source_value}")

        dest = settings.downloads_dir / src.name
        if src.resolve() != dest.resolve():
            copy2(src, dest)
        return str(dest), src.stem

    def _ingest_url(self, source_value: str) -> tuple[str, str]:
        parsed = urlparse(source_value)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("URL invalida")

        try:
            from yt_dlp import YoutubeDL
            from yt_dlp.utils import DownloadError
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError(
                "Dependencia ausente para download por URL. Instale o pacote yt-dlp."
            ) from exc

        ydl_base_opts = {
            "format": "bv*+ba/b",
            "noplaylist": True,
            "restrictfilenames": True,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
        }
        if local_ffmpeg_bin.exists():
            ydl_base_opts["ffmpeg_location"] = str(local_ffmpeg_bin)

        try:
            with YoutubeDL(ydl_base_opts) as ydl:
                info = ydl.extract_info(source_value, download=False)
        except DownloadError as exc:
            raise RuntimeError(f"Falha ao consultar URL: {exc}") from exc

        if not info:
            raise RuntimeError("Nao foi possivel obter informacoes do video informado.")

        if "entries" in info:
            info = next((entry for entry in info["entries"] if entry), None)
            if not info:
                raise RuntimeError("A URL nao retornou um video valido para download.")

        video_id = info.get("id")
        cached_video = self._find_existing_download(video_id)
        if cached_video:
            source_title = info.get("title") or cached_video.stem
            return str(cached_video), source_title

        download_prefix = video_id or "video"
        ydl_download_opts = dict(ydl_base_opts)
        ydl_download_opts["outtmpl"] = str(
            settings.downloads_dir / f"{download_prefix}_{uuid4().hex}.%(ext)s"
        )

        try:
            with YoutubeDL(ydl_download_opts) as ydl:
                info = ydl.extract_info(source_value, download=True)
        except DownloadError as exc:
            raise RuntimeError(f"Falha ao baixar URL: {exc}") from exc

        if "entries" in info:
            info = next((entry for entry in info["entries"] if entry), None)
            if not info:
                raise RuntimeError("A URL nao retornou um video valido para download.")

        video_path = self._resolve_download_path(info)
        source_title = info.get("title") or video_path.stem
        return str(video_path), source_title

    def _resolve_download_path(self, info: dict) -> Path:
        candidates: list[Path] = []

        requested_downloads = info.get("requested_downloads") or []
        for item in requested_downloads:
            filepath = item.get("filepath")
            if filepath:
                candidates.append(Path(filepath))

        filename = info.get("_filename")
        if filename:
            candidates.append(Path(filename))

        video_id = info.get("id")
        ext = info.get("ext")
        if video_id and ext:
            candidates.append(settings.downloads_dir / f"{video_id}.{ext}")
        if video_id:
            candidates.extend(sorted(settings.downloads_dir.glob(f"{video_id}.*")))

        for candidate in candidates:
            if candidate.exists():
                return candidate

        raise FileNotFoundError(
            "Video baixado, mas o arquivo final nao foi encontrado em data/downloads."
        )

    def _find_existing_download(self, video_id: str | None) -> Path | None:
        if not video_id:
            return None

        candidates = sorted(
            settings.downloads_dir.glob(f"{video_id}*"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        for candidate in candidates:
            if not candidate.is_file():
                continue
            if candidate.suffix in {".part", ".tmp", ".ytdl"}:
                continue
            return candidate
        return None
