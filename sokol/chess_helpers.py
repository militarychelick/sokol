# -*- coding: utf-8 -*-
"""
Optional chess utilities when the `chess` package (python-chess) is installed.
Install: pip install chess   or   pip install ".[chess]" from project root.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

try:
    import chess
except ImportError:
    chess = None  # type: ignore


def chess_available() -> bool:
    return chess is not None


def legal_sans_from_fen(fen: str) -> Optional[List[str]]:
    """Return SAN strings for all legal moves, or None if FEN invalid / library missing."""
    if chess is None or not (fen or "").strip():
        return None
    try:
        board = chess.Board(fen.strip())
        return [board.san(m) for m in board.legal_moves]
    except ValueError:
        return None


def parse_san_legal(fen: str, san: str) -> Tuple[bool, str]:
    """
    True if `san` is a legal move from `fen`.
    On missing library or bad FEN, returns (True, "skip") so callers do not block the UI.
    """
    if chess is None:
        return True, "chess_not_installed"
    try:
        board = chess.Board((fen or "").strip())
    except ValueError:
        return False, "invalid_fen"
    try:
        move = board.parse_san((san or "").strip())
    except ValueError:
        return False, "illegal_or_unparseable_san"
    if move not in board.legal_moves:
        return False, "not_legal"
    return True, board.san(move)
