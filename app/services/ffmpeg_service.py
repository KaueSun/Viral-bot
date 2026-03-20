import shutil
import subprocess
from pathlib import Path

from app.config import settings


class FFmpegService:
    def __init__(self) -> None:
        self.ffmpeg_binary: str | None = None

    @staticmethod
    def _candidate_paths() -> list[Path]:
        configured = Path(settings.ffmpeg_binary)
        local_app_data = Path.home() / "AppData/Local/Microsoft/WinGet/Packages"
        candidates = [
            configured,
            Path("ffmpeg.exe"),
            Path("bin/ffmpeg.exe"),
            Path("vendor/ffmpeg/ffmpeg.exe"),
            Path("tools/ffmpeg.exe"),
            Path("tools/ffmpeg/bin/ffmpeg.exe"),
        ]
        candidates.extend(local_app_data.glob("Gyan.FFmpeg_*/*/bin/ffmpeg.exe"))
        return candidates

    def _resolve_ffmpeg_binary(self) -> str:
        configured = settings.ffmpeg_binary
        resolved = shutil.which(configured)
        if resolved:
            return resolved

        for candidate in self._candidate_paths():
            if candidate.exists():
                return str(candidate)

        raise RuntimeError(
            "FFmpeg nao foi encontrado. Instale o ffmpeg e adicione-o ao PATH, "
            "ou configure settings.ffmpeg_binary com o caminho completo do executavel."
        )

    def _get_ffmpeg_binary(self) -> str:
        if self.ffmpeg_binary is None:
            self.ffmpeg_binary = self._resolve_ffmpeg_binary()
        return self.ffmpeg_binary

    def get_ffmpeg_dir(self) -> str:
        return str(Path(self._get_ffmpeg_binary()).resolve().parent)

    def run(self, cmd: list[str]) -> None:
        binary = self._get_ffmpeg_binary()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"Nao foi possivel executar o FFmpeg em '{binary}'. "
                "Verifique a instalacao ou ajuste settings.ffmpeg_binary."
            ) from exc
        if result.returncode != 0:
            raise RuntimeError(result.stderr)

    def extract_audio(self, video_path: str, audio_path: str) -> None:
        self.run([
            self._get_ffmpeg_binary(), "-y",
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
            self._get_ffmpeg_binary(), "-y",
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
            self._get_ffmpeg_binary(), "-y",
            "-i", input_path,
            "-vf", subtitle_filter,
            "-c:v", "libx264",
            "-c:a", "aac",
            output_path,
        ])

    def make_thumbnail(self, input_path: str, second: float, output_path: str) -> None:
        self.run([
            self._get_ffmpeg_binary(), "-y",
            "-ss", str(second),
            "-i", input_path,
            "-vframes", "1",
            output_path,
        ])
