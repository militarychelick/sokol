"""Long-term memory - patterns and templates."""

import sqlite3
from datetime import datetime
from typing import Any

from sokol.core.types import LongTermMemory as LongTermMemoryModel
from sokol.observability.logging import get_logger

from .base import MemoryStore

logger = get_logger("sokol.memory.longterm")


class LongTermMemory(MemoryStore[LongTermMemoryModel]):
    """Long-term memory store - patterns and templates."""

    def _init_db(self) -> None:
        conn = self._get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS longterm_memory (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                pattern_type TEXT NOT NULL DEFAULT 'general',
                pattern_data TEXT NOT NULL DEFAULT '{}',
                usage_count INTEGER NOT NULL DEFAULT 0,
                last_used TEXT,
                tags TEXT NOT NULL DEFAULT '[]',
                metadata TEXT NOT NULL DEFAULT '{}'
            )
        """)
        # Index for pattern type searches
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pattern_type ON longterm_memory(pattern_type)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_usage_count ON longterm_memory(usage_count DESC)"
        )
        conn.commit()

    def create_pattern(
        self,
        pattern_type: str,
        pattern_data: dict[str, Any],
        tags: list[str] | None = None,
    ) -> LongTermMemoryModel:
        """Create a new pattern."""
        pattern = LongTermMemoryModel(
            pattern_type=pattern_type,
            pattern_data=pattern_data,
            tags=tags or [],
        )
        self.save(pattern)
        logger.info_data(
            "Pattern created",
            {"pattern_id": pattern.id, "type": pattern_type},
        )
        return pattern

    def save(self, entry: LongTermMemoryModel) -> str:
        """Save pattern."""
        conn = self._get_connection()
        conn.execute(
            """
            INSERT OR REPLACE INTO longterm_memory
            (id, created_at, updated_at, pattern_type, pattern_data, usage_count,
             last_used, tags, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.id,
                entry.created_at.isoformat(),
                entry.updated_at.isoformat(),
                entry.pattern_type,
                self._json_serialize(entry.pattern_data),
                entry.usage_count,
                entry.last_used.isoformat() if entry.last_used else None,
                self._json_serialize(entry.tags),
                self._json_serialize(entry.metadata),
            ),
        )
        conn.commit()
        return entry.id

    def get(self, entry_id: str) -> LongTermMemoryModel | None:
        """Get pattern by ID."""
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM longterm_memory WHERE id = ?",
            (entry_id,),
        )
        row = cursor.fetchone()
        if row:
            return self._row_to_model(row)
        return None

    def update(self, entry_id: str, data: dict[str, Any]) -> bool:
        """Update pattern."""
        entry = self.get(entry_id)
        if not entry:
            return False

        if "pattern_type" in data:
            entry.pattern_type = data["pattern_type"]
        if "pattern_data" in data:
            entry.pattern_data.update(data["pattern_data"])
        if "tags" in data:
            entry.tags = data["tags"]
        if "metadata" in data:
            entry.metadata.update(data["metadata"])

        entry.updated_at = datetime.now()
        self.save(entry)
        return True

    def delete(self, entry_id: str) -> bool:
        """Delete pattern."""
        conn = self._get_connection()
        cursor = conn.execute(
            "DELETE FROM longterm_memory WHERE id = ?",
            (entry_id,),
        )
        conn.commit()
        return cursor.rowcount > 0

    def list_all(self, limit: int = 100, offset: int = 0) -> list[LongTermMemoryModel]:
        """List all patterns."""
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM longterm_memory ORDER BY usage_count DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return [self._row_to_model(row) for row in cursor.fetchall()]

    def find_by_type(self, pattern_type: str) -> list[LongTermMemoryModel]:
        """Find patterns by type."""
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM longterm_memory WHERE pattern_type = ? ORDER BY usage_count DESC",
            (pattern_type,),
        )
        return [self._row_to_model(row) for row in cursor.fetchall()]

    def find_by_tags(self, tags: list[str]) -> list[LongTermMemoryModel]:
        """Find patterns by tags (any match)."""
        conn = self._get_connection()
        patterns = []
        cursor = conn.execute("SELECT * FROM longterm_memory")
        for row in cursor.fetchall():
            pattern = self._row_to_model(row)
            if any(tag in pattern.tags for tag in tags):
                patterns.append(pattern)
        return patterns

    def record_usage(self, entry_id: str) -> bool:
        """Record usage of a pattern."""
        entry = self.get(entry_id)
        if not entry:
            return False

        entry.usage_count += 1
        entry.last_used = datetime.now()
        entry.updated_at = datetime.now()
        self.save(entry)
        return True

    def get_most_used(self, limit: int = 10) -> list[LongTermMemoryModel]:
        """Get most used patterns."""
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM longterm_memory ORDER BY usage_count DESC LIMIT ?",
            (limit,),
        )
        return [self._row_to_model(row) for row in cursor.fetchall()]

    def get_recently_used(self, limit: int = 10) -> list[LongTermMemoryModel]:
        """Get recently used patterns."""
        conn = self._get_connection()
        cursor = conn.execute(
            """
            SELECT * FROM longterm_memory
            WHERE last_used IS NOT NULL
            ORDER BY last_used DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [self._row_to_model(row) for row in cursor.fetchall()]

    def cleanup_unused(self, min_usage: int = 0, older_than_days: int = 30) -> int:
        """Remove unused patterns."""
        conn = self._get_connection()
        cursor = conn.execute(
            """
            DELETE FROM longterm_memory
            WHERE usage_count <= ?
            AND datetime(last_used) < datetime('now', ? || ' days')
            """,
            (min_usage, f"-{older_than_days}"),
        )
        conn.commit()
        return cursor.rowcount

    def _row_to_model(self, row) -> LongTermMemoryModel:
        """Convert database row to model."""
        return LongTermMemoryModel(
            id=row["id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            pattern_type=row["pattern_type"],
            pattern_data=self._json_deserialize(row["pattern_data"]),
            usage_count=row["usage_count"],
            last_used=datetime.fromisoformat(row["last_used"]) if row["last_used"] else None,
            tags=self._json_deserialize(row["tags"]),
            metadata=self._json_deserialize(row["metadata"]),
        )
