# -*- coding: utf-8 -*-
"""Central logging + audit file for Sokol."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from .config import SOKOL_LOG_DIR


_SETUP_DONE = False


def setup_logging(level: int | None = None) -> None:
    """Idempotent basic config: console + rotating-style single file."""
    global _SETUP_DONE
    if _SETUP_DONE:
        return
    env_lvl = os.environ.get("SOKOL_LOG_LEVEL", "INFO").upper()
    lvl = level if level is not None else getattr(logging, env_lvl, logging.INFO)
    Path(SOKOL_LOG_DIR).mkdir(parents=True, exist_ok=True)
    log_path = os.path.join(SOKOL_LOG_DIR, "sokol.log")
    audit_path = os.path.join(SOKOL_LOG_DIR, "sokol_audit.log")

    root = logging.getLogger()
    root.setLevel(lvl)
    if not root.handlers:
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        root.addHandler(sh)
        try:
            fh = logging.FileHandler(log_path, encoding="utf-8")
            fh.setFormatter(fmt)
            root.addHandler(fh)
        except OSError:
            pass

    audit = logging.getLogger("sokol.audit")
    audit.setLevel(logging.INFO)
    audit.propagate = False
    if not audit.handlers:
        try:
            ah = logging.FileHandler(audit_path, encoding="utf-8")
            ah.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
            audit.addHandler(ah)
        except OSError:
            pass

    _SETUP_DONE = True


def audit_line(message: str) -> None:
    """Security-sensitive events (no passwords / full command bodies)."""
    setup_logging()
    logging.getLogger("sokol.audit").info(message)
