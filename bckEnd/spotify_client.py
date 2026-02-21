import spotipy
from spotipy.oauth2 import SpotifyOAuth

try:
    from .config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI
except ImportError:
    from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI

SCOPE = "playlist-modify-public playlist-modify-private"


def get_spotify_client() -> spotipy.Spotify:
    auth = SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope=SCOPE,
        open_browser=True,
    )
    return spotipy.Spotify(auth_manager=auth)


def create_playlist(sp: spotipy.Spotify, user_id: str, name: str, public: bool = True):
    playlist = sp.user_playlist_create(user=user_id, name=name, public=public)
    return playlist["id"], playlist["external_urls"]["spotify"]


def search_track_id(sp: spotipy.Spotify, track_name: str, artist_name: str):
    q = f'track:"{track_name}" artist:"{artist_name}"'
    res = sp.search(q=q, type="track", limit=1)
    items = res.get("tracks", {}).get("items", [])
    return items[0]["id"] if items else None


def get_spotify_client_from_token(access_token: str) -> spotipy.Spotify:
    """Create a Spotify client using an existing access token."""
    return spotipy.Spotify(auth=access_token)
