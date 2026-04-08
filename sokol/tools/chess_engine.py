# -*- coding: utf-8 -*-
"""
External chess engine (Stockfish) via UCI. Path: STOCKFISH_PATH env or config.STOCKFISH_PATH.
"""
from __future__ import annotations

import os
import subprocess
import threading
from typing import List, Optional

from ..config import STOCKFISH_PATH

_LOCK = threading.Lock()


def _engine_exe() -> Optional[str]:
    p = (STOCKFISH_PATH or os.environ.get("STOCKFISH_PATH") or "").strip()
    return p if p and os.path.isfile(p) else None


def best_move(fen: str, movetime_ms: int = 400) -> tuple[bool, str]:
    """
    Return (ok, san_or_error). Requires Stockfish binary.
    """
    exe = _engine_exe()
    if not exe:
        return False, "Stockfish not configured: set STOCKFISH_PATH to stockfish.exe"
    fen = (fen or "").strip()
    if not fen:
        return False, "Empty FEN"

    try:
        proc = subprocess.Popen(
            [exe],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError as e:
        return False, f"Cannot start engine: {e}"

    def cmd(line: str) -> None:
        assert proc.stdin
        proc.stdin.write(line + "\n")
        proc.stdin.flush()

    try:
        cmd("uci")
        lines: List[str] = []
        assert proc.stdout
        while True:
            line = proc.stdout.readline()
            if not line:
                break
            lines.append(line.strip())
            if line.strip() == "uciok":
                break
        cmd("isready")
        while True:
            line = proc.stdout.readline()
            if not line:
                break
            if line.strip() == "readyok":
                break
        cmd(f"position fen {fen}")
        cmd(f"go movetime {max(50, int(movetime_ms))}")
        best = ""
        while True:
            line = proc.stdout.readline()
            if not line:
                break
            line = line.strip()
            if line.startswith("bestmove "):
                parts = line.split()
                if len(parts) >= 2 and parts[1] != "(none)":
                    best = parts[1]
                break
        cmd("quit")
        proc.wait(timeout=5)
        if best:
            return True, best
        return False, "No legal move (game over or invalid FEN?)"
    except Exception as e:
        try:
            proc.kill()
        except Exception:
            pass
        return False, str(e)


def best_move_threadsafe(fen: str, movetime_ms: int = 400) -> tuple[bool, str]:
    with _LOCK:
        return best_move(fen, movetime_ms=movetime_ms)
