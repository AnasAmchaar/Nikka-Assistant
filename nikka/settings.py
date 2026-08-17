"""
Nikka — Typed application settings with environment variable overrides.

All configuration is centralised here.  Override any value at runtime via
environment variables prefixed with ``NIKKA_`` (e.g. ``NIKKA_LM_STUDIO_BASE_URL``)
or via a ``.env`` file in the project root.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class NikkaSettings(BaseSettings):
    """Application-wide settings with sensible defaults."""

    model_config = SettingsConfigDict(
        env_prefix="NIKKA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── LM Studio Endpoint ─────────────────────────────────────────────────
    lm_studio_base_url: str = Field(
        default="http://127.0.0.1:1234/v1",
        description="OpenAI-compatible API base URL served by LM Studio.",
    )
    lm_studio_api_key: str = Field(
        default="lm-studio",
        description="API key (LM Studio ignores this, but the SDK requires it).",
    )
    lm_studio_model_id: str = Field(
        default="openai/google/gemma-3-12b",
        description="LiteLLM model identifier.  'openai/' prefix selects the OpenAI-compatible provider.",
    )

    # ── Agent Tuning ───────────────────────────────────────────────────────
    max_agent_steps: int = Field(
        default=20,
        ge=1,
        description="Hard ceiling on ReAct iterations per user request.",
    )
    verbosity: int = Field(
        default=2,
        ge=0,
        le=2,
        description="Logging verbosity: 0 = WARNING, 1 = INFO, 2 = DEBUG.",
    )

    # ── UI Parsing ─────────────────────────────────────────────────────────
    ui_parse_depth: int = Field(
        default=40,
        ge=1,
        description="Maximum depth when walking the pywinauto element tree.",
    )
    ui_max_elements: int = Field(
        default=80,
        ge=1,
        description="Cap on interactive elements sent to the LLM per context refresh.",
    )

    # ── Application Launching ──────────────────────────────────────────────
    app_launch_wait_sec: float = Field(
        default=3.0,
        ge=0.0,
        description="Seconds to wait after subprocess.Popen before moving a window.",
    )

    # ── Application Aliases ────────────────────────────────────────────────
    # Cannot be overridden via env vars easily; extend in code or a JSON file.
    app_aliases: dict[str, str] = Field(
        default={
            "edge":           "start msedge",
            "browser":        "start msedge",
            "chrome":         "start chrome",
            "firefox":        "start firefox",
            "notepad":        "start notepad",
            "explorer":       "start explorer",
            "file explorer":  "start explorer",
            "terminal":       "start wt",
            "cmd":            "start cmd",
            "powershell":     "start powershell",
            "calculator":     "start calc",
            "calc":           "start calc",
            "paint":          "start mspaint",
            "word":           "start winword",
            "excel":          "start excel",
            "powerpoint":     "start powerpnt",
            "vscode":         "start code",
            "code":           "start code",
            "spotify":        "start spotify",
            "discord":        "start discord",
            "settings":       "start ms-settings:",
            "task manager":   "start taskmgr",
        },
        description="Friendly app names → shell commands.",
    )

    # ── System Prompt ──────────────────────────────────────────────────────
    system_prompt: str = Field(
        default="""\
You are **Nikka**, an expert AI assistant that controls a Windows PC.
You can operate any Windows application (Native apps, Electron/Spotify/Discord, and Canvas apps like Photoshop/Paint).

## Core Interaction Strategy
1. **Native Windows Apps (Notepad, Explorer, Settings, Office, Edge)**:
   - Call `get_screen_context()` to read the UI tree with sequential [ID: X] items.
   - Use `click_element(element_id)` and `type_text(text, submit=True)` or `paste_text(text)`.

2. **Web & Electron Apps (Spotify, Discord, VS Code, Slack, Browsers)**:
   - To search or trigger actions quickly, use standard shortcuts:
     - Spotify / Discord Search: `press_hotkey(["ctrl", "k"])` or `press_hotkey(["ctrl", "l"])`
     - Global Media Control: `media_control("play_pause")`, `media_control("next_track")`, `media_control("volume_up")`
     - Instant URI launching: `open_uri_or_path("spotify:search:song name")`
     - Focus windows: `focus_window("Spotify")`

3. **Canvas & Creative Suites (Photoshop, Illustrator, Paint, Blender, CAD)**:
   - Tool Shortcuts: e.g. in Photoshop `press_hotkey(["ctrl", "n"])` (New Document), `press_key("b")` (Brush), `press_key("v")` (Move tool), `press_hotkey(["ctrl", "s"])` (Save).
   - Canvas Drawing / Sliders: `mouse_drag(start_x, start_y, end_x, end_y)` to draw strokes or drag layers.
   - Direct Clicks: `mouse_click(x, y)` or `mouse_right_click(x, y)`.

4. **Multi-Tasking & Desktops**:
   - `switch_virtual_desktop(desktop_number)` (1-indexed)
   - `move_window_to_desktop(app_name, desktop_number)` — use desktop_number=0 to target Nikka's desktop.

5. **Working on Your Own Desktop** (IMPORTANT):
   - Before multi-step GUI work (opening apps, clicking, typing), call `ensure_nikka_desktop()` to switch to your own dedicated desktop so the user is not disturbed.
   - Do ALL your GUI work on Nikka's desktop.
   - When done, call `return_to_user_desktop()` to return to the user's desktop.
   - Use `get_desktop_info()` to check which desktop you're on if unsure.
   - If you only need to run a single quick action, you may skip this workflow.

6. **Spotify Playback Control** (USE THESE for Spotify tasks):
   - Single song: `spotify_search_and_play("song name artist")` — searches and plays immediately.
   - Queue a song: `spotify_add_to_queue("song name")` — adds to queue without interrupting current playback.
   - **Play a list in order**: `spotify_play_songs_in_order(["song1", "song2", "song3"])` — plays the first, queues the rest.
   - Toggle shuffle: `spotify_toggle_shuffle(False)` — disable for ordered playback.
   - Basic controls: `media_control("play_pause")`, `media_control("next")`, `media_control("prev")`.
   - ALWAYS prefer these dedicated Spotify tools over manual step-by-step UI interaction.

## Best Practices
- Prefer `paste_text(text)` over `type_text` for paths, complex strings, or non-ASCII characters.
- If an element has an ID from `get_screen_context()`, use `click_element(element_id)`.
- If an element is not exposed in the UI tree, use hotkeys (`press_hotkey`) or direct mouse coordinates (`mouse_click`).
- Keep reasoning steps brief and concise.
- For complex multi-item tasks (playlists, batch operations), prefer compound tools that handle loops internally.
""",
        description="System prompt injected into the LLM context.",
    )


# ── Singleton ──────────────────────────────────────────────────────────────────
settings = NikkaSettings()
