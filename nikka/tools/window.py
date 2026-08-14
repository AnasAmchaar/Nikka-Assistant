"""
Nikka — Window State & Focus Management Tools.
"""

from __future__ import annotations

import logging
import time

import win32con
import win32gui
from pywinauto import Desktop
from smolagents import tool

logger = logging.getLogger("nikka.tools.window")


@tool
def focus_window(title_query: str) -> str:
    """
    Bring a specific window to the foreground and focus it by matching a substring in its title.

    Args:
        title_query: Window title or substring to search for (e.g. 'Photoshop', 'Spotify', 'Chrome').

    Returns:
        Confirmation or error message.
    """
    logger.info("Attempting to focus window matching: '%s'", title_query)
    search = title_query.lower().strip()
    matched_hwnds: list[tuple[int, str]] = []

    def _enum_callback(hwnd: int, extra: list[tuple[int, str]]) -> None:
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title and search in title.lower():
                extra.append((hwnd, title))

    try:
        win32gui.EnumWindows(_enum_callback, matched_hwnds)
        if not matched_hwnds:
            return f"No open window matching '{title_query}' was found."

        hwnd, full_title = matched_hwnds[0]
        # Restore if minimized
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        # Bring to front
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.3)
        return f"Focused window: '{full_title}' (HWND: {hwnd})."
    except Exception as exc:
        logger.error("Failed to focus window '%s': %s", title_query, exc)
        return f"Failed to focus window: {exc}"


@tool
def maximize_window() -> str:
    """
    Maximize the currently active foreground window to fill the screen.

    Returns:
        Confirmation string.
    """
    try:
        hwnd = win32gui.GetForegroundWindow()
        if hwnd:
            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            return "Maximized active window."
        return "No active window to maximize."
    except Exception as exc:
        return f"Failed to maximize window: {exc}"


@tool
def minimize_window() -> str:
    """
    Minimize the currently active foreground window to the taskbar.

    Returns:
        Confirmation string.
    """
    try:
        hwnd = win32gui.GetForegroundWindow()
        if hwnd:
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
            return "Minimized active window."
        return "No active window to minimize."
    except Exception as exc:
        return f"Failed to minimize window: {exc}"


@tool
def close_window() -> str:
    """
    Close the currently active foreground window (sends Alt+F4 / WM_CLOSE).

    Returns:
        Confirmation string.
    """
    try:
        hwnd = win32gui.GetForegroundWindow()
        if hwnd:
            title = win32gui.GetWindowText(hwnd)
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            return f"Closed window '{title}'."
        return "No active window to close."
    except Exception as exc:
        return f"Failed to close window: {exc}"


@tool
def list_open_windows() -> str:
    """
    List all currently open and visible application windows on the system.

    Returns:
        Formatted list of window titles.
    """
    windows: list[str] = []

    def _enum_callback(hwnd: int, extra: list[str]) -> None:
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title and title not in ("Program Manager", "Default IME", "MSCTFIME UI"):
                extra.append(title)

    try:
        win32gui.EnumWindows(_enum_callback, windows)
        if not windows:
            return "No visible windows found."
        lines = ["Visible Windows:"] + [f"  • {w}" for w in windows[:40]]
        return "\n".join(lines)
    except Exception as exc:
        return f"Failed to list windows: {exc}"
