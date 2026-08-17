"""
Nikka — Agent Factory Module.

Configures and builds the smolagents CodeAgent wired to the local LLM endpoint.
"""

from __future__ import annotations

import logging
import re
from typing import Sequence

from smolagents import CodeAgent, LiteLLMModel
from smolagents.tools import Tool

from nikka.settings import settings
from nikka.tools._registry import discover_tools

logger = logging.getLogger("nikka.agent")


# ── Patch smolagents code parser for local LLM compatibility ──────────────────
# Local models (Gemma, Llama, Mistral, etc.) sometimes output code blocks with
# non-standard language tags like ```tool_code, ```code, ```Tool, etc.
# The stock smolagents parser only accepts ```python/```py and <code> tags.
# This patch normalizes those before parsing so Nikka works reliably with any LLM.

_CODE_BLOCK_ALIASES = re.compile(
    r"```(?:tool_code|code|tool|py|python|Tool_code|PYTHON)\b",
    re.IGNORECASE,
)


def _patch_code_parser() -> None:
    """Monkey-patch smolagents.utils.parse_code_blobs for broader format support."""
    import smolagents.utils as _utils

    _original_parse = _utils.parse_code_blobs

    def _patched_parse(text: str, code_block_tags: tuple[str, str]) -> str:
        # Normalize any non-standard code block tags to ```python
        normalized = _CODE_BLOCK_ALIASES.sub("```python", text)
        return _original_parse(normalized, code_block_tags)

    _utils.parse_code_blobs = _patched_parse

    # Also patch at the module level where agents.py imported it
    try:
        import smolagents.agents as _agents

        _agents.parse_code_blobs = _patched_parse
    except (ImportError, AttributeError):
        pass

    logger.debug("Patched smolagents code parser for local LLM compatibility")


_patch_code_parser()


# ── Agent factory ─────────────────────────────────────────────────────────────


def build_agent(
    custom_tools: Sequence[Tool] | None = None,
    model_id: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    max_steps: int | None = None,
) -> CodeAgent:
    """
    Build and return a fully configured CodeAgent instance for Windows automation.

    Args:
        custom_tools: Optional custom list of smolagents tools. If None, auto-discovers
                      all tools inside the `nikka.tools` package.
        model_id: Optional model identifier override.
        base_url: Optional endpoint URL override.
        api_key: Optional API key override.
        max_steps: Optional maximum ReAct steps per task.

    Returns:
        Configured CodeAgent ready to execute tasks.
    """
    target_model_id = model_id or settings.lm_studio_model_id
    target_base_url = base_url or settings.lm_studio_base_url
    target_api_key = api_key or settings.lm_studio_api_key
    target_max_steps = max_steps or settings.max_agent_steps

    logger.info("Initializing LLM client: %s @ %s", target_model_id, target_base_url)

    model = LiteLLMModel(
        model_id=target_model_id,
        api_base=target_base_url,
        api_key=target_api_key,
    )

    tools_to_use = list(custom_tools) if custom_tools is not None else discover_tools()
    logger.info("Configured agent with %d tools: %s", len(tools_to_use), [t.name for t in tools_to_use])

    agent = CodeAgent(
        tools=tools_to_use,
        model=model,
        max_steps=target_max_steps,
        add_base_tools=False,
        code_block_tags="markdown",
    )

    return agent

