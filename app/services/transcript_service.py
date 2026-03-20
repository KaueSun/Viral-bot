import json
import os
import whisper
from pathlib import Path

from app.config import settings
from app.services.ffmpeg_service import FFmpegService


class TranscriptService:
    def __init__(self) -> None:
        ffmpeg_dir = FFmpegService().get_ffmpeg_dir()
        current_path = os.environ.get("PATH", "")
        if ffmpeg_dir not in current_path.split(os.pathsep):
            os.environ["PATH"] = os.pathsep.join([ffmpeg_dir, current_path]) if current_path else ffmpeg_dir
        self.model = whisper.load_model(settings.whisper_model)

    def transcribe(self, audio_path: str, output_json_path: str) -> dict:
        result = self.model.transcribe(audio_path, language="pt")
        Path(output_json_path).write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return result
