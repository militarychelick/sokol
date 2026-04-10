"""
Text input/output layer - fallback when voice is unavailable
"""

from __future__ import annotations

import asyncio
from typing import Callable


class TextLayer:
    """
    Text input/output interface.
    
    Provides a fallback when voice is unavailable or
    user prefers text input.
    """
    
    def __init__(self) -> None:
        self._input_queue: asyncio.Queue[str | None] = asyncio.Queue()
        self._output_callback: Callable[[str], None] | None = None
    
    def set_output_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for text output."""
        self._output_callback = callback
    
    async def get_input(self, timeout: float = 60.0) -> str | None:
        """
        Get text input from user.
        
        This is typically called from GUI when user types a command.
        
        Args:
            timeout: Maximum time to wait
        
        Returns:
            User text input or None if timeout
        """
        try:
            return await asyncio.wait_for(
                self._input_queue.get(),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            return None
    
    def submit_input(self, text: str) -> None:
        """
        Submit text input from external source (e.g., GUI).
        
        Args:
            text: User input text
        """
        self._input_queue.put_nowait(text)
    
    async def output(self, text: str) -> None:
        """
        Output text to user.
        
        Args:
            text: Text to display
        """
        if self._output_callback:
            self._output_callback(text)
    
    def clear(self) -> None:
        """Clear the input queue."""
        while not self._input_queue.empty():
            try:
                self._input_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
