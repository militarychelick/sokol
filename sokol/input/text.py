"""
Text I/O - Text-first input for Sokol v2
"""

from __future__ import annotations

import asyncio
import sys


class TextIO:
    """Text input/output (primary interface)."""
    
    def __init__(self) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._reader_task: asyncio.Task | None = None
    
    async def start_stdin_reader(self) -> None:
        """Start stdin reader in background."""
        if self._reader_task is None:
            self._reader_task = asyncio.create_task(self._read_stdin())
    
    async def stop_stdin_reader(self) -> None:
        """Stop stdin reader."""
        if self._reader_task:
            self._reader_task.cancel()
            self._reader_task = None
    
    async def _read_stdin(self) -> None:
        """Read from stdin and put in queue."""
        loop = asyncio.get_event_loop()
        while True:
            try:
                line = await loop.run_in_executor(None, sys.stdin.readline)
                if line:
                    await self._queue.put(line.strip())
            except asyncio.CancelledError:
                break
    
    async def get_input(self) -> str | None:
        """Get input from queue (non-blocking)."""
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            return None
    
    async def output(self, text: str) -> None:
        """Output text to stdout."""
        print(text)
