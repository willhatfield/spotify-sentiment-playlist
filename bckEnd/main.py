import asyncio
from typing import Literal
import time
import secrets
import logging
from urllib.parse import quote, urlencode

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel, Field
import httpx

try:
    from .openai_scorer import score_start_end_with_openai
    from .arc_planner import make_arc
    from .config import (
        CORS_ORIGINS,
        SESSION_SECRET,
        FRONTEND_URL,
        SPOTIFY_CLIENT_ID,
        SPOTIFY_CLIENT_SECRET,
        SPOTIFY_REDIRECT_URI,
        SPOTIFY_SCOPES,
    )
    from .track_selector import pick_tracks_for_arc
    from .spotify_client import get_spotify_client, create_playlist, search_track_id, get_spotify_client_from_token
except ImportError:
    from openai_scorer import score_start_end_with_openai
    from arc_planner import make_arc
    from config import (
        CORS_ORIGINS,
        SESSION_SECRET,
        FRONTEND_URL,
        SPOTIFY_CLIENT_ID,
        SPOTIFY_CLIENT_SECRET,
        SPOTIFY_REDIRECT_URI,
        SPOTIFY_SCOPES,
    )
    from track_selector import pick_tracks_for_arc
    from spotify_client import get_spotify_client, create_playlist, search_track_id, get_spotify_client_from_token

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
logger = logging.getLogger(__name__)


def _resolve_cors_origins() -> list[str]:
    # The frontend sends credentials; keep origins explicit and avoid wildcard usage.
    resolved = [origin for origin in CORS_ORIGINS if origin != "*"]
    if resolved:
        return resolved
    return ["http://localhost:8000", "http://localhost:3000"]


def _tracks_preview(selected_df, limit: int = 10) -> list[dict]:
    """Generate a preview list of selected tracks with stage info."""
    preview = []
    for _, row in selected_df.head(limit).iterrows():
        track_info = {
            "name": str(row.get("track_name", "Unknown")),
            "artist": str(row.get("artist_name", "Unknown")),
        }
        # Include arc stage if available
        if "_arc_stage" in row.index:
            track_info["stage"] = int(row["_arc_stage"]) + 1  # 1-indexed for display
        preview.append(track_info)
    return preview


app = FastAPI(title="Mood-Change Spotify Playlist Generator (OpenAI-scored)")

# Session middleware must be added before CORS middleware
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_resolve_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class MoodArcRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000, description="User's current situation/feeling")
    goal: str = Field(..., min_length=1, max_length=300, description="Where they want to end up (e.g., 'motivated and confident')")
    mode: Literal["uplift", "focus", "calm", "gym", "sleep", "rage_release"] = "uplift"
    stages: int = Field(default=5, ge=2, le=10)
    tracks: int = Field(default=30, ge=10, le=60)
    public: bool = True


@app.get("/health")
def health():
    return {"ok": True}


# ============ OAuth Endpoints ============

async def _refresh_token_if_needed(request: Request) -> str | None:
    """Refresh the access token if it's expired. Returns the valid access token or None."""
    access_token = request.session.get("access_token")
    refresh_token = request.session.get("refresh_token")
    expires_at = request.session.get("expires_at", 0)

    if not access_token:
        return None

    # Check if token is expired (with 60 second buffer)
    if time.time() < expires_at - 60:
        return access_token

    # Token is expired, try to refresh
    if not refresh_token:
        return None

    async with httpx.AsyncClient() as client:
        response = await client.post(
            SPOTIFY_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": SPOTIFY_CLIENT_ID,
                "client_secret": SPOTIFY_CLIENT_SECRET,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if response.status_code != 200:
            return None

        token_data = response.json()
        request.session["access_token"] = token_data["access_token"]
        request.session["expires_at"] = time.time() + token_data.get("expires_in", 3600)
        # Spotify may or may not return a new refresh token
        if "refresh_token" in token_data:
            request.session["refresh_token"] = token_data["refresh_token"]

        return token_data["access_token"]


async def _ensure_spotify_profile(request: Request, access_token: str) -> dict | None:
    """Ensure Spotify user profile is present in session; fetch from Spotify API when missing."""
    user_id = request.session.get("user_id")
    if user_id:
        return {
            "id": user_id,
            "display_name": request.session.get("user_display_name"),
            "email": request.session.get("user_email"),
        }

    profile_response = None
    # Spotify occasionally returns a transient 401/429 immediately after code exchange.
    for attempt in range(2):
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            profile_response = await client.get(
                "https://api.spotify.com/v1/me",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
            )

        if profile_response.status_code == 200:
            break
        if attempt == 0 and profile_response.status_code in {401, 429, 500, 502, 503, 504}:
            await asyncio.sleep(0.25)
            continue
        logger.warning(
            "Spotify profile fetch failed status=%s body=%s",
            profile_response.status_code,
            profile_response.text[:400],
        )
        return None

    if profile_response is None:
        return None

    profile = profile_response.json()
    spotify_user_id = profile.get("id")
    if not spotify_user_id:
        logger.warning("Spotify profile response missing id: %s", str(profile)[:400])
        return None

    request.session["user_id"] = spotify_user_id
    request.session["user_display_name"] = profile.get("display_name") or spotify_user_id
    request.session["user_email"] = profile.get("email")
    return profile


@app.get("/auth/login")
def auth_login(request: Request):
    """Redirect to Spotify authorization page."""
    # Always start OAuth from a clean session to avoid stale user/token state.
    request.session.clear()
    state = secrets.token_urlsafe(16)
    request.session["oauth_state"] = state

    params = {
        "client_id": SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "scope": SPOTIFY_SCOPES,
        "state": state,
        # Force Spotify to show the account/login consent dialog every time.
        "show_dialog": "true",
    }
    auth_url = f"{SPOTIFY_AUTH_URL}?{urlencode(params, quote_via=quote)}"
    return RedirectResponse(url=auth_url)


@app.get("/auth/callback")
async def auth_callback(request: Request, code: str = None, state: str = None, error: str = None):
    """Handle Spotify OAuth callback."""
    webapp_url = f"{FRONTEND_URL}/webapp.html"
    login_url = f"{FRONTEND_URL}/login.html"

    if error:
        return RedirectResponse(url=f"{login_url}?error={error}")

    stored_state = request.session.get("oauth_state")
    if not state or state != stored_state:
        return RedirectResponse(url=f"{login_url}?error=state_mismatch")

    if not code:
        return RedirectResponse(url=f"{login_url}?error=no_code")

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        response = await client.post(
            SPOTIFY_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": SPOTIFY_REDIRECT_URI,
                "client_id": SPOTIFY_CLIENT_ID,
                "client_secret": SPOTIFY_CLIENT_SECRET,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if response.status_code != 200:
            return RedirectResponse(url=f"{login_url}?error=token_exchange_failed")

        token_data = response.json()

    # Store tokens in session
    request.session.pop("user_id", None)
    request.session.pop("user_display_name", None)
    request.session.pop("user_email", None)
    request.session["access_token"] = token_data["access_token"]
    request.session["refresh_token"] = token_data.get("refresh_token")
    request.session["expires_at"] = time.time() + token_data.get("expires_in", 3600)

    profile = await _ensure_spotify_profile(request, token_data["access_token"])
    if not profile:
        request.session.clear()
        return RedirectResponse(url=f"{login_url}?error=profile_fetch_failed")

    # Clear the oauth state
    request.session.pop("oauth_state", None)

    return RedirectResponse(url=webapp_url)


@app.get("/auth/me")
async def auth_me(request: Request):
    """Return current user info from session."""
    access_token = await _refresh_token_if_needed(request)

    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    profile = await _ensure_spotify_profile(request, access_token)
    if not profile:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Spotify session is invalid. Please sign in again.")

    return {
        "authenticated": True,
        "user_id": request.session.get("user_id"),
        "display_name": request.session.get("user_display_name"),
        "email": request.session.get("user_email"),
    }


@app.post("/auth/logout")
def auth_logout(request: Request):
    """Clear the session."""
    request.session.clear()
    return {"ok": True}


# ============ Playlist Generation ============

@app.post("/generate-mood-arc-playlist")
async def generate_mood_arc_playlist(request: Request, req: MoodArcRequest):
    # 1) OpenAI scores start + end mood vectors
    try:
        plan = score_start_end_with_openai(req.text, req.goal, req.mode)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OpenAI scoring failed: {exc}") from exc

    start = plan.start.model_dump()
    end = plan.end.model_dump()

    # 2) Turn that into a staged arc (the "song steps")
    arc_targets = make_arc(start, end, stages=req.stages)

    # 3) Sample tracks from dataset per stage
    selected_df = pick_tracks_for_arc(arc_targets, total_tracks=req.tracks)
    preview_tracks = _tracks_preview(selected_df, limit=10)

    playlist_name = f"Mood Arc: {plan.start_label} -> {plan.end_label} ({req.mode})"
    playlist_url = None
    track_ids = []
    misses = 0
    spotify_note = None

    # 4) Try Spotify: create playlist + add tracks using session token
    access_token = await _refresh_token_if_needed(request)

    if not access_token:
        spotify_note = "Not authenticated with Spotify. Please log in."
    else:
        try:
            profile = await _ensure_spotify_profile(request, access_token)
            if not profile:
                raise RuntimeError("No authenticated Spotify user found in session.")

            sp = get_spotify_client_from_token(access_token)
            user_id = str(profile["id"])
            playlist_id, playlist_url = create_playlist(sp, user_id, playlist_name, public=req.public)

            for _, row in selected_df.iterrows():
                tid = search_track_id(sp, row["track_name"], row["artist_name"])
                if tid:
                    track_ids.append(tid)
                else:
                    misses += 1

            if track_ids:
                sp.playlist_add_items(playlist_id, track_ids)
        except Exception as exc:
            spotify_note = f"Spotify playlist step failed: {exc}"

    # Calculate tracks per stage for response
    tracks_per_stage = []
    if "_arc_stage" in selected_df.columns:
        for stage_idx in range(len(arc_targets)):
            count = len(selected_df[selected_df["_arc_stage"] == stage_idx])
            tracks_per_stage.append(count)
    else:
        # Fallback estimate
        per_stage = req.tracks // len(arc_targets) if len(arc_targets) > 0 else req.tracks
        tracks_per_stage = [per_stage] * len(arc_targets)

    return {
        "playlist_url": playlist_url,
        "playlist_name": playlist_name,
        "mode": req.mode,
        "start_label": plan.start_label,
        "end_label": plan.end_label,
        "start_vector": start,
        "end_vector": end,
        "arc_targets": arc_targets,
        "stages_count": len(arc_targets),
        "tracks_per_stage": tracks_per_stage,
        "tracks_requested": req.tracks,
        "tracks_selected": len(selected_df),
        "tracks_added": len(track_ids),
        "tracks_missed": misses,
        "tracks_preview": preview_tracks,
        "spotify_note": spotify_note,
        "safety_note": plan.safety_note,
    }


# ============ Static File Serving ============
# Mount frontend directory for serving static files
# This must be added AFTER all API routes
from pathlib import Path

_frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if _frontend_dir.exists():
    app.mount("/frontend", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
