"""Pytest configuration and fixtures."""

import pytest
import tempfile
from pathlib import Path

from sokol.core.config import Config
from sokol.core.types import AgentState


@pytest.fixture
def temp_dir():
    """Create temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_config(temp_dir):
    """Create test configuration."""
    return Config(
        logging={"level": "DEBUG", "file": str(temp_dir / "test.log")},
        memory={
            "profile_path": str(temp_dir / "profile.db"),
            "longterm_path": str(temp_dir / "longterm.db"),
        },
    )


@pytest.fixture
def mock_orchestrator(test_config):
    """Create mock orchestrator for testing."""
    from sokol.runtime.orchestrator import Orchestrator
    orch = Orchestrator(test_config)
    orch.setup()
    yield orch
    orch.stop("test_cleanup")


@pytest.fixture
def mock_memory(temp_dir):
    """Create mock memory manager for testing."""
    from sokol.memory.manager import MemoryManager
    mem = MemoryManager(temp_dir)
    yield mem
    mem.shutdown()


@pytest.fixture
def tool_registry():
    """Create tool registry for testing."""
    from sokol.tools.registry import ToolRegistry
    registry = ToolRegistry()
    registry.discover_tools()
    return registry
