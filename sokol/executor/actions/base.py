"""
Base action interface
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ...core.intent import Intent
from ...core.result import ActionResult


class BaseAction(ABC):
    """Base interface for all actions."""
    
    @abstractmethod
    def execute(self, intent: Intent) -> ActionResult:
        """Execute the action (synchronous)."""
        pass
