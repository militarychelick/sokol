"""
Base action interface
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ...core.agent import ActionResult, Intent


class BaseAction(ABC):
    """Base interface for all actions."""
    
    @abstractmethod
    async def execute(self, intent: Intent) -> ActionResult:
        """Execute the action."""
        pass
