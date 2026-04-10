"""
Memory store - SQLite database layer
"""

from __future__ import annotations

import aiosqlite
from datetime import datetime
from pathlib import Path
from typing import Any


class MemoryStore:
    """
    SQLite database for memory storage.
    
    Tables:
    - session_memory: Current session interactions
    - user_profile: User preferences and settings
    - habits: Behavioral patterns
    - interactions: Full interaction history
    """
    
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._connection: aiosqlite.Connection | None = None
    
    async def initialize(self) -> None:
        """Initialize database and create tables."""
        self._connection = await aiosqlite.connect(self.db_path)
        await self._create_tables()
    
    async def _create_tables(self) -> None:
        """Create all database tables."""
        if self._connection is None:
            return
        
        # Session memory
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS session_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                input_text TEXT,
                intent_type TEXT,
                action_taken TEXT,
                result TEXT,
                success BOOLEAN
            )
        """)
        
        # User profile
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS user_profile (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Habits
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS habits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_type TEXT,
                pattern_data TEXT,
                frequency INTEGER DEFAULT 1,
                last_used DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Full interaction history
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                input TEXT,
                intent TEXT,
                action TEXT,
                success BOOLEAN,
                feedback TEXT
            )
        """)
        
        await self._connection.commit()
    
    async def store_session(
        self,
        input_text: str,
        intent_type: str,
        action_taken: str,
        result: str,
        success: bool,
    ) -> None:
        """Store session interaction."""
        if self._connection is None:
            return
        
        await self._connection.execute(
            """
            INSERT INTO session_memory (input_text, intent_type, action_taken, result, success)
            VALUES (?, ?, ?, ?, ?)
            """,
            (input_text, intent_type, action_taken, result, success),
        )
        await self._connection.commit()
    
    async def get_session_memory(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent session memory."""
        if self._connection is None:
            return []
        
        cursor = await self._connection.execute(
            """
            SELECT * FROM session_memory
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        )
        
        rows = await cursor.fetchall()
        
        return [
            {
                "id": row[0],
                "timestamp": row[1],
                "input_text": row[2],
                "intent_type": row[3],
                "action_taken": row[4],
                "result": row[5],
                "success": row[6],
            }
            for row in rows
        ]
    
    async def clear_session(self) -> None:
        """Clear session memory."""
        if self._connection is None:
            return
        
        await self._connection.execute("DELETE FROM session_memory")
        await self._connection.commit()
    
    async def set_profile(self, key: str, value: str) -> None:
        """Set profile value."""
        if self._connection is None:
            return
        
        await self._connection.execute(
            """
            INSERT OR REPLACE INTO user_profile (key, value, updated_at)
            VALUES (?, ?, ?)
            """,
            (key, value, datetime.now().isoformat()),
        )
        await self._connection.commit()
    
    async def get_profile(self, key: str) -> str | None:
        """Get profile value."""
        if self._connection is None:
            return None
        
        cursor = await self._connection.execute(
            "SELECT value FROM user_profile WHERE key = ?",
            (key,),
        )
        
        row = await cursor.fetchone()
        return row[0] if row else None
    
    async def get_all_profile(self) -> dict[str, str]:
        """Get all profile values."""
        if self._connection is None:
            return {}
        
        cursor = await self._connection.execute("SELECT key, value FROM user_profile")
        rows = await cursor.fetchall()
        
        return {row[0]: row[1] for row in rows}
    
    async def increment_habit(self, pattern_type: str, pattern_data: str) -> None:
        """Increment habit frequency."""
        if self._connection is None:
            return
        
        await self._connection.execute(
            """
            INSERT INTO habits (pattern_type, pattern_data, frequency, last_used)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(pattern_type, pattern_data)
            DO UPDATE SET frequency = frequency + 1, last_used = ?
            """,
            (pattern_type, pattern_data, datetime.now().isoformat(), datetime.now().isoformat()),
        )
        await self._connection.commit()
    
    async def get_habits(self, pattern_type: str | None = None) -> list[dict[str, Any]]:
        """Get habits."""
        if self._connection is None:
            return []
        
        if pattern_type:
            cursor = await self._connection.execute(
                "SELECT * FROM habits WHERE pattern_type = ? ORDER BY frequency DESC",
                (pattern_type,),
            )
        else:
            cursor = await self._connection.execute(
                "SELECT * FROM habits ORDER BY frequency DESC",
            )
        
        rows = await cursor.fetchall()
        
        return [
            {
                "id": row[0],
                "pattern_type": row[1],
                "pattern_data": row[2],
                "frequency": row[3],
                "last_used": row[4],
            }
            for row in rows
        ]
    
    async def close(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None
