"""Profile memory - user preferences and habits."""

import sqlite3
from datetime import datetime
from typing import Any

from sokol.core.types import UserProfile
from sokol.observability.logging import get_logger

from .base import MemoryStore

logger = get_logger("sokol.memory.profile")


class ProfileMemory(MemoryStore[UserProfile]):
    """Profile memory store - user preferences and habits."""

    def _init_db(self) -> None:
        conn = self._get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                name TEXT,
                preferences TEXT NOT NULL DEFAULT '{}',
                frequently_used_apps TEXT NOT NULL DEFAULT '[]',
                command_templates TEXT NOT NULL DEFAULT '{}',
                work_habits TEXT NOT NULL DEFAULT '{}',
                tags TEXT NOT NULL DEFAULT '[]',
                metadata TEXT NOT NULL DEFAULT '{}'
            )
        """)
        conn.commit()

    def create_profile(self, name: str | None = None) -> UserProfile:
        """Create a new user profile."""
        profile = UserProfile(name=name)
        self.save(profile)
        logger.info_data("Profile created", {"profile_id": profile.id, "name": name})
        return profile

    def save(self, entry: UserProfile) -> str:
        """Save profile."""
        conn = self._get_connection()
        conn.execute(
            """
            INSERT OR REPLACE INTO profiles
            (id, created_at, updated_at, name, preferences, frequently_used_apps,
             command_templates, work_habits, tags, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.id,
                entry.created_at.isoformat(),
                entry.updated_at.isoformat(),
                entry.name,
                self._json_serialize(entry.preferences),
                self._json_serialize(entry.frequently_used_apps),
                self._json_serialize(entry.command_templates),
                self._json_serialize(entry.work_habits),
                self._json_serialize(entry.tags),
                self._json_serialize(entry.metadata),
            ),
        )
        conn.commit()
        return entry.id

    def get(self, entry_id: str) -> UserProfile | None:
        """Get profile by ID."""
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM profiles WHERE id = ?",
            (entry_id,),
        )
        row = cursor.fetchone()
        if row:
            return self._row_to_model(row)
        return None

    def get_default_profile(self) -> UserProfile:
        """Get or create default profile."""
        conn = self._get_connection()
        cursor = conn.execute("SELECT * FROM profiles LIMIT 1")
        row = cursor.fetchone()
        if row:
            return self._row_to_model(row)
        return self.create_profile(name="default")

    def update(self, entry_id: str, data: dict[str, Any]) -> bool:
        """Update profile."""
        entry = self.get(entry_id)
        if not entry:
            return False

        if "name" in data:
            entry.name = data["name"]
        if "preferences" in data:
            entry.preferences.update(data["preferences"])
        if "frequently_used_apps" in data:
            entry.frequently_used_apps = data["frequently_used_apps"]
        if "command_templates" in data:
            entry.command_templates.update(data["command_templates"])
        if "work_habits" in data:
            entry.work_habits.update(data["work_habits"])
        if "tags" in data:
            entry.tags = data["tags"]
        if "metadata" in data:
            entry.metadata.update(data["metadata"])

        entry.updated_at = datetime.now()
        self.save(entry)
        return True

    def delete(self, entry_id: str) -> bool:
        """Delete profile."""
        conn = self._get_connection()
        cursor = conn.execute("DELETE FROM profiles WHERE id = ?", (entry_id,))
        conn.commit()
        return cursor.rowcount > 0

    def list_all(self, limit: int = 100, offset: int = 0) -> list[UserProfile]:
        """List all profiles."""
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM profiles ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return [self._row_to_model(row) for row in cursor.fetchall()]

    def set_preference(self, profile_id: str, key: str, value: Any) -> bool:
        """Set a preference."""
        entry = self.get(profile_id)
        if not entry:
            return False

        entry.preferences[key] = value
        entry.updated_at = datetime.now()
        self.save(entry)

        logger.debug_data(
            "Preference set",
            {"profile_id": profile_id, "key": key},
        )
        return True

    def get_preference(self, profile_id: str, key: str, default: Any = None) -> Any:
        """Get a preference."""
        entry = self.get(profile_id)
        if not entry:
            return default
        return entry.preferences.get(key, default)

    def add_frequently_used_app(self, profile_id: str, app_name: str) -> bool:
        """Add app to frequently used list."""
        entry = self.get(profile_id)
        if not entry:
            return False

        # Remove if already exists (will be moved to front)
        if app_name in entry.frequently_used_apps:
            entry.frequently_used_apps.remove(app_name)

        # Add to front
        entry.frequently_used_apps.insert(0, app_name)

        # Keep only top 20
        entry.frequently_used_apps = entry.frequently_used_apps[:20]

        entry.updated_at = datetime.now()
        self.save(entry)
        return True

    def add_command_template(
        self,
        profile_id: str,
        name: str,
        template: str,
    ) -> bool:
        """Add command template."""
        entry = self.get(profile_id)
        if not entry:
            return False

        entry.command_templates[name] = template
        entry.updated_at = datetime.now()
        self.save(entry)
        return True

    def get_command_template(self, profile_id: str, name: str) -> str | None:
        """Get command template."""
        entry = self.get(profile_id)
        if not entry:
            return None
        return entry.command_templates.get(name)

    def update_work_habit(
        self,
        profile_id: str,
        habit_name: str,
        habit_data: dict[str, Any],
    ) -> bool:
        """Update work habit."""
        entry = self.get(profile_id)
        if not entry:
            return False

        entry.work_habits[habit_name] = habit_data
        entry.updated_at = datetime.now()
        self.save(entry)
        return True

    def _row_to_model(self, row) -> UserProfile:
        """Convert database row to model."""
        return UserProfile(
            id=row["id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            name=row["name"],
            preferences=self._json_deserialize(row["preferences"]),
            frequently_used_apps=self._json_deserialize(row["frequently_used_apps"]),
            command_templates=self._json_deserialize(row["command_templates"]),
            work_habits=self._json_deserialize(row["work_habits"]),
            tags=self._json_deserialize(row["tags"]),
            metadata=self._json_deserialize(row["metadata"]),
        )
