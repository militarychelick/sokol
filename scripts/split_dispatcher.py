# -*- coding: utf-8 -*-
"""One-off helper to extract modules from dispatcher.py (run from repo root)."""
from pathlib import Path

root = Path(__file__).resolve().parent.parent
lines = (root / "sokol" / "dispatcher.py").read_text(encoding="utf-8").splitlines(True)

help_src = "".join(lines[55:105])
vision_src = "".join(lines[107:310])
pr_src = "".join(lines[317:645])
prompts_tail = "".join(lines[651:700])

pre_router = (
    "# -*- coding: utf-8 -*-\n"
    '"""Instant regex routing (PreRouter) and help text."""\n'
    "import re\n"
    "import textwrap\n\n"
    "from .config import VERSION, SYSTEM_TOOLS, WEB_SERVICES, FOLDER_ALIASES, RUS_APP_MAP\n\n"
    + help_src
    + "\n\n"
    + pr_src
)
(root / "sokol" / "pre_router.py").write_text(pre_router, encoding="utf-8")

vision = (
    "# -*- coding: utf-8 -*-\n"
    '"""VisionAgent: OCR + LLM step loop for GUI automation."""\n'
    "import json\n"
    "import re\n"
    "import time\n\n"
    "from .config import VISION_MAX_STEPS, VISION_STEP_DELAY\n"
    "from .core import INTERRUPT\n"
    "from .automation import GUIAutomation, VisionLite\n"
    "from .tools import SmartLauncher\n\n"
    + vision_src
)
(root / "sokol" / "vision_agent.py").write_text(vision, encoding="utf-8")

prompts = (
    "# -*- coding: utf-8 -*-\n"
    '"""LLM system / classify prompts for Sokol."""\n'
    "import textwrap\n\n"
    "CLASSIFY_PROMPT = "
    + prompts_tail.split("CLASSIFY_PROMPT =", 1)[1]
)
(root / "sokol" / "prompts.py").write_text(prompts, encoding="utf-8")
print("OK: pre_router.py, vision_agent.py, prompts.py")
