"""Session memory - current conversation and context."""

import sqlite3
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from sokol.core.types import MemoryEntry, SessionMemory as SessionMemoryModel
from sokol.observability.logging import get_logger

from .base import MemoryStore

logger = get_logger("sokol.memory.session")


class ConversationEntry(BaseModel):
    """Single conversation entry."""

    role: str  # user, assistant, system
    content: str
    timestamp: datetime
    metadata: dict[str, Any] = {}


class SessionMemory(MemoryStore[SessionMemoryModel]):
    """Session memory store - current conversation and context."""

    def _init_db(self) -> None:
        conn = self._get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                conversation TEXT NOT NULL DEFAULT '[]',
                context TEXT NOT NULL DEFAULT '{}',
                active_tools TEXT NOT NULL DEFAULT '[]',
                tags TEXT NOT NULL DEFAULT '[]',
                metadata TEXT NOT NULL DEFAULT '{}'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}',
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)
        conn.commit()

    def create_session(self) -> SessionMemoryModel:
        """Create a new session."""
        session = SessionMemoryModel()
        self.save(session)
        logger.info_data("Session created", {"session_id": session.id})
        return session

    def save(self, entry: SessionMemoryModel) -> str:
        """Save session."""
        conn = self._get_connection()
        conn.execute(
            """
            INSERT OR REPLACE INTO sessions
            (id, created_at, updated_at, conversation, context, active_tools, tags, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.id,
                entry.created_at.isoformat(),
                entry.updated_at.isoformat(),
                self._json_serialize(entry.conversation),
                self._json_serialize(entry.context),
                self._json_serialize(entry.active_tools),
                self._json_serialize(entry.tags),
                self._json_serialize(entry.metadata),
            ),
        )
        conn.commit()
        return entry.id

    def get(self, entry_id: str) -> SessionMemoryModel | None:
        """Get session by ID."""
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM sessions WHERE id = ?",
            (entry_id,),
        )
        row = cursor.fetchone()
        if row:
            return self._row_to_model(row)
        return None

    def update(self, entry_id: str, data: dict[str, Any]) -> bool:
        """Update session."""
        entry = self.get(entry_id)
        if not entry:
            return False

        # Update fields
        if "conversation" in data:
            entry.conversation = data["conversation"]
        if "context" in data:
            entry.context.update(data["context"])
        if "active_tools" in data:
            entry.active_tools = data["active_tools"]
        if "tags" in data:
            entry.tags = data["tags"]
        if "metadata" in data:
            entry.metadata.update(data["metadata"])

        entry.updated_at = datetime.now()
        self.save(entry)
        return True

    def delete(self, entry_id: str) -> bool:
        """Delete session."""
        conn = self._get_connection()
        cursor = conn.execute("DELETE FROM sessions WHERE id = ?", (entry_id,))
        conn.commit()
        return cursor.rowcount > 0

    def list_all(self, limit: int = 100, offset: int = 0) -> list[SessionMemoryModel]:
        """List all sessions."""
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return [self._row_to_model(row) for row in cursor.fetchall()]

    def add_conversation_entry(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Add entry to conversation history."""
        entry = ConversationEntry(
            role=role,
            content=content,
            timestamp=datetime.now(),
            metadata=metadata or {},
        )

        conn = self._get_connection()
        conn.execute(
            """
            INSERT INTO conversation_history
            (session_id, role, content, timestamp, metadata)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                session_id,
                role,
                content,
                entry.timestamp.isoformat(),
                self._json_serialize(entry.metadata),
            ),
        )
        conn.commit()

        # Update session timestamp
        self.update(session_id, {})

        logger.debug_data(
            "Conversation entry added",
            {"session_id": session_id, "role": role, "content_preview": content[:50]},
        )

        return True

    def get_conversation(
        self,
        session_id: str,
        limit: int = 50,
    ) -> list[ConversationEntry]:
        """Get conversation history for session."""
        conn = self._get_connection()
        cursor = conn.execute(
            """
            SELECT role, content, timestamp, metadata
            FROM conversation_history
            WHERE session_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (session_id, limit),
        )

        entries = []
        for row in cursor.fetchall():
            entries.append(ConversationEntry(
                role=row["role"],
                content=row["content"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                metadata=self._json_deserialize(row["metadata"]),
            ))

        return list(reversed(entries))  # Return in chronological order

    def clear_conversation(self, session_id: str) -> int:
        """Clear conversation history for session."""
        conn = self._get_connection()
        cursor = conn.execute(
            "DELETE FROM conversation_history WHERE session_id = ?",
            (session_id,),
        )
        conn.commit()
        return cursor.rowcount

    def set_context(self, session_id: str, key: str, value: Any) -> bool:
        """Set context value."""
        entry = self.get(session_id)
        if not entry:
            return False

        entry.context[key] = value
        entry.updated_at = datetime.now()
        self.save(entry)
        return True

    def get_context(self, session_id: str, key: str) -> Any:
        """Get context value."""
        entry = self.get(session_id)
        if not entry:
            return None
        return entry.context.get(key)

    def _row_to_model(self, row: sqlite3.Row) -> SessionMemoryModel:
        """Convert database row to model."""
        return SessionMemoryModel(
            id=row["id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            conversation=self._json_deserialize(row["conversation"]),
            context=self._json_deserialize(row["context"]),
            active_tools=self._json_deserialize(row["active_tools"]),
            tags=self._json_deserialize(row["tags"]),
            metadata=self._json_deserialize(row["metadata"]),
        )
