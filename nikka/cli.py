"""
Nikka — Command Line Interface & Interactive REPL.
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import NoReturn

from colorama import Fore, Style

from nikka import __version__
from nikka.agent import build_agent
from nikka.core.ui_parser import parse_screen_context
from nikka.logging import setup_logging
from nikka.settings import settings
from nikka.tools.apps import list_running_apps

logger = logging.getLogger("nikka.cli")

BANNER = f"""
{Fore.MAGENTA}{'━' * 60}{Style.RESET_ALL}
{Fore.MAGENTA}  ███╗   ██╗██╗██╗  ██╗██╗  ██╗ █████╗
  ████╗  ██║██║██║ ██╔╝██║ ██╔╝██╔══██╗
  ██╔██╗ ██║██║█████╔╝ █████╔╝ ███████║
  ██║╚██╗██║██║██╔═██╗ ██╔═██╗ ██╔══██║
  ██║ ╚████║██║██║  ██╗██║  ██╗██║  ██║
  ╚═╝  ╚═══╝╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝{Style.RESET_ALL}

{Fore.CYAN}  AI Desktop Agent (v{__version__}) — For & By Anas Amchaar{Style.RESET_ALL}
{Fore.WHITE}  Model   : {settings.lm_studio_model_id}{Style.RESET_ALL}
{Fore.WHITE}  Endpoint: {settings.lm_studio_base_url}{Style.RESET_ALL}
{Fore.MAGENTA}{'━' * 60}{Style.RESET_ALL}

{Fore.GREEN}  Commands:{Style.RESET_ALL}
  • Type any instruction: {Fore.YELLOW}"Open edge on desktop 2"{Style.RESET_ALL}
  • {Fore.CYAN}context{Style.RESET_ALL} : Inspect current UI tree without calling LLM
  • {Fore.CYAN}apps{Style.RESET_ALL}    : List active user applications
  • {Fore.CYAN}exit{Style.RESET_ALL} / {Fore.CYAN}quit{Style.RESET_ALL} : Stop Nikka
"""


def repl(agent) -> NoReturn:
    """Run the interactive REPL session."""
    print(BANNER)

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

        # Quick direct actions
        if lower == "context":
            try:
                print(parse_screen_context())
            except Exception as exc:
                print(f"{Fore.RED}Error inspecting UI: {exc}{Style.RESET_ALL}")
            continue

        if lower == "apps":
            print(list_running_apps())
            continue

        # Execute through agent
        print(f"{Fore.CYAN}⏳ Thinking…{Style.RESET_ALL}")
        try:
            result = agent.run(user_input)
            print(f"\n{Fore.MAGENTA}Nikka:{Style.RESET_ALL} {result}")
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}⚠ Action interrupted by user.{Style.RESET_ALL}")
        except Exception as exc:
            logger.error("Execution error: %s", exc, exc_info=True)
            print(f"{Fore.RED}❌ Error: {exc}{Style.RESET_ALL}")


def main() -> None:
    """CLI entry point parsing arguments and launching Nikka."""
    parser = argparse.ArgumentParser(
        prog="nikka",
        description="Nikka — AI Desktop Agent for Windows automation via local LLM.",
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        help="Optional single command to execute non-interactively (e.g. 'nikka \"open edge\"').",
    )
    parser.add_argument(
        "--model",
        default=None,
        help=f"Override LLM model ID (default: {settings.lm_studio_model_id})",
    )
    parser.add_argument(
        "--url",
        default=None,
        help=f"Override LLM API base URL (default: {settings.lm_studio_base_url})",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=None,
        help=f"Max ReAct agent steps (default: {settings.max_agent_steps})",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose DEBUG logging.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"Nikka v{__version__}",
    )

    args = parser.parse_args()

    if args.verbose:
        settings.verbosity = 2

    setup_logging()

    agent = build_agent(
        model_id=args.model,
        base_url=args.url,
        max_steps=args.steps,
    )

    if args.prompt:
        # Non-interactive single command
        try:
            result = agent.run(args.prompt)
            print(f"{Fore.MAGENTA}Nikka:{Style.RESET_ALL} {result}")
        except Exception as exc:
            logger.error("Command execution error: %s", exc)
            print(f"{Fore.RED}Error: {exc}{Style.RESET_ALL}", file=sys.stderr)
            sys.exit(1)
    else:
        repl(agent)


if __name__ == "__main__":
    main()
