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
        """Get database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
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
