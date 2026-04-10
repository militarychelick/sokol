"""
Base executor interface
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from ..core.agent import ActionResult, Step
from ..core.constants import ActionCategory


@dataclass
class ExecutionResult:
    """Result of executing a single action."""
    success: bool
    message: str
    data: Any = None
    error: str | None = None


class BaseExecutor(ABC):
    """Base class for all executors."""
    
    def __init__(self) -> None:
        pass
    
    @abstractmethod
    def execute(self, step: Step) -> ExecutionResult:
        """Execute a single step."""
        pass
    
    @abstractmethod
    def can_execute(self, action_category: ActionCategory) -> bool:
        """Check if this executor can handle the action."""
        pass
