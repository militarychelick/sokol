# -*- coding: utf-8 -*-
"""Lightweight keyword recall over saved notes (optional RAG precursor)."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from .memory import ContextMemory


def recall_note_hints(memory: "ContextMemory", query: str, max_chars: int = 800) -> str:
    """
    Scan pinned notes for words from query; return concatenated excerpts.
    No embeddings — deterministic keyword overlap.
    """
    q = (query or "").lower()
    if len(q) < 2:
        return ""
    tokens = [t for t in re.split(r"\W+", q) if len(t) > 2]
    if not tokens:
        return ""

    notes = memory.pinned.get("notes") or []
    if not isinstance(notes, list):
        return ""

    hits: List[str] = []
    for entry in notes[-30:]:
        if not isinstance(entry, dict):
            continue
        text = (entry.get("text") or "").strip()
        if not text:
            continue
        low = text.lower()
        if any(t in low for t in tokens):
            hits.append(text[:400])

    if not hits:
        return ""
    blob = "\n---\n".join(hits[:5])
    return blob[:max_chars]
