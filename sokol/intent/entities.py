"""
Entity extractor - Extract named entities from text
"""

from __future__ import annotations

import re
from typing import Any


class EntityExtractor:
    """
    Extracts entities like app names, file paths, URLs from text.
    
    Uses pattern matching and heuristics for common entities.
    """
    
    # Common app name patterns
    APP_PATTERNS = {
        "chrome": ["chrome", "google chrome", "browser"],
        "firefox": ["firefox", "mozilla firefox"],
        "edge": ["edge", "microsoft edge"],
        "vscode": ["vs code", "vscode", "visual studio code", "code"],
        "notepad": ["notepad", "notepad++"],
        "calculator": ["calculator", "calc"],
        "explorer": ["explorer", "file explorer", "files"],
        "spotify": ["spotify", "music"],
        "discord": ["discord"],
        "telegram": ["telegram", "tg"],
        "steam": ["steam"],
        "vlc": ["vlc", "vlc player"],
        "cmd": ["cmd", "command prompt", "terminal"],
        "powershell": ["powershell", "ps"],
    }
    
    # URL pattern
    URL_PATTERN = re.compile(
        r'https?://[^\s<>"{}|\\^`\[\]]+'
    )
    
    # File path patterns (Windows)
    FILE_PATH_PATTERN = re.compile(
        r'[A-Za-z]:\\(?:[^\s\\/:*?"<>|]+\\)*[^\s\\/:*?"<>|]*'
    )
    
    def extract(self, text: str) -> dict[str, Any]:
        """
        Extract entities from text.
        
        Args:
            text: Input text
        
        Returns:
            Dictionary of extracted entities
        """
        entities: dict[str, Any] = {}
        
        # Extract URLs
        urls = self.URL_PATTERN.findall(text)
        if urls:
            entities["urls"] = urls
        
        # Extract file paths
        paths = self.FILE_PATH_PATTERN.findall(text)
        if paths:
            entities["paths"] = paths
        
        # Extract app names
        app = self._extract_app(text)
        if app:
            entities["app"] = app
        
        # Extract search query (remaining text after removing entities)
        query = self._extract_query(text, entities)
        if query:
            entities["query"] = query
        
        return entities
    
    def _extract_app(self, text: str) -> str | None:
        """Extract app name from text."""
        text_lower = text.lower()
        
        for app_name, patterns in self.APP_PATTERNS.items():
            for pattern in patterns:
                if pattern in text_lower:
                    return app_name
        
        return None
    
    def _extract_query(self, text: str, entities: dict) -> str | None:
        """Extract search query from remaining text."""
        # Remove already extracted entities
        cleaned = text.lower()
        
        for url in entities.get("urls", []):
            cleaned = cleaned.replace(url.lower(), "")
        
        for path in entities.get("paths", []):
            cleaned = cleaned.replace(path.lower(), "")
        
        if app := entities.get("app"):
            cleaned = cleaned.replace(app, "")
        
        # Remove common action words
        action_words = {"open", "launch", "start", "find", "search", "play", "for", "the", "a", "an"}
        words = [w for w in cleaned.split() if w not in action_words and len(w) > 2]
        
        if words:
            return " ".join(words)
        
        return None
    
    def normalize_app_name(self, app: str) -> str:
        """Normalize app name to executable name."""
        app_lower = app.lower().strip()
        
        for exe_name, patterns in self.APP_PATTERNS.items():
            if app_lower in patterns or app_lower == exe_name:
                return exe_name
        
        # Return as-is if no match
        return app_lower
