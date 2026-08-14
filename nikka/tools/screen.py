"""
Nikka — Screen and UI Interaction Tools.
"""

from __future__ import annotations

import logging
import time

import pyautogui
from smolagents import tool

from nikka.core.ui_parser import parse_screen_context
from nikka.core.ui_state import ui_state

logger = logging.getLogger("nikka.tools.screen")

# Safety settings for physical input simulation
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.08


@tool
def get_screen_context() -> str:
    """
    Parse the active foreground window's UI tree and return a numbered list
    of interactive elements (buttons, edit fields, menu items, etc.).
    Each element is mapped to a unique integer ID.

    Call this FIRST to see the available elements on the screen.

    Returns:
        A formatted string listing all interactive elements with IDs.
    """
    return parse_screen_context()


@tool
def click_element(element_id: int) -> str:
    """
    Left-click the interactive element corresponding to the given numeric ID.
    The ID must come from the most recent get_screen_context() output.

    Args:
        element_id: The integer ID of the element to click.

    Returns:
        Confirmation of the clicked element or an error message.
    """
    el = ui_state.lookup(element_id)
    if el is None:
        return (
            f"Error: Element ID {element_id} not found. "
            f"Valid IDs currently: {ui_state.valid_ids}. Call get_screen_context() to refresh."
        )

    logger.info(
        "Clicking [ID:%d] %s '%s' at screen coords (%d, %d)",
        el.element_id,
        el.control_type,
        el.name,
        el.center_x,
        el.center_y,
    )
    try:
        pyautogui.click(el.center_x, el.center_y)
        time.sleep(0.3)  # UI settling delay
        return f"Clicked [ID:{el.element_id}] {el.control_type}: '{el.name}' at ({el.center_x}, {el.center_y})."
    except Exception as exc:
        logger.error("Click execution failed: %s", exc)
        return f"Click failed: {exc}"
