"""Tests for memory system."""

import pytest

from sokol.memory.session import SessionMemory
from sokol.memory.profile import ProfileMemory
from sokol.memory.longterm import LongTermMemory
from sokol.memory.manager import MemoryManager


class TestSessionMemory:
    """Tests for SessionMemory."""

    def test_create_session(self, temp_dir):
        """Can create a session."""
        memory = SessionMemory(temp_dir / "session.db")
        try:
            session = memory.create_session()

            assert session.id is not None
            assert session.conversation == []
        finally:
            memory.close()

    def test_add_conversation_entry(self, temp_dir):
        """Can add conversation entries."""
        memory = SessionMemory(temp_dir / "session.db")
        try:
            session = memory.create_session()

            memory.add_conversation_entry(session.id, "user", "Hello")
            memory.add_conversation_entry(session.id, "assistant", "Hi there!")

            history = memory.get_conversation(session.id)
            assert len(history) == 2
            assert history[0].role == "user"
            assert history[0].content == "Hello"
        finally:
            memory.close()

    def test_set_context(self, temp_dir):
        """Can set and get context."""
        memory = SessionMemory(temp_dir / "session.db")
        try:
            session = memory.create_session()

            memory.set_context(session.id, "current_app", "notepad")
            assert memory.get_context(session.id, "current_app") == "notepad"
        finally:
            memory.close()

    def test_clear_conversation(self, temp_dir):
        """Can clear conversation history."""
        memory = SessionMemory(temp_dir / "session.db")
        try:
            session = memory.create_session()

            memory.add_conversation_entry(session.id, "user", "Test")
            assert memory.clear_conversation(session.id) == 1

            history = memory.get_conversation(session.id)
            assert len(history) == 0
        finally:
            memory.close()


class TestProfileMemory:
    """Tests for ProfileMemory."""

    def test_create_profile(self, temp_dir):
        """Can create a profile."""
        memory = ProfileMemory(temp_dir / "profile.db")
        try:
            profile = memory.create_profile(name="Test User")

            assert profile.id is not None
            assert profile.name == "Test User"
        finally:
            memory.close()

    def test_set_preference(self, temp_dir):
        """Can set and get preferences."""
        memory = ProfileMemory(temp_dir / "profile.db")
        try:
            profile = memory.create_profile()

            memory.set_preference(profile.id, "theme", "dark")
            assert memory.get_preference(profile.id, "theme") == "dark"
        finally:
            memory.close()

    def test_add_frequently_used_app(self, temp_dir):
        """Can track frequently used apps."""
        memory = ProfileMemory(temp_dir / "profile.db")
        try:
            profile = memory.create_profile()

            memory.add_frequently_used_app(profile.id, "notepad")
            memory.add_frequently_used_app(profile.id, "chrome")

            profile = memory.get(profile.id)
            assert "chrome" in profile.frequently_used_apps
            assert "notepad" in profile.frequently_used_apps
        finally:
            memory.close()

    def test_add_command_template(self, temp_dir):
        """Can add command templates."""
        memory = ProfileMemory(temp_dir / "profile.db")
        try:
            profile = memory.create_profile()

            memory.add_command_template(
                profile.id,
                "open_browser",
                "open chrome",
            )

            template = memory.get_command_template(profile.id, "open_browser")
            assert template == "open chrome"
        finally:
            memory.close()

    def test_get_default_profile(self, temp_dir):
        """Can get or create default profile."""
        memory = ProfileMemory(temp_dir / "profile.db")
        try:
            profile = memory.get_default_profile()

            assert profile is not None
        finally:
            memory.close()


class TestLongTermMemory:
    """Tests for LongTermMemory."""

    def test_create_pattern(self, temp_dir):
        """Can create a pattern."""
        memory = LongTermMemory(temp_dir / "longterm.db")
        try:
            pattern = memory.create_pattern(
                pattern_type="command_sequence",
                pattern_data={"steps": ["open", "type", "save"]},
                tags=["automation"],
            )

            assert pattern.id is not None
            assert pattern.pattern_type == "command_sequence"
        finally:
            memory.close()

    def test_find_by_type(self, temp_dir):
        """Can find patterns by type."""
        memory = LongTermMemory(temp_dir / "longterm.db")
        try:
            memory.create_pattern("type_a", {"data": 1})
            memory.create_pattern("type_b", {"data": 2})
            memory.create_pattern("type_a", {"data": 3})

            patterns = memory.find_by_type("type_a")
            assert len(patterns) == 2
        finally:
            memory.close()

    def test_record_usage(self, temp_dir):
        """Can record pattern usage."""
        memory = LongTermMemory(temp_dir / "longterm.db")
        try:
            pattern = memory.create_pattern("test", {"data": 1})

            memory.record_usage(pattern.id)
            memory.record_usage(pattern.id)

            updated = memory.get(pattern.id)
            assert updated.usage_count == 2
            assert updated.last_used is not None
        finally:
            memory.close()

    def test_get_most_used(self, temp_dir):
        """Can get most used patterns."""
        memory = LongTermMemory(temp_dir / "longterm.db")
        try:
            p1 = memory.create_pattern("test", {"data": 1})
            p2 = memory.create_pattern("test", {"data": 2})
            p3 = memory.create_pattern("test", {"data": 3})

            memory.record_usage(p1.id)
            memory.record_usage(p1.id)
            memory.record_usage(p2.id)

            most_used = memory.get_most_used(limit=2)
            assert len(most_used) == 2
            assert most_used[0].id == p1.id
        finally:
            memory.close()


class TestMemoryManager:
    """Tests for MemoryManager."""

    def test_start_session(self, temp_dir):
        """Can start a session."""
        manager = MemoryManager(temp_dir)
        try:
            session = manager.start_session()

            assert session is not None
            assert manager.current_session is not None
        finally:
            manager.shutdown()

    def test_load_profile(self, temp_dir):
        """Can load profile."""
        manager = MemoryManager(temp_dir)
        try:
            profile = manager.load_profile()

            assert profile is not None
            assert manager.current_profile is not None
        finally:
            manager.shutdown()

    def test_add_message(self, temp_dir):
        """Can add messages through manager."""
        manager = MemoryManager(temp_dir)
        try:
            manager.start_session()

            manager.add_message("user", "Hello")
            manager.add_message("assistant", "Hi!")

            history = manager.get_conversation_history()
            assert len(history) == 2
        finally:
            manager.shutdown()

    def test_set_preference(self, temp_dir):
        """Can set preferences through manager."""
        manager = MemoryManager(temp_dir)
        try:
            manager.load_profile()

            manager.set_preference("theme", "dark")
            assert manager.get_preference("theme") == "dark"
        finally:
            manager.shutdown()

    def test_export_session(self, temp_dir):
        """Can export session data."""
        manager = MemoryManager(temp_dir)
        try:
            manager.start_session()
            manager.add_message("user", "Test")

            exported = manager.export_session()
            assert "session_id" in exported
            assert "conversation" in exported
            assert len(exported["conversation"]) == 1
        finally:
            manager.shutdown()

    def test_shutdown(self, temp_dir):
        """Can shutdown cleanly."""
        manager = MemoryManager(temp_dir)
        manager.start_session()
        manager.load_profile()

        # Should not raise
        manager.shutdown()
