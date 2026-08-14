"""
Nikka — Windows Virtual Desktop Management Tools.
"""

from __future__ import annotations

import logging
import time

from pywinauto import Desktop
from smolagents import tool

from nikka.exceptions import DesktopError

logger = logging.getLogger("nikka.tools.desktop")


@tool
def switch_virtual_desktop(desktop_number: int) -> str:
    """
    Switch to a specific Windows Virtual Desktop (1-indexed).

    Args:
        desktop_number: The target virtual desktop index (1, 2, 3, etc.).

    Returns:
        Confirmation or error message.
    """
    try:
        from pyvda import VirtualDesktop, get_virtual_desktops

        desktops = get_virtual_desktops()
        total = len(desktops)
        logger.info("Total virtual desktops: %d. Switching to #%d", total, desktop_number)

        if desktop_number < 1 or desktop_number > total:
            return (
                f"Error: Desktop #{desktop_number} does not exist. "
                f"Available: 1 through {total}. Create additional desktops in Task View (Win+Tab)."
            )

        VirtualDesktop(desktop_number).go()
        time.sleep(0.5)
        return f"Switched to virtual desktop #{desktop_number} (of {total})."
    except ImportError:
        return "Error: pyvda is not installed. Please install it using `pip install pyvda`."
    except Exception as exc:
        logger.error("Failed to switch virtual desktop: %s", exc)
        return f"Failed to switch desktop: {exc}"


@tool
def move_window_to_desktop(app_name: str, desktop_number: int) -> str:
    """
    Move an open window to a specific virtual desktop.
    The window is matched by finding a substring in its title (case-insensitive).

    Args:
        app_name: Substring or title of the target application window.
        desktop_number: Target virtual desktop index (1-indexed).

    Returns:
        Confirmation or error message.
    """
    try:
        from pyvda import AppView, VirtualDesktop, get_virtual_desktops

        desktops = get_virtual_desktops()
        total = len(desktops)
        if desktop_number < 1 or desktop_number > total:
            return f"Error: Desktop #{desktop_number} does not exist. Available: 1 through {total}."

        target_desktop = VirtualDesktop(desktop_number)
        search = app_name.lower().strip()

        desktop_obj = Desktop(backend="uia")
        for win in desktop_obj.windows():
            title = (win.window_text() or "").lower()
            if search in title:
                try:
                    hwnd = win.handle
                    app_view = AppView(hwnd)
                    app_view.move(target_desktop)
                    logger.info("Moved window '%s' (HWND: %s) to desktop #%d", win.window_text(), hwnd, desktop_number)
                    return f"Moved window '{win.window_text()}' to virtual desktop #{desktop_number}."
                except Exception as exc:
                    logger.warning("Could not move window '%s': %s", win.window_text(), exc)
                    continue

        return (
            f"No window matching '{app_name}' was found. "
            "Please ensure the application is open and visible on the current desktop."
        )
    except ImportError:
        return "Error: pyvda is not installed. Please install it using `pip install pyvda`."
    except Exception as exc:
        logger.error("Failed to move window to desktop: %s", exc)
        return f"Failed to move window: {exc}"
