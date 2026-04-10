"""
Intent parser - Extract structured intent from user text
"""

from __future__ import annotations

import json
from typing import Any

from ..core.agent import Intent
from ..core.config import Config
from ..core.constants import ActionCategory, IntentType
from ..core.exceptions import IntentError


class IntentParser:
    """
    Parses user text into structured Intent objects.
    
    Uses LLM to understand natural language commands.
    """
    
    # Keywords for quick classification (no LLM needed)
    QUICK_PATTERNS: dict[str, tuple[IntentType, ActionCategory]] = {
        # App launch - English
        "open": (IntentType.COMMAND, ActionCategory.APP_LAUNCH),
        "launch": (IntentType.COMMAND, ActionCategory.APP_LAUNCH),
        "start": (IntentType.COMMAND, ActionCategory.APP_LAUNCH),
        "run": (IntentType.COMMAND, ActionCategory.APP_LAUNCH),
        
        # App launch - Russian
        "открой": (IntentType.COMMAND, ActionCategory.APP_LAUNCH),
        "запусти": (IntentType.COMMAND, ActionCategory.APP_LAUNCH),
        "включи": (IntentType.COMMAND, ActionCategory.APP_LAUNCH),
        "включи": (IntentType.COMMAND, ActionCategory.APP_LAUNCH),
        
        # App close - English
        "close": (IntentType.COMMAND, ActionCategory.APP_CLOSE),
        "quit": (IntentType.COMMAND, ActionCategory.APP_CLOSE),
        "exit": (IntentType.COMMAND, ActionCategory.APP_CLOSE),
        "kill": (IntentType.COMMAND, ActionCategory.APP_CLOSE),
        
        # App close - Russian
        "закрой": (IntentType.COMMAND, ActionCategory.APP_CLOSE),
        "выключи": (IntentType.COMMAND, ActionCategory.APP_CLOSE),
        "останови": (IntentType.COMMAND, ActionCategory.APP_CLOSE),
        
        # File operations - English
        "find": (IntentType.COMMAND, ActionCategory.FILE_SEARCH),
        "search": (IntentType.COMMAND, ActionCategory.FILE_SEARCH),
        
        # File operations - Russian
        "найди": (IntentType.COMMAND, ActionCategory.FILE_SEARCH),
        "поиск": (IntentType.COMMAND, ActionCategory.FILE_SEARCH),
        "искать": (IntentType.COMMAND, ActionCategory.FILE_SEARCH),
        
        # Browser - English
        "browse": (IntentType.COMMAND, ActionCategory.BROWSER_OPEN),
        "go to": (IntentType.COMMAND, ActionCategory.BROWSER_NAVIGATE),
        "visit": (IntentType.COMMAND, ActionCategory.BROWSER_NAVIGATE),
        
        # Browser - Russian
        "открой в браузере": (IntentType.COMMAND, ActionCategory.BROWSER_OPEN),
        "зайди на": (IntentType.COMMAND, ActionCategory.BROWSER_NAVIGATE),
        
        # Media - English
        "play": (IntentType.COMMAND, ActionCategory.MEDIA_CONTROL),
        "pause": (IntentType.COMMAND, ActionCategory.MEDIA_CONTROL),
        "stop": (IntentType.COMMAND, ActionCategory.MEDIA_CONTROL),
        
        # Media - Russian
        "играй": (IntentType.COMMAND, ActionCategory.MEDIA_CONTROL),
        "пауза": (IntentType.COMMAND, ActionCategory.MEDIA_CONTROL),
        
        # Window - English
        "minimize": (IntentType.COMMAND, ActionCategory.WINDOW_MANAGE),
        "maximize": (IntentType.COMMAND, ActionCategory.WINDOW_MANAGE),
        "switch": (IntentType.COMMAND, ActionCategory.APP_SWITCH),
        
        # Window - Russian
        "сверни": (IntentType.COMMAND, ActionCategory.WINDOW_MANAGE),
        "разверни": (IntentType.COMMAND, ActionCategory.WINDOW_MANAGE),
        
        # Hotkeys
        "нажми": (IntentType.COMMAND, ActionCategory.HOTKEY),
        "press": (IntentType.COMMAND, ActionCategory.HOTKEY),
        
        # Cancel
        "cancel": (IntentType.CANCEL, ActionCategory.UNKNOWN),
        "отмена": (IntentType.CANCEL, ActionCategory.UNKNOWN),
    }
    
    def __init__(self, config: Config) -> None:
        self.config = config
        self._llm_router: Any = None
    
    @property
    def llm(self) -> Any:
        """Lazy load LLM router."""
        if self._llm_router is None:
            from ..llm import LLMRouter
            self._llm_router = LLMRouter(self.config.llm)
        return self._llm_router
    
    async def parse(self, text: str, context: dict[str, Any] | None = None) -> Intent:
        """
        Parse user text into structured Intent.
        
        Args:
            text: User input text
            context: Additional context from memory
        
        Returns:
            Structured Intent object
        """
        text_lower = text.lower().strip()
        
        # Quick pattern matching first (faster, no LLM)
        intent = self._try_quick_parse(text_lower)
        if intent and intent.confidence > 0.8:
            return intent
        
        # Use LLM for complex parsing
        return await self._llm_parse(text, context or {})
    
    def _try_quick_parse(self, text: str) -> Intent | None:
        """Try quick pattern-based parsing."""
        for pattern, (intent_type, action_category) in self.QUICK_PATTERNS.items():
            if text.startswith(pattern):
                # Extract entity after pattern
                entity_text = text[len(pattern):].strip()
                
                # Map to new structure
                action_type, target, params, safety_level = self._map_to_new_structure(
                    action_category, entity_text
                )
                
                return Intent(
                    action_type=action_type,
                    target=target,
                    params=params,
                    safety_level=safety_level,
                    complexity=1,
                    confidence=0.9,
                    raw_text=text,
                )
        
        return None
    
    def _map_to_new_structure(
        self, action_category: ActionCategory, entity_text: str
    ) -> tuple[str, str | None, dict, SafetyLevel]:
        """Map old action_category to new action_type structure."""
        from ..core.constants import SafetyLevel
        
        # Map action_category to action_type
        action_type_map = {
            ActionCategory.APP_LAUNCH: "launch_app",
            ActionCategory.APP_CLOSE: "close_app",
            ActionCategory.APP_SWITCH: "switch_app",
            ActionCategory.BROWSER_OPEN: "open_url",
            ActionCategory.BROWSER_NAVIGATE: "open_url",
            ActionCategory.FILE_SEARCH: "search_file",
            ActionCategory.FILE_OPEN: "open_file",
            ActionCategory.HOTKEY: "press_hotkey",
            ActionCategory.WINDOW_MANAGE: "manage_window",
            ActionCategory.SYSTEM_POWER: "system_action",
        }
        
        action_type = action_type_map.get(action_category, "unknown")
        
        # Determine target and params
        target = None
        params = {}
        
        if action_category in (ActionCategory.APP_LAUNCH, ActionCategory.APP_CLOSE, ActionCategory.APP_SWITCH):
            target = self._normalize_app_name(entity_text)
            params["app"] = target
        elif action_category in (ActionCategory.BROWSER_OPEN, ActionCategory.BROWSER_NAVIGATE):
            url = self._extract_url(entity_text)
            if url:
                target = url
                params["url"] = url
            else:
                params["query"] = entity_text
        elif action_category == ActionCategory.FILE_SEARCH:
            params["query"] = entity_text
        elif action_category == ActionCategory.HOTKEY:
            keys = self._parse_hotkey(entity_text)
            target = "+".join(keys)
            params["keys"] = keys
        elif action_category == ActionCategory.WINDOW_MANAGE:
            params["window_action"] = entity_text
        elif action_category == ActionCategory.SYSTEM_POWER:
            params["system_action"] = entity_text
        
        # Determine safety level
        safety_map = {
            ActionCategory.APP_CLOSE: SafetyLevel.CAUTION,
            ActionCategory.FILE_DELETE: SafetyLevel.DANGEROUS,
            ActionCategory.SYSTEM_POWER: SafetyLevel.DANGEROUS,
        }
        
        safety_level = safety_map.get(action_category, SafetyLevel.SAFE)
        
        return action_type, target, params, safety_level
    
    def _extract_entities_quick(
        self,
        text: str,
        category: ActionCategory,
    ) -> dict[str, Any]:
        """Quick entity extraction for simple patterns."""
        entities: dict[str, Any] = {}
        
        if category == ActionCategory.APP_LAUNCH:
            # Normalize app name
            app_name = self._normalize_app_name(text)
            entities["app"] = app_name
        
        elif category == ActionCategory.FILE_SEARCH:
            entities["query"] = text
        
        elif category == ActionCategory.BROWSER_NAVIGATE:
            # Check if it's a known site
            url = self._extract_url(text)
            if url:
                entities["url"] = url
            else:
                entities["query"] = text
        
        elif category == ActionCategory.HOTKEY:
            # Parse hotkey
            entities["keys"] = self._parse_hotkey(text)
        
        elif category == ActionCategory.MEDIA_CONTROL:
            entities["action"] = text
        
        return entities
    
    def _normalize_app_name(self, text: str) -> str:
        """Normalize app name to common format."""
        text_lower = text.lower().strip()
        
        # Common mappings
        mappings = {
            "chrome": "chrome",
            "хром": "chrome",
            "хромиум": "chrome",
            "firefox": "firefox",
            "фаерфокс": "firefox",
            "edge": "msedge",
            "эдж": "msedge",
            "youtube": "chrome",  # YouTube usually opens in Chrome
            "ютуб": "chrome",
            "notepad": "notepad",
            "блокнот": "notepad",
            "калькулятор": "calc",
            "калькулятор": "calc",
        }
        
        return mappings.get(text_lower, text_lower)
    
    def _parse_hotkey(self, text: str) -> list[str]:
        """Parse hotkey combination."""
        # Simple parsing: "ctrl+c", "ctrl shift c", etc.
        parts = text.lower().replace("+", " ").split()
        
        # Normalize
        normalized = []
        for part in parts:
            if part in ["ctrl", "control"]:
                normalized.append("ctrl")
            elif part in ["alt"]:
                normalized.append("alt")
            elif part in ["shift"]:
                normalized.append("shift")
            elif part in ["win", "windows", "meta"]:
                normalized.append("win")
            else:
                # Assume it's a key
                normalized.append(part)
        
        return normalized
    
    def _extract_url(self, text: str) -> str | None:
        """Extract URL from text, handling common sites."""
        text_lower = text.lower().strip()
        
        # Known sites mapping
        site_mappings = {
            "youtube": "https://youtube.com",
            "ютуб": "https://youtube.com",
            "google": "https://google.com",
            "гугл": "https://google.com",
            "github": "https://github.com",
            "гитхаб": "https://github.com",
            "stackoverflow": "https://stackoverflow.com",
        }
        
        if text_lower in site_mappings:
            return site_mappings[text_lower]
        
        # Check if already a URL
        if text_lower.startswith("http://") or text_lower.startswith("https://"):
            return text_lower
        
        # Check if looks like a domain
        if "." in text_lower and " " not in text_lower:
            return f"https://{text_lower}"
        
        return None
    
    async def _llm_parse(
        self,
        text: str,
        context: dict[str, Any],
    ) -> Intent:
        """Use LLM to parse complex intent."""
        from ..core.constants import SafetyLevel
        
        prompt = f"""Analyze this user input and extract the intent.

Input: "{text}"

Context: {context or "No additional context"}

Respond in JSON format:
{{
  "action_type": "launch_app|close_app|switch_app|open_url|press_hotkey|search_file|open_file|manage_window|system_action|unknown",
  "target": "chrome|youtube.com|ctrl+c (or null)",
  "params": {{"app": "chrome", "url": "https://...", "keys": ["ctrl", "c"]}},
  "safety_level": "safe|caution|dangerous",
  "complexity": 1-10,
  "requires_planning": true|false,
  "confidence": 0.0-1.0
}}

Only respond with valid JSON."""

        try:
            response = await self.llm.generate(
                prompt,
                system_prompt="You are an intent parser. Respond only with valid JSON.",
                complexity=3,
            )
            
            # Parse JSON response
            data = json.loads(response.text)
            
            # Map safety level
            safety_str = data.get("safety_level", "safe")
            safety_map = {
                "safe": SafetyLevel.SAFE,
                "caution": SafetyLevel.CAUTION,
                "dangerous": SafetyLevel.DANGEROUS,
            }
            safety_level = safety_map.get(safety_str, SafetyLevel.SAFE)
            
            return Intent(
                action_type=data.get("action_type", "unknown"),
                target=data.get("target"),
                params=data.get("params", {}),
                safety_level=safety_level,
                complexity=data.get("complexity", 5),
                requires_planning=data.get("requires_planning", False),
                confidence=data.get("confidence", 0.5),
                raw_text=text,
            )
            
        except json.JSONDecodeError:
            # Fallback to unknown intent
            return Intent(
                action_type="unknown",
                target=None,
                params={},
                safety_level=SafetyLevel.CAUTION,
                complexity=5,
                requires_planning=False,
                confidence=0.3,
                raw_text=text,
            )
        except Exception as e:
            raise IntentError("Failed to parse intent", str(e))
    
    def is_affirmative(self, text: str) -> bool:
        """Check if text is an affirmative response."""
        affirmative = {
            "yes", "yeah", "yep", "yup", "sure", "ok", "okay",
            "go ahead", "proceed", "do it", "confirm",
            "da", "davai", "konechno",  # Russian
        }
        return text.lower().strip() in affirmative
    
    def is_negative(self, text: str) -> bool:
        """Check if text is a negative response."""
        negative = {
            "no", "nope", "nah", "cancel", "abort", "stop",
            "net", "otmena",  # Russian
        }
        return text.lower().strip() in negative
