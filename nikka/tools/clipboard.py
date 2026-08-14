"""
Nikka — Clipboard Management Tools.
"""

from __future__ import annotations

import logging
import time

import pyautogui
import pyperclip
from smolagents import tool

logger = logging.getLogger("nikka.tools.clipboard")


@tool
def get_clipboard() -> str:
    """
    Read and return the text currently stored in the Windows clipboard.

    Returns:
        The current clipboard text string.
    """
    try:
        content = pyperclip.paste()
        return content if content else "[Clipboard is currently empty]"
    except Exception as exc:
        logger.error("Failed to read clipboard: %s", exc)
        return f"Failed to read clipboard: {exc}"


@tool
def set_clipboard(text: str) -> str:
    """
    Copy a given text string into the Windows clipboard.

    Args:
        text: The string to store on the clipboard.

    Returns:
        Confirmation string.
    """
    try:
        pyperclip.copy(text)
        return f"Copied {len(text)} characters to clipboard."
    except Exception as exc:
        logger.error("Failed to set clipboard: %s", exc)
        return f"Failed to set clipboard: {exc}"


@tool
def paste_text(text: str, submit: bool = False) -> str:
    """
    Paste the given text string directly into the currently active/focused element via Ctrl+V.
    Highly recommended over type_text for complex strings, non-ASCII characters,
    URLs, file paths, and multi-line content.

    Args:
        text: The text to paste.
        submit: If True, press Enter after pasting. Defaults to False.

    Returns:
        Confirmation string.
    """
    logger.info("Pasting text via clipboard (len=%d, submit=%s)", len(text), submit)
    try:
        pyperclip.copy(text)
        time.sleep(0.05)
        pyautogui.hotkey("ctrl", "v")
        if submit:
            time.sleep(0.1)
            pyautogui.press("enter")
        return f"Pasted '{text[:60]}...' via clipboard." + (" (Pressed Enter)" if submit else "")
    except Exception as exc:
        logger.error("Failed to paste text: %s", exc)
        return f"Failed to paste text: {exc}"
