"""
Nikka — Configuration Constants
All tunables for the LM Studio endpoint, model behaviour, and system prompt.
"""

# ─── LM Studio Endpoint ────────────────────────────────────────────────────────
LM_STUDIO_BASE_URL = "http://127.0.0.1:1234/v1"
LM_STUDIO_API_KEY  = "lm-studio"          # LM Studio ignores this, but the SDK requires it
LM_STUDIO_MODEL_ID = "openai/google/gemma-3-12b"  # 'openai/' prefix tells LiteLLM to use OpenAI-compatible API

# ─── Agent Tuning ──────────────────────────────────────────────────────────────
MAX_AGENT_STEPS      = 12        # hard ceiling on ReAct iterations per request
AGENT_VERBOSITY      = 2         # 0 = silent, 1 = summary, 2 = full trace
UI_PARSE_DEPTH       = 40        # max depth when walking the pywinauto element tree
UI_MAX_ELEMENTS      = 80        # cap elements sent to LLM to save context tokens
APP_LAUNCH_WAIT_SEC  = 3.0       # seconds to wait after subprocess.Popen before moving window

# ─── Application Aliases ───────────────────────────────────────────────────────
# Maps friendly names → shell commands understood by `subprocess.Popen(shell=True)`
APP_ALIASES: dict[str, str] = {
    "edge":          "start msedge",
    "browser":       "start msedge",
    "chrome":        "start chrome",
    "firefox":       "start firefox",
    "notepad":       "start notepad",
    "explorer":      "start explorer",
    "file explorer":  "start explorer",
    "terminal":      "start wt",
    "cmd":           "start cmd",
    "powershell":    "start powershell",
    "calculator":    "start calc",
    "calc":          "start calc",
    "paint":         "start mspaint",
    "word":          "start winword",
    "excel":         "start excel",
    "powerpoint":    "start powerpnt",
    "vscode":        "start code",
    "code":          "start code",
    "spotify":       "start spotify",
    "discord":       "start discord",
    "settings":      "start ms-settings:",
    "task manager":  "start taskmgr",
}

# ─── System Prompt ──────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
You are **Nikka**, an expert AI assistant that controls a Windows PC.

## How You Work
1. You receive a **UI Context** — a numbered list of interactive elements visible
   in the active window (buttons, text fields, menu items, etc.).
2. You reason step-by-step about what action to take next.
3. You call **exactly one tool** per step.

## Available Tools
| Tool | Purpose |
|------|---------|
| `get_screen_context()` | Read the current window's interactive elements. Call this FIRST. |
| `click_element(element_id)` | Left-click the element with the given numeric ID. |
| `type_text(text, submit)` | Type text. Set `submit=True` to press Enter after. |
| `switch_virtual_desktop(desktop_number)` | Go to virtual desktop N (1-indexed). |
| `move_window_to_desktop(app_name, desktop_number)` | Push a window to another desktop. |
| `launch_application(app_name)` | Open an app by name (e.g. "edge", "notepad"). |

## Rules
- **NEVER guess coordinates.** Always use `click_element` with an ID from the context.
- If unsure what's on screen, call `get_screen_context()` to refresh.
- Keep your reasoning short — you have limited context.
- After completing the user's request, give a brief confirmation.
"""
