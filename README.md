# Nikka 🤖

> **AI Desktop Agent for Windows OS Automation via Local LLMs**
> Created for & by **Anas Amchaar**

Nikka is a production-grade, low-context AI desktop assistant designed to run on Windows PCs powered by local LLMs (e.g., Gemma 3 12B / 4B via LM Studio) without requiring heavy vision models.

---

## 🚀 Key Features

- **Anti-Hallucination UI Abstraction**: Traverses the Windows UI Automation (UIA) tree via `pywinauto`, filters to interactive controls, and maps sequential integer IDs (e.g. `[ID: 1] Button: 'Save'`) to coordinates in internal memory. The LLM only reasons over IDs — never pixel coordinates.
- **Universal Multi-Modal Capabilities**:
  - **Native Windows Apps**: UI tree inspection (`get_screen_context`, `click_element`, `type_text`).
  - **Electron & Media (Spotify, Discord, VS Code, Chrome)**: System hotkeys (`press_hotkey`), global media controls (`media_control`), direct URI running (`open_uri_or_path`), and instant clipboard pasting (`paste_text`).
  - **Creative Suites & Canvas (Photoshop, Paint, Blender, CAD)**: Tool shortcuts (`press_key`), canvas drawing & brush strokes (`mouse_drag`), coordinate clicking (`mouse_click`), and mouse scrolling (`mouse_scroll`).
  - **Window & Workspace Management**: Window focus (`focus_window`), maximize/minimize/close, and virtual desktop migration (`switch_virtual_desktop`, `move_window_to_desktop`).
- **smolagents `CodeAgent` Integration**: High tool-calling precision using executable Python action steps.
- **Dynamic Tool Registry**: Auto-discovers any tool in `nikka.tools` without manual wiring.
- **Typed Pydantic Configuration**: Configure via `nikka/settings.py`, `.env` file, or CLI flags.
- **Physical Failsafe**: Integrated `pyautogui.FAILSAFE` — move mouse to screen corner to abort actions.

---

## 📦 Project Structure

```
Nikka/
├── pyproject.toml              # Modern Python packaging & dependencies
├── README.md                   # Documentation
├── .env.example                # Environment variables template
├── tests/                      # Unit tests
│   ├── __init__.py
│   └── test_tools.py
└── nikka/                      # Main package
    ├── __init__.py             # Version metadata
    ├── __main__.py             # python -m nikka entry point
    ├── settings.py             # Pydantic Settings with .env support
    ├── exceptions.py           # Custom exception hierarchy
    ├── logging.py              # Centralized logging
    ├── agent.py                # CodeAgent builder
    ├── cli.py                  # CLI & Interactive REPL
    ├── core/                   # UI tree traversal & coordinate mapping
    │   ├── __init__.py
    │   ├── ui_state.py         # Ephemeral ID ↔ Coordinate registry
    │   └── ui_parser.py        # pywinauto UIA tree walker
    └── tools/                  # Extensible tool modules
        ├── __init__.py         # Public tool exports
        ├── _registry.py        # Automatic tool discovery
        ├── screen.py           # Screen inspection & ID clicking
        ├── keyboard.py         # Keyboard input
        ├── desktop.py          # Virtual desktop switching & window moving
        └── apps.py             # Application launcher & process manager
```

---

## 🛠️ Installation & Setup

1. **Clone and activate your virtual environment:**
   ```powershell
   cd Nikka
   uv venv .venv
   .\.venv\Scripts\activate
   ```

2. **Install in editable mode with development dependencies:**
   ```powershell
   uv pip install -e ".[dev]"
   ```

3. **Start LM Studio:**
   - Load `google/gemma-3-12b` (or `gemma-3-4b`)
   - Enable the Local Server (port `1234`)

4. **Launch Nikka:**
   ```powershell
   nikka
   # or
   python -m nikka
   ```

---

## 🧩 Extending Nikka with New Tools

To add a new capability (e.g. file operations, clipboard, audio control):

1. Create a new file in `nikka/tools/` (e.g., `nikka/tools/clipboard.py`):
   ```python
   from smolagents import tool

   @tool
   def read_clipboard() -> str:
       """
       Read and return text currently stored in the Windows clipboard.
       """
       import pyperclip
       return pyperclip.paste()
   ```
2. That's it! `discover_tools()` automatically finds and registers any `@tool` in `nikka/tools/` on startup.

---

## 🧪 Running Tests

```powershell
pytest tests/ -v
```
