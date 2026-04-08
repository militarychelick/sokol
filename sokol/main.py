# -*- coding: utf-8 -*-
"""SOKOL v7.2 — Entry Point"""
import os
import sys
import json
import urllib.request
import tkinter as tk
from tkinter import messagebox
from .config import OLLAMA_MODEL, OLLAMA_API_BASE


def _configure_stdio_utf8():
    """Avoid UnicodeEncodeError on Windows when libraries print █/Unicode to the console."""
    if sys.platform != "win32":
        return
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def preflight_check():
    """Verify Ollama is reachable and model is available (skipped if Groq is primary)."""
    if (os.environ.get("GROQ_API_KEY") or "").strip():
        return True, "OK"
    try:
        req = urllib.request.Request(f"{OLLAMA_API_BASE}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status != 200:
                return False, "Ollama not responding."
            data = json.loads(resp.read().decode())
    except Exception:
        return False, f"Cannot connect to Ollama at {OLLAMA_API_BASE}"

    models = [m.get("name", "") for m in data.get("models", [])]
    model_found = any(OLLAMA_MODEL in m for m in models)

    if not model_found:
        return False, (
            f"Model '{OLLAMA_MODEL}' not found.\n"
            f"Available: {', '.join(models[:10]) if models else '(none)'}\n\n"
            f"Run:  ollama pull {OLLAMA_MODEL}"
        )
    return True, "OK"


def main():
    _configure_stdio_utf8()
    from .logging_config import setup_logging
    setup_logging()
    ok, msg = preflight_check()
    if not ok:
        root = tk.Tk()
        root.withdraw()
        retry = messagebox.askretrycancel(
            "Sokol — Connection Error",
            f"{msg}\n\n"
            "Make sure:\n"
            "  1. Ollama is installed and running\n"
            f"  2. Model pulled: ollama pull {OLLAMA_MODEL}\n\n"
            "Retry?",
        )
        root.destroy()
        if retry:
            return main()
        sys.exit(1)

    from .gui_main import SokolGUI
    try:
        app = SokolGUI()
        app.run()
    except KeyboardInterrupt:
        pass # Gracefully handle manual exit via console Ctrl+C
