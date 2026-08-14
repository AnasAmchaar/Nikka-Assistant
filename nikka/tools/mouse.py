"""
Nikka — Precise Mouse & Canvas Interaction Tools.
Essential for creative suites (Photoshop, Illustrator, Blender), CAD, video editors,
custom toolbars, sliders, and drag-and-drop operations.
"""

from __future__ import annotations

import logging
import time

import pyautogui
from smolagents import tool

logger = logging.getLogger("nikka.tools.mouse")


@tool
def mouse_click(x: int, y: int, button: str = "left", clicks: int = 1) -> str:
    """
    Perform a mouse click at absolute screen coordinates (X, Y).
    Use this when targeting canvas tools, color pickers, or elements not exposed by UIA.

    Args:
        x: Horizontal pixel coordinate.
        y: Vertical pixel coordinate.
        button: Mouse button ('left', 'right', 'middle'). Defaults to 'left'.
        clicks: Number of clicks (1 for single, 2 for double click). Defaults to 1.

    Returns:
        Confirmation string.
    """
    logger.info("Mouse click at (%d, %d) [button=%s, clicks=%d]", x, y, button, clicks)
    try:
        pyautogui.click(x, y, clicks=clicks, button=button)
        time.sleep(0.1)
        return f"Clicked {button} button at ({x}, {y}) [x{clicks}]."
    except Exception as exc:
        logger.error("Failed mouse click: %s", exc)
        return f"Failed mouse click: {exc}"


@tool
def mouse_double_click(x: int, y: int) -> str:
    """
    Perform a rapid left double-click at absolute screen coordinates (X, Y).

    Args:
        x: Horizontal pixel coordinate.
        y: Vertical pixel coordinate.

    Returns:
        Confirmation string.
    """
    try:
        pyautogui.doubleClick(x, y)
        time.sleep(0.1)
        return f"Double-clicked at ({x}, {y})."
    except Exception as exc:
        return f"Failed double-click: {exc}"


@tool
def mouse_right_click(x: int, y: int) -> str:
    """
    Perform a context menu right-click at absolute screen coordinates (X, Y).

    Args:
        x: Horizontal pixel coordinate.
        y: Vertical pixel coordinate.

    Returns:
        Confirmation string.
    """
    try:
        pyautogui.rightClick(x, y)
        time.sleep(0.1)
        return f"Right-clicked at ({x}, {y})."
    except Exception as exc:
        return f"Failed right-click: {exc}"


@tool
def mouse_drag(
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    duration: float = 0.5,
    button: str = "left",
) -> str:
    """
    Click and drag from (start_x, start_y) to (end_x, end_y).
    Crucial for:
    - Photoshop brush strokes & pencil tool drawing
    - Moving layers, sliders, and timeline playheads
    - Selecting marquee areas or text blocks
    - Drag-and-drop file operations

    Args:
        start_x: Starting X coordinate.
        start_y: Starting Y coordinate.
        end_x: Target ending X coordinate.
        end_y: Target ending Y coordinate.
        duration: Duration in seconds for smooth dragging motion (default: 0.5s).
        button: Mouse button to hold during drag ('left', 'right', 'middle').

    Returns:
        Confirmation string.
    """
    logger.info("Mouse drag from (%d, %d) to (%d, %d) [dur=%.2f, btn=%s]", start_x, start_y, end_x, end_y, duration, button)
    try:
        pyautogui.moveTo(start_x, start_y)
        time.sleep(0.05)
        pyautogui.dragTo(end_x, end_y, duration=duration, button=button)
        return f"Dragged from ({start_x}, {start_y}) to ({end_x}, {end_y}) using {button} button."
    except Exception as exc:
        logger.error("Failed mouse drag: %s", exc)
        return f"Failed mouse drag: {exc}"


@tool
def mouse_scroll(amount: int, direction: str = "down") -> str:
    """
    Scroll the mouse wheel in the active window.

    Args:
        amount: Number of scroll ticks (e.g. 3, 5, 10).
        direction: 'up' or 'down'. Defaults to 'down'.

    Returns:
        Confirmation string.
    """
    multiplier = -1 if direction.lower() == "down" else 1
    ticks = abs(amount) * multiplier * 120
    try:
        pyautogui.scroll(ticks)
        return f"Scrolled {direction} by {amount} units."
    except Exception as exc:
        return f"Failed to scroll: {exc}"


@tool
def get_mouse_position_and_resolution() -> str:
    """
    Get the current mouse cursor position and primary display resolution.

    Returns:
        Information string containing X, Y and screen width/height.
    """
    try:
        x, y = pyautogui.position()
        w, h = pyautogui.size()
        return f"Current Mouse: ({x}, {y}) | Display Resolution: {w}x{h}"
    except Exception as exc:
        return f"Failed to get position: {exc}"
