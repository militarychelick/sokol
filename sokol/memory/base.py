"""Base memory store with SQLite backend."""

import json
import sqlite3
import threading
import queue
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Generic, TypeVar

from pydantic import BaseModel
from sokol.observability.logging import get_logger

logger = get_logger("sokol.memory.base")

T = TypeVar("T", bound=BaseModel)


class MemoryStore(ABC, Generic[T]):
    """Base class for memory stores."""

    def __init__(self, db_path: Path | str, enable_write_buffer: bool = True, buffer_size: int = 100) -> None:
        """
        Initialize memory store.
        
        Args:
            db_path: Path to SQLite database
            enable_write_buffer: Enable write buffering to reduce blocking
            buffer_size: Maximum number of writes to buffer before flush
        """
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._init_db()
        
        # P1: Write buffer mechanism to reduce SQLite blocking
        self._enable_write_buffer = enable_write_buffer
        self._buffer_size = buffer_size
        self._write_buffer: list[tuple[str, tuple]] = []
        self._buffer_lock = threading.Lock()
        self._write_thread: Optional[threading.Thread] = None
        self._stop_writer = threading.Event()
        
        if self._enable_write_buffer:
            self._start_write_thread()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with WAL mode and timeout for concurrent access."""
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self._db_path),
                check_same_thread=False,
                timeout=10.0  # 10 second timeout for locks
            )
            self._conn.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrent read/write support
            self._conn.execute("PRAGMA journal_mode=WAL")
            # Set busy timeout for lock retries
            self._conn.execute("PRAGMA busy_timeout=5000")
            # Enable foreign keys
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def _init_db(self) -> None:
        """Initialize database tables. Override in subclass."""
        pass
    
    def _start_write_thread(self) -> None:
        """Start background write thread for buffered writes."""
        self._write_thread = threading.Thread(
            target=self._write_loop,
            daemon=True,
            name="MemoryStoreWriter"
        )
        self._write_thread.start()
        logger.info("Memory store write buffer thread started")
    
    def _write_loop(self) -> None:
        """Background thread that flushes write buffer periodically."""
        while not self._stop_writer.is_set():
            try:
                # Wait for buffer to fill or timeout
                self._stop_writer.wait(timeout=1.0)
                
                # Flush buffer if not empty
                self.flush_buffer()
            except Exception as e:
                logger.error_data("Write buffer thread error", {"error": str(e)})
        
        # Final flush on shutdown
        self.flush_buffer()
    
    def _buffered_write(self, operation: str, params: tuple = ()) -> None:
        """
        Buffer a write operation for batch execution.
        
        Args:
            operation: SQL statement
            params: Query parameters
        """
        if not self._enable_write_buffer:
            # Direct write if buffer disabled
            self._execute_with_retry(operation, params, commit=True)
            return
        
        with self._buffer_lock:
            self._write_buffer.append((operation, params))
            
            # Flush if buffer size reached
            if len(self._write_buffer) >= self._buffer_size:
                self._flush_buffer_unlocked()
    
    def flush_buffer(self) -> None:
        """Flush write buffer to database (thread-safe)."""
        if not self._enable_write_buffer:
            return
        
        with self._buffer_lock:
            self._flush_buffer_unlocked()
    
    def _flush_buffer_unlocked(self) -> None:
        """Flush write buffer to database (must hold buffer lock)."""
        if not self._write_buffer:
            return
        
        try:
            conn = self._get_connection()
            # Batch execute all buffered writes
            for operation, params in self._write_buffer:
                conn.execute(operation, params)
            conn.commit()
            
            flushed = len(self._write_buffer)
            self._write_buffer.clear()
            
            logger.debug_data("Write buffer flushed", {"count": flushed})
        except Exception as e:
            logger.error_data("Failed to flush write buffer", {"error": str(e)})
            # Clear buffer to avoid re-attempting failed writes
            self._write_buffer.clear()

    @abstractmethod
    def save(self, entry: T) -> str:
        """Save an entry. Returns entry ID."""
        pass

    @abstractmethod
    def get(self, entry_id: str) -> T | None:
        """Get an entry by ID."""
        pass

    @abstractmethod
    def update(self, entry_id: str, data: dict[str, Any]) -> bool:
        """Update an entry."""
        pass

    @abstractmethod
    def delete(self, entry_id: str) -> bool:
        """Delete an entry."""
        pass

    @abstractmethod
    def list_all(self, limit: int = 100, offset: int = 0) -> list[T]:
        """List all entries."""
        pass

    def _json_serialize(self, obj: Any) -> str:
        """Serialize object to JSON string."""
        def default(o: Any) -> Any:
            if isinstance(o, datetime):
                return o.isoformat()
            if isinstance(o, BaseModel):
                return o.model_dump()
            raise TypeError(f"Object of type {type(o)} is not JSON serializable")
        return json.dumps(obj, default=default, ensure_ascii=False)

    def _json_deserialize(self, data: str) -> Any:
        """Deserialize JSON string."""
        return json.loads(data)

    def _execute_with_retry(
        self,
        operation: str,
        params: tuple = (),
        max_retries: int = 3,
        commit: bool = True
    ) -> sqlite3.Cursor:
        """
        Execute SQL with retry logic for SQLITE_BUSY errors.
        
        Args:
            operation: SQL statement
            params: Query parameters
            max_retries: Maximum retry attempts
            commit: Whether to commit after execution
            
        Returns:
            Cursor from execution
        """
        import time
        conn = self._get_connection()
        last_error = None
        
        for attempt in range(max_retries):
            try:
                cursor = conn.execute(operation, params)
                if commit:
                    conn.commit()
                return cursor
            except sqlite3.OperationalError as e:
                last_error = e
                if "locked" in str(e) or "busy" in str(e):
                    if attempt < max_retries - 1:
                        wait_time = 0.1 * (attempt + 1)
                        logger.warning_data(
                            "SQLite lock detected, retrying",
                            {"attempt": attempt + 1, "wait": wait_time}
                        )
                        time.sleep(wait_time)
                        continue
                raise
        
        raise last_error

    def close(self) -> None:
        """Close database connection and shutdown write buffer."""
        # P1: Stop write thread and flush buffer
        if self._enable_write_buffer and self._write_thread:
            self._stop_writer.set()
            self.flush_buffer()
            if self._write_thread.is_alive():
                self._write_thread.join(timeout=2.0)
        
        if self._conn:
            self._conn.close()
            self._conn = None

    def clear(self) -> int:
        """Clear all entries. Returns count deleted."""
        conn = self._get_connection()
        cursor = conn.execute("DELETE FROM memory_entries")
        conn.commit()
        return cursor.rowcount

    def __enter__(self) -> "MemoryStore[T]":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
