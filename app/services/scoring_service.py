from __future__ import annotations

import re
import unicodedata
from typing import Any


STOPWORDS = {
    "a", "as", "o", "os", "um", "uma", "uns", "umas", "de", "da", "do", "das", "dos",
    "e", "ou", "em", "no", "na", "nos", "nas", "por", "para", "pra", "com", "sem",
    "que", "se", "eu", "voce", "voces", "ele", "ela", "eles", "elas", "isso", "isto",
    "aquele", "aquela", "aquilo", "me", "te", "nos", "lhe", "lhes", "meu", "minha",
    "seu", "sua", "mas", "porque", "quando", "como", "onde", "entao", "ai", "tipo",
    "ta", "to", "pra", "foi", "era", "ser", "ter", "tinha", "tem", "vai", "vou",
}

FILLER_WORDS = {
    "tipo", "mano", "cara", "assim", "ne", "nossa", "ta", "ahn", "hum", "aham",
    "meio", "basicamente", "literalmente", "enfim", "sei", "sabe",
}

WEAK_START_MARKERS = (
    "e ", "ai ", "entao ", "mas ", "porque ", "quando ", "que ", "pra ", "para ",
)

WEAK_END_MARKERS = (
    "porque", "quando", "mas", "entao", "pra", "para", "que", "se", "ou",
)

LAUGHTER_MARKERS = ("kkk", "haha", "hahaha", "risada", "rir", "rindo")

STYLE_PROFILES = {
    "viral": {
        "focus": "gancho forte, virada e reacao emocional",
        "signal_phrases": [
            "nao acredito", "meu deus", "olha isso", "que isso", "caraca", "serio",
            "do nada", "na hora", "pior que", "polemica", "absurdo", "vazou",
        ],
        "hook_phrases": [
            "vou te mostrar", "olha isso", "presta atencao", "escuta isso", "mano",
        ],
        "payoff_phrases": [
            "e foi ai", "no final", "resultado", "deu ruim", "aconteceu isso",
        ],
        "emotion_words": [
            "absurdo", "chocante", "inacreditavel", "surreal", "ridiculo",
        ],
        "weights": {
            "signals": 2.4,
            "hook": 1.8,
            "payoff": 1.8,
            "emotion": 1.6,
            "continuity": 1.2,
            "completeness": 1.3,
            "density": 1.0,
        },
    },
    "engracado": {
        "focus": "setup curto, virada e payoff de humor",
        "signal_phrases": [
            "engracado", "piada", "zoeira", "meme", "eu ri", "ri muito", "comedia",
            "humor", "kkk", "hahaha", "risada",
        ],
        "hook_phrases": [
            "olha isso", "escuta essa", "mano", "na moral", "o pior e", "do nada",
        ],
        "payoff_phrases": [
            "eu comecei a rir", "todo mundo riu", "na hora eu ri", "foi muito bom",
            "nao tankei",
        ],
        "emotion_words": [
            "ridiculo", "doido", "maluco", "bizarro", "absurdo",
        ],
        "weights": {
            "signals": 2.6,
            "hook": 1.4,
            "payoff": 2.2,
            "emotion": 1.4,
            "continuity": 1.2,
            "completeness": 1.4,
            "density": 0.8,
        },
    },
    "chocante": {
        "focus": "tensao, gravidade e revelacao clara",
        "signal_phrases": [
            "grave", "chocante", "absurdo", "escandalo", "vazou", "bizarro",
            "urgente", "revoltante", "inacreditavel", "perigo", "ameaca",
        ],
        "hook_phrases": [
            "voce nao vai acreditar", "presta atencao", "olha isso", "escuta isso",
        ],
        "payoff_phrases": [
            "o problema e", "o pior foi", "acabou nisso", "deu nisso", "o resultado foi",
        ],
        "emotion_words": [
            "grave", "perigoso", "chocante", "revoltante", "escandalo",
        ],
        "weights": {
            "signals": 2.8,
            "hook": 1.7,
            "payoff": 1.9,
            "emotion": 1.7,
            "continuity": 1.1,
            "completeness": 1.4,
            "density": 0.9,
        },
    },
    "informativo": {
        "focus": "explicacao clara, contexto suficiente e conclusao util",
        "signal_phrases": [
            "como", "porque", "explicando", "aprenda", "dica", "passo a passo",
            "resumo", "estrategia", "tecnica", "funciona assim", "o segredo e",
        ],
        "hook_phrases": [
            "vou te explicar", "como funciona", "seguinte", "a ideia e", "presta atencao",
        ],
        "payoff_phrases": [
            "por isso", "entao faz assim", "o ponto e", "resumindo", "na pratica",
        ],
        "emotion_words": [
            "importante", "essencial", "fundamental", "melhor", "certo",
        ],
        "weights": {
            "signals": 2.2,
            "hook": 1.3,
            "payoff": 1.8,
            "emotion": 0.8,
            "continuity": 1.5,
            "completeness": 1.8,
            "density": 1.5,
        },
    },
}


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return ascii_text.lower().strip()


def tokenize(text: str) -> list[str]:
    return [
        token for token in re.findall(r"[a-z0-9']+", normalize_text(text))
        if len(token) > 2 and token not in STOPWORDS
    ]


def count_phrase_hits(text: str, phrases: list[str]) -> int:
    return sum(1 for phrase in phrases if normalize_text(phrase) in text)


def overlap_ratio(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


class ScoringService:
    def score_segments(self, transcript: dict[str, Any], cut_style: str = "viral") -> list[dict]:
        prepared = self._prepare_segments(transcript.get("segments", []))
        profile = STYLE_PROFILES.get(cut_style, STYLE_PROFILES["viral"])
        candidates: list[dict[str, Any]] = []

        for start_idx in range(len(prepared)):
            duration = 0.0
            for end_idx in range(start_idx, min(len(prepared), start_idx + 6)):
                duration += prepared[end_idx]["duration"]
                if duration > 65:
                    break
                if duration < 8:
                    continue
                window = prepared[start_idx:end_idx + 1]
                candidates.append(self._score_window(window, profile, cut_style))

        return sorted(candidates, key=lambda item: item["score"], reverse=True)

    def merge_top_segments(
        self,
        scored_segments: list[dict],
        top_n: int,
        min_clip_seconds: int,
        max_clip_seconds: int,
    ) -> list[dict]:
        selected: list[dict[str, Any]] = []

        for candidate in scored_segments:
            refined = self._refine_window(candidate, min_clip_seconds, max_clip_seconds)
            if self._overlaps_existing(refined, selected):
                continue

            selected.append({
                "start": round(refined["start"], 2),
                "end": round(refined["end"], 2),
                "duration": round(refined["duration"], 2),
                "score": round(candidate["score"], 2),
                "hook_text": candidate["text"][:160],
                "cut_style": candidate.get("cut_style", "viral"),
                "selection_reason": candidate["selection_reason"],
            })
            if len(selected) >= top_n:
                break

        return selected

    def _prepare_segments(self, segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        prepared: list[dict[str, Any]] = []
        for index, segment in enumerate(segments):
            text = (segment.get("text") or "").strip()
            if not text:
                continue

            start = float(segment.get("start", 0.0))
            end = float(segment.get("end", start))
            duration = max(0.1, end - start)
            normalized_text = normalize_text(text)
            tokens = tokenize(text)
            token_set = set(tokens)
            word_count = len(re.findall(r"\w+", text, flags=re.UNICODE))

            prepared.append({
                "index": index,
                "text": text,
                "normalized_text": normalized_text,
                "tokens": tokens,
                "token_set": token_set,
                "start": start,
                "end": end,
                "duration": duration,
                "word_count": word_count,
            })
        return prepared

    def _score_window(self, window: list[dict[str, Any]], profile: dict[str, Any], cut_style: str) -> dict:
        text = " ".join(segment["text"] for segment in window).strip()
        normalized_text = normalize_text(text)
        combined_tokens = [token for segment in window for token in segment["tokens"]]
        unique_tokens = set(combined_tokens)
        duration = window[-1]["end"] - window[0]["start"]

        signal_hits = count_phrase_hits(normalized_text, profile["signal_phrases"])
        hook_hits = count_phrase_hits(
            " ".join(segment["normalized_text"] for segment in window[:2]),
            profile["hook_phrases"],
        )
        payoff_hits = count_phrase_hits(
            " ".join(segment["normalized_text"] for segment in window[-2:]),
            profile["payoff_phrases"],
        )
        emotion_hits = count_phrase_hits(normalized_text, profile["emotion_words"])
        laughter_hits = count_phrase_hits(normalized_text, list(LAUGHTER_MARKERS))

        punctuation_score = min(text.count("!") * 0.35 + text.count("?") * 0.25, 2.2)
        density_score = min((len(unique_tokens) / max(1, len(combined_tokens))) * 5.0, 2.0)
        filler_penalty = self._filler_penalty(combined_tokens)
        continuity_score = self._continuity_score(window)
        completeness_score = self._completeness_score(window, duration)
        style_bonus = self._style_bonus(
            cut_style=cut_style,
            signal_hits=signal_hits,
            hook_hits=hook_hits,
            payoff_hits=payoff_hits,
            emotion_hits=emotion_hits,
            laughter_hits=laughter_hits,
            density_score=density_score,
        )
        boundary_penalty = self._boundary_penalty(window)

        weights = profile["weights"]
        score = (
            signal_hits * weights["signals"]
            + hook_hits * weights["hook"]
            + payoff_hits * weights["payoff"]
            + (emotion_hits + laughter_hits) * weights["emotion"]
            + continuity_score * weights["continuity"]
            + completeness_score * weights["completeness"]
            + density_score * weights["density"]
            + punctuation_score
            + style_bonus
            - filler_penalty
            - boundary_penalty
        )

        reasons = self._build_reason_parts(
            cut_style=cut_style,
            signal_hits=signal_hits,
            hook_hits=hook_hits,
            payoff_hits=payoff_hits,
            continuity_score=continuity_score,
            completeness_score=completeness_score,
            density_score=density_score,
            laughter_hits=laughter_hits,
        )

        return {
            "text": text,
            "start": window[0]["start"],
            "end": window[-1]["end"],
            "duration": duration,
            "score": round(score, 2),
            "cut_style": cut_style,
            "selection_reason": "IA local priorizou este trecho porque " + ", ".join(reasons) + ".",
        }

    def _style_bonus(
        self,
        *,
        cut_style: str,
        signal_hits: int,
        hook_hits: int,
        payoff_hits: int,
        emotion_hits: int,
        laughter_hits: int,
        density_score: float,
    ) -> float:
        if cut_style == "engracado":
            return laughter_hits * 1.8 + payoff_hits * 0.9
        if cut_style == "chocante":
            return emotion_hits * 1.2 + max(signal_hits - 1, 0) * 0.6
        if cut_style == "informativo":
            return density_score * 1.4 + payoff_hits * 0.5
        return hook_hits * 0.7 + payoff_hits * 0.7 + emotion_hits * 0.4

    def _filler_penalty(self, tokens: list[str]) -> float:
        if not tokens:
            return 1.0
        filler_count = sum(1 for token in tokens if token in FILLER_WORDS)
        return min((filler_count / len(tokens)) * 4.0, 1.8)

    def _continuity_score(self, window: list[dict[str, Any]]) -> float:
        if len(window) < 2:
            return 0.2

        overlaps = [
            overlap_ratio(left["token_set"], right["token_set"])
            for left, right in zip(window, window[1:])
        ]
        if not overlaps:
            return 0.2
        return min((sum(overlaps) / len(overlaps)) * 10.0, 2.0)

    def _completeness_score(self, window: list[dict[str, Any]], duration: float) -> float:
        start_text = window[0]["normalized_text"]
        end_text = window[-1]["normalized_text"]

        score = 0.0
        if len(window) >= 2:
            score += 0.8
        if 15 <= duration <= 42:
            score += 0.9
        if not start_text.startswith(WEAK_START_MARKERS):
            score += 0.5
        if not end_text.endswith(WEAK_END_MARKERS):
            score += 0.6
        if any(marker in end_text for marker in ("por isso", "resultado", "resumindo", "foi ai")):
            score += 0.5
        return min(score, 2.6)

    def _boundary_penalty(self, window: list[dict[str, Any]]) -> float:
        start_text = window[0]["normalized_text"]
        end_text = window[-1]["normalized_text"]
        penalty = 0.0
        if start_text.startswith(WEAK_START_MARKERS):
            penalty += 0.6
        if end_text.endswith(WEAK_END_MARKERS):
            penalty += 0.8
        if len(window) == 1 and window[0]["word_count"] < 8:
            penalty += 0.6
        return penalty

    def _build_reason_parts(
        self,
        *,
        cut_style: str,
        signal_hits: int,
        hook_hits: int,
        payoff_hits: int,
        continuity_score: float,
        completeness_score: float,
        density_score: float,
        laughter_hits: int,
    ) -> list[str]:
        reasons: list[str] = []
        if hook_hits:
            reasons.append("abre com um gancho forte")
        if payoff_hits:
            reasons.append("fecha com payoff mais claro")
        if continuity_score >= 0.9:
            reasons.append("mantem o mesmo assunto sem parecer aleatorio")
        if completeness_score >= 1.5:
            reasons.append("tem contexto suficiente para fazer sentido sozinho")
        if signal_hits:
            reasons.append(f"combina com o perfil {cut_style}")
        if cut_style == "engracado" and laughter_hits:
            reasons.append("tem sinais de humor e reacao")
        if cut_style == "informativo" and density_score >= 1.1:
            reasons.append("entrega informacao densa em pouco tempo")
        if not reasons:
            reasons.append("equilibra contexto, continuidade e gancho")
        return reasons[:4]

    def _refine_window(self, candidate: dict[str, Any], min_clip_seconds: int, max_clip_seconds: int) -> dict[str, float]:
        start = max(0.0, candidate["start"] - 1.6)
        end = candidate["end"] + 1.2
        duration = end - start

        if duration < min_clip_seconds:
            deficit = min_clip_seconds - duration
            start = max(0.0, start - (deficit * 0.45))
            end = end + (deficit * 0.55)
            duration = end - start

        if duration > max_clip_seconds:
            overflow = duration - max_clip_seconds
            start = start + (overflow * 0.35)
            end = end - (overflow * 0.65)
            duration = end - start

        return {
            "start": start,
            "end": end,
            "duration": max(0.1, duration),
        }

    def _overlaps_existing(self, candidate: dict[str, float], existing: list[dict[str, Any]]) -> bool:
        for item in existing:
            if candidate["start"] < item["end"] and candidate["end"] > item["start"]:
                return True
        return False
