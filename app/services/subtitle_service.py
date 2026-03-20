from pathlib import Path


def sec_to_srt(seconds: float) -> str:
    ms = int((seconds % 1) * 1000)
    total = int(seconds)
    s = total % 60
    m = (total // 60) % 60
    h = total // 3600
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


class SubtitleService:
    def clip_to_srt(self, transcript: dict, clip_start: float, clip_end: float, srt_path: str) -> None:
        lines: list[str] = []
        index = 1
        for seg in transcript.get("segments", []):
            seg_start = float(seg.get("start", 0))
            seg_end = float(seg.get("end", 0))
            if seg_end < clip_start or seg_start > clip_end:
                continue

            start = max(seg_start, clip_start) - clip_start
            end = min(seg_end, clip_end) - clip_start
            text = seg.get("text", "").strip()
            if not text:
                continue

            lines.append(
                f"{index}\n{sec_to_srt(start)} --> {sec_to_srt(end)}\n{text}\n"
            )
            index += 1

        Path(srt_path).write_text("\n".join(lines), encoding="utf-8")