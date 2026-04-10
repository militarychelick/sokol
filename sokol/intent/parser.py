"""
Intent parser v2 - Deterministic intent parsing
"""

from __future__ import annotations

import re
from typing import Any

from ..core.intent import Intent, SafetyLevel
from ..core.config import Config


class IntentParser:
    """
    Deterministic intent parser - no special cases, no hacks.
    
    Pipeline:
    raw_text → normalize() → match_action_type() → extract_target() → extract_params() → build_intent()
    """
    
    # Action patterns by action_type (deterministic)
    ACTION_PATTERNS: dict[str, list[str]] = {
        "open_url": [
            r"открой\s+(youtube|github|google|facebook|twitter|reddit)",
            r"open\s+(youtube|github|google|facebook|twitter|reddit)",
        ],
        "manage_window": [
            r"закрой\s+окно",
            r"сверни\s+окно",
            r"разверни\s+окно",
            r"minimize",
            r"maximize",
        ],
        "launch_app": [
            r"открой\s+(\S+)",
            r"запусти\s+(\S+)",
            r"включи\s+(\S+)",
            r"open\s+(\S+)",
            r"launch\s+(\S+)",
            r"start\s+(\S+)",
            r"run\s+(\S+)",
        ],
        "close_app": [
            r"закрой\s+(\S+)",
            r"выключи\s+(\S+)",
            r"останови\s+(\S+)",
            r"close\s+(\S+)",
            r"quit\s+(\S+)",
            r"exit\s+(\S+)",
            r"kill\s+(\S+)",
        ],
        "press_hotkey": [
            r"нажми\s+(\S+)",
            r"жми\s+(\S+)",
            r"press\s+(\S+)",
            r"hit\s+(\S+)",
        ],
        "search_file": [
            r"найди\s+(\S+)",
            r"поиск\s+(\S+)",
            r"искать\s+(\S+)",
            r"find\s+(\S+)",
            r"search\s+(\S+)",
        ],
        "system_action": [
            r"выключи",
            r"перезагрузи",
            r"shutdown",
            r"restart",
        ],
    }
    
    # Popular sites mapping
    POPULAR_SITES: dict[str, str] = {
        "youtube": "youtube.com",
        "github": "github.com",
        "google": "google.com",
        "facebook": "facebook.com",
        "twitter": "twitter.com",
        "reddit": "reddit.com",
    }
    
    # Window actions mapping
    WINDOW_ACTIONS: dict[str, str] = {
        "закрой окно": "close",
        "сверни окно": "minimize",
        "разверни окно": "maximize",
        "minimize": "minimize",
        "maximize": "maximize",
    }
    
    def __init__(self, config: Config) -> None:
        self.config = config
    
    def normalize_text(self, text: str) -> str:
        """Normalize text for consistent matching."""
        return text.lower().replace("ё", "е").strip()
    
    def match_action_type(self, text: str) -> tuple[str, str | None]:
        """Match action type using deterministic regex patterns."""
        normalized = self.normalize_text(text)
        
        for action_type, patterns in self.ACTION_PATTERNS.items():
            for pattern in patterns:
                match = re.match(pattern, normalized)
                if match:
                    if match.groups():
                        target = match.group(1)
                    else:
                        target = None
                    return action_type, target
        
        return "unknown", None
    
    def extract_params(self, action_type: str, target: str | None, text: str) -> dict[str, Any]:
        """Extract params based on action_type (deterministic)."""
        params = {}
        
        if action_type == "launch_app":
            params["app"] = target
        elif action_type == "open_url":
            if target in self.POPULAR_SITES:
                params["url"] = f"https://{self.POPULAR_SITES[target]}"
            else:
                params["url"] = f"https://{target}.com"
        elif action_type == "close_app":
            params["app"] = target
        elif action_type == "press_hotkey":
            params["keys"] = self._parse_hotkey(target or "")
        elif action_type == "search_file":
            params["query"] = target
        elif action_type == "manage_window":
            params["window_action"] = self._extract_window_action(text)
        elif action_type == "system_action":
            params["system_action"] = self._extract_system_action(text)
        
        return params
    
    def _parse_hotkey(self, text: str) -> list[str]:
        """Parse hotkey combination."""
        parts = text.lower().replace("+", " ").split()
        return parts
    
    def _extract_window_action(self, text: str) -> str:
        """Extract window action from text."""
        normalized = self.normalize_text(text)
        for pattern, action in self.WINDOW_ACTIONS.items():
            if pattern in normalized:
                return action
        return "close"
    
    def _extract_system_action(self, text: str) -> str:
        """Extract system action from text."""
        normalized = self.normalize_text(text)
        if "shutdown" in normalized or "выключи" in normalized:
            return "shutdown"
        elif "restart" in normalized or "перезагрузи" in normalized:
            return "restart"
        return "shutdown"
    
    async def parse(self, text: str, context: dict[str, Any] | None = None) -> Intent:
        """Parse user text into structured Intent."""
        action_type, target = self.match_action_type(text)
        params = self.extract_params(action_type, target, text)
        safety_level = self._classify_safety(action_type)
        
        return Intent(
            action_type=action_type,
            target=target,
            params=params,
            safety_level=safety_level,
            complexity=1,
            raw_text=text,
        )
    
    def _classify_safety(self, action_type: str) -> SafetyLevel:
        """Classify safety level based on action_type."""
        dangerous = ["close_app", "system_action"]
        if action_type in dangerous:
            return SafetyLevel.CAUTION
        return SafetyLevel.SAFE
    
    def is_affirmative(self, text: str) -> bool:
        """Check if text is an affirmative response."""
        affirmative = {"yes", "yeah", "yep", "yup", "sure", "ok", "okay", "да", "конечно"}
        return text.lower().strip() in affirmative
    
    def is_negative(self, text: str) -> bool:
        """Check if text is a negative response."""
        negative = {"no", "nope", "nah", "cancel", "abort", "stop", "нет", "отмена"}
        return text.lower().strip() in negative
