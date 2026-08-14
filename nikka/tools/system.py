"""
Nikka — System, Hotkeys, Media Control, and URI Execution Tools.
"""

from __future__ import annotations

import logging
import os
import subprocess
import time

import pyautogui
from smolagents import tool

logger = logging.getLogger("nikka.tools.system")


@tool
def press_hotkey(keys: list[str]) -> str:
    """
    Press a keyboard shortcut combination simultaneously.
    Essential for apps like Photoshop, Spotify, VS Code, browsers, and Windows navigation.

    Examples:
    - Spotify Search: ["ctrl", "k"] or ["ctrl", "l"]
    - Photoshop New Document: ["ctrl", "n"]
    - Photoshop Save: ["ctrl", "s"] or ["ctrl", "shift", "s"]
    - Photoshop Brush Tool: ["b"]
    - Photoshop Undo: ["ctrl", "z"]
    - Switch Windows: ["alt", "tab"]
    - Close Window/Tab: ["ctrl", "w"] or ["alt", "f4"]
    - Select All: ["ctrl", "a"]
    - Copy / Paste: ["ctrl", "c"], ["ctrl", "v"]

    Args:
        keys: List of key names (e.g. ['ctrl', 'k'], ['alt', 'f4'], ['win', 'd']).

    Returns:
        Confirmation string.
    """
    logger.info("Executing hotkey combination: %s", "+".join(keys))
    try:
        pyautogui.hotkey(*keys)
        time.sleep(0.15)
        return f"Executed hotkey: {' + '.join(keys)}"
    except Exception as exc:
        logger.error("Failed to execute hotkey %s: %s", keys, exc)
        return f"Failed to press hotkey: {exc}"


@tool
def press_key(key: str, presses: int = 1) -> str:
    """
    Press a single keyboard key (or repeat it multiple times).

    Supported keys include:
    'enter', 'esc', 'space', 'tab', 'backspace', 'delete', 'up', 'down', 'left', 'right',
    'f1' through 'f12', 'home', 'end', 'pageup', 'pagedown', 'capslock', etc.

    Args:
        key: The key identifier to press.
        presses: Number of times to press the key (default: 1).

    Returns:
        Confirmation string.
    """
    logger.info("Pressing key: '%s' (x%d)", key, presses)
    try:
        pyautogui.press(key, presses=presses, interval=0.05)
        return f"Pressed key '{key}' ({presses} time(s))."
    except Exception as exc:
        logger.error("Failed to press key '%s': %s", key, exc)
        return f"Failed to press key: {exc}"


@tool
def media_control(action: str) -> str:
    """
    Trigger Windows hardware media controls for playback and volume.
    Works globally with Spotify, YouTube, VLC, media players, and system sound.

    Args:
        action: One of: 'play_pause', 'next', 'prev', 'volume_up', 'volume_down', 'mute'.

    Returns:
        Confirmation string or error message.
    """
    action_map = {
        "play_pause": "playpause",
        "play": "playpause",
        "pause": "playpause",
        "next": "nexttrack",
        "next_track": "nexttrack",
        "prev": "prevtrack",
        "prev_track": "prevtrack",
        "volume_up": "volumeup",
        "volume_down": "volumedown",
        "mute": "volumemute",
    }

    key = action_map.get(action.lower().strip())
    if not key:
        return f"Unknown media action '{action}'. Supported actions: {list(action_map.keys())}"

    logger.info("Executing media action: %s -> %s", action, key)
    try:
        pyautogui.press(key)
        return f"Executed media control: {action}"
    except Exception as exc:
        logger.error("Failed to execute media control '%s': %s", action, exc)
        return f"Failed media control: {exc}"


@tool
def open_uri_or_path(uri_or_path: str) -> str:
    """
    Open any URI protocol scheme, URL, or local file/folder path directly via Windows shell.

    Examples:
    - Spotify Search Query: 'spotify:search:DIPLOMATICO%20El%20GrandeToto'
    - Spotify Track/Artist URI: 'spotify:track:4cOdK2wGLETKBW3PvgPWqT'
    - Web URL: 'https://www.google.com'
    - File or Folder: 'C:\\Users\\anas_\\Pictures' or 'D:\\Projects\\design.psd'
    - Windows Settings URI: 'ms-settings:display'

    Args:
        uri_or_path: The URI string, web link, or Windows file path to open.

    Returns:
        Confirmation string or error.
    """
    logger.info("Opening URI or path: %s", uri_or_path)
    try:
        os.startfile(uri_or_path)
        time.sleep(1.0)
        return f"Opened URI or path: '{uri_or_path}'"
    except Exception as exc:
        logger.error("Failed to open '%s': %s", uri_or_path, exc)
        return f"Failed to open URI/path: {exc}"


@tool
def wait_seconds(seconds: float) -> str:
    """
    Pause execution for a brief moment to allow an app to finish loading, rendering, or searching.

    Args:
        seconds: Duration in seconds to wait (e.g. 1.0, 2.5).

    Returns:
        Confirmation string.
    """
    clamped = max(0.1, min(seconds, 15.0))
    time.sleep(clamped)
    return f"Waited {clamped:.1f} seconds."
