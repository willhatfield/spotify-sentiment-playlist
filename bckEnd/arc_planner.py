# bckEnd/arc_planner.py
from typing import Dict, List

# Required keys for mood vectors
REQUIRED_KEYS = {"valence", "energy", "danceability", "tempo", "acousticness", "instrumentalness"}


def clamp01(x: float) -> float:
    """Clamp a value to the [0, 1] range."""
    return max(0.0, min(1.0, float(x)))


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation between a and b at parameter t."""
    return a + (b - a) * t


def validate_mood_vector(vec: Dict[str, float], name: str = "vector") -> Dict[str, float]:
    """Validate and normalize a mood vector, filling missing keys with defaults."""
    if not isinstance(vec, dict):
        raise ValueError(f"{name} must be a dictionary, got {type(vec)}")

    validated = {}
    for key in REQUIRED_KEYS:
        value = vec.get(key, 0.5)  # Default to middle value if missing
        validated[key] = clamp01(value)

    return validated


def make_arc(start: Dict[str, float], end: Dict[str, float], stages: int = 5) -> List[Dict[str, float]]:
    """
    Produces a list of per-stage feature targets moving from start -> end.
    Uses linear interpolation (LERP) to create smooth transitions.

    Args:
        start: Starting mood vector with keys like valence, energy, etc.
        end: Ending mood vector with matching keys.
        stages: Number of stages (steps) in the arc. Minimum 2, maximum 10.

    Returns:
        List of mood vectors representing the gradual transition.
        The first element equals start, the last equals end.
    """
    # Validate and clamp stages to reasonable bounds
    stages = max(2, min(10, int(stages)))

    # Validate input vectors
    start_validated = validate_mood_vector(start, "start")
    end_validated = validate_mood_vector(end, "end")

    keys = list(REQUIRED_KEYS)
    arc: List[Dict[str, float]] = []

    for i in range(stages):
        # t ranges from 0.0 (start) to 1.0 (end)
        t = i / (stages - 1) if stages > 1 else 0.0
        arc.append({k: clamp01(lerp(start_validated[k], end_validated[k], t)) for k in keys})

    return arc