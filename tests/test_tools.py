"""
Unit tests for Nikka core state manager, settings, and tool discovery.
"""

from __future__ import annotations

import pytest

from nikka.core.ui_state import UIElement, UIStateManager
from nikka.settings import NikkaSettings, settings
from nikka.tools._registry import discover_tools


def test_ui_state_manager_lifecycle():
    """Test element registration, sequential ID generation, lookup, and reset."""
    manager = UIStateManager()
    assert manager.count == 0
    assert manager.valid_ids == []

    el1 = UIElement(
        element_id=0,
        control_type="Button",
        name="Save",
        rect=(10, 10, 100, 50),
        center_x=55,
        center_y=30,
    )
    el2 = UIElement(
        element_id=0,
        control_type="Edit",
        name="Search",
        rect=(110, 10, 300, 50),
        center_x=205,
        center_y=30,
    )

    id1 = manager.register(el1)
    id2 = manager.register(el2)

    assert id1 == 1
    assert id2 == 2
    assert manager.count == 2
    assert manager.valid_ids == [1, 2]

    found1 = manager.lookup(1)
    assert found1 is not None
    assert found1.name == "Save"
    assert found1.center_x == 55

    found2 = manager.lookup(2)
    assert found2 is not None
    assert found2.name == "Search"

    assert manager.lookup(999) is None

    # Reset
    manager.reset()
    assert manager.count == 0
    assert manager.lookup(1) is None
    assert manager.valid_ids == []


def test_tool_discovery():
    """Verify that discover_tools finds all tools in nikka.tools."""
    tools = discover_tools("nikka.tools")
    tool_names = {t.name for t in tools}

    expected_tools = {
        # Screen
        "get_screen_context",
        "click_element",
        # Keyboard
        "type_text",
        # System & Hotkeys
        "press_hotkey",
        "press_key",
        "media_control",
        "open_uri_or_path",
        "wait_seconds",
        # Clipboard
        "get_clipboard",
        "set_clipboard",
        "paste_text",
        # Window
        "focus_window",
        "maximize_window",
        "minimize_window",
        "close_window",
        "list_open_windows",
        # Desktop
        "switch_virtual_desktop",
        "move_window_to_desktop",
        # Mouse
        "mouse_click",
        "mouse_double_click",
        "mouse_right_click",
        "mouse_drag",
        "mouse_scroll",
        "get_mouse_position_and_resolution",
        # Apps
        "launch_application",
        "list_running_apps",
    }

    for expected in expected_tools:
        assert expected in tool_names, f"Expected tool '{expected}' was not discovered"


def test_clipboard_tools():
    """Test clipboard set and get functionality."""
    from nikka.tools.clipboard import get_clipboard, set_clipboard
    set_clipboard("Nikka Universal Test String 12345")
    assert get_clipboard() == "Nikka Universal Test String 12345"


def test_settings_defaults():
    """Verify that default settings match configuration requirements."""
    test_settings = NikkaSettings()
    assert "127.0.0.1:1234" in test_settings.lm_studio_base_url
    assert test_settings.max_agent_steps >= 5
    assert "edge" in test_settings.app_aliases
    assert "notepad" in test_settings.app_aliases
