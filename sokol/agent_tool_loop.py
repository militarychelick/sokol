# -*- coding: utf-8 -*-
"""
Structured tool round-trip: classify → validate → execute (single pass).

Use this as the extension point for multi-step ReAct loops later.
For now the main GUI still uses ActionDispatcher.dispatch; this module
documents the intended contract and can be wired via env SOKOL_TOOL_LOOP=1.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Tuple

from .action_schemas import validate_llm_action
from .tool_registry import tools_prompt_block

_log = logging.getLogger("sokol.tool_loop")


def tool_loop_enabled() -> bool:
    return os.environ.get("SOKOL_TOOL_LOOP", "").strip().lower() in ("1", "true", "yes", "on")


def classify_validate_execute(
    user_input: str,
    gui: Any,
    dispatcher_cls: Any,
) -> Tuple[bool, Any]:
    """
    One classify round: LLM classify → pydantic validate → execute_action.
    Returns (ok, message_or_quick_result).
    """
    llm = dispatcher_cls._get_llm_client(gui)
    if llm is None:
        return False, "LLM unavailable."
    raw = llm.classify(user_input)
    rtype, action = dispatcher_cls.parse_classify(raw)
    if rtype != "action" or not action:
        return True, None  # signal caller to run chat
    validated, err = validate_llm_action(action)
    if err:
        _log.warning("tool_loop: validation failed: %s", err)
        return True, None
    return dispatcher_cls.execute_action(validated, gui, user_input=user_input)


def augment_classify_prompt(base_prompt: str) -> str:
    """Append compact tool registry (for experiments)."""
    if os.environ.get("SOKOL_PROMPT_TOOLS", "").strip().lower() not in ("1", "true", "yes", "on"):
        return base_prompt
    return base_prompt + "\n\n" + tools_prompt_block()
