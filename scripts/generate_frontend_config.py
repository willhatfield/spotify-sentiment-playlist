#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import dotenv_values


def str_to_bool(value: str | None) -> bool | None:
    if value is None:
        return None

    text = value.strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return None


def is_localhost_url(value: str) -> bool:
    lowered = value.lower()
    return lowered.startswith("http://localhost") or lowered.startswith("https://localhost")


def main() -> int:
    root = Path(__file__).resolve().parents[1]

    parser = argparse.ArgumentParser(
        description="Generate frontend/runtime-config.js from .env values."
    )
    parser.add_argument(
        "--env-file",
        default=str(root / ".env"),
        help="Path to .env file (default: project .env)",
    )
    parser.add_argument(
        "--out-file",
        default=str(root / "frontend" / "runtime-config.js"),
        help="Output JS file path (default: frontend/runtime-config.js)",
    )
    args = parser.parse_args()

    env_path = Path(args.env_file).expanduser().resolve()
    out_path = Path(args.out_file).expanduser().resolve()

    if not env_path.exists():
        raise FileNotFoundError(f".env file not found: {env_path}")

    env = dotenv_values(env_path)
    api_base_url = (
        env.get("NEXT_PUBLIC_API_BASE_URL")
        or env.get("LOCAL_BACKEND_PUBLIC_URL")
        or ""
    ).strip()

    config = {
        "apiBaseUrl": api_base_url,
        "frontendBasePath": (env.get("FRONTEND_BASE_PATH") or "").strip(),
        "supabaseUrl": (env.get("SUPABASE_URL") or "").strip(),
        "supabaseAnonKey": (env.get("SUPABASE_ANON_KEY") or "").strip(),
        "supabaseProfilesTable": (env.get("SUPABASE_PROFILES_TABLE") or "profiles").strip(),
        "supabaseMoodHistoryTable": (env.get("SUPABASE_MOOD_HISTORY_TABLE") or "mood_history").strip(),
    }

    spotify_show_dialog = str_to_bool(env.get("SPOTIFY_SHOW_DIALOG"))
    if spotify_show_dialog is not None:
        config["spotifyShowDialog"] = spotify_show_dialog

    out_path.parent.mkdir(parents=True, exist_ok=True)
    content = (
        "window.__MOODMIX_CONFIG__ = Object.assign(\n"
        "  {},\n"
        "  window.__MOODMIX_CONFIG__ || {},\n"
        f"  {json.dumps(config, indent=2)}\n"
        ");\n"
    )
    out_path.write_text(content, encoding="utf-8")

    print(f"Generated {out_path} from {env_path}")
    if not api_base_url:
        print("Warning: API base URL is empty. Set NEXT_PUBLIC_API_BASE_URL or LOCAL_BACKEND_PUBLIC_URL.")
    elif is_localhost_url(api_base_url) and config["supabaseUrl"]:
        print(
            "Warning: API base URL points to localhost. A Supabase-hosted frontend cannot reach localhost directly."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
