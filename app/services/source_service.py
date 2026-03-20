from pathlib import Path
from shutil import copy2
from urllib.parse import urlparse
from yt_dlp import YoutubeDL
from app.config import settings


class SourceService:
    def ingest(self, source_type: str, source_value: str) -> tuple[str, str]:
        """
        Retorna (video_path, source_title)
        """

        # 📁 ARQUIVO LOCAL
        if source_type == "local":
            src = Path(source_value)
            if not src.exists():
                raise FileNotFoundError(f"Arquivo não encontrado: {source_value}")

            dest = settings.downloads_dir / src.name
            copy2(src, dest)

            return str(dest), src.stem

        # 🌐 URL (AQUI ESTÁ O PULO DO GATO)
        parsed = urlparse(source_value)
        if not parsed.scheme:
            raise ValueError("URL inválida")

        output_template = str(settings.downloads_dir / "%(title).120s.%(ext)s")

        ydl_opts = {
            "outtmpl": output_template,
            "format": "mp4/bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
            "noplaylist": True,
            "quiet": False,  # deixa true depois
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(source_value, download=True)

            downloaded_path = ydl.prepare_filename(info)

            # força mp4
            final_path = str(Path(downloaded_path).with_suffix(".mp4"))

            title = info.get("title") or Path(final_path).stem

            return final_path, title