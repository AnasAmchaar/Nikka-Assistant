"""
Nikka — Spotify Automation Tools.

High-level compound tools that handle full Spotify UI workflows internally,
so the agent can search, play, and queue songs in a single tool call without
burning multiple ReAct steps.

Uses pyautogui + win32gui directly (not via agent tools) for speed and
to avoid step budget consumption.
"""

from __future__ import annotations

import logging
import time
from urllib.parse import quote

import pyautogui
import pyperclip
import win32con
import win32gui
from smolagents import tool

logger = logging.getLogger("nikka.tools.spotify")

# Safety settings
pyautogui.FAILSAFE = True

# ── Spotify context-menu labels (English + French) ─────────────────────────────
_QUEUE_LABELS = {
    "add to queue",
    "ajouter à la file d'attente",
    "ajouter à la file",
}


# ── Internal helpers (not exposed as agent tools) ──────────────────────────────


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
    # Ctrl+K opens Spotify's search bar (works in all recent versions)
    pyautogui.hotkey("ctrl", "k")
    time.sleep(0.4)

    # Select all existing text and replace with our query
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.05)

    # Use clipboard paste for reliability (handles Unicode, accents, etc.)
    pyperclip.copy(query)
    time.sleep(0.05)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(wait_for_results)


def _play_top_result() -> None:
    """Press Enter to play the top search result in Spotify."""
    pyautogui.press("enter")
    time.sleep(1.0)


def _add_top_result_to_queue() -> bool:
    """
    Add the top search result to Spotify's queue via context menu.

    Strategy:
    1. Tab into the results list to select the first result
    2. Open context menu via Shift+F10 (keyboard-driven, reliable)
    3. Navigate menu items looking for "Add to queue" / "Ajouter à la file d'attente"
    4. Click it

    Returns True if the queue action was found and clicked.
    """
    # Tab to focus on the first search result
    pyautogui.press("tab")
    time.sleep(0.3)
    pyautogui.press("tab")
    time.sleep(0.3)

    # Open context menu via Shift+F10 (more reliable than right-click)
    pyautogui.hotkey("shift", "f10")
    time.sleep(0.6)

    # Try to find "Add to queue" in the context menu using pywinauto
    try:
        from pywinauto import Desktop as PwaDesktop

        desktop = PwaDesktop(backend="uia")
        context_menus = desktop.windows(class_name_re=".*", title="")

        # Walk through all popup/context windows to find the queue option
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

    # Fallback: Navigate the context menu with arrow keys
    # "Add to queue" is typically among the first few items
    logger.info("Falling back to keyboard navigation for context menu")
    for i in range(12):
        pyautogui.press("down")
        time.sleep(0.15)
        # We can't read the highlighted item easily, so we try Enter on each
        # This is a last resort — we press down and check

    # If pywinauto didn't work, try a second approach: close menu and use
    # Spotify's keyboard shortcut for adding to queue (if available)
    pyautogui.press("escape")
    time.sleep(0.2)

    # Some Spotify versions support right-click via mouse after tabbing to result
    # Let's try mouse-based right-click on the focused element
    try:
        pos = pyautogui.position()
        pyautogui.rightClick()
        time.sleep(0.5)

        # Scan the context menu again
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


# ── Agent-facing tools ─────────────────────────────────────────────────────────


@tool
def spotify_search_and_play(song_name: str) -> str:
    """
    Search for a song on Spotify and immediately play the top result.
    Focuses Spotify, types the search query, and plays the first match.

    Args:
        song_name: The name of the song (and optionally the artist) to search for and play.

    Returns:
        Confirmation or error message.
    """
    logger.info("Spotify search & play: '%s'", song_name)

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
        logger.error("Spotify search & play failed: %s", exc)
        return f"Failed to search and play '{song_name}': {exc}"


@tool
def spotify_add_to_queue(song_name: str) -> str:
    """
    Search for a song on Spotify and add the top result to the playback queue.
    Does NOT interrupt the currently playing track.

    Args:
        song_name: The name of the song (and optionally the artist) to add to queue.

    Returns:
        Confirmation or error message.
    """
    logger.info("Spotify add to queue: '%s'", song_name)

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
        else:
            return (
                f"Searched for '{song_name}' but could not find the 'Add to queue' option. "
                "The song was found in search results but queue action failed."
            )
    except Exception as exc:
        logger.error("Spotify add to queue failed: %s", exc)
        return f"Failed to add '{song_name}' to queue: {exc}"


@tool
def spotify_play_songs_in_order(songs: list[str]) -> str:
    """
    Play a list of songs in order on Spotify.
    The first song starts playing immediately, and the remaining songs are added
    to the queue in sequence so they play next in the given order.

    This is the recommended tool when the user gives you a playlist or list of songs.

    Args:
        songs: List of song names (and optionally artists) to play in order.
               Example: ["DIPLOMATICO El GrandeToto", "Casablanca", "Pourquoi"]

    Returns:
        Summary of which songs were played/queued and any that failed.
    """
    if not songs:
        return "Error: No songs provided. Please provide at least one song name."

    logger.info("Spotify play songs in order: %s", songs)

    if not _focus_spotify():
        return (
            "Error: Spotify is not open or could not be focused. "
            "Please open Spotify first using launch_application('spotify')."
        )

    results: list[str] = []

    try:
        # First song: search and play immediately
        first = songs[0]
        logger.info("Playing first song: '%s'", first)
        _spotify_search(first, wait_for_results=2.0)
        _play_top_result()
        results.append(f"▶ Playing: '{first}'")

        # Remaining songs: search and add to queue
        for i, song in enumerate(songs[1:], start=2):
            logger.info("Queueing song #%d: '%s'", i, song)
            time.sleep(0.5)  # Brief pause between operations

            _focus_spotify()  # Re-focus in case something stole focus
            time.sleep(0.3)

            _spotify_search(song, wait_for_results=2.0)
            success = _add_top_result_to_queue()

            if success:
                results.append(f"⏭ Queued #{i}: '{song}'")
            else:
                results.append(f"⚠ Failed to queue #{i}: '{song}' (could not find queue option)")

        # Close search overlay and return to player
        pyautogui.press("escape")
        time.sleep(0.2)

    except Exception as exc:
        logger.error("Spotify play songs in order failed mid-sequence: %s", exc)
        results.append(f"❌ Error during playback setup: {exc}")

    summary = "\n".join(results)
    return f"Spotify Playlist Result ({len(songs)} songs):\n{summary}"


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

    if not _focus_spotify():
        return (
            "Error: Spotify is not open or could not be focused. "
            "Please open Spotify first using launch_application('spotify')."
        )

    try:
        # Spotify's shuffle shortcut is Ctrl+S
        pyautogui.hotkey("ctrl", "s")
        time.sleep(0.3)
        action = "Toggled" if True else ("Enabled" if enable else "Disabled")
        return (
            f"{action} shuffle in Spotify. "
            "Note: This toggles the current state. Check the Spotify UI to confirm."
        )
    except Exception as exc:
        logger.error("Spotify toggle shuffle failed: %s", exc)
        return f"Failed to toggle shuffle: {exc}"
