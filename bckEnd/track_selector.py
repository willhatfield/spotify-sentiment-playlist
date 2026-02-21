# bckEnd/track_selector.py
from typing import Dict, List, Set

import pandas as pd

try:
    from .config import CSV_PATH
except ImportError:
    from config import CSV_PATH


df = pd.read_csv(CSV_PATH)

REQUIRED = {
    "track_name",
    "artist_name",
    "energy",
    "valence",
    "danceability",
    "tempo",
    "acousticness",
    "instrumentalness",
}
missing = REQUIRED - set(df.columns)
if missing:
    raise ValueError(
        f"CSV missing required columns: {missing}\n"
        f"Found columns: {list(df.columns)[:60]}\n\n"
        "Fix: rename your CSV columns or update REQUIRED/column names."
    )

# Normalize tempo (BPM) into [0,1] based on dataset range
tempo_min = float(df["tempo"].min())
tempo_max = float(df["tempo"].max())
tempo_rng = max(1e-9, tempo_max - tempo_min)


def _tempo01(x: float) -> float:
    return (float(x) - tempo_min) / tempo_rng


def _filter_candidates(target: Dict[str, float], tol: float) -> pd.DataFrame:
    tempo_norm = df["tempo"].apply(_tempo01)
    mask = (
        ((df["energy"] - target["energy"]).abs() < tol)
        & ((df["valence"] - target["valence"]).abs() < tol)
        & ((df["danceability"] - target["danceability"]).abs() < tol)
        & ((tempo_norm - target["tempo"]).abs() < tol)
        & ((df["acousticness"] - target["acousticness"]).abs() < tol)
        & ((df["instrumentalness"] - target["instrumentalness"]).abs() < tol)
    )
    return df[mask]


def pick_tracks_for_arc(
    arc_targets: List[Dict[str, float]],
    total_tracks: int = 30,
    base_tol: float = 0.12,
    max_tol: float = 0.28,
) -> pd.DataFrame:
    """
    Picks tracks stage-by-stage along the arc, ensuring gradual mood transition.

    This function distributes tracks evenly across all stages of the mood arc,
    so that the playlist transitions smoothly from the starting mood to the
    ending mood. Each stage gets approximately equal tracks.

    Args:
        arc_targets: List of mood vectors for each stage (from arc_planner.make_arc).
        total_tracks: Total number of tracks to select (10-60, default 30).
        base_tol: Starting tolerance for feature matching (default 0.12).
        max_tol: Maximum tolerance expansion (default 0.28).

    Returns:
        DataFrame with selected tracks ordered by arc stage.

    Example:
        If arc_targets has 5 stages and total_tracks is 30:
        - Each stage gets 6 tracks (30 / 5 = 6)
        - Tracks are selected to match each stage's mood vector
        - Result is 30 tracks that gradually transition through the 5 stages
    """
    # Validate total_tracks bounds
    total_tracks = max(10, min(60, int(total_tracks)))

    stages = len(arc_targets)
    if stages == 0:
        # Fallback: random selection if no arc targets
        return df.sample(min(total_tracks, len(df)))

    # Calculate even distribution of tracks per stage
    # Example: 30 tracks / 5 stages = 6 per stage
    # With remainder distribution for uneven cases
    per_stage = max(1, total_tracks // stages)
    remainder = total_tracks - per_stage * stages

    used: Set[str] = set()
    picks = []
    stage_track_counts = []  # Track how many songs per stage for verification

    def key(row) -> str:
        """Generate unique key for track de-duplication."""
        if "track_id" in df.columns and pd.notna(row.get("track_id", None)):
            return str(row["track_id"])
        return f'{row["track_name"]}||{row["artist_name"]}'

    for stage_idx, target in enumerate(arc_targets):
        # Distribute remainder to early stages (first N stages get +1 track)
        want = per_stage + (1 if stage_idx < remainder else 0)

        # Progressive tolerance expansion to find enough matching tracks
        tol = base_tol
        cand = _filter_candidates(target, tol)
        while len(cand) < want and tol < max_tol:
            tol += 0.04
            cand = _filter_candidates(target, tol)

        # Fallback to entire dataset if no candidates found
        if len(cand) == 0:
            cand = df

        # Sample more than needed to account for duplicates
        sample_size = min(len(cand), max(want * 4, want + 20))
        sampled = cand.sample(sample_size)
        stage_rows = []

        # Select unique tracks for this stage
        for _, r in sampled.iterrows():
            k = key(r)
            if k in used:
                continue
            used.add(k)
            stage_rows.append(r)
            if len(stage_rows) >= want:
                break

        # Fill remaining slots with random tracks if needed
        fallback_attempts = 0
        max_fallback_attempts = want * 10  # Prevent infinite loop
        while len(stage_rows) < want and fallback_attempts < max_fallback_attempts:
            r = df.sample(1).iloc[0]
            k = key(r)
            if k not in used:
                used.add(k)
                stage_rows.append(r)
            fallback_attempts += 1

        picks.extend(stage_rows)
        stage_track_counts.append(len(stage_rows))

    result_df = pd.DataFrame(picks)

    # Add stage index to each track for debugging/verification
    if len(result_df) > 0:
        stage_indices = []
        track_idx = 0
        for stage_idx, count in enumerate(stage_track_counts):
            stage_indices.extend([stage_idx] * count)
        if len(stage_indices) == len(result_df):
            result_df["_arc_stage"] = stage_indices

    return result_df


# Optional alias if you used older name elsewhere:
pick_tracks = pick_tracks_for_arc
