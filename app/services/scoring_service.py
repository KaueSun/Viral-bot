from typing import Any

STRONG_KEYWORDS = [
    "não acredito", "meu deus", "caraca", "mentira", "polêmica",
    "olha isso", "sério", "absurdo", "vazou", "que isso"
]


class ScoringService:
    def score_segments(self, transcript: dict[str, Any]) -> list[dict]:
        segments = transcript.get("segments", [])
        scored = []

        for seg in segments:
            text = seg.get("text", "").strip().lower()
            start = float(seg.get("start", 0))
            end = float(seg.get("end", 0))
            duration = max(0.1, end - start)

            keyword_score = sum(1 for kw in STRONG_KEYWORDS if kw in text) * 2.0
            punctuation_score = text.count("!") * 0.8 + text.count("?") * 0.6
            density_score = min(len(text.split()) / 8.0, 2.0)
            duration_score = 1.0 if 4 <= duration <= 14 else 0.3
            score = keyword_score + punctuation_score + density_score + duration_score

            scored.append({
                "text": text,
                "start": start,
                "end": end,
                "duration": duration,
                "score": round(score, 2),
            })

        return sorted(scored, key=lambda x: x["score"], reverse=True)

    def merge_top_segments(
        self,
        scored_segments: list[dict],
        top_n: int,
        min_clip_seconds: int,
        max_clip_seconds: int,
    ) -> list[dict]:
        top = scored_segments[:top_n]
        merged = []
        for seg in top:
            desired = max(min_clip_seconds, min(max_clip_seconds, seg["duration"] + 8))
            start = max(0.0, seg["start"] - 3)
            end = start + desired
            merged.append({
                "start": round(start, 2),
                "end": round(end, 2),
                "duration": round(desired, 2),
                "score": seg["score"],
                "hook_text": seg["text"][:160],
            })
        return merged