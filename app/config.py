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
    ffmpeg_binary: str = "ffmpeg"


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
