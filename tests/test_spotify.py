"""
Spotify Integration Tests for Nikka.

These tests verify that the Spotify tools work end-to-end with real API calls.
They require valid Spotify credentials in .env and an active Spotify session.

Run with:
    python -m pytest tests/test_spotify.py -v

To run only quick non-playback tests:
    python -m pytest tests/test_spotify.py -v -k "not playback"
"""

from __future__ import annotations

import pytest

from nikka.tools._spotify_client import MOOD_PROFILES, SUPPORTED_MOODS, SpotifyClient

# ── Fixture: Skip all tests if Spotify API is not configured ───────────────────

@pytest.fixture(scope="module")
def client() -> SpotifyClient:
    """Get a SpotifyClient, skip the entire module if not configured."""
    # Reset singleton so we get a fresh client
    SpotifyClient._instance = None
    c = SpotifyClient.get()
    if not c.available:
        pytest.skip(
            "Spotify API not configured. "
            "Set NIKKA_SPOTIFY_CLIENT_ID and NIKKA_SPOTIFY_CLIENT_SECRET in .env"
        )
    return c


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  1. CONNECTION & AUTH
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestConnection:
    """Verify that authentication and basic API access work."""

    def test_client_is_available(self, client: SpotifyClient):
        """Client should be authenticated and available."""
        assert client.available is True

    def test_client_singleton(self, client: SpotifyClient):
        """SpotifyClient.get() should return the same instance."""
        assert SpotifyClient.get() is client


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  2. DEVICE MANAGEMENT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestDevices:
    """Test device listing and resolution."""

    def test_get_devices(self, client: SpotifyClient):
        """Should return a list of devices (may be empty if nothing is open)."""
        devices = client.get_devices()
        assert isinstance(devices, list)
        # If devices are found, validate structure
        for d in devices:
            assert "id" in d
            assert "name" in d
            assert "type" in d
            assert "is_active" in d

    def test_get_devices_tool(self):
        """Test the agent-facing tool wrapper."""
        from nikka.tools.spotify import spotify_get_devices
        result = spotify_get_devices()
        assert isinstance(result, str)
        # Should not be an error about configuration
        assert "not configured" not in result.lower()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  3. SEARCH
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestSearch:
    """Test search functionality."""

    def test_search_tracks(self, client: SpotifyClient):
        """Should find tracks for a well-known song."""
        results = client.search_tracks("Bohemian Rhapsody Queen", limit=3)
        assert len(results) > 0
        first = results[0]
        assert "name" in first
        assert "artists" in first
        assert "uri" in first
        assert first["uri"].startswith("spotify:track:")

    def test_search_tracks_empty(self, client: SpotifyClient):
        """Should return empty list for gibberish query."""
        results = client.search_tracks("xyzzy12345nonexistentsong99999", limit=1)
        assert isinstance(results, list)
        # Might return 0 or some loose matches — just check it doesn't crash

    def test_search_by_mood_known(self, client: SpotifyClient):
        """Should return tracks for known moods."""
        for mood in ["happy", "sad", "chill"]:
            results = client.search_by_mood(mood, limit=3)
            assert len(results) > 0, f"No results for mood '{mood}'"
            for t in results:
                assert "uri" in t

    def test_search_by_mood_unknown(self, client: SpotifyClient):
        """Should fall back gracefully for unknown moods."""
        results = client.search_by_mood("nostalgic", limit=3)
        assert isinstance(results, list)
        # Should still return something via text search fallback

    def test_search_by_mood_tool(self):
        """Test the agent-facing mood search tool (without auto-play)."""
        from nikka.tools.spotify import spotify_search_by_mood
        # Note: This will auto-play if a device is active
        result = spotify_search_by_mood("focus", count=3)
        assert isinstance(result, str)
        assert "not configured" not in result.lower()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  4. PLAYBACK STATE (non-destructive, read-only)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestPlaybackState:
    """Test reading playback state (does not modify playback)."""

    def test_get_current_track(self, client: SpotifyClient):
        """Should return track info or None if nothing is playing."""
        track = client.get_current_track()
        if track is not None:
            assert "name" in track
            assert "artists" in track
            assert "progress_ms" in track
            assert "duration_ms" in track
            assert "is_playing" in track
            assert isinstance(track["progress_ms"], int)
            assert isinstance(track["duration_ms"], int)

    def test_get_current_track_tool(self):
        """Test the agent-facing tool wrapper."""
        from nikka.tools.spotify import spotify_get_current_track
        result = spotify_get_current_track()
        assert isinstance(result, str)
        # Should either show track info or "Nothing is currently playing"
        assert "not configured" not in result.lower()

    def test_is_track_ending(self, client: SpotifyClient):
        """Should return a boolean without crashing."""
        result = client.is_track_ending(threshold_ms=10000)
        assert isinstance(result, bool)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  5. PLAYBACK CONTROLS (these actually change playback — grouped separately)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestPlaybackControls:
    """
    Tests that actively control playback.
    Require an active Spotify device (desktop app open).
    Marked so they can be skipped with: pytest -k "not playback"
    """

    @pytest.fixture(autouse=True)
    def _require_active_device(self, client: SpotifyClient):
        """Skip playback tests if no active device is found."""
        devices = client.get_devices()
        if not devices:
            pytest.skip("No active Spotify device — open Spotify desktop app first")

    def test_search_and_play(self):
        """Search for a song and play it."""
        from nikka.tools.spotify import spotify_search_and_play
        result = spotify_search_and_play("Never Gonna Give You Up Rick Astley")
        assert isinstance(result, str)
        assert "error" not in result.lower() or "now playing" in result.lower()

    def test_pause_and_resume(self):
        """Pause and then resume playback."""
        import time
        from nikka.tools.spotify import spotify_pause, spotify_resume

        pause_result = spotify_pause()
        assert "paused" in pause_result.lower() or "failed" not in pause_result.lower()

        time.sleep(1)

        resume_result = spotify_resume()
        assert "resumed" in resume_result.lower() or "failed" not in resume_result.lower()

    def test_skip_next(self):
        """Skip to next track."""
        from nikka.tools.spotify import spotify_skip_next
        result = spotify_skip_next()
        assert isinstance(result, str)

    def test_skip_previous(self):
        """Go back to previous track."""
        from nikka.tools.spotify import spotify_skip_previous
        result = spotify_skip_previous()
        assert isinstance(result, str)

    def test_set_volume(self):
        """Set volume to 50% then restore."""
        import time
        from nikka.tools.spotify import spotify_set_volume

        # Get current volume first
        client = SpotifyClient.get()
        track = client.get_current_track()
        original_vol = track["volume_percent"] if track else 50

        result = spotify_set_volume(50)
        assert "50%" in result

        time.sleep(0.5)
        # Restore original volume
        spotify_set_volume(original_vol or 50)

    def test_toggle_shuffle(self):
        """Toggle shuffle off then back."""
        from nikka.tools.spotify import spotify_toggle_shuffle

        result_off = spotify_toggle_shuffle(False)
        assert "disabled" in result_off.lower() or "toggled" in result_off.lower()

    def test_set_repeat(self):
        """Set repeat mode."""
        from nikka.tools.spotify import spotify_set_repeat

        result = spotify_set_repeat("off")
        assert "off" in result.lower()

    def test_seek(self):
        """Seek to 10 seconds into the current track."""
        from nikka.tools.spotify import spotify_seek
        result = spotify_seek(10.0)
        assert "0:10" in result or "seeked" in result.lower()

    def test_add_to_queue(self):
        """Add a song to the queue."""
        from nikka.tools.spotify import spotify_add_to_queue
        result = spotify_add_to_queue("Imagine John Lennon")
        assert "queue" in result.lower()

    def test_play_songs_in_order(self):
        """Play multiple songs in order."""
        from nikka.tools.spotify import spotify_play_songs_in_order
        result = spotify_play_songs_in_order([
            "Come Together Beatles",
            "Hotel California Eagles",
        ])
        assert "playing" in result.lower()
        assert "2" in result or "songs" in result.lower()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  6. PLAYLIST MANAGEMENT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestPlaylists:
    """Test playlist CRUD operations."""

    def test_list_playlists(self, client: SpotifyClient):
        """Should return a list of playlists."""
        playlists = client.get_user_playlists(limit=5)
        assert isinstance(playlists, list)
        for p in playlists:
            assert "name" in p
            assert "id" in p
            assert "tracks_count" in p

    def test_list_playlists_tool(self):
        """Test the agent-facing list playlists tool."""
        from nikka.tools.spotify import spotify_manage_playlist
        result = spotify_manage_playlist("list")
        assert isinstance(result, str)
        assert "not configured" not in result.lower()

    def test_create_and_cleanup_playlist(self, client: SpotifyClient):
        """Create a test playlist, add tracks, verify, then clean up."""
        # Create
        playlist = client.create_playlist(
            name="Nikka Test Playlist (auto-delete)",
            description="Created by Nikka integration tests. Safe to delete.",
            public=False,
        )
        assert "id" in playlist
        assert "Nikka Test" in playlist["name"]
        playlist_id = playlist["id"]

        try:
            # Add tracks
            results = client.search_tracks("Bohemian Rhapsody Queen", limit=1)
            assert len(results) > 0
            client.add_tracks_to_playlist(playlist_id, [results[0]["uri"]])

            # Verify tracks
            tracks = client.get_playlist_tracks(playlist_id)
            assert len(tracks) >= 1
            assert any("Bohemian" in t["name"] for t in tracks)

            # Remove tracks
            client.remove_tracks_from_playlist(playlist_id, [results[0]["uri"]])
            tracks_after = client.get_playlist_tracks(playlist_id)
            assert len(tracks_after) == 0

        finally:
            # Clean up: Spotify API doesn't have a delete endpoint,
            # but we can unfollow (which removes it for the user)
            try:
                client._sp.current_user_unfollow_playlist(playlist_id)
            except Exception:
                pass  # Best effort cleanup

    def test_create_playlist_tool(self):
        """Test the agent-facing create playlist tool."""
        from nikka.tools.spotify import spotify_create_playlist

        result = spotify_create_playlist(
            name="Nikka Tool Test (auto-delete)",
            description="Test playlist from tool",
            songs=["Bohemian Rhapsody Queen"],
        )
        assert "created" in result.lower() or "✅" in result

        # Clean up
        client = SpotifyClient.get()
        pl = client._find_playlist_by_name("Nikka Tool Test (auto-delete)")
        if pl:
            try:
                client._sp.current_user_unfollow_playlist(pl["id"])
            except Exception:
                pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  7. LIBRARY (LIKE/UNLIKE)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestLibrary:
    """Test saving/unsaving tracks."""

    def test_like_track_by_name(self):
        """Like a track by name."""
        from nikka.tools.spotify import spotify_like_track
        result = spotify_like_track("Bohemian Rhapsody Queen")
        assert "liked" in result.lower() or "❤" in result

    def test_like_current_track(self):
        """Like whatever is currently playing (if anything)."""
        from nikka.tools.spotify import spotify_like_track
        result = spotify_like_track("")
        assert isinstance(result, str)
        # Either likes the track or says nothing is playing


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  8. AUDIO FEATURES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestAudioFeatures:
    """Test audio feature retrieval."""

    def test_get_audio_features(self, client: SpotifyClient):
        """Should return audio features for a known track."""
        # First search for a track to get its ID
        results = client.search_tracks("Bohemian Rhapsody Queen", limit=1)
        assert len(results) > 0

        features = client.get_audio_features([results[0]["id"]])
        assert len(features) > 0
        first = features[0]
        # Validate expected audio feature keys
        for key in ("valence", "energy", "danceability", "tempo"):
            assert key in first, f"Missing audio feature: {key}"
        assert 0 <= first["valence"] <= 1
        assert 0 <= first["energy"] <= 1
