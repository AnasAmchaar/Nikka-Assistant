"""
Nikka Tools Package.

Contains smolagents tool definitions categorized into modules:
- screen: UI parsing and coordinate-safe element clicking
- keyboard: Text typing and keystroke execution
- desktop: Virtual desktop management and window moving
- apps: Application launcher and process inspection
- system: Hotkeys (Photoshop, Spotify, browser shortcuts), media keys, URI runner
- clipboard: Text reading, copying, and Ctrl+V pasting
- window: Window focus, maximize, minimize, close, and listing
- mouse: Direct coordinates, double/right click, dragging/brushing, scrolling
- spotify: Compound Spotify playback and queue automation
- security: Static security analysis for code and payloads
"""

from nikka.tools._registry import discover_tools
from nikka.tools.apps import launch_application, list_running_apps
from nikka.tools.clipboard import get_clipboard, paste_text, set_clipboard
from nikka.tools.desktop import move_window_to_desktop, switch_virtual_desktop
from nikka.tools.desktop import ensure_nikka_desktop, return_to_user_desktop, get_desktop_info
from nikka.tools.keyboard import type_text
from nikka.tools.mouse import (
    get_mouse_position_and_resolution,
    mouse_click,
    mouse_double_click,
    mouse_drag,
    mouse_right_click,
    mouse_scroll,
)
from nikka.tools.screen import click_element, get_screen_context
from nikka.tools.spotify import (
    spotify_add_to_queue,
    spotify_play_songs_in_order,
    spotify_search_and_play,
    spotify_toggle_shuffle,
)
from nikka.tools.security import SecurityAnalyzerTool, analyze_security
from nikka.tools.system import media_control, open_uri_or_path, press_hotkey, press_key, wait_seconds
from nikka.tools.window import close_window, focus_window, list_open_windows, maximize_window, minimize_window

__all__ = [
    "discover_tools",
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
    # Windows
    "focus_window",
    "maximize_window",
    "minimize_window",
    "close_window",
    "list_open_windows",
    # Virtual Desktops
    "switch_virtual_desktop",
    "move_window_to_desktop",
    "ensure_nikka_desktop",
    "return_to_user_desktop",
    "get_desktop_info",
    # Spotify
    "spotify_search_and_play",
    "spotify_add_to_queue",
    "spotify_play_songs_in_order",
    "spotify_toggle_shuffle",
    # Mouse & Canvas
    "mouse_click",
    "mouse_double_click",
    "mouse_right_click",
    "mouse_drag",
    "mouse_scroll",
    "get_mouse_position_and_resolution",
    # Apps
    "launch_application",
    "list_running_apps",
    # Security
    "SecurityAnalyzerTool",
    "analyze_security",
]
