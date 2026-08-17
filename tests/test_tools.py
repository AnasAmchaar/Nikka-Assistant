"""
Unit tests for Nikka core state manager, settings, and tool discovery.
"""

from __future__ import annotations

import textwrap

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
        "ensure_nikka_desktop",
        "return_to_user_desktop",
        "get_desktop_info",
        # Mouse
        "mouse_click",
        "mouse_double_click",
        "mouse_right_click",
        "mouse_drag",
        "mouse_scroll",
        "get_mouse_position_and_resolution",
        # Spotify
        "spotify_search_and_play",
        "spotify_add_to_queue",
        "spotify_play_songs_in_order",
        "spotify_toggle_shuffle",
        # Apps
        "launch_application",
        "list_running_apps",
        # Security
        "analyze_security",
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


def test_security_scanner():
    """Verify that the security scanner detects known vulnerability patterns."""
    import json as _json

    from nikka.tools.security import SecurityAnalyzerTool, analyze_security

    # 1. Source code analysis
    vulnerable_code = textwrap.dedent("""\
        import os
        import pickle

        password = "SuperSecret123"
        user_input = input("cmd> ")
        os.system(user_input)
        data = pickle.loads(open("data.pkl", "rb").read())
        result = eval(user_input)
    """)

    tool_instance = SecurityAnalyzerTool()
    result = tool_instance(vulnerable_code)
    report = _json.loads(result)

    assert report["scan_summary"]["total_findings"] >= 3, (
        f"Expected at least 3 findings, got {report['scan_summary']['total_findings']}"
    )

    categories = {f["category"] for f in report["findings"]}
    assert "Command Injection" in categories, "Should detect os.system / eval"
    assert "Unsafe Deserialization" in categories, "Should detect pickle.loads"
    assert "Hardcoded Credentials" in categories, "Should detect password assignment"

    # Verify line numbers are captured
    for finding in report["findings"]:
        if finding["category"] == "Command Injection" and finding["line"] is not None:
            assert finding["line"] in (6, 8)
            assert finding["severity"] == "CRITICAL"
            assert "recommendation" in finding

    # 2. Raw binary shellcode payload (hex formatted)
    hex_payload = "90 90 90 90 cd 80"
    hex_result = analyze_security(hex_payload)
    hex_report = _json.loads(hex_result)
    assert hex_report["scan_summary"]["total_findings"] >= 1
    assert any("shellcode" in f["description"].lower() or "nop" in f["description"].lower() or "syscall" in f["description"].lower() for f in hex_report["findings"])

    # 3. Base64 payload containing /bin/sh
    import base64
    b64_payload = base64.b64encode(b"some prefix text /bin/sh some suffix").decode("ascii")
    b64_result = analyze_security(b64_payload)
    b64_report = _json.loads(b64_result)
    assert b64_report["scan_summary"]["total_findings"] >= 1


