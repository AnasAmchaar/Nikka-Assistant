"""
Nikka — Centralised logging configuration.

Call :func:`setup_logging` once at startup.  All modules then use
``logging.getLogger("nikka.<component>")`` as usual.
"""

from __future__ import annotations

import logging
import sys

from colorama import Fore, Style, init as colorama_init

from nikka.settings import settings

_LOG_FORMAT = (
    Fore.CYAN + "%(asctime)s " + Style.RESET_ALL
    + "%(levelname)-8s "
    + Fore.YELLOW + "%(name)s" + Style.RESET_ALL
    + " │ %(message)s"
)

_NOISY_LOGGERS = (
    "httpx",
    "httpcore",
    "openai",
    "litellm",
    "LiteLLM",
)


def setup_logging() -> None:
    """Initialise the root logger and silence noisy third-party loggers."""
    colorama_init(autoreset=True)

    level_map = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}
    level = level_map.get(settings.verbosity, logging.DEBUG)

    logging.basicConfig(level=level, format=_LOG_FORMAT, stream=sys.stderr)

    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    logging.getLogger("smolagents").setLevel(logging.INFO)
