"""
Restriction checker - Hard-block rules for dangerous actions
"""

from __future__ import annotations

import re
from typing import Any

from ..core.constants import (
    DANGEROUS_PATTERNS,
    RESTRICTED_PATHS,
    ActionCategory,
)


class RestrictionChecker:
    """
    Checks if actions are hard-restricted.
    
    Hard restrictions cannot be overridden by user confirmation.
    These are for system protection.
    """
    
    # Windows system directories that cannot be modified
    SYSTEM_DIRECTORIES = {
        "C:\\Windows",
        "C:\\Program Files",
        "C:\\Program Files (x86)",
        "C:\\ProgramData",
        "C:\\Users\\Public",
        "C:\\Windows\\System32",
        "C:\\Windows\\SysWOW64",
    }
    
    # File patterns that are always protected
    PROTECTED_PATTERNS = {
        "*.sys",  # System drivers
        "*.dll",  # System libraries
        "*.exe",  # Executables in system paths
        "*.bat",  # Batch files
        "*.cmd",  # Command files
        "*.ps1",  # PowerShell scripts
        "*.vbs",  # VBScript files
        "*.reg",  # Registry files
    }
    
    # Keywords in file paths that indicate protection
    PROTECTED_KEYWORDS = {
        "password",
        "credential",
        "secret",
        "private",
        "key",
        "token",
        "wallet",
        "backup",
    }
    
    def __init__(self) -> None:
        # Load custom restrictions from config
        self._custom_restrictions: list[dict[str, str]] = []
        self._load_custom_restrictions()
    
    def _load_custom_restrictions(self) -> None:
        """Load custom restrictions from safety.yaml."""
        try:
            from pathlib import Path
            import yaml
            
            rules_path = Path(__file__).parent.parent.parent / "config" / "safety.yaml"
            
            if rules_path.exists():
                with open(rules_path, "r", encoding="utf-8") as f:
                    rules = yaml.safe_load(f) or {}
                    
                    if "hard_restrictions" in rules:
                        self._custom_restrictions = rules["hard_restrictions"]
        except Exception:
            pass  # Use defaults
    
    def check(
        self,
        action: ActionCategory,
        entities: dict[str, Any],
    ) -> str | None:
        """
        Check if action is restricted.
        
        Args:
            action: Action category
            entities: Action entities (files, paths, URLs, etc.)
        
        Returns:
            Reason string if restricted, None if allowed
        """
        # Check file-based restrictions
        if action in (
            ActionCategory.FILE_DELETE,
            ActionCategory.FILE_MODIFY,
            ActionCategory.FILE_MOVE,
        ):
            return self._check_file_restrictions(entities, action)
        
        # Check system settings restrictions
        if action == ActionCategory.SYSTEM_SETTINGS:
            return "System settings modification requires elevated privileges"
        
        # Check code execution
        if action == ActionCategory.CODE_EXECUTION:
            return "Code execution is restricted by default"
        
        return None
    
    def _check_file_restrictions(
        self,
        entities: dict[str, Any],
        action: ActionCategory,
    ) -> str | None:
        """Check if file operation is restricted."""
        paths = entities.get("paths", [])
        if isinstance(paths, str):
            paths = [paths]
        
        for path in paths:
            # Check against system directories
            if self._is_system_path(path):
                return f"Cannot modify system directory: {path}"
            
            # Check against protected patterns
            if self._is_protected_pattern(path):
                return f"Cannot modify protected file: {path}"
            
            # Check against protected keywords
            if self._is_protected_keyword(path):
                return f"Cannot modify protected file: {path}"
            
            # Check custom restrictions
            if custom_reason := self._check_custom_restrictions(path, action):
                return custom_reason
        
        return None
    
    def _is_system_path(self, path: str) -> bool:
        """Check if path is in system directory."""
        path_normalized = path.lower()
        
        for sys_dir in self.SYSTEM_DIRECTORIES:
            if path_normalized.startswith(sys_dir.lower()):
                return True
        
        return False
    
    def _is_protected_pattern(self, path: str) -> bool:
        """Check if path matches protected pattern."""
        path_lower = path.lower()
        
        for pattern in self.PROTECTED_PATTERNS:
            if pattern.startswith("*."):
                ext = pattern[1:]  # .sys, .dll, etc.
                if path_lower.endswith(ext):
                    # Only restrict in system paths
                    if self._is_system_path(path):
                        return True
            elif pattern in path_lower:
                return True
        
        return False
    
    def _is_protected_keyword(self, path: str) -> bool:
        """Check if path contains protected keyword."""
        path_lower = path.lower()
        
        for keyword in self.PROTECTED_KEYWORDS:
            if keyword in path_lower:
                return True
        
        return False
    
    def _check_custom_restrictions(
        self,
        path: str,
        action: ActionCategory,
    ) -> str | None:
        """Check against custom restrictions from config."""
        path_lower = path.lower()
        action_str = action.value
        
        for restriction in self._custom_restrictions:
            pattern = restriction.get("pattern", "")
            restricted_action = restriction.get("action", "")
            reason = restriction.get("reason", "Restricted by policy")
            
            # Check pattern match
            if pattern:
                # Convert glob pattern to regex
                regex_pattern = pattern.replace("*", ".*").replace("?", ".")
                if re.search(regex_pattern, path_lower, re.IGNORECASE):
                    # Check if action matches
                    if not restricted_action or restricted_action == action_str:
                        return reason
        
        return None
    
    def is_safe_url(self, url: str) -> bool:
        """Check if URL is safe to open."""
        # Basic URL validation
        if not (url.startswith("http://") or url.startswith("https://")):
            return False
        
        # Check for obviously dangerous protocols
        dangerous_protocols = ["javascript:", "data:", "file:"]
        for proto in dangerous_protocols:
            if url.lower().startswith(proto):
                return False
        
        return True
