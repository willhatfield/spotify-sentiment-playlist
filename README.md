# MoodMix

MoodMix is a web app that generates Spotify playlists based on your emotional state. Describe how you're feeling and where you want to be, and MoodMix creates a playlist that takes you on a smooth emotional journey from start to finish. It uses OpenAI to interpret your mood as audio-feature vectors and matches them against a 200k+ track dataset to build a personalized arc of songs — then saves the playlist straight to your Spotify account.

**Devpost:** [https://devpost.com/software/moodmix-mwdox0](https://devpost.com/software/moodmix-mwdox0?ref_content=my-projects-tab&ref_feature=my_projects)

## How It Works

1. Log in with your Spotify account
2. Describe your current mood and your goal mood (e.g. "I'm stressed from work" -> "I want to feel calm and ready for sleep")
3. MoodMix uses OpenAI to convert your descriptions into 6-dimensional mood vectors (valence, energy, danceability, tempo, acousticness, instrumentalness)
4. An interpolated arc is built across multiple stages to create a gradual transition
5. Tracks are selected from a local dataset to match each stage of the arc
6. A private playlist is created on your Spotify account with a creative AI-generated name

### Mood Modes

MoodMix auto-detects keywords in your input to apply preset end-state tuning:

- **uplift** — boost mood (default)
- **focus** — study/work mode
- **calm** — reduce anxiety
- **gym** — high energy workout
- **sleep** — wind down
- **rage_release** — controlled intensity release

## Setup

### Prerequisites

- Python 3.8+
- A [Spotify Developer](https://developer.spotify.com/dashboard) application
- An [OpenAI API key](https://platform.openai.com/api-keys)

### 1. Clone the repo

```bash
git clone https://github.com/<your-org>/spotify-sentiment-playlist.git
cd spotify-sentiment-playlist
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate   # macOS / Linux
# .venv\Scripts\activate    # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy the example file and fill in your keys:

```bash
cp .env.example .env
```

Open `.env` and set the following:

| Variable | Description |
|----------|-------------|
| `SESSION_SECRET` | Any secure random string used to sign sessions |
| `OPENAI_API_KEY` | Your OpenAI API key |
| `OPENAI_MODEL` | Model to use (default: `gpt-4.1-mini`) |
| `SPOTIFY_CLIENT_ID` | From your Spotify Developer Dashboard app |
| `SPOTIFY_CLIENT_SECRET` | From your Spotify Developer Dashboard app |
| `SPOTIFY_REDIRECT_URI` | Must match what's registered in your Spotify app — default: `http://127.0.0.1:8000/auth/callback` |

The remaining variables can be left at their defaults:

| Variable | Default |
|----------|---------|
| `APP_HOST` | `0.0.0.0` |
| `APP_PORT` | `8000` |
| `FRONTEND_URL` | `http://127.0.0.1:8000//frontend/index.html` |
| `SPOTIFY_DATASET_PATH` / `CSV_PATH` | `./Data/SpotifyTracksData.csv` |
| `SPOTIFY_SCOPES` | `playlist-modify-private,playlist-read-private,ugc-image-upload,user-read-email,user-read-private` |
| `CORS_ORIGINS` | `http://127.0.0.1:8000/` |

### 5. Set up your Spotify Developer app

1. Go to [https://developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)
2. Create a new app (or use an existing one)
3. Under **Redirect URIs**, add: `http://127.0.0.1:8000/auth/callback`
4. Copy the **Client ID** and **Client Secret** into your `.env`

## Running the Server

```bash
uvicorn bckEnd.main:app --host 0.0.0.0 --port 8000 --reload
```

Once running, open your browser to:

- **Login page:** [http://127.0.0.1:8000/frontend/login.html](http://127.0.0.1:8000/frontend/login.html)
- **Main app (after login):** [http://127.0.0.1:8000/frontend/webapp.html](http://127.0.0.1:8000/frontend/webapp.html)

## Tech Stack

- **Backend:** FastAPI + Uvicorn
- **AI:** OpenAI (mood scoring & playlist naming)
- **Music Data:** Spotify Web API + local 200k-track CSV dataset
- **Frontend:** Vanilla HTML/CSS/JS
