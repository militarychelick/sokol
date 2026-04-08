# -*- coding: utf-8 -*-
"""Fuzzy string matching for commands and synonyms (rapidfuzz)."""
from __future__ import annotations

import re
from typing import Iterable, List, Optional, Tuple

try:
    from rapidfuzz import fuzz
except ImportError:
    fuzz = None  # type: ignore


def _norm(s: str) -> str:
    return re.sub(r"[^\w\sа-яёa-z0-9]+", " ", (s or "").lower()).strip()


def best_match(
    query: str,
    choices: Iterable[str],
    *,
    threshold: int = 80,
) -> Tuple[Optional[str], int]:
    """
    Return (best_choice, score) if score >= threshold, else (None, best_score).
    Uses max of ratio and partial_ratio for robustness to typos and substrings.
    """
    q = _norm(query)
    if not q or fuzz is None:
        return None, 0
    best_c: Optional[str] = None
    best_s = 0
    for c in choices:
        cn = _norm(c)
        if not cn:
            continue
        s = max(fuzz.ratio(q, cn), fuzz.partial_ratio(q, cn))
        if s > best_s:
            best_s = s
            best_c = c
    if best_c is not None and best_s >= threshold:
        return best_c, int(best_s)
    return None, int(best_s)


def best_match_against_templates(query: str, templates: List[str], *, threshold: int = 78) -> bool:
    """True if query fuzzy-matches any template (short conversational phrases)."""
    q = _norm(query)
    if not q:
        return False
    if fuzz is None:
        return any(t in q for t in templates)
    for t in templates:
        tn = _norm(t)
        if not tn:
            continue
        if max(fuzz.ratio(q, tn), fuzz.partial_ratio(q, tn)) >= threshold:
            return True
    return False
