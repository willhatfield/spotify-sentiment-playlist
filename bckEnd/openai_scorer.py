from typing import Literal, Optional

from pydantic import BaseModel, Field

try:
    from .config import OPENAI_API_KEY, OPENAI_MODEL
except ImportError:
    from config import OPENAI_API_KEY, OPENAI_MODEL


class MoodVector(BaseModel):
    """All values are normalized to [0,1] for audio-feature matching."""

    valence: float = Field(..., ge=0.0, le=1.0, description="Sad->happy")
    energy: float = Field(..., ge=0.0, le=1.0, description="Low->high intensity")
    danceability: float = Field(..., ge=0.0, le=1.0)
    tempo: float = Field(..., ge=0.0, le=1.0, description="0=slow, 1=fast")
    acousticness: float = Field(..., ge=0.0, le=1.0, description="0=electronic, 1=acoustic")
    instrumentalness: float = Field(..., ge=0.0, le=1.0, description="0=vocal, 1=instrumental")


class MoodPlan(BaseModel):
    start: MoodVector
    end: MoodVector
    start_label: str = Field(..., description="Short phrase like 'stressed, disappointed'")
    end_label: str = Field(..., description="Short phrase like 'motivated, confident'")
    safety_note: Optional[str] = Field(None, description="Optional safety/system note")


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _looks_like_placeholder(value: str) -> bool:
    text = (value or "").strip().lower()
    if not text:
        return True
    if text.startswith("your_"):
        return True
    return text in {"change-me", "replace-me", "todo"}


def _count_matches(text: str, words: set[str]) -> int:
    return sum(1 for word in words if word in text)


def _fallback_end_vector(mode: str) -> MoodVector:
    presets = {
        "uplift": MoodVector(
            valence=0.82,
            energy=0.78,
            danceability=0.70,
            tempo=0.74,
            acousticness=0.24,
            instrumentalness=0.20,
        ),
        "focus": MoodVector(
            valence=0.58,
            energy=0.55,
            danceability=0.34,
            tempo=0.56,
            acousticness=0.36,
            instrumentalness=0.72,
        ),
        "calm": MoodVector(
            valence=0.62,
            energy=0.30,
            danceability=0.36,
            tempo=0.28,
            acousticness=0.56,
            instrumentalness=0.55,
        ),
        "gym": MoodVector(
            valence=0.76,
            energy=0.92,
            danceability=0.84,
            tempo=0.88,
            acousticness=0.14,
            instrumentalness=0.12,
        ),
        "sleep": MoodVector(
            valence=0.48,
            energy=0.12,
            danceability=0.14,
            tempo=0.10,
            acousticness=0.74,
            instrumentalness=0.70,
        ),
        "rage_release": MoodVector(
            valence=0.66,
            energy=0.58,
            danceability=0.46,
            tempo=0.54,
            acousticness=0.30,
            instrumentalness=0.34,
        ),
    }
    return presets.get(mode, presets["uplift"])


def _fallback_start_vector(user_text: str) -> MoodVector:
    text = (user_text or "").lower()

    positive = _count_matches(text, {"happy", "hopeful", "good", "great", "excited", "optimistic", "confident"})
    negative = _count_matches(text, {"sad", "down", "bad", "depressed", "angry", "upset", "frustrated", "stressed", "anxious"})
    tired = _count_matches(text, {"tired", "sleepy", "exhausted", "burnt out", "drained"})
    energetic = _count_matches(text, {"energized", "hyped", "active", "pumped", "motivated"})
    calm_words = _count_matches(text, {"calm", "steady", "peaceful", "relaxed"})
    focus_words = _count_matches(text, {"focus", "study", "work", "concentrate", "productive"})
    party_words = _count_matches(text, {"party", "dance", "club", "celebrate"})

    valence = _clamp01(0.50 + 0.08 * (positive - negative))
    energy = _clamp01(0.52 + 0.08 * (energetic - tired) + 0.04 * (negative - calm_words))
    danceability = _clamp01(0.50 + 0.05 * (party_words + energetic - tired))
    tempo = _clamp01(0.50 + 0.06 * (energetic - tired))
    acousticness = _clamp01(0.42 + 0.06 * (calm_words + tired - energetic))
    instrumentalness = _clamp01(0.34 + 0.07 * (focus_words + calm_words - party_words))

    return MoodVector(
        valence=valence,
        energy=energy,
        danceability=danceability,
        tempo=tempo,
        acousticness=acousticness,
        instrumentalness=instrumentalness,
    )


def _fallback_plan(
    user_text: str,
    goal: str,
    mode: Literal["uplift", "focus", "calm", "gym", "sleep", "rage_release"],
    reason: str,
) -> MoodPlan:
    goal_labels = {
        "uplift": "happier and energized",
        "focus": "focused and productive",
        "calm": "calm and steady",
        "gym": "powerful and motivated",
        "sleep": "sleepy and relaxed",
        "rage_release": "released and stable",
    }

    start_label = (user_text or "current mood").strip()[:60] or "current mood"
    end_label = (goal or "").strip()[:60] or goal_labels.get(mode, "better mood")

    return MoodPlan(
        start=_fallback_start_vector(user_text),
        end=_fallback_end_vector(mode),
        start_label=start_label,
        end_label=end_label,
        safety_note=f"Local fallback scoring used ({reason}).",
    )


def score_start_end_with_openai(
    user_text: str,
    goal: str,
    mode: Literal["uplift", "focus", "calm", "gym", "sleep", "rage_release"] = "uplift",
) -> MoodPlan:
    """
    Prefer OpenAI scoring; fall back to deterministic local scoring when unavailable.
    """

    api_key = (OPENAI_API_KEY or "").strip()
    if _looks_like_placeholder(api_key):
        return _fallback_plan(user_text, goal, mode, reason="missing_openai_key")

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        system = (
            "You are a music recommendation scoring system. "
            "Given a user's text describing how they feel, infer a START mood vector. "
            "Given a GOAL and MODE, infer an END mood vector. "
            "Return only values in [0,1] for each field. "
            "The vectors will be used to select songs by audio features from a dataset.\n\n"
            "Guidelines:\n"
            "- valence: sadness(0)->happiness(1)\n"
            "- energy: calm(0)->intense(1)\n"
            "- danceability: low(0)->high(1)\n"
            "- tempo: slow(0)->fast(1)\n"
            "- acousticness: electronic(0)->acoustic(1)\n"
            "- instrumentalness: vocals(0)->instrumental(1)\n\n"
            "MODE intent:\n"
            "- uplift: end should be higher valence + higher energy\n"
            "- focus: moderate energy, moderate valence, lower danceability, higher instrumentalness\n"
            "- calm: lower energy, medium valence, slower tempo\n"
            "- gym: high energy, faster tempo, higher danceability\n"
            "- sleep: very low energy, slow tempo, high acousticness\n"
            "- rage_release: start may be high energy/low valence; end becomes medium energy + higher valence\n"
        )

        user_prompt = (
            f"USER_TEXT:\n{user_text}\n\n"
            f"GOAL:\n{goal}\n\n"
            f"MODE:\n{mode}\n\n"
            "Return start/end vectors consistent with the user's text and the goal."
        )

        resp = client.beta.chat.completions.parse(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
            response_format=MoodPlan,
        )

        plan = resp.choices[0].message.parsed
        if plan is None:
            return _fallback_plan(user_text, goal, mode, reason="unparseable_openai_output")
        return plan
    except Exception as exc:
        return _fallback_plan(user_text, goal, mode, reason=f"openai_error:{exc}")
