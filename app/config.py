import os
from pathlib import Path
from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "Viral Cuts Bot v2"
    base_dir: Path = Path(".")
    data_dir: Path = base_dir / "data"
    uploads_dir: Path = data_dir / "uploads"
    downloads_dir: Path = data_dir / "downloads"
    exports_dir: Path = data_dir / "exports"
    audio_dir: Path = data_dir / "audio"
    transcripts_dir: Path = data_dir / "transcripts"
    clips_dir: Path = data_dir / "clips"
    subtitles_dir: Path = data_dir / "subtitles"
    thumbs_dir: Path = data_dir / "thumbs"
    whisper_model: str = "base"


settings = Settings()

local_ffmpeg_bin = (settings.base_dir / ".tools" / "ffmpeg" / "bin").resolve()
if local_ffmpeg_bin.exists():
    current_path = os.environ.get("PATH", "")
    local_ffmpeg_str = str(local_ffmpeg_bin)
    if local_ffmpeg_str not in current_path:
        os.environ["PATH"] = f"{local_ffmpeg_str}{os.pathsep}{current_path}"

for folder in [
    settings.data_dir,
    settings.uploads_dir,
    settings.downloads_dir,
    settings.exports_dir,
    settings.audio_dir,
    settings.transcripts_dir,
    settings.clips_dir,
    settings.subtitles_dir,
    settings.thumbs_dir,
]:
    folder.mkdir(parents=True, exist_ok=True)
