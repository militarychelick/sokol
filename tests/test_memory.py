"""
Tests for memory save/load
"""

import pytest
from pathlib import Path
import tempfile

from sokol.memory.store import MemoryStore


@pytest.mark.asyncio
async def test_memory_store_initialize():
    """Test memory store initialization."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = MemoryStore(db_path)
        
        await store.initialize()
        await store.close()


@pytest.mark.asyncio
async def test_profile_save_load():
    """Test profile save and load."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = MemoryStore(db_path)
        
        await store.initialize()
        
        # Save
        await store.set_profile("test_key", "test_value")
        
        # Load
        value = await store.get_profile("test_key")
        assert value == "test_value"
        
        await store.close()


@pytest.mark.asyncio
async def test_session_memory():
    """Test session memory storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = MemoryStore(db_path)
        
        await store.initialize()
        
        # Store session
        await store.store_session(
            input_text="test input",
            intent_type="command",
            action_taken="app_launch",
            result="success",
            success=True,
        )
        
        # Retrieve
        memory = await store.get_session_memory(limit=10)
        assert len(memory) == 1
        assert memory[0]["input_text"] == "test input"
        
        await store.close()
