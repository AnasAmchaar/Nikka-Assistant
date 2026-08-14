"""
Nikka — Process and Application Management Tools.
"""

from __future__ import annotations

import logging
import subprocess
import time

import psutil
from smolagents import tool

from nikka.settings import settings

logger = logging.getLogger("nikka.tools.apps")


@tool
def launch_application(app_name: str) -> str:
    """
    Launch a Windows application by name or common alias.
    Supported shortcuts include: edge, chrome, firefox, notepad, explorer,
    terminal, calculator, paint, vscode, spotify, settings, etc.

    Args:
        app_name: Friendly name or path of the application (e.g., 'notepad', 'edge').

    Returns:
        Confirmation or error message.
    """
    key = app_name.strip().lower()
    cmd = settings.app_aliases.get(key, f"start {key}")
    logger.info("Launching '%s' via command: `%s`", app_name, cmd)

    try:
        subprocess.Popen(cmd, shell=True)
        time.sleep(settings.app_launch_wait_sec)
        return f"Successfully launched '{app_name}' (executed command: `{cmd}`)."
    except Exception as exc:
        logger.error("Failed to launch application '%s': %s", app_name, exc)
        return f"Failed to launch '{app_name}': {exc}"


@tool
def list_running_apps() -> str:
    """
    Get a compact list of currently active user-facing applications and processes.

    Returns:
        A formatted list of active process names and PIDs.
    """
    seen: set[str] = set()
    lines: list[str] = ["Running user applications:"]
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            name = proc.info["name"]
            if name and name not in seen and not name.lower().startswith("svchost"):
                seen.add(name)
                lines.append(f"  • {name} (PID: {proc.info['pid']})")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return "\n".join(lines[:50])
