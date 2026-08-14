"""
Nikka — Keyboard Input Automation Tools.
"""

from __future__ import annotations

import logging
import time

import pyautogui
from smolagents import tool

logger = logging.getLogger("nikka.tools.keyboard")


@tool
def type_text(text: str, submit: bool = True) -> str:
    """
    Type the specified string using the keyboard into whatever element is currently focused.
    Optionally press Enter afterwards to submit/search.

    Args:
        text: The string content to type.
        submit: If True, press the Enter key after typing text. Defaults to True.

    Returns:
        Confirmation string.
    """
    logger.info("Typing text (len=%d, submit=%s)", len(text), submit)
    try:
        pyautogui.write(text, interval=0.02)
        if submit:
            time.sleep(0.1)
            pyautogui.press("enter")
        return f"Typed '{text}'" + (" and pressed Enter." if submit else ".")
    except Exception as exc:
        logger.error("Typing execution failed: %s", exc)
        return f"Typing failed: {exc}"
