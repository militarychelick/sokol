# -*- coding: utf-8 -*-
from pathlib import Path

root = Path(__file__).resolve().parent.parent
p = root / "sokol" / "dispatcher.py"
lines = p.read_text(encoding="utf-8").splitlines(True)
# Keep first 17 lines (docstring header), replace body through before ActionDispatcher
# Original file: ActionDispatcher starts at line 707 -> index 706
tail = "".join(lines[702:])

new_head = '''# -*- coding: utf-8 -*-
"""
SOKOL — Dispatcher: ActionDispatcher + LLM routing.

Routing pieces live in pre_router, vision_agent, prompts.
"""

import os
import re
import json
import time
import ast
import random
import copy
import logging
import threading
import urllib.request
from datetime import datetime

from .config import (
    OLLAMA_MODEL, OLLAMA_API_BASE, VERSION,
    SYSTEM_TOOLS, WEB_SERVICES, FOLDER_ALIASES, RUS_APP_MAP,
    VISION_MAX_STEPS, VISION_STEP_DELAY, SOKOL_GPU_BACKEND,
    CONTACTS_PATH, KNOWLEDGE_BASE_PATH, NOTES_PATH,
)
from .core import CodeExecutor, INTERRUPT
from .tools import (
    SystemTools, SmartLauncher, ProcessKiller, WebRouter,
    MediaController, PowerController, NetworkDiag, SystemTriage,
    WindowManager, ScreenManager, FileMachine, FileAgent,
    WindowEnumerator, ServiceManager, WiFiManager, DiskAnalyzer,
    StartupManager, SystemQuickInfo, ContentSearch,
)
from .automation import GUIAutomation, ScreenCapture, VisionLite, BulkFileOps
from .terminal import TerminalExecutor, SystemDashboard
from .web_fetcher import WebFetcher
from .deep_research import DeepResearchAgent
from .special_modes import DeepClean, GamingMode, GhostMode
from .memory import ClipboardManager
from .tools.stem import STEMCore
from .tools.info_hub import InfoHub

from .pre_router import PreRouter, HELP_TEXT
from .vision_agent import VisionAgent
from .prompts import CLASSIFY_PROMPT, CHAT_SYSTEM_MESSAGE
from . import policy
from .action_schemas import validate_llm_action, coerce_action_dict
from .agent_tool_loop import tool_loop_enabled, classify_validate_execute
from .rag_hints import recall_note_hints
from .logging_config import audit_line

_log = logging.getLogger("sokol.dispatcher")


'''

p.write_text(new_head + "\n" + tail, encoding="utf-8")
print("dispatcher rebuilt, bytes", p.stat().st_size)
