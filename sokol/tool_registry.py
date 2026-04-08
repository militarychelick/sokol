# -*- coding: utf-8 -*-
"""Tool metadata: risk tiers and descriptions for routing / future native tool-calling."""
from __future__ import annotations

from enum import IntEnum
from typing import Any


class RiskTier(IntEnum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3


# Known action types -> default risk (unknown types treated as MEDIUM)
ACTION_RISK: dict[str, RiskTier] = {
    "help": RiskTier.LOW,
    "identity": RiskTier.LOW,
    "get_joke": RiskTier.LOW,
    "get_fact": RiskTier.LOW,
    "get_history": RiskTier.LOW,
    "coin_flip": RiskTier.LOW,
    "system_quick_status": RiskTier.LOW,
    "network_ping": RiskTier.LOW,
    "network_info": RiskTier.LOW,
    "clipboard_read": RiskTier.MEDIUM,
    "ocr_screen": RiskTier.MEDIUM,
    "launch_app": RiskTier.MEDIUM,
    "open_app": RiskTier.MEDIUM,
    "open_web": RiskTier.MEDIUM,
    "web_search": RiskTier.MEDIUM,
    "messenger_send": RiskTier.HIGH,
    "agentic_control": RiskTier.HIGH,
    "terminal_ps": RiskTier.CRITICAL,
    "terminal_cmd": RiskTier.CRITICAL,
    "wifi_passwords": RiskTier.CRITICAL,
    "power_shutdown": RiskTier.HIGH,
    "power_restart": RiskTier.HIGH,
    "power_sleep": RiskTier.HIGH,
    "deep_clean": RiskTier.CRITICAL,
    "bulk_delete": RiskTier.CRITICAL,
    "close_app": RiskTier.MEDIUM,
    "file_delete": RiskTier.HIGH,
    "service_stop": RiskTier.HIGH,
    "service_restart": RiskTier.HIGH,
}

TOOL_REGISTRY: list[dict[str, Any]] = [
    {"name": "launch_app", "risk": int(RiskTier.MEDIUM), "summary": "Start an application by name"},
    {"name": "close_app", "risk": int(RiskTier.MEDIUM), "summary": "Stop/kill an application by name"},
    {"name": "open_web", "risk": int(RiskTier.MEDIUM), "summary": "Open a known web service"},
    {"name": "web_search", "risk": int(RiskTier.MEDIUM), "summary": "Search the web"},
    {"name": "terminal_ps", "risk": int(RiskTier.CRITICAL), "summary": "Run PowerShell (requires confirmation)"},
    {"name": "terminal_cmd", "risk": int(RiskTier.CRITICAL), "summary": "Run CMD (requires confirmation)"},
    {"name": "messenger_send", "risk": int(RiskTier.HIGH), "summary": "Send a Telegram-style message"},
    {
        "name": "wifi_passwords",
        "risk": int(RiskTier.CRITICAL),
        "summary": "List saved Wi-Fi passwords (requires confirmation)",
    },
    {"name": "power_shutdown", "risk": int(RiskTier.HIGH), "summary": "Shut down PC (with confirmation in UI)"},
]


def get_risk_tier(atype: str) -> RiskTier:
    return ACTION_RISK.get((atype or "").lower(), RiskTier.MEDIUM)


def tools_prompt_block() -> str:
    """Short text block for future LLM tool-calling prompts."""
    lines = ["Available tools (name — risk 0-3):"]
    for t in TOOL_REGISTRY:
        lines.append(f"  - {t['name']}: risk={t['risk']} — {t['summary']}")
    return "\n".join(lines)
