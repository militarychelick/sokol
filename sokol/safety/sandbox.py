"""
Sandbox - Safe code execution environment
"""

from __future__ import annotations


class Sandbox:
    """Sandbox for safe code execution."""
    
    def __init__(self) -> None:
        self._enabled = False
    
    async def execute(self, code: str) -> str:
        """Execute code in sandbox."""
        # TODO: Implement safe code execution
        # For MVP, code execution is disabled
        return "Code execution not enabled"
