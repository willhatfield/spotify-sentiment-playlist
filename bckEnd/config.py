import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(ROOT_ENV_PATH, override=True)

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.2")

SPOTIFY_CLIENT_ID = os.environ["SPOTIFY_CLIENT_ID"]
SPOTIFY_CLIENT_SECRET = os.environ["SPOTIFY_CLIENT_SECRET"]
SPOTIFY_REDIRECT_URI = os.environ["SPOTIFY_REDIRECT_URI"]

SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-secret-change-me")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8000/frontend")


def _parse_csv_list(raw_value: str) -> list[str]:
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _parse_scopes(raw_value: str) -> str:
    # Accept either comma-separated or space-separated scopes from env.
    normalized = raw_value.replace(",", " ")
    scopes: list[str] = []
    for item in normalized.split():
        scope = item.strip()
        if scope and scope not in scopes:
            scopes.append(scope)
    return " ".join(scopes)


CSV_PATH = os.getenv("SPOTIFY_DATASET_PATH") or os.getenv("CSV_PATH", "../Data/SpotifyTracksData.csv")

CORS_ORIGINS = _parse_csv_list(
    os.getenv("CORS_ORIGINS", "http://localhost:8000,http://localhost:3000")
)

SPOTIFY_SCOPES = _parse_scopes(
    os.getenv(
        "SPOTIFY_SCOPES",
        "playlist-modify-public playlist-modify-private user-read-email user-read-private",
    )
)
