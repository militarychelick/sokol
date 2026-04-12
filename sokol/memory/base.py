"""Base memory store with SQLite backend."""

import json
import sqlite3
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

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._init_db()

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
        """Close database connection."""
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
