"""
Nikka — Spotify Web API Client (Singleton).

Wraps spotipy to provide authentication, token management, device resolution,
mood-based search via audio features, and all playback/playlist operations.

Falls back gracefully when credentials are not configured.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from nikka.settings import settings

logger = logging.getLogger("nikka.tools.spotify")

# ── Mood → Spotify Audio Feature Mapping ───────────────────────────────────────

MOOD_PROFILES: dict[str, dict[str, Any]] = {
    "happy": {
        "min_valence": 0.6, "max_valence": 1.0,
        "min_energy": 0.5, "max_energy": 1.0,
        "seed_genres": ["pop", "dance", "happy"],
    },
    "sad": {
        "min_valence": 0.0, "max_valence": 0.3,
        "min_energy": 0.0, "max_energy": 0.5,
        "seed_genres": ["sad", "acoustic", "piano"],
    },
    "energetic": {
        "min_energy": 0.7, "max_energy": 1.0,
        "min_tempo": 120,
        "seed_genres": ["edm", "electronic", "dance"],
    },
    "calm": {
        "min_energy": 0.0, "max_energy": 0.4,
        "min_tempo": 60, "max_tempo": 100,
        "seed_genres": ["ambient", "chill", "classical"],
    },
    "romantic": {
        "min_valence": 0.4, "max_valence": 0.8,
        "min_danceability": 0.4, "max_danceability": 0.7,
        "min_acousticness": 0.3,
        "seed_genres": ["romance", "r-n-b", "soul"],
    },
    "party": {
        "min_danceability": 0.7, "max_danceability": 1.0,
        "min_energy": 0.7, "max_energy": 1.0,
        "seed_genres": ["party", "dance", "club"],
    },
    "focus": {
        "min_instrumentalness": 0.5,
        "min_energy": 0.2, "max_energy": 0.6,
        "seed_genres": ["study", "ambient", "classical"],
    },
    "angry": {
        "min_energy": 0.7, "max_energy": 1.0,
        "min_valence": 0.0, "max_valence": 0.3,
        "seed_genres": ["metal", "rock", "punk"],
    },
    "chill": {
        "min_energy": 0.1, "max_energy": 0.5,
        "min_valence": 0.3, "max_valence": 0.7,
        "seed_genres": ["chill", "lo-fi", "indie"],
    },
    "workout": {
        "min_energy": 0.8, "max_energy": 1.0,
        "min_tempo": 130,
        "seed_genres": ["work-out", "hip-hop", "edm"],
    },
}

# All moods as a sorted list for documentation / error messages
SUPPORTED_MOODS = sorted(MOOD_PROFILES.keys())


# ── Spotify Client Singleton ───────────────────────────────────────────────────

class SpotifyClient:
    """
    Singleton wrapper around spotipy.Spotify.

    Usage::

        client = SpotifyClient.get()
        if client.available:
            track = client.get_current_track()
    """

    _instance: SpotifyClient | None = None

    def __init__(self) -> None:
        self._sp: Any = None  # spotipy.Spotify instance
        self._available = False
        self._init_client()

    @classmethod
    def get(cls) -> SpotifyClient:
        """Return the singleton SpotifyClient, creating it on first call."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def available(self) -> bool:
        """True if the Spotify API client is authenticated and usable."""
        return self._available

    # ── Initialization ─────────────────────────────────────────────────────

    def _init_client(self) -> None:
        """Initialize the spotipy client with OAuth credentials."""
        client_id = settings.spotify_client_id
        client_secret = settings.spotify_client_secret

        if not client_id or not client_secret:
            logger.info(
                "Spotify API credentials not configured. "
                "Set NIKKA_SPOTIFY_CLIENT_ID and NIKKA_SPOTIFY_CLIENT_SECRET in .env. "
                "Falling back to UI automation."
            )
            return

        try:
            import spotipy
            from spotipy.oauth2 import SpotifyOAuth

            scopes = " ".join([
                "user-read-playback-state",
                "user-modify-playback-state",
                "user-read-currently-playing",
                "user-library-read",
                "user-library-modify",
                "playlist-read-private",
                "playlist-read-collaborative",
                "playlist-modify-public",
                "playlist-modify-private",
                "user-top-read",
            ])

            auth_manager = SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=settings.spotify_redirect_uri,
                scope=scopes,
                open_browser=True,
            )

            self._sp = spotipy.Spotify(auth_manager=auth_manager)
            # Verify authentication by fetching current user
            user = self._sp.current_user()
            self._available = True
            logger.info("Spotify API authenticated as: %s", user.get("display_name", user.get("id")))

        except Exception as exc:
            logger.warning("Spotify API initialization failed: %s. Falling back to UI automation.", exc)
            self._sp = None
            self._available = False

    # ── Device Management ──────────────────────────────────────────────────

    def get_devices(self) -> list[dict[str, Any]]:
        """List available Spotify playback devices."""
        result = self._sp.devices()
        devices = result.get("devices", [])
        return [
            {
                "id": d["id"],
                "name": d["name"],
                "type": d["type"],
                "is_active": d["is_active"],
                "volume_percent": d.get("volume_percent"),
            }
            for d in devices
        ]

    def _resolve_device_id(self) -> str | None:
        """
        Resolve the target device ID.
        Prefers the configured default device, falls back to the active device.
        """
        devices = self.get_devices()
        if not devices:
            return None

        # If a preferred device name is configured, try to match it
        preferred = settings.spotify_default_device.strip().lower()
        if preferred:
            for d in devices:
                if preferred in d["name"].lower():
                    return d["id"]

        # Fall back to the currently active device
        for d in devices:
            if d["is_active"]:
                return d["id"]

        # Fall back to the first available device
        return devices[0]["id"]

    def transfer_playback(self, device_name: str) -> dict[str, Any]:
        """Transfer playback to a device by name."""
        devices = self.get_devices()
        target = None
        for d in devices:
            if device_name.lower() in d["name"].lower():
                target = d
                break

        if not target:
            return {"success": False, "error": f"Device '{device_name}' not found. Available: {[d['name'] for d in devices]}"}

        self._sp.transfer_playback(device_id=target["id"], force_play=True)
        return {"success": True, "device": target["name"]}

    # ── Playback State ─────────────────────────────────────────────────────

    def get_current_track(self) -> dict[str, Any] | None:
        """Get currently playing track info including progress and duration."""
        result = self._sp.current_playback()
        if not result or not result.get("item"):
            return None

        item = result["item"]
        return {
            "name": item["name"],
            "artists": ", ".join(a["name"] for a in item.get("artists", [])),
            "album": item.get("album", {}).get("name", ""),
            "uri": item["uri"],
            "id": item["id"],
            "progress_ms": result.get("progress_ms", 0),
            "duration_ms": item.get("duration_ms", 0),
            "is_playing": result.get("is_playing", False),
            "shuffle_state": result.get("shuffle_state", False),
            "repeat_state": result.get("repeat_state", "off"),
            "device": result.get("device", {}).get("name", ""),
            "volume_percent": result.get("device", {}).get("volume_percent"),
        }

    def is_track_ending(self, threshold_ms: int = 10000) -> bool:
        """Check if the current track is within threshold_ms of ending."""
        track = self.get_current_track()
        if not track:
            return False
        remaining = track["duration_ms"] - track["progress_ms"]
        return remaining <= threshold_ms and track["is_playing"]

    # ── Playback Control ───────────────────────────────────────────────────

    def play_track(self, track_uri: str) -> None:
        """Start playing a specific track."""
        device_id = self._resolve_device_id()
        self._sp.start_playback(device_id=device_id, uris=[track_uri])

    def play_tracks(self, track_uris: list[str]) -> None:
        """Play a list of tracks (first plays, rest are in the context)."""
        device_id = self._resolve_device_id()
        self._sp.start_playback(device_id=device_id, uris=track_uris)

    def add_to_queue(self, track_uri: str) -> None:
        """Add a track to the playback queue."""
        device_id = self._resolve_device_id()
        self._sp.add_to_queue(uri=track_uri, device_id=device_id)

    def pause(self) -> None:
        """Pause playback."""
        device_id = self._resolve_device_id()
        self._sp.pause_playback(device_id=device_id)

    def resume(self) -> None:
        """Resume playback."""
        device_id = self._resolve_device_id()
        self._sp.start_playback(device_id=device_id)

    def skip_next(self) -> None:
        """Skip to the next track."""
        device_id = self._resolve_device_id()
        self._sp.next_track(device_id=device_id)

    def skip_previous(self) -> None:
        """Go to the previous track."""
        device_id = self._resolve_device_id()
        self._sp.previous_track(device_id=device_id)

    def seek(self, position_ms: int) -> None:
        """Seek to a position in the current track."""
        device_id = self._resolve_device_id()
        self._sp.seek_track(position_ms=position_ms, device_id=device_id)

    def set_volume(self, percent: int) -> None:
        """Set volume (0–100)."""
        percent = max(0, min(100, percent))
        device_id = self._resolve_device_id()
        self._sp.volume(volume_percent=percent, device_id=device_id)

    def set_shuffle(self, state: bool) -> None:
        """Enable or disable shuffle."""
        device_id = self._resolve_device_id()
        self._sp.shuffle(state=state, device_id=device_id)

    def set_repeat(self, state: str) -> None:
        """Set repeat mode: 'off', 'track', or 'context'."""
        if state not in ("off", "track", "context"):
            raise ValueError(f"Invalid repeat state: {state}. Use 'off', 'track', or 'context'.")
        device_id = self._resolve_device_id()
        self._sp.repeat(state=state, device_id=device_id)

    # ── Search ─────────────────────────────────────────────────────────────

    def search_tracks(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search for tracks by name/artist."""
        results = self._sp.search(q=query, type="track", limit=limit)
        tracks = results.get("tracks", {}).get("items", [])
        return [
            {
                "name": t["name"],
                "artists": ", ".join(a["name"] for a in t.get("artists", [])),
                "album": t.get("album", {}).get("name", ""),
                "uri": t["uri"],
                "id": t["id"],
                "duration_ms": t.get("duration_ms", 0),
            }
            for t in tracks
        ]

    def search_by_mood(self, mood: str, limit: int = 10) -> list[dict[str, Any]]:
        """
        Search for tracks matching a mood/vibe using Spotify's recommendations API
        with audio feature targets derived from the mood profile.
        """
        mood_key = mood.lower().strip()
        profile = MOOD_PROFILES.get(mood_key)

        if not profile:
            # Try fuzzy matching
            for key in MOOD_PROFILES:
                if key in mood_key or mood_key in key:
                    profile = MOOD_PROFILES[key]
                    mood_key = key
                    break

        if not profile:
            # Fall back to a text search if mood isn't in our profiles
            return self.search_tracks(f"{mood} vibes", limit=limit)

        # Build recommendation parameters from the mood profile
        rec_kwargs: dict[str, Any] = {
            "limit": limit,
            "seed_genres": profile.get("seed_genres", ["pop"])[:5],
        }

        # Map mood profile fields to Spotify recommendation parameter names
        for key, value in profile.items():
            if key == "seed_genres":
                continue
            rec_kwargs[key] = value

        try:
            results = self._sp.recommendations(**rec_kwargs)
            tracks = results.get("tracks", [])
            return [
                {
                    "name": t["name"],
                    "artists": ", ".join(a["name"] for a in t.get("artists", [])),
                    "album": t.get("album", {}).get("name", ""),
                    "uri": t["uri"],
                    "id": t["id"],
                    "duration_ms": t.get("duration_ms", 0),
                }
                for t in tracks
            ]
        except Exception as exc:
            logger.warning("Recommendations API failed: %s. Falling back to text search.", exc)
            return self.search_tracks(f"{mood} vibes", limit=limit)

    # ── Library ────────────────────────────────────────────────────────────

    def save_track(self, track_id: str) -> None:
        """Save (like) a track to user's library."""
        self._sp.current_user_saved_tracks_add(tracks=[track_id])

    def unsave_track(self, track_id: str) -> None:
        """Remove (unlike) a track from user's library."""
        self._sp.current_user_saved_tracks_delete(tracks=[track_id])

    # ── Playlist Management ────────────────────────────────────────────────

    def get_user_playlists(self, limit: int = 20) -> list[dict[str, Any]]:
        """List the current user's playlists."""
        user = self._sp.current_user()
        results = self._sp.user_playlists(user["id"], limit=limit)
        playlists = results.get("items", [])
        return [
            {
                "name": p["name"],
                "id": p["id"],
                "tracks_count": p.get("tracks", {}).get("total", 0),
                "public": p.get("public", False),
                "description": p.get("description", ""),
                "uri": p["uri"],
            }
            for p in playlists
        ]

    def create_playlist(
        self,
        name: str,
        description: str = "",
        public: bool = False,
    ) -> dict[str, Any]:
        """Create a new playlist."""
        user = self._sp.current_user()
        result = self._sp.user_playlist_create(
            user=user["id"],
            name=name,
            public=public,
            description=description,
        )
        return {
            "name": result["name"],
            "id": result["id"],
            "uri": result["uri"],
            "url": result.get("external_urls", {}).get("spotify", ""),
        }

    def add_tracks_to_playlist(self, playlist_id: str, track_uris: list[str]) -> None:
        """Add tracks to a playlist."""
        # Spotify API limits to 100 tracks per request
        for i in range(0, len(track_uris), 100):
            batch = track_uris[i : i + 100]
            self._sp.playlist_add_items(playlist_id=playlist_id, items=batch)

    def remove_tracks_from_playlist(self, playlist_id: str, track_uris: list[str]) -> None:
        """Remove tracks from a playlist."""
        # Spotify API limits to 100 tracks per request
        for i in range(0, len(track_uris), 100):
            batch = track_uris[i : i + 100]
            self._sp.playlist_remove_all_occurrences_of_items(
                playlist_id=playlist_id, items=batch,
            )

    def get_playlist_tracks(self, playlist_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Get tracks from a playlist."""
        results = self._sp.playlist_tracks(playlist_id=playlist_id, limit=limit)
        items = results.get("items", [])
        tracks = []
        for item in items:
            t = item.get("track")
            if t:
                tracks.append({
                    "name": t["name"],
                    "artists": ", ".join(a["name"] for a in t.get("artists", [])),
                    "album": t.get("album", {}).get("name", ""),
                    "uri": t["uri"],
                    "id": t["id"],
                    "duration_ms": t.get("duration_ms", 0),
                })
        return tracks

    def _find_playlist_by_name(self, name: str) -> dict[str, Any] | None:
        """Find a user's playlist by name (case-insensitive partial match)."""
        playlists = self.get_user_playlists(limit=50)
        name_lower = name.lower().strip()
        for p in playlists:
            if name_lower == p["name"].lower():
                return p
        # Partial match as fallback
        for p in playlists:
            if name_lower in p["name"].lower():
                return p
        return None

    # ── Audio Features (for mood analysis) ─────────────────────────────────

    def get_audio_features(self, track_ids: list[str]) -> list[dict[str, Any]]:
        """Get audio features for tracks (valence, energy, danceability, etc.)."""
        # API limits to 100 tracks per request
        all_features = []
        for i in range(0, len(track_ids), 100):
            batch = track_ids[i : i + 100]
            features = self._sp.audio_features(tracks=batch)
            all_features.extend(f for f in features if f is not None)
        return all_features
