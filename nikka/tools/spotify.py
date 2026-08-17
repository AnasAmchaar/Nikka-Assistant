"""
Nikka — Spotify Automation Tools.

API-first tools powered by spotipy (Spotify Web API), with fallback to
UI automation via pyautogui + win32gui when API credentials are not configured.

The agent should always prefer these compound tools over manual step-by-step
UI interaction for reliability and speed.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import pyautogui
import pyperclip
import win32con
import win32gui
from smolagents import tool

from nikka.tools._spotify_client import SUPPORTED_MOODS, SpotifyClient

logger = logging.getLogger("nikka.tools.spotify")

# Safety settings
pyautogui.FAILSAFE = True


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  UI-AUTOMATION FALLBACK HELPERS (kept for when API is unavailable)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Context-menu labels (English + French)
_QUEUE_LABELS = {
    "add to queue",
    "ajouter à la file d'attente",
    "ajouter à la file",
}


def _find_spotify_hwnd() -> int | None:
    """Find the Spotify main window handle."""
    result: list[tuple[int, str]] = []

    def _enum(hwnd: int, extra: list) -> None:
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title and "spotify" in title.lower():
                extra.append((hwnd, title))

    win32gui.EnumWindows(_enum, result)
    if not result:
        return None
    return result[0][0]


def _focus_spotify() -> bool:
    """Bring Spotify to the foreground. Returns True on success."""
    hwnd = _find_spotify_hwnd()
    if hwnd is None:
        return False
    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.5)
        return True
    except Exception as exc:
        logger.error("Failed to focus Spotify: %s", exc)
        return False


def _spotify_search(query: str, wait_for_results: float = 1.5) -> None:
    """Open Spotify search, paste the query, and wait for results to load."""
    pyautogui.hotkey("ctrl", "k")
    time.sleep(0.4)
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.05)
    pyperclip.copy(query)
    time.sleep(0.05)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(wait_for_results)


def _play_top_result() -> None:
    """Press Enter to play the top search result in Spotify."""
    pyautogui.press("enter")
    time.sleep(1.0)


def _add_top_result_to_queue() -> bool:
    """Add the top search result to Spotify's queue via context menu."""
    pyautogui.press("tab")
    time.sleep(0.3)
    pyautogui.press("tab")
    time.sleep(0.3)

    pyautogui.hotkey("shift", "f10")
    time.sleep(0.6)

    try:
        from pywinauto import Desktop as PwaDesktop

        desktop = PwaDesktop(backend="uia")
        for win in desktop.windows():
            try:
                for child in win.descendants():
                    try:
                        name = (child.window_text() or "").strip().lower()
                        if name in _QUEUE_LABELS:
                            child.click_input()
                            logger.info("Clicked '%s' in context menu", child.window_text())
                            time.sleep(0.3)
                            return True
                    except Exception:
                        continue
            except Exception:
                continue
    except Exception as exc:
        logger.debug("pywinauto context menu scan failed: %s", exc)

    logger.info("Falling back to keyboard navigation for context menu")
    for _ in range(12):
        pyautogui.press("down")
        time.sleep(0.15)

    pyautogui.press("escape")
    time.sleep(0.2)

    try:
        pyautogui.rightClick()
        time.sleep(0.5)
        from pywinauto import Desktop as PwaDesktop2

        desktop = PwaDesktop2(backend="uia")
        for win in desktop.windows():
            try:
                for child in win.descendants():
                    try:
                        name = (child.window_text() or "").strip().lower()
                        if name in _QUEUE_LABELS:
                            child.click_input()
                            logger.info("Clicked '%s' via mouse context menu", child.window_text())
                            time.sleep(0.3)
                            return True
                    except Exception:
                        continue
            except Exception:
                continue
    except Exception as exc:
        logger.debug("Mouse context menu fallback also failed: %s", exc)

    pyautogui.press("escape")
    time.sleep(0.2)
    return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  HELPER: Format track info for agent consumption
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _format_track(t: dict[str, Any]) -> str:
    """Format a track dict into a readable one-liner."""
    duration_sec = t.get("duration_ms", 0) // 1000
    mins, secs = divmod(duration_sec, 60)
    return f"'{t['name']}' by {t['artists']} [{t.get('album', '')}] ({mins}:{secs:02d})"


def _format_ms_as_time(ms: int) -> str:
    """Format milliseconds as M:SS."""
    total_sec = ms // 1000
    mins, secs = divmod(total_sec, 60)
    return f"{mins}:{secs:02d}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  AGENT-FACING TOOLS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@tool
def spotify_search_and_play(song_name: str) -> str:
    """
    Search for a song on Spotify and immediately play the top result.
    Uses the Spotify API for speed and reliability; falls back to UI automation.

    Args:
        song_name: The name of the song (and optionally the artist) to search for and play.

    Returns:
        Confirmation with track details, or error message.
    """
    logger.info("Spotify search & play: '%s'", song_name)
    client = SpotifyClient.get()

    if client.available:
        try:
            results = client.search_tracks(song_name, limit=1)
            if not results:
                return f"No results found on Spotify for '{song_name}'."
            track = results[0]
            client.play_track(track["uri"])
            return f"▶ Now playing: {_format_track(track)}"
        except Exception as exc:
            logger.warning("API play failed, falling back to UI: %s", exc)

    # Fallback to UI automation
    if not _focus_spotify():
        return (
            "Error: Spotify is not open or could not be focused. "
            "Please open Spotify first using launch_application('spotify')."
        )
    try:
        _spotify_search(song_name, wait_for_results=2.0)
        _play_top_result()
        return f"Searched for '{song_name}' on Spotify and started playing the top result."
    except Exception as exc:
        return f"Failed to search and play '{song_name}': {exc}"


@tool
def spotify_add_to_queue(song_name: str) -> str:
    """
    Search for a song on Spotify and add the top result to the playback queue.
    Does NOT interrupt the currently playing track.

    Args:
        song_name: The name of the song (and optionally the artist) to add to queue.

    Returns:
        Confirmation with track details, or error message.
    """
    logger.info("Spotify add to queue: '%s'", song_name)
    client = SpotifyClient.get()

    if client.available:
        try:
            results = client.search_tracks(song_name, limit=1)
            if not results:
                return f"No results found on Spotify for '{song_name}'."
            track = results[0]
            client.add_to_queue(track["uri"])
            return f"⏭ Added to queue: {_format_track(track)}"
        except Exception as exc:
            logger.warning("API queue failed, falling back to UI: %s", exc)

    # Fallback to UI automation
    if not _focus_spotify():
        return (
            "Error: Spotify is not open or could not be focused. "
            "Please open Spotify first using launch_application('spotify')."
        )
    try:
        _spotify_search(song_name, wait_for_results=2.0)
        success = _add_top_result_to_queue()
        if success:
            return f"Added '{song_name}' to Spotify queue."
        return (
            f"Searched for '{song_name}' but could not find the 'Add to queue' option. "
            "The song was found in search results but queue action failed."
        )
    except Exception as exc:
        return f"Failed to add '{song_name}' to queue: {exc}"


@tool
def spotify_play_songs_in_order(songs: list[str]) -> str:
    """
    Play a list of songs in order on Spotify.
    Searches each song, then starts playback with all tracks in sequence.
    This is the recommended tool when the user gives you a playlist or list of songs.

    Args:
        songs: List of song names (and optionally artists) to play in order.
               Example: ["DIPLOMATICO El GrandeToto", "Casablanca", "Pourquoi"]

    Returns:
        Summary of which songs were resolved and played.
    """
    if not songs:
        return "Error: No songs provided. Please provide at least one song name."

    logger.info("Spotify play songs in order: %s", songs)
    client = SpotifyClient.get()

    if client.available:
        try:
            resolved_uris: list[str] = []
            results_summary: list[str] = []

            for i, song in enumerate(songs, start=1):
                tracks = client.search_tracks(song, limit=1)
                if tracks:
                    resolved_uris.append(tracks[0]["uri"])
                    results_summary.append(f"  {i}. ✅ {_format_track(tracks[0])}")
                else:
                    results_summary.append(f"  {i}. ❌ Not found: '{song}'")

            if not resolved_uris:
                return "Could not find any of the requested songs on Spotify."

            client.play_tracks(resolved_uris)
            return (
                f"▶ Playing {len(resolved_uris)}/{len(songs)} songs in order:\n"
                + "\n".join(results_summary)
            )
        except Exception as exc:
            logger.warning("API ordered play failed, falling back to UI: %s", exc)

    # Fallback to UI automation
    if not _focus_spotify():
        return (
            "Error: Spotify is not open or could not be focused. "
            "Please open Spotify first using launch_application('spotify')."
        )

    results: list[str] = []
    try:
        first = songs[0]
        _spotify_search(first, wait_for_results=2.0)
        _play_top_result()
        results.append(f"▶ Playing: '{first}'")

        for i, song in enumerate(songs[1:], start=2):
            time.sleep(0.5)
            _focus_spotify()
            time.sleep(0.3)
            _spotify_search(song, wait_for_results=2.0)
            success = _add_top_result_to_queue()
            if success:
                results.append(f"⏭ Queued #{i}: '{song}'")
            else:
                results.append(f"⚠ Failed to queue #{i}: '{song}'")

        pyautogui.press("escape")
        time.sleep(0.2)
    except Exception as exc:
        results.append(f"❌ Error during playback setup: {exc}")

    return f"Spotify Playlist Result ({len(songs)} songs):\n" + "\n".join(results)


@tool
def spotify_toggle_shuffle(enable: bool) -> str:
    """
    Enable or disable shuffle mode in Spotify.
    IMPORTANT: Disable shuffle when playing songs in a specific order.

    Args:
        enable: True to enable shuffle, False to disable it.

    Returns:
        Confirmation message.
    """
    logger.info("Spotify toggle shuffle: %s", "enable" if enable else "disable")
    client = SpotifyClient.get()

    if client.available:
        try:
            client.set_shuffle(enable)
            state = "enabled" if enable else "disabled"
            return f"Shuffle {state} on Spotify."
        except Exception as exc:
            logger.warning("API shuffle failed, falling back to UI: %s", exc)

    # Fallback to UI automation
    if not _focus_spotify():
        return (
            "Error: Spotify is not open or could not be focused. "
            "Please open Spotify first using launch_application('spotify')."
        )
    try:
        pyautogui.hotkey("ctrl", "s")
        time.sleep(0.3)
        return (
            "Toggled shuffle in Spotify. "
            "Note: This toggles the current state. Check the Spotify UI to confirm."
        )
    except Exception as exc:
        return f"Failed to toggle shuffle: {exc}"


# ── New API-only tools ─────────────────────────────────────────────────────────


@tool
def spotify_get_current_track() -> str:
    """
    Get information about the currently playing track on Spotify.
    Returns track name, artist, album, progress, duration, playback state,
    shuffle/repeat status, and active device.

    Use this to detect when a track is ending (compare progress to duration)
    or to check what's currently playing.

    Returns:
        Formatted track info or error message.
    """
    client = SpotifyClient.get()

    if not client.available:
        return (
            "Spotify API not configured. Set NIKKA_SPOTIFY_CLIENT_ID and "
            "NIKKA_SPOTIFY_CLIENT_SECRET in .env to enable this feature."
        )

    try:
        track = client.get_current_track()
        if not track:
            return "Nothing is currently playing on Spotify."

        progress = _format_ms_as_time(track["progress_ms"])
        duration = _format_ms_as_time(track["duration_ms"])
        remaining_ms = track["duration_ms"] - track["progress_ms"]
        remaining = _format_ms_as_time(remaining_ms)
        status = "▶ Playing" if track["is_playing"] else "⏸ Paused"

        return (
            f"{status}: '{track['name']}' by {track['artists']}\n"
            f"  Album: {track['album']}\n"
            f"  Progress: {progress} / {duration} (remaining: {remaining})\n"
            f"  Shuffle: {'on' if track['shuffle_state'] else 'off'} | "
            f"Repeat: {track['repeat_state']}\n"
            f"  Device: {track['device']} | Volume: {track['volume_percent']}%\n"
            f"  Track ending soon: {'YES' if remaining_ms < 15000 else 'no'}"
        )
    except Exception as exc:
        return f"Failed to get current track: {exc}"


@tool
def spotify_pause() -> str:
    """
    Pause Spotify playback.

    Returns:
        Confirmation or error message.
    """
    client = SpotifyClient.get()

    if client.available:
        try:
            client.pause()
            return "⏸ Spotify playback paused."
        except Exception as exc:
            logger.warning("API pause failed: %s", exc)
            return f"Failed to pause: {exc}"

    return "Spotify API not configured. Use media_control('play_pause') as an alternative."


@tool
def spotify_resume() -> str:
    """
    Resume Spotify playback.

    Returns:
        Confirmation or error message.
    """
    client = SpotifyClient.get()

    if client.available:
        try:
            client.resume()
            return "▶ Spotify playback resumed."
        except Exception as exc:
            logger.warning("API resume failed: %s", exc)
            return f"Failed to resume: {exc}"

    return "Spotify API not configured. Use media_control('play_pause') as an alternative."


@tool
def spotify_skip_next() -> str:
    """
    Skip to the next track in Spotify.

    Returns:
        Confirmation or error message.
    """
    client = SpotifyClient.get()

    if client.available:
        try:
            client.skip_next()
            time.sleep(0.5)
            track = client.get_current_track()
            if track:
                return f"⏭ Skipped to: {_format_track(track)}"
            return "⏭ Skipped to next track."
        except Exception as exc:
            logger.warning("API skip next failed: %s", exc)
            return f"Failed to skip: {exc}"

    return "Spotify API not configured. Use media_control('next') as an alternative."


@tool
def spotify_skip_previous() -> str:
    """
    Go to the previous track in Spotify.

    Returns:
        Confirmation or error message.
    """
    client = SpotifyClient.get()

    if client.available:
        try:
            client.skip_previous()
            time.sleep(0.5)
            track = client.get_current_track()
            if track:
                return f"⏮ Went back to: {_format_track(track)}"
            return "⏮ Went to previous track."
        except Exception as exc:
            logger.warning("API skip previous failed: %s", exc)
            return f"Failed to go to previous track: {exc}"

    return "Spotify API not configured. Use media_control('prev') as an alternative."


@tool
def spotify_set_volume(percent: int) -> str:
    """
    Set the Spotify playback volume.

    Args:
        percent: Volume level from 0 (mute) to 100 (max).

    Returns:
        Confirmation or error message.
    """
    client = SpotifyClient.get()

    if not client.available:
        return "Spotify API not configured. Use media_control('volume_up') or media_control('volume_down') instead."

    try:
        clamped = max(0, min(100, percent))
        client.set_volume(clamped)
        bar = "█" * (clamped // 5) + "░" * (20 - clamped // 5)
        return f"🔊 Volume set to {clamped}%  [{bar}]"
    except Exception as exc:
        return f"Failed to set volume: {exc}"


@tool
def spotify_set_repeat(mode: str) -> str:
    """
    Set the Spotify repeat mode.

    Args:
        mode: Repeat mode — 'off' (no repeat), 'track' (repeat current track),
              or 'context' (repeat current album/playlist).

    Returns:
        Confirmation or error message.
    """
    client = SpotifyClient.get()

    if not client.available:
        return "Spotify API not configured."

    if mode not in ("off", "track", "context"):
        return f"Invalid repeat mode '{mode}'. Use 'off', 'track', or 'context'."

    try:
        client.set_repeat(mode)
        icons = {"off": "➡️", "track": "🔂", "context": "🔁"}
        return f"{icons.get(mode, '')} Repeat mode set to: {mode}"
    except Exception as exc:
        return f"Failed to set repeat mode: {exc}"


@tool
def spotify_seek(position_seconds: float) -> str:
    """
    Seek to a specific position within the currently playing track.

    Args:
        position_seconds: Position in seconds to seek to (e.g. 30 for 0:30, 90 for 1:30).

    Returns:
        Confirmation or error message.
    """
    client = SpotifyClient.get()

    if not client.available:
        return "Spotify API not configured."

    try:
        position_ms = int(position_seconds * 1000)
        client.seek(position_ms)
        return f"⏩ Seeked to {_format_ms_as_time(position_ms)} in current track."
    except Exception as exc:
        return f"Failed to seek: {exc}"


@tool
def spotify_search_by_mood(mood: str, count: int = 10) -> str:
    """
    Find and play songs matching a mood or vibe.
    Uses Spotify's audio feature analysis to find tracks that match the
    emotional profile of the requested mood.

    Supported moods: happy, sad, energetic, calm, romantic, party, focus,
                     angry, chill, workout.

    For moods not in the list, performs a smart text search.

    Args:
        mood: The mood, vibe, or feeling to match (e.g. "happy", "chill", "workout").
        count: Number of tracks to find (default 10, max 50).

    Returns:
        List of matching tracks with option to play them.
    """
    client = SpotifyClient.get()

    if not client.available:
        return "Spotify API not configured. Set NIKKA_SPOTIFY_CLIENT_ID and NIKKA_SPOTIFY_CLIENT_SECRET."

    try:
        count = max(1, min(50, count))
        tracks = client.search_by_mood(mood, limit=count)

        if not tracks:
            return f"No tracks found matching the '{mood}' mood."

        # Auto-play the results
        track_uris = [t["uri"] for t in tracks]
        client.play_tracks(track_uris)

        lines = [f"🎵 Playing {len(tracks)} '{mood}' tracks:"]
        for i, t in enumerate(tracks, start=1):
            lines.append(f"  {i}. {_format_track(t)}")
        lines.append(f"\nSupported moods: {', '.join(SUPPORTED_MOODS)}")
        return "\n".join(lines)
    except Exception as exc:
        return f"Failed to search by mood: {exc}"


@tool
def spotify_create_playlist(name: str, description: str = "", songs: list[str] | None = None) -> str:
    """
    Create a new Spotify playlist and optionally populate it with songs.
    The playlist is created as private by default.

    Args:
        name: Name for the new playlist.
        description: Optional description for the playlist.
        songs: Optional list of song names to search for and add to the playlist.

    Returns:
        Confirmation with playlist details and any songs that were added.
    """
    client = SpotifyClient.get()

    if not client.available:
        return "Spotify API not configured."

    try:
        playlist = client.create_playlist(name=name, description=description, public=False)
        result_lines = [
            f"✅ Created playlist '{playlist['name']}'",
            f"   URL: {playlist.get('url', 'N/A')}",
        ]

        # Add songs if provided
        if songs:
            added = []
            failed = []
            for song in songs:
                tracks = client.search_tracks(song, limit=1)
                if tracks:
                    added.append(tracks[0])
                else:
                    failed.append(song)

            if added:
                uris = [t["uri"] for t in added]
                client.add_tracks_to_playlist(playlist["id"], uris)
                result_lines.append(f"\n   Added {len(added)} tracks:")
                for i, t in enumerate(added, start=1):
                    result_lines.append(f"     {i}. {_format_track(t)}")

            if failed:
                result_lines.append(f"\n   ⚠ Could not find: {', '.join(failed)}")

        return "\n".join(result_lines)
    except Exception as exc:
        return f"Failed to create playlist: {exc}"


@tool
def spotify_manage_playlist(action: str, playlist_name: str = "", songs: list[str] | None = None) -> str:
    """
    Manage Spotify playlists: list playlists, view tracks, or add/remove tracks.

    Args:
        action: One of 'list', 'tracks', 'add', 'remove'.
                - 'list': Show all your playlists (playlist_name and songs not needed).
                - 'tracks': Show tracks in a playlist (requires playlist_name).
                - 'add': Add songs to a playlist (requires playlist_name and songs).
                - 'remove': Remove songs from a playlist (requires playlist_name and songs).
        playlist_name: Name of the playlist (for 'tracks', 'add', 'remove' actions).
        songs: List of song names to add or remove (for 'add' and 'remove' actions).

    Returns:
        Formatted results or error message.
    """
    client = SpotifyClient.get()

    if not client.available:
        return "Spotify API not configured."

    action = action.lower().strip()

    try:
        if action == "list":
            playlists = client.get_user_playlists(limit=30)
            if not playlists:
                return "You don't have any playlists."
            lines = [f"📋 Your playlists ({len(playlists)}):"]
            for i, p in enumerate(playlists, start=1):
                visibility = "🌍" if p["public"] else "🔒"
                lines.append(f"  {i}. {visibility} {p['name']} ({p['tracks_count']} tracks)")
            return "\n".join(lines)

        if action == "tracks":
            if not playlist_name:
                return "Error: playlist_name is required for 'tracks' action."
            playlist = client._find_playlist_by_name(playlist_name)
            if not playlist:
                return f"Playlist '{playlist_name}' not found."
            tracks = client.get_playlist_tracks(playlist["id"], limit=50)
            if not tracks:
                return f"Playlist '{playlist['name']}' is empty."
            lines = [f"🎵 Tracks in '{playlist['name']}' ({len(tracks)}):"]
            for i, t in enumerate(tracks, start=1):
                lines.append(f"  {i}. {_format_track(t)}")
            return "\n".join(lines)

        if action == "add":
            if not playlist_name:
                return "Error: playlist_name is required for 'add' action."
            if not songs:
                return "Error: songs list is required for 'add' action."
            playlist = client._find_playlist_by_name(playlist_name)
            if not playlist:
                return f"Playlist '{playlist_name}' not found."
            added, failed = [], []
            for song in songs:
                results = client.search_tracks(song, limit=1)
                if results:
                    added.append(results[0])
                else:
                    failed.append(song)
            if added:
                client.add_tracks_to_playlist(playlist["id"], [t["uri"] for t in added])
            lines = [f"Added {len(added)} tracks to '{playlist['name']}':"]
            for i, t in enumerate(added, start=1):
                lines.append(f"  {i}. ✅ {_format_track(t)}")
            if failed:
                lines.append(f"  ⚠ Not found: {', '.join(failed)}")
            return "\n".join(lines)

        if action == "remove":
            if not playlist_name:
                return "Error: playlist_name is required for 'remove' action."
            if not songs:
                return "Error: songs list is required for 'remove' action."
            playlist = client._find_playlist_by_name(playlist_name)
            if not playlist:
                return f"Playlist '{playlist_name}' not found."
            # Search for tracks to remove
            removed, failed = [], []
            for song in songs:
                results = client.search_tracks(song, limit=1)
                if results:
                    removed.append(results[0])
                else:
                    failed.append(song)
            if removed:
                client.remove_tracks_from_playlist(playlist["id"], [t["uri"] for t in removed])
            lines = [f"Removed {len(removed)} tracks from '{playlist['name']}':"]
            for i, t in enumerate(removed, start=1):
                lines.append(f"  {i}. 🗑 {_format_track(t)}")
            if failed:
                lines.append(f"  ⚠ Not found: {', '.join(failed)}")
            return "\n".join(lines)

        return f"Unknown action '{action}'. Use 'list', 'tracks', 'add', or 'remove'."

    except Exception as exc:
        return f"Playlist operation failed: {exc}"


@tool
def spotify_get_devices() -> str:
    """
    List all available Spotify playback devices (computer, phone, speaker, etc.).
    Useful for checking which devices are available before transferring playback.

    Returns:
        Formatted list of devices or error message.
    """
    client = SpotifyClient.get()

    if not client.available:
        return "Spotify API not configured."

    try:
        devices = client.get_devices()
        if not devices:
            return "No active Spotify devices found. Open Spotify on a device first."
        lines = ["🔊 Available Spotify devices:"]
        for d in devices:
            active = " ← ACTIVE" if d["is_active"] else ""
            vol = f" | Vol: {d['volume_percent']}%" if d["volume_percent"] is not None else ""
            lines.append(f"  • {d['name']} ({d['type']}){vol}{active}")
        return "\n".join(lines)
    except Exception as exc:
        return f"Failed to list devices: {exc}"


@tool
def spotify_transfer_playback(device_name: str) -> str:
    """
    Transfer Spotify playback to a different device (e.g., phone, speaker, TV).

    Args:
        device_name: Name (or partial name) of the target device.

    Returns:
        Confirmation or error message.
    """
    client = SpotifyClient.get()

    if not client.available:
        return "Spotify API not configured."

    try:
        result = client.transfer_playback(device_name)
        if result["success"]:
            return f"📱 Playback transferred to: {result['device']}"
        return result["error"]
    except Exception as exc:
        return f"Failed to transfer playback: {exc}"


@tool
def spotify_like_track(song_name: str = "") -> str:
    """
    Save (like/heart) a track to your Spotify library.
    If no song name is provided, likes the currently playing track.

    Args:
        song_name: Name of the song to like. Leave empty to like the current track.

    Returns:
        Confirmation or error message.
    """
    client = SpotifyClient.get()

    if not client.available:
        return "Spotify API not configured."

    try:
        if not song_name:
            # Like the currently playing track
            current = client.get_current_track()
            if not current:
                return "Nothing is currently playing. Provide a song name to search for."
            client.save_track(current["id"])
            return f"❤️ Liked: '{current['name']}' by {current['artists']}"
        else:
            # Search and like
            results = client.search_tracks(song_name, limit=1)
            if not results:
                return f"No results found for '{song_name}'."
            track = results[0]
            client.save_track(track["id"])
            return f"❤️ Liked: {_format_track(track)}"
    except Exception as exc:
        return f"Failed to like track: {exc}"
