"""
Safety policy - Classify actions by risk level
"""

from __future__ import annotations

from typing import Any

import yaml

from ..core.agent import Intent
from ..core.config import SafetyConfig
from ..core.constants import (
    DANGEROUS_PATTERNS,
    RESTRICTED_PATHS,
    ActionCategory,
    SafetyLevel,
)
from ..core.exceptions import RestrictedActionError, SafetyError
from .restrictions import RestrictionChecker


class SafetyPolicy:
    """
    Classifies actions by safety level and enforces restrictions.
    
    Safety levels:
    - SAFE: Execute immediately
    - CAUTION: Ask for confirmation
    - DANGEROUS: Require explicit approval
    """
    
    # Default safety classification
    DEFAULT_CLASSIFICATION: dict[ActionCategory, SafetyLevel] = {
        ActionCategory.APP_LAUNCH: SafetyLevel.SAFE,
        ActionCategory.APP_SWITCH: SafetyLevel.SAFE,
        ActionCategory.APP_CLOSE: SafetyLevel.CAUTION,
        ActionCategory.FILE_OPEN: SafetyLevel.SAFE,
        ActionCategory.FILE_SEARCH: SafetyLevel.SAFE,
        ActionCategory.FILE_DELETE: SafetyLevel.DANGEROUS,
        ActionCategory.FILE_MODIFY: SafetyLevel.CAUTION,
        ActionCategory.FILE_COPY: SafetyLevel.SAFE,
        ActionCategory.FILE_MOVE: SafetyLevel.CAUTION,
        ActionCategory.SYSTEM_SETTINGS: SafetyLevel.DANGEROUS,
        ActionCategory.SYSTEM_POWER: SafetyLevel.DANGEROUS,
        ActionCategory.CODE_EXECUTION: SafetyLevel.DANGEROUS,
        ActionCategory.BROWSER_OPEN: SafetyLevel.SAFE,
        ActionCategory.BROWSER_NAVIGATE: SafetyLevel.CAUTION,
        ActionCategory.BROWSER_TAB: SafetyLevel.SAFE,
        ActionCategory.HOTKEY: SafetyLevel.CAUTION,
        ActionCategory.MEDIA_CONTROL: SafetyLevel.SAFE,
        ActionCategory.WINDOW_MANAGE: SafetyLevel.SAFE,
        ActionCategory.SEARCH_WEB: SafetyLevel.SAFE,
        ActionCategory.UNKNOWN: SafetyLevel.CAUTION,
    }
    
    def __init__(self, config: SafetyConfig) -> None:
        self.config = config
        self.restrictions = RestrictionChecker()
        
        # Load safety rules from file
        self._safety_rules: dict[str, Any] = {}
        self._load_safety_rules()
    
    def _load_safety_rules(self) -> None:
        """Load safety rules from YAML file."""
        try:
            from pathlib import Path
            rules_path = Path(__file__).parent.parent.parent / "config" / "safety.yaml"
            
            if rules_path.exists():
                with open(rules_path, "r", encoding="utf-8") as f:
                    self._safety_rules = yaml.safe_load(f) or {}
        except Exception:
            pass  # Use defaults
    
    def classify(
        self,
        action_category: ActionCategory,
        entities: dict[str, Any] | None = None,
    ) -> SafetyLevel:
        """
        Classify action by safety level.
        
        Args:
            action_category: Type of action
            entities: Action entities (files, URLs, etc.)
        
        Returns:
            SafetyLevel for the action
        """
        # Check hard restrictions first
        if entities:
            restriction = self.restrictions.check(action_category, entities)
            if restriction:
                raise RestrictedActionError(
                    action=str(action_category),
                    reason=restriction,
                )
        
        # Get base classification
        base_level = self.DEFAULT_CLASSIFICATION.get(
            action_category,
            SafetyLevel.CAUTION,
        )
        
        # Check for dangerous patterns
        if entities:
            if self._has_dangerous_patterns(entities):
                return SafetyLevel.DANGEROUS
        
        # Check for code execution
        if action_category == ActionCategory.CODE_EXECUTION:
            if not self.config.code_execution:
                raise RestrictedActionError(
                    action="code_execution",
                    reason="Code execution is disabled in settings",
                )
            return SafetyLevel.DANGEROUS
        
        return base_level
    
    def classify_by_action_type(self, action_type: str) -> SafetyLevel:
        """Classify by action type (new structure)."""
        # Map action types to safety levels
        safety_map = {
            "close_app": SafetyLevel.CAUTION,
            "system_action": SafetyLevel.DANGEROUS,
        }
        return safety_map.get(action_type, SafetyLevel.SAFE)
    
    def _has_dangerous_patterns(self, entities: dict[str, Any]) -> bool:
        """Check if entities match dangerous patterns."""
        # Check file paths
        paths = entities.get("paths", [])
        if isinstance(paths, str):
            paths = [paths]
        
        for path in paths:
            path_lower = path.lower()
            for pattern in DANGEROUS_PATTERNS:
                # Convert glob pattern to check
                if pattern.startswith("*."):
                    ext = pattern[1:]  # .exe, .bat, etc.
                    if path_lower.endswith(ext):
                        return True
                elif pattern in path_lower:
                    return True
        
        # Check URLs
        urls = entities.get("urls", [])
        if isinstance(urls, str):
            urls = [urls]
        
        # Unknown URLs are more dangerous
        for url in urls:
            if not self._is_safe_url(url):
                return True  # Will be CAUTION, not DANGEROUS
        
        return False
    
    def _is_safe_url(self, url: str) -> bool:
        """Check if URL is in safe list."""
        safe_domains = [
            "google.com",
            "youtube.com",
            "github.com",
            "stackoverflow.com",
            "wikipedia.org",
        ]
        
        url_lower = url.lower()
        return any(domain in url_lower for domain in safe_domains)
    
    def generate_confirmation_prompt(self, intent: Intent) -> str:
        """Generate confirmation prompt for caution-level action."""
        action = intent.action_category
        entities = intent.entities
        
        if action == ActionCategory.APP_CLOSE:
            app = entities.get("app", "the application")
            return f"I'll close {app}. Confirm?"
        
        elif action == ActionCategory.FILE_MODIFY:
            file = entities.get("file", entities.get("paths", ["the file"])[0])
            return f"I'm going to modify {file}. Should I continue?"
        
        elif action == ActionCategory.BROWSER_NAVIGATE:
            url = entities.get("url", entities.get("urls", ["the URL"])[0])
            return f"I'm about to open {url}. Is this okay?"
        
        elif action == ActionCategory.HOTKEY:
            return "I'll press that key combination. Ready?"
        
        else:
            return f"I'm about to {intent.raw_text}. Proceed?"
    
    def generate_permission_prompt(self, intent: Intent) -> str:
        """Generate permission prompt for dangerous action."""
        action = intent.action_category
        entities = intent.entities
        
        if action == ActionCategory.FILE_DELETE:
            file = entities.get("file", entities.get("paths", ["the file"])[0])
            return f"WARNING: I'm about to DELETE {file}. This cannot be undone. Are you absolutely sure?"
        
        elif action == ActionCategory.SYSTEM_SETTINGS:
            return f"WARNING: This will change system settings. Proceed with caution. Are you sure?"
        
        elif action == ActionCategory.SYSTEM_POWER:
            return "WARNING: This will affect your computer's power state. Are you sure?"
        
        elif action == ActionCategory.CODE_EXECUTION:
            return "WARNING: You're asking me to run code. This can be dangerous. Are you absolutely sure?"
        
        else:
            return f"WARNING: This action is potentially dangerous. Are you sure you want to proceed?"
    
    def is_restricted(self, action: ActionCategory, entities: dict[str, Any]) -> str | None:
        """Check if action is hard-restricted."""
        return self.restrictions.check(action, entities)
