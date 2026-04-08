# -*- coding: utf-8 -*-
"""Pydantic validation for LLM-produced action JSON."""
from __future__ import annotations

import logging
from typing import Any, Optional, Tuple

from pydantic import BaseModel, Field

_log = logging.getLogger("sokol.actions")


class LlmActionModel(BaseModel):
    """Structured action from classify / tool loop."""

    model_config = {"extra": "allow"}

    type: str = Field(..., min_length=1, max_length=120)
    target: str = ""
    params: dict[str, Any] = Field(default_factory=dict)


def validate_llm_action(raw: Optional[dict]) -> Tuple[Optional[dict], Optional[str]]:
    """
    Validate and normalize action dict.
    Returns (normalized_dict, None) or (None, error_message).
    """
    if not raw or not isinstance(raw, dict):
        return None, "not_a_dict"
    try:
        m = LlmActionModel.model_validate(raw)
        return m.model_dump(), None
    except Exception as e:
        return None, str(e)


def coerce_action_dict(d: dict) -> dict:
    """Best-effort normalization without failing (for internal/pre-router actions)."""
    try:
        m = LlmActionModel.model_validate(d)
        return m.model_dump()
    except Exception:
        return d
