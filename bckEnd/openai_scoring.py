from __future__ import annotations

import json
import os
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

SYSTEM_PROMPT = (
    "You convert a user's mood text into a PARTIAL Spotify audio-feature target object.\n"
    "Return ONLY JSON. Use null for unspecified features. Do NOT include key.\n"
    "Rules:\n"
    "- If explicit_allowed is false, explicit must be false.\n"
    "- Provided values must obey ranges:\n"
    "  danceability, energy, speechiness, acousticness, instrumentalness, liveness, valence in [0,1]\n"
    "  tempo integer in [60,180]\n"
    "  loudness float in [-20,-3]\n"
    "  mode 0 or 1\n"
    "Return JSON with keys:\n"
    "explicit, danceability, energy, loudness, mode, speechiness, acousticness, "
    "instrumentalness, liveness, valence, tempo"
)

USER_PROMPT_TEMPLATE = 'Mood text: "{text}"\nexplicit_allowed: {explicit_allowed}'

_ZERO_ONE_FEATURES = (
    "danceability",
    "energy",
    "speechiness",
    "acousticness",
    "instrumentalness",
    "liveness",
    "valence",
)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(int(value))
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class PartialFeatures(BaseModel):
    model_config = ConfigDict(extra="ignore")

    explicit: bool = False
    danceability: float | None = None
    energy: float | None = None
    loudness: float | None = None
    mode: int | None = None
    speechiness: float | None = None
    acousticness: float | None = None
    instrumentalness: float | None = None
    liveness: float | None = None
    valence: float | None = None
    tempo: int | None = None

    @field_validator("explicit", mode="before")
    @classmethod
    def _coerce_explicit(cls, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "y", "t"}:
                return True
            if lowered in {"false", "0", "no", "n", "f"}:
                return False
        return False

    @field_validator(*_ZERO_ONE_FEATURES, mode="before")
    @classmethod
    def _coerce_zero_one(cls, value: Any) -> float | None:
        num = _coerce_float(value)
        if num is None:
            return None
        return _clamp(num, 0.0, 1.0)

    @field_validator("loudness", mode="before")
    @classmethod
    def _coerce_loudness(cls, value: Any) -> float | None:
        num = _coerce_float(value)
        if num is None:
            return None
        return _clamp(num, -20.0, -3.0)

    @field_validator("tempo", mode="before")
    @classmethod
    def _coerce_tempo(cls, value: Any) -> int | None:
        num = _coerce_float(value)
        if num is None:
            return None
        return int(_clamp(round(num), 60, 180))

    @field_validator("mode", mode="before")
    @classmethod
    def _coerce_mode(cls, value: Any) -> int | None:
        num = _coerce_float(value)
        if num is None:
            return None
        return 1 if round(num) >= 1 else 0


def _fallback_partial() -> dict[str, Any]:
    return PartialFeatures(explicit=False).model_dump()


def _validate_partial_payload(payload: Any, explicit_allowed: bool) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _fallback_partial()

    try:
        model = PartialFeatures.model_validate(payload)
    except Exception:
        return _fallback_partial()

    if not explicit_allowed:
        model.explicit = False

    return model.model_dump()


def score_text_to_partial_features(text: str, explicit_allowed: bool) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("OpenAI SDK is not installed. Install package 'openai'.") from exc

    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    user_prompt = USER_PROMPT_TEMPLATE.format(
        text=(text or "").replace('"', '\\"'),
        explicit_allowed=str(bool(explicit_allowed)).lower(),
    )

    response = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )

    content = ""
    if response.choices and response.choices[0].message:
        content = response.choices[0].message.content or ""

    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return _fallback_partial()

    return _validate_partial_payload(payload, explicit_allowed=explicit_allowed)
