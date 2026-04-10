"""
Text input/output layer - fallback when voice is unavailable
"""

from __future__ import annotations

import asyncio
import sys
from typing import Callable


class TextLayer:
    """
    Text input/output interface.
    
    Provides a fallback when voice is unavailable or
    user prefers text input.
    """
    
    def __init__(self, use_stdin: bool = True) -> None:
        self._input_queue: asyncio.Queue[str | None] = asyncio.Queue()
        self._output_callback: Callable[[str], None] | None = None
        self._use_stdin = use_stdin
        self._stdin_task: asyncio.Task | None = None
    
    def set_output_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for text output."""
        self._output_callback = callback
    
    async def start_stdin_reader(self) -> None:
        """Start reading from stdin in background."""
        if not self._use_stdin:
            return
        
        async def read_stdin():
            loop = asyncio.get_event_loop()
            while True:
                try:
                    line = await loop.run_in_executor(None, sys.stdin.readline)
                    if not line:
                        break
                    text = line.strip()
                    if text:
                        self._input_queue.put_nowait(text)
                except EOFError:
                    break
        
        self._stdin_task = asyncio.create_task(read_stdin())
    
    async def stop_stdin_reader(self) -> None:
        """Stop reading from stdin."""
        if self._stdin_task:
            self._stdin_task.cancel()
            try:
                await self._stdin_task
            except asyncio.CancelledError:
                pass
            self._stdin_task = None
    
    async def get_input(self, timeout: float = 60.0) -> str | None:
        """
        Get text input from user.
        
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
        # Always print to console for visibility
        print(f"\n[Agent]: {text}")
        
        if self._output_callback:
            self._output_callback(text)
    
    def clear(self) -> None:
        """Clear the input queue."""
        while not self._input_queue.empty():
            try:
                self._input_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
