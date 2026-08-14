"""
Nikka — UI Tree Parser.

Walks the pywinauto UIA element tree for the foreground window, filters
to interactive controls, and returns a compact text representation with
sequential IDs.
"""

from __future__ import annotations

import logging

from pywinauto import Desktop
from pywinauto.controls.uiawrapper import UIAWrapper

from nikka.core.ui_state import UIElement, ui_state
from nikka.exceptions import UIParseError
from nikka.settings import settings

logger = logging.getLogger("nikka.core.ui_parser")

# ── Control-type classification ────────────────────────────────────────────────

INTERACTIVE_TYPES = frozenset({
    "Button", "CheckBox", "ComboBox", "Edit", "Hyperlink",
    "ListItem", "MenuItem", "RadioButton", "Slider",
    "Spinner", "SplitButton", "TabItem", "TreeItem",
    "DataItem", "ToggleButton", "MenuBar", "Menu",
})

SKIP_TYPES = frozenset({
    "Pane", "Window", "Group", "ScrollBar", "Thumb",
    "Separator", "StatusBar", "TitleBar", "ToolBar",
    "Image", "Text", "Document", "Custom", "Header",
    "HeaderItem", "ProgressBar", "Table",
})


# ── Tree walker ────────────────────────────────────────────────────────────────

def _walk_tree(
    wrapper: UIAWrapper,
    depth: int = 0,
    collected: list[UIElement] | None = None,
) -> list[UIElement]:
    """Recursively walk a pywinauto UIA element tree and collect interactive nodes."""
    if collected is None:
        collected = []

    if depth > settings.ui_parse_depth:
        return collected
    if len(collected) >= settings.ui_max_elements:
        return collected

    try:
        ctrl_type = wrapper.element_info.control_type or ""
    except Exception:
        return collected

    # Skip invisible elements
    try:
        if not wrapper.is_visible():
            return collected
    except Exception:
        pass  # some wrappers don't support is_visible

    if ctrl_type in SKIP_TYPES:
        # Still recurse into children — interactive controls can live inside Groups
        try:
            for child in wrapper.children():
                _walk_tree(child, depth + 1, collected)
        except Exception:
            pass
        return collected

    # Collect interactive elements
    if ctrl_type in INTERACTIVE_TYPES:
        try:
            rect = wrapper.rectangle()
            name = (wrapper.window_text() or "").strip()

            # Skip elements with zero-area rects (off-screen / collapsed)
            width = rect.right - rect.left
            height = rect.bottom - rect.top
            if width > 0 and height > 0:
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

                element = UIElement(
                    element_id=0,  # assigned by UIStateManager.register()
                    control_type=ctrl_type,
                    name=name if name else f"({ctrl_type})",
                    rect=(rect.left, rect.top, rect.right, rect.bottom),
                    center_x=(rect.left + rect.right) // 2,
                    center_y=(rect.top + rect.bottom) // 2,
                    is_enabled=wrapper.is_enabled(),
                    automation_id=auto_id,
                    value=value,
                )
                collected.append(element)
        except Exception as exc:
            logger.debug("Skipping element due to error: %s", exc)

    # Recurse into children
    try:
        for child in wrapper.children():
            if len(collected) >= settings.ui_max_elements:
                break
            _walk_tree(child, depth + 1, collected)
    except Exception:
        pass

    return collected


# ── Public API ─────────────────────────────────────────────────────────────────

def parse_screen_context() -> str:
    """
    Parse the foreground window's UI tree, assign sequential IDs to all
    interactive elements, and return a compact text listing for the LLM.

    Side effect:
        Resets and repopulates :data:`nikka.core.ui_state.ui_state`.

    Raises:
        UIParseError: If the UI tree cannot be read at all.

    Returns:
        A formatted string listing all interactive elements with their IDs.
    """
    ui_state.reset()

    try:
        desktop = Desktop(backend="uia")
        windows = desktop.windows()
        if not windows:
            return "[No windows detected on the current desktop.]"

        # Foreground window = first in z-order
        fg = windows[0]
        ui_state.window_title = fg.window_text() or "(Untitled)"
        logger.info("Parsing UI tree for: %s", ui_state.window_title)

        elements = _walk_tree(fg)
    except Exception as exc:
        raise UIParseError(f"Failed to parse UI tree: {exc}") from exc

    if not elements:
        return (
            f"Active Window: {ui_state.window_title}\n"
            "[No interactive elements found. The window may be loading or empty.]"
        )

    # Register elements and build output
    lines: list[str] = [f"Active Window: {ui_state.window_title}", ""]
    for el in elements:
        ui_state.register(el)
        # Format: [ID: 1] Button: 'Save'
        label = f"[ID: {el.element_id}] {el.control_type}: '{el.name}'"
        if el.value and el.value != el.name:
            label += f"  (value: '{el.value[:60]}')"
        if not el.is_enabled:
            label += "  [disabled]"
        lines.append(label)

    result = "\n".join(lines)
    logger.info("Parsed %d interactive elements", ui_state.count)
    logger.debug("UI Context:\n%s", result)
    return result
