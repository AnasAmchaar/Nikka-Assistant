"""
Nikka — OS Tools & ID-Based UI Abstraction Layer
Implements the anti-hallucination strategy:
  pywinauto parses the UI tree → assigns sequential IDs → feeds ONLY text to the LLM.
  When the LLM calls click_element(id), we resolve real coordinates here.
"""

from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass, field
from typing import Optional

import psutil
import pyautogui
from pywinauto import Desktop
from pywinauto.application import Application
from pywinauto.controls.uiawrapper import UIAWrapper

import config

# ─── Safety ────────────────────────────────────────────────────────────────────
pyautogui.FAILSAFE = True          # move mouse to corner to abort
pyautogui.PAUSE    = 0.08          # small pause between pyautogui actions

logger = logging.getLogger("nikka.os_tools")


# ─── Data Types ────────────────────────────────────────────────────────────────

@dataclass
class UIElement:
    """A single interactive UI element discovered from pywinauto."""
    element_id:   int
    control_type: str
    name:         str
    rect:         tuple[int, int, int, int]   # (left, top, right, bottom)
    center_x:     int
    center_y:     int
    is_enabled:   bool  = True
    automation_id: str  = ""
    value:        str   = ""                   # current value for edit boxes, etc.


@dataclass
class UIStateManager:
    """
    Maintains the ephemeral mapping from integer IDs → screen coordinates.
    Re-built on every call to get_screen_context().
    """
    elements: dict[int, UIElement] = field(default_factory=dict)
    _next_id: int = 1
    window_title: str = ""

    def reset(self) -> None:
        self.elements.clear()
        self._next_id = 1
        self.window_title = ""

    def register(self, el: UIElement) -> int:
        el.element_id = self._next_id
        self.elements[self._next_id] = el
        self._next_id += 1
        return el.element_id

    def lookup(self, element_id: int) -> Optional[UIElement]:
        return self.elements.get(element_id)


# ── Singleton state shared across all tool invocations ─────────────────────────
_ui_state = UIStateManager()


# ═══════════════════════════════════════════════════════════════════════════════
#  1.  UI TREE PARSING
# ═══════════════════════════════════════════════════════════════════════════════

# Control types that are interactive and worth presenting to the LLM
_INTERACTIVE_TYPES = frozenset({
    "Button", "CheckBox", "ComboBox", "Edit", "Hyperlink",
    "ListItem", "MenuItem", "RadioButton", "Slider",
    "Spinner", "SplitButton", "TabItem", "TreeItem",
    "DataItem", "ToggleButton", "MenuBar", "Menu",
})

# Control types to always skip (containers that clutter the output)
_SKIP_TYPES = frozenset({
    "Pane", "Window", "Group", "ScrollBar", "Thumb",
    "Separator", "StatusBar", "TitleBar", "ToolBar",
    "Image", "Text", "Document", "Custom", "Header",
    "HeaderItem", "ProgressBar", "Table",
})


def _walk_tree(
    wrapper: UIAWrapper,
    depth: int = 0,
    collected: list[UIElement] | None = None,
) -> list[UIElement]:
    """Recursively walk a pywinauto UIA element tree and collect interactive nodes."""
    if collected is None:
        collected = []

    if depth > config.UI_PARSE_DEPTH:
        return collected
    if len(collected) >= config.UI_MAX_ELEMENTS:
        return collected

    try:
        ctrl_type = wrapper.element_info.control_type or ""
    except Exception:
        return collected

    # ── Skip invisible / disabled / irrelevant ──
    try:
        if not wrapper.is_visible():
            return collected
    except Exception:
        pass  # some wrappers don't support is_visible

    if ctrl_type in _SKIP_TYPES:
        # Still recurse into children — interactive controls can live inside Groups
        try:
            for child in wrapper.children():
                _walk_tree(child, depth + 1, collected)
        except Exception:
            pass
        return collected

    # ── Collect interactive elements ──
    if ctrl_type in _INTERACTIVE_TYPES:
        try:
            rect = wrapper.rectangle()
            name = (wrapper.window_text() or "").strip()

            # Skip elements with zero-area rects (off-screen / collapsed)
            width  = rect.right - rect.left
            height = rect.bottom - rect.top
            if width <= 0 or height <= 0:
                pass  # skip but still recurse
            else:
                # Read current value for edit boxes
                value = ""
                if ctrl_type == "Edit":
                    try:
                        value = wrapper.get_value() or ""
                    except Exception:
                        try:
                            value = wrapper.window_text() or ""
                        except Exception:
                            pass

                auto_id = ""
                try:
                    auto_id = wrapper.element_info.automation_id or ""
                except Exception:
                    pass

                el = UIElement(
                    element_id=0,  # will be assigned by the state manager
                    control_type=ctrl_type,
                    name=name if name else f"({ctrl_type})",
                    rect=(rect.left, rect.top, rect.right, rect.bottom),
                    center_x=(rect.left + rect.right) // 2,
                    center_y=(rect.top + rect.bottom) // 2,
                    is_enabled=wrapper.is_enabled(),
                    automation_id=auto_id,
                    value=value,
                )
                collected.append(el)
        except Exception as exc:
            logger.debug("Skipping element due to error: %s", exc)

    # ── Recurse ──
    try:
        for child in wrapper.children():
            if len(collected) >= config.UI_MAX_ELEMENTS:
                break
            _walk_tree(child, depth + 1, collected)
    except Exception:
        pass

    return collected


def get_screen_context() -> str:
    """
    Parse the foreground window's UI tree. Assign sequential IDs to all
    interactive elements. Return a compact text table for the LLM.

    Returns:
        A formatted string listing all interactive elements with their IDs.
    """
    _ui_state.reset()

    try:
        desktop = Desktop(backend="uia")
        windows = desktop.windows()
        if not windows:
            return "[No windows detected on the current desktop.]"

        # Foreground window = first in z-order
        fg = windows[0]
        _ui_state.window_title = fg.window_text() or "(Untitled)"
        logger.info("Parsing UI tree for: %s", _ui_state.window_title)

        elements = _walk_tree(fg)
    except Exception as exc:
        logger.error("Failed to parse UI tree: %s", exc)
        return f"[Error reading UI: {exc}]"

    if not elements:
        return (
            f"Active Window: {_ui_state.window_title}\n"
            "[No interactive elements found. The window may be loading or empty.]"
        )

    # Register elements and build output
    lines: list[str] = [f"Active Window: {_ui_state.window_title}", ""]
    for el in elements:
        _ui_state.register(el)
        # Format: [ID: 1] Button: 'Save'
        label = f"[ID: {el.element_id}] {el.control_type}: '{el.name}'"
        if el.value and el.value != el.name:
            label += f"  (value: '{el.value[:60]}')"
        if not el.is_enabled:
            label += "  [disabled]"
        lines.append(label)

    result = "\n".join(lines)
    logger.info("Parsed %d interactive elements", len(elements))
    logger.debug("UI Context:\n%s", result)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
#  2.  CLICK ELEMENT
# ═══════════════════════════════════════════════════════════════════════════════

def click_element(element_id: int) -> str:
    """
    Look up element_id in the internal state mapping and execute a left-click
    at its centre coordinates.

    Args:
        element_id: The numeric ID from the most recent get_screen_context().

    Returns:
        Confirmation string or error message.
    """
    el = _ui_state.lookup(element_id)
    if el is None:
        available = sorted(_ui_state.elements.keys())
        return (
            f"Error: element ID {element_id} not found. "
            f"Valid IDs: {available}. Call get_screen_context() to refresh."
        )

    logger.info(
        "Clicking [ID:%d] %s '%s' at (%d, %d)",
        el.element_id, el.control_type, el.name, el.center_x, el.center_y,
    )
    try:
        pyautogui.click(el.center_x, el.center_y)
        time.sleep(0.3)  # let the UI settle
        return f"Clicked [ID:{el.element_id}] {el.control_type}: '{el.name}' at ({el.center_x}, {el.center_y})."
    except Exception as exc:
        return f"Click failed: {exc}"


# ═══════════════════════════════════════════════════════════════════════════════
#  3.  TYPE TEXT
# ═══════════════════════════════════════════════════════════════════════════════

def type_text(text: str, submit: bool = True) -> str:
    """
    Type the given string using the keyboard. Optionally press Enter.

    Args:
        text:   The string to type.
        submit: If True, press Enter after typing.

    Returns:
        Confirmation string.
    """
    logger.info("Typing: '%s' (submit=%s)", text, submit)
    try:
        pyautogui.write(text, interval=0.02)
        if submit:
            time.sleep(0.1)
            pyautogui.press("enter")
        return f"Typed '{text}'" + (" and pressed Enter." if submit else ".")
    except Exception as exc:
        return f"Typing failed: {exc}"


# ═══════════════════════════════════════════════════════════════════════════════
#  4.  VIRTUAL DESKTOP — SWITCH
# ═══════════════════════════════════════════════════════════════════════════════

def switch_virtual_desktop(desktop_number: int) -> str:
    """
    Switch to the specified virtual desktop (1-indexed).

    Args:
        desktop_number: The desktop to switch to (1, 2, 3, …).

    Returns:
        Confirmation string or error message.
    """
    try:
        from pyvda import VirtualDesktop, get_virtual_desktops

        desktops = get_virtual_desktops()
        total = len(desktops)
        logger.info("Total virtual desktops: %d. Switching to #%d", total, desktop_number)

        if desktop_number < 1 or desktop_number > total:
            return (
                f"Error: desktop {desktop_number} does not exist. "
                f"Available: 1–{total}. Create more desktops in Task View (Win+Tab)."
            )

        VirtualDesktop(desktop_number).go()
        time.sleep(0.5)
        return f"Switched to virtual desktop {desktop_number} (of {total})."
    except ImportError:
        return "Error: pyvda is not installed. Run: pip install pyvda"
    except Exception as exc:
        return f"Failed to switch desktop: {exc}"


# ═══════════════════════════════════════════════════════════════════════════════
#  5.  VIRTUAL DESKTOP — MOVE WINDOW
# ═══════════════════════════════════════════════════════════════════════════════

def move_window_to_desktop(app_name: str, desktop_number: int) -> str:
    """
    Move a window matching `app_name` to the given virtual desktop.

    Args:
        app_name:       Substring to match in the window title (case-insensitive).
        desktop_number: Target desktop (1-indexed).

    Returns:
        Confirmation string or error message.
    """
    try:
        from pyvda import AppView, VirtualDesktop, get_virtual_desktops

        desktops = get_virtual_desktops()
        total = len(desktops)
        if desktop_number < 1 or desktop_number > total:
            return (
                f"Error: desktop {desktop_number} doesn't exist. "
                f"Available: 1–{total}."
            )

        target_desktop = VirtualDesktop(desktop_number)
        search = app_name.lower()

        # Iterate all visible windows to find a match
        desktop_obj = Desktop(backend="uia")
        for win in desktop_obj.windows():
            title = (win.window_text() or "").lower()
            if search in title:
                try:
                    hwnd = win.handle
                    app_view = AppView(hwnd)
                    app_view.move(target_desktop)
                    logger.info("Moved '%s' (hwnd=%s) → desktop %d", title, hwnd, desktop_number)
                    return f"Moved window '{win.window_text()}' to desktop {desktop_number}."
                except Exception as exc:
                    logger.warning("Could not move '%s': %s", title, exc)
                    continue

        return (
            f"No window matching '{app_name}' found. "
            "Make sure the application is open and visible."
        )
    except ImportError:
        return "Error: pyvda is not installed. Run: pip install pyvda"
    except Exception as exc:
        return f"Failed to move window: {exc}"


# ═══════════════════════════════════════════════════════════════════════════════
#  6.  LAUNCH APPLICATION
# ═══════════════════════════════════════════════════════════════════════════════

def launch_application(app_name: str) -> str:
    """
    Launch an application by friendly name. Uses config.APP_ALIASES to resolve
    the shell command. Falls back to ``start <app_name>`` if no alias matches.

    Args:
        app_name: Friendly name like "edge", "notepad", "explorer".

    Returns:
        Confirmation string or error message.
    """
    key = app_name.strip().lower()
    cmd = config.APP_ALIASES.get(key, f"start {key}")
    logger.info("Launching '%s' → `%s`", app_name, cmd)

    try:
        subprocess.Popen(cmd, shell=True)
        time.sleep(config.APP_LAUNCH_WAIT_SEC)
        return f"Launched '{app_name}' (command: `{cmd}`)."
    except Exception as exc:
        return f"Failed to launch '{app_name}': {exc}"


# ═══════════════════════════════════════════════════════════════════════════════
#  7.  UTILITY — PROCESS INFO
# ═══════════════════════════════════════════════════════════════════════════════

def list_running_apps() -> str:
    """Return a compact list of user-facing running applications."""
    seen: set[str] = set()
    lines: list[str] = ["Running applications:"]
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            name = proc.info["name"]
            if name and name not in seen and not name.startswith("svchost"):
                seen.add(name)
                lines.append(f"  • {name} (PID {proc.info['pid']})")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return "\n".join(lines[:50])  # cap for context budget
