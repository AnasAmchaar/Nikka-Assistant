"""
Nikka — Tool Registry & Auto-Discovery Helper.

Provides utilities for discovering, managing, and registering tools
for the smolagents CodeAgent.
"""

from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
from typing import Any

from smolagents.tools import Tool

logger = logging.getLogger("nikka.tools")


def discover_tools(package_name: str = "nikka.tools") -> list[Tool]:
    """
    Dynamically discover and collect all smolagents Tool instances
    defined or decorated in submodules of the specified package.
    """
    tools: list[Tool] = []
    seen_names: set[str] = set()

    try:
        package = importlib.import_module(package_name)
    except Exception as exc:
        logger.error("Failed to import package %s for tool discovery: %s", package_name, exc)
        return tools

    package_path = getattr(package, "__path__", None)
    if not package_path:
        return tools

    for _, module_name, _ in pkgutil.iter_modules(package_path):
        if module_name.startswith("_"):
            continue

        full_module_name = f"{package_name}.{module_name}"
        try:
            mod = importlib.import_module(full_module_name)
            for attr_name in dir(mod):
                if attr_name.startswith("_"):
                    continue
                attr = getattr(mod, attr_name)
                # Check if attr is a smolagents Tool instance or Tool subclass
                if isinstance(attr, Tool):
                    if attr.name not in seen_names:
                        seen_names.add(attr.name)
                        tools.append(attr)
                        logger.debug("Discovered tool: %s (%s)", attr.name, full_module_name)
                elif inspect.isclass(attr) and issubclass(attr, Tool) and attr is not Tool:
                    # Instantiable Tool class
                    try:
                        instance = attr()
                        if instance.name not in seen_names:
                            seen_names.add(instance.name)
                            tools.append(instance)
                            logger.debug("Instantiated and registered tool class: %s (%s)", instance.name, full_module_name)
                    except Exception as inst_exc:
                        logger.warning("Could not auto-instantiate tool class %s: %s", attr_name, inst_exc)
        except Exception as exc:
            logger.error("Error loading tools from module %s: %s", full_module_name, exc)

    return tools
