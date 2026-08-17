"""
Nikka — Windows Virtual Desktop Management Tools.
"""

from __future__ import annotations

import logging
import time

from pywinauto import Desktop
from smolagents import tool

from nikka.core.desktop_workspace import workspace
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

    Special values for desktop_number:
    - Use 0 to target Nikka's dedicated workspace desktop.
    - Use any positive integer (1, 2, 3, ...) for a specific desktop.

    Args:
        app_name: Substring or title of the target application window.
        desktop_number: Target virtual desktop index (1-indexed), or 0 for Nikka's desktop.

    Returns:
        Confirmation or error message.
    """
    try:
        from pyvda import AppView, VirtualDesktop, get_virtual_desktops

        # Resolve desktop_number == 0 to Nikka's workspace
        if desktop_number == 0:
            nikka_num = workspace.nikka_desktop_number
            if nikka_num is None:
                workspace.ensure()
                nikka_num = workspace.nikka_desktop_number
            if nikka_num is None:
                return "Error: Could not resolve Nikka's workspace desktop."
            desktop_number = nikka_num

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


# ── Nikka Workspace Tools ─────────────────────────────────────────────────────


@tool
def ensure_nikka_desktop() -> str:
    """
    Create or find Nikka's dedicated virtual desktop and switch to it.
    Call this BEFORE doing multi-step GUI work so the user's main desktop
    is not disturbed. If the desktop already exists, it simply switches to it.

    Returns:
        Status message with desktop numbers.
    """
    try:
        workspace.ensure()
        result = workspace.switch_to_nikka()
        return result
    except ImportError:
        return "Error: pyvda is not installed. Please install it using `pip install pyvda`."
    except Exception as exc:
        logger.error("Failed to ensure Nikka desktop: %s", exc)
        return f"Failed to set up Nikka's workspace: {exc}"


@tool
def return_to_user_desktop() -> str:
    """
    Switch back to the user's original desktop after finishing work on Nikka's desktop.
    Call this AFTER completing GUI work to restore the user's view.

    Returns:
        Confirmation message.
    """
    try:
        return workspace.switch_to_user()
    except ImportError:
        return "Error: pyvda is not installed. Please install it using `pip install pyvda`."
    except Exception as exc:
        logger.error("Failed to return to user desktop: %s", exc)
        return f"Failed to return to user desktop: {exc}"


@tool
def get_desktop_info() -> str:
    """
    Get information about the current virtual desktop setup: which desktop
    Nikka is using, which is the user's desktop, total count, and whether
    Nikka is currently on her own desktop.

    Returns:
        Formatted status string with desktop information.
    """
    try:
        info = workspace.get_info()
        lines = [
            "Desktop Workspace Info:",
            f"  • Nikka's desktop  : #{info['nikka_desktop'] or 'not created'}",
            f"  • User's desktop   : #{info['user_desktop'] or 'unknown'}",
            f"  • Current desktop  : #{info['current_desktop'] or 'unknown'}",
            f"  • Total desktops   : {info['total_desktops'] or 'unknown'}",
            f"  • On Nikka desktop : {info['is_on_nikka_desktop']}",
            f"  • Initialized      : {info['initialized']}",
        ]
        return "\n".join(lines)
    except ImportError:
        return "Error: pyvda is not installed. Please install it using `pip install pyvda`."
    except Exception as exc:
        logger.error("Failed to get desktop info: %s", exc)
        return f"Failed to get desktop info: {exc}"

