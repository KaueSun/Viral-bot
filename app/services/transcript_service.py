import json
import whisper
from pathlib import Path
from app.config import settings


class TranscriptService:
    def __init__(self) -> None:
        self.model = whisper.load_model(settings.whisper_model)

    def transcribe(self, audio_path: str, output_json_path: str) -> dict:
        result = self.model.transcribe(
            audio_path,
            language="pt",
            word_timestamps=True,
            condition_on_previous_text=False,
        )
        Path(output_json_path).write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return result
