from __future__ import annotations

import re
from pathlib import Path
from typing import Any


MAX_WORDS_PER_CAPTION = 4
MAX_CHARS_PER_CAPTION = 24
MAX_CAPTION_DURATION = 1.8
MIN_CAPTION_DURATION = 0.5


def sec_to_srt(seconds: float) -> str:
    ms = int((seconds % 1) * 1000)
    total = int(seconds)
    s = total % 60
    m = (total // 60) % 60
    h = total // 3600
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


class SubtitleService:
    def clip_to_srt(self, transcript: dict[str, Any], clip_start: float, clip_end: float, srt_path: str) -> None:
        words = self._collect_words(transcript, clip_start, clip_end)
        captions = self._group_words_into_captions(words, clip_end - clip_start)

        lines: list[str] = []
        for index, caption in enumerate(captions, start=1):
            lines.append(
                f"{index}\n"
                f"{sec_to_srt(caption['start'])} --> {sec_to_srt(caption['end'])}\n"
                f"{caption['text']}\n"
            )

        Path(srt_path).write_text("\n".join(lines), encoding="utf-8")

    def _collect_words(self, transcript: dict[str, Any], clip_start: float, clip_end: float) -> list[dict[str, float | str]]:
        words: list[dict[str, float | str]] = []

        for segment in transcript.get("segments", []):
            seg_start = float(segment.get("start", 0.0))
            seg_end = float(segment.get("end", 0.0))
            if seg_end < clip_start or seg_start > clip_end:
                continue

            segment_words = segment.get("words") or self._approximate_words(segment)
            for word in segment_words:
                raw_text = str(word.get("word", "")).strip()
                if not raw_text:
                    continue

                word_start = float(word.get("start", seg_start))
                word_end = float(word.get("end", word_start + 0.2))
                if word_end < clip_start or word_start > clip_end:
                    continue

                words.append({
                    "text": self._clean_word(raw_text),
                    "start": max(word_start, clip_start) - clip_start,
                    "end": min(word_end, clip_end) - clip_start,
                })

        return words

    def _approximate_words(self, segment: dict[str, Any]) -> list[dict[str, float | str]]:
        text = str(segment.get("text", "")).strip()
        tokens = [token for token in re.split(r"\s+", text) if token]
        if not tokens:
            return []

        seg_start = float(segment.get("start", 0.0))
        seg_end = float(segment.get("end", seg_start + 0.5))
        duration = max(0.2, seg_end - seg_start)
        step = duration / len(tokens)

        words = []
        for index, token in enumerate(tokens):
            start = seg_start + (index * step)
            end = seg_start + ((index + 1) * step)
            words.append({
                "word": token,
                "start": start,
                "end": end,
            })
        return words

    def _group_words_into_captions(
        self,
        words: list[dict[str, float | str]],
        clip_duration: float,
    ) -> list[dict[str, float | str]]:
        if not words:
            return []

        captions: list[dict[str, float | str]] = []
        current: list[dict[str, float | str]] = []

        for word in words:
            candidate = current + [word]
            candidate_text = " ".join(str(item["text"]) for item in candidate).strip()
            candidate_duration = float(candidate[-1]["end"]) - float(candidate[0]["start"])

            should_flush = False
            if current:
                if len(candidate) > MAX_WORDS_PER_CAPTION:
                    should_flush = True
                elif len(candidate_text) > MAX_CHARS_PER_CAPTION:
                    should_flush = True
                elif candidate_duration > MAX_CAPTION_DURATION:
                    should_flush = True
                elif str(current[-1]["text"]).endswith((".", "!", "?")):
                    should_flush = True

            if should_flush:
                captions.append(self._caption_from_words(current, clip_duration))
                current = [word]
            else:
                current = candidate

        if current:
            captions.append(self._caption_from_words(current, clip_duration))

        return captions

    def _caption_from_words(
        self,
        words: list[dict[str, float | str]],
        clip_duration: float,
    ) -> dict[str, float | str]:
        start = float(words[0]["start"])
        end = float(words[-1]["end"])
        if end - start < MIN_CAPTION_DURATION:
            end = min(clip_duration, start + MIN_CAPTION_DURATION)

        tokens = [str(word["text"]).upper() for word in words]
        if len(tokens) >= 3:
            split_index = len(tokens) // 2
            text = " ".join(tokens[:split_index]) + "\n" + " ".join(tokens[split_index:])
        else:
            text = " ".join(tokens)

        return {
            "start": start,
            "end": end,
            "text": text.strip(),
        }

    def _clean_word(self, word: str) -> str:
        cleaned = re.sub(r"\s+", " ", word).strip()
        return cleaned
