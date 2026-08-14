"""
Nikka — Agent Entry Point
Sets up the smolagents CodeAgent backed by the local LM Studio endpoint,
injects all OS tools, and runs an interactive terminal REPL.

Usage:
    python agent.py
"""

from __future__ import annotations

import logging
import sys
from typing import NoReturn

from colorama import Fore, Style, init as colorama_init
from smolagents import LiteLLMModel, CodeAgent, tool

import config
import os_tools

# ─── Logging Setup ─────────────────────────────────────────────────────────────

LOG_FORMAT = (
    Fore.CYAN + "%(asctime)s " + Style.RESET_ALL
    + "%(levelname)-8s "
    + Fore.YELLOW + "%(name)s" + Style.RESET_ALL
    + " │ %(message)s"
)

def _setup_logging() -> None:
    colorama_init(autoreset=True)
    level = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}.get(
        config.AGENT_VERBOSITY, logging.DEBUG
    )
    logging.basicConfig(level=level, format=LOG_FORMAT, stream=sys.stderr)
    # Quiet noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("litellm").setLevel(logging.WARNING)
    logging.getLogger("LiteLLM").setLevel(logging.WARNING)
    logging.getLogger("smolagents").setLevel(logging.INFO)


# ─── Wrap OS Functions as smolagents @tool ──────────────────────────────────────
# smolagents needs the @tool decorator to extract metadata (name, description,
# arg types) from docstrings.  We re-export the os_tools functions here with
# the decorator so the underlying logic stays in os_tools.py.

@tool
def get_screen_context() -> str:
    """
    Parse the active window's UI tree and return a numbered list of interactive
    elements (buttons, text fields, menus, etc.).  Each element is assigned a
    unique integer ID that can be used with click_element().

    Call this FIRST to see what is on screen before acting.

    Returns:
        A formatted string listing all interactive elements with IDs.
    """
    return os_tools.get_screen_context()


@tool
def click_element(element_id: int) -> str:
    """
    Left-click the interactive element with the given numeric ID.
    The ID must come from the most recent get_screen_context() output.

    Args:
        element_id: The integer ID of the element to click.

    Returns:
        Confirmation of what was clicked, or an error if the ID is invalid.
    """
    return os_tools.click_element(element_id)


@tool
def type_text(text: str, submit: bool = True) -> str:
    """
    Type the specified string using the keyboard.
    Optionally presses Enter afterwards to submit.

    Args:
        text:   The string to type.
        submit: If True, press Enter after typing. Defaults to True.

    Returns:
        Confirmation string.
    """
    return os_tools.type_text(text, submit)


@tool
def switch_virtual_desktop(desktop_number: int) -> str:
    """
    Switch to a specific Windows virtual desktop.

    Args:
        desktop_number: Target desktop number (1-indexed: 1, 2, 3, …).

    Returns:
        Confirmation or error if the desktop doesn't exist.
    """
    return os_tools.switch_virtual_desktop(desktop_number)


@tool
def move_window_to_desktop(app_name: str, desktop_number: int) -> str:
    """
    Move an open window to a different virtual desktop. The window is found
    by matching app_name against window titles (case-insensitive substring).

    Args:
        app_name:       Name or substring of the window title to find.
        desktop_number: Target desktop number (1-indexed).

    Returns:
        Confirmation or error message.
    """
    return os_tools.move_window_to_desktop(app_name, desktop_number)


@tool
def launch_application(app_name: str) -> str:
    """
    Launch a Windows application by friendly name.
    Supported names include: edge, chrome, notepad, explorer, terminal,
    calculator, paint, vscode, settings, and more.

    Args:
        app_name: Friendly application name (e.g. "edge", "notepad").

    Returns:
        Confirmation or error message.
    """
    return os_tools.launch_application(app_name)


# ─── Agent Initialization ──────────────────────────────────────────────────────

def _build_agent() -> CodeAgent:
    """Create the smolagents CodeAgent wired to LM Studio."""
    logger = logging.getLogger("nikka.agent")
    logger.info(
        "Connecting to LM Studio at %s (model: %s)",
        config.LM_STUDIO_BASE_URL,
        config.LM_STUDIO_MODEL_ID,
    )

    model = LiteLLMModel(
        model_id=config.LM_STUDIO_MODEL_ID,
        api_base=config.LM_STUDIO_BASE_URL,
        api_key=config.LM_STUDIO_API_KEY,
    )

    agent = CodeAgent(
        tools=[
            get_screen_context,
            click_element,
            type_text,
            switch_virtual_desktop,
            move_window_to_desktop,
            launch_application,
        ],
        model=model,
        max_steps=config.MAX_AGENT_STEPS,
        add_base_tools=False,
    )

    logger.info("Agent initialised with %d tools.", len(agent.tools))
    return agent


# ─── Interactive REPL ───────────────────────────────────────────────────────────

_BANNER = f"""
{Fore.MAGENTA}{'━' * 60}{Style.RESET_ALL}
{Fore.MAGENTA}  ███╗   ██╗██╗██╗  ██╗██╗  ██╗ █████╗
  ████╗  ██║██║██║ ██╔╝██║ ██╔╝██╔══██╗
  ██╔██╗ ██║██║█████╔╝ █████╔╝ ███████║
  ██║╚██╗██║██║██╔═██╗ ██╔═██╗ ██╔══██║
  ██║ ╚████║██║██║  ██╗██║  ██╗██║  ██║
  ╚═╝  ╚═══╝╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝{Style.RESET_ALL}

{Fore.CYAN}  AI Desktop Agent — For & By Anas Amchaar{Style.RESET_ALL}
{Fore.WHITE}  Model : {config.LM_STUDIO_MODEL_ID}{Style.RESET_ALL}
{Fore.WHITE}  Endpoint: {config.LM_STUDIO_BASE_URL}{Style.RESET_ALL}
{Fore.MAGENTA}{'━' * 60}{Style.RESET_ALL}

{Fore.GREEN}  Type a command (e.g. "Open edge on desktop 2"){Style.RESET_ALL}
{Fore.GREEN}  Type 'quit' or 'exit' to stop.{Style.RESET_ALL}
{Fore.GREEN}  Type 'context' to view current UI elements.{Style.RESET_ALL}
{Fore.GREEN}  Type 'apps' to list running applications.{Style.RESET_ALL}
"""


def _repl(agent: CodeAgent) -> NoReturn:
    """Run the interactive terminal loop."""
    logger = logging.getLogger("nikka.repl")
    print(_BANNER)

    while True:
        try:
            user_input = input(f"\n{Fore.GREEN}Nikka ❯ {Style.RESET_ALL}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{Fore.YELLOW}Goodbye!{Style.RESET_ALL}")
            sys.exit(0)

        if not user_input:
            continue

        lower = user_input.lower()
        if lower in ("quit", "exit", "q"):
            print(f"{Fore.YELLOW}Goodbye!{Style.RESET_ALL}")
            sys.exit(0)

        # ── Quick shortcuts that bypass the LLM ──
        if lower == "context":
            print(os_tools.get_screen_context())
            continue
        if lower == "apps":
            print(os_tools.list_running_apps())
            continue

        # ── Send to the agent ──
        print(f"{Fore.CYAN}⏳ Thinking…{Style.RESET_ALL}")
        try:
            result = agent.run(user_input)
            print(f"\n{Fore.MAGENTA}Nikka:{Style.RESET_ALL} {result}")
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}⚠ Interrupted.{Style.RESET_ALL}")
        except Exception as exc:
            logger.error("Agent error: %s", exc, exc_info=True)
            print(f"{Fore.RED}❌ Error: {exc}{Style.RESET_ALL}")


# ─── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    _setup_logging()
    agent = _build_agent()
    _repl(agent)


if __name__ == "__main__":
    main()
