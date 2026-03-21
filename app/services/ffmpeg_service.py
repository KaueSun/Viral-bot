import os
import subprocess
import tempfile
from pathlib import Path


def resolve_ffmpeg_binary() -> str:
    override = os.getenv("FFMPEG_BINARY")
    if override:
        return override

    local_bin = Path(".tools/ffmpeg/bin/ffmpeg.exe")
    if local_bin.exists():
        return str(local_bin.resolve())

    return "ffmpeg"


SUBTITLE_COLOR_MAP = {
    "white": "&H00FFFFFF",
    "yellow": "&H0000FFFF",
    "cyan": "&H00FFFF00",
    "green": "&H0000FF00",
    "pink": "&H00FF80FF",
}


class FFmpegService:
    def __init__(self) -> None:
        self.ffmpeg_binary = resolve_ffmpeg_binary()

    @staticmethod
    def run(cmd: list[str]) -> None:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr)

    def extract_audio(self, video_path: str, audio_path: str) -> None:
        self.run([
            self.ffmpeg_binary, "-y",
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
            self.ffmpeg_binary, "-y",
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

    def burn_subtitles(
        self,
        input_path: str,
        srt_path: str,
        output_path: str,
        subtitle_font: str = "Arial",
        subtitle_color: str = "yellow",
    ) -> None:
        subtitle_path = Path(srt_path).resolve().as_posix().replace(":", "\\:")
        primary_color = SUBTITLE_COLOR_MAP.get(subtitle_color, SUBTITLE_COLOR_MAP["yellow"])
        force_style = ",".join([
            f"FontName={subtitle_font}",
            "FontSize=14",
            "Bold=1",
            f"PrimaryColour={primary_color}",
            "OutlineColour=&H00000000",
            "BackColour=&H14000000",
            "BorderStyle=1",
            "Outline=1.4",
            "Shadow=0",
            "Alignment=2",
            "MarginV=88",
            "WrapStyle=2",
        ])
        subtitle_filter = f"subtitles='{subtitle_path}':force_style='{force_style}'"
        self.run([
            self.ffmpeg_binary, "-y",
            "-i", input_path,
            "-vf", subtitle_filter,
            "-c:v", "libx264",
            "-c:a", "aac",
            output_path,
        ])

    def make_thumbnail(self, input_path: str, second: float, output_path: str) -> None:
        self.run([
            self.ffmpeg_binary, "-y",
            "-ss", str(second),
            "-i", input_path,
            "-vframes", "1",
            output_path,
        ])

    def concat_clips(self, input_paths: list[str], output_path: str) -> None:
        if not input_paths:
            raise ValueError("Nenhum clip foi informado para concatenacao.")

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as handle:
            list_path = Path(handle.name)
            for input_path in input_paths:
                escaped = Path(input_path).resolve().as_posix().replace("'", "'\\''")
                handle.write(f"file '{escaped}'\n")

        try:
            self.run([
                self.ffmpeg_binary, "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(list_path),
                "-c:v", "libx264",
                "-c:a", "aac",
                "-preset", "medium",
                "-movflags", "+faststart",
                output_path,
            ])
        finally:
            try:
                list_path.unlink(missing_ok=True)
            except OSError:
                pass
