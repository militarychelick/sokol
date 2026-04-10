"""Tests for tools registry and builtin tools."""

import pytest

from sokol.core.types import RiskLevel
from sokol.tools.registry import ToolRegistry
from sokol.tools.base import Tool, ToolResult


class MockTool(Tool[str]):
    """Mock tool for testing."""

    @property
    def name(self) -> str:
        return "mock_tool"

    @property
    def description(self) -> str:
        return "Mock tool for testing"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.READ

    def get_schema(self):
        return {
            "type": "object",
            "properties": {
                "input": {"type": "string"},
            },
            "required": ["input"],
        }

    def execute(self, input: str) -> ToolResult[str]:
        return ToolResult(success=True, data=f"processed: {input}")


class TestToolRegistry:
    """Tests for ToolRegistry."""

    def test_register_tool(self):
        """Can register a tool."""
        registry = ToolRegistry()
        tool = MockTool()
        registry.register(tool)

        assert registry.has_tool("mock_tool")
        assert registry.get("mock_tool") is tool

    def test_unregister_tool(self):
        """Can unregister a tool."""
        registry = ToolRegistry()
        tool = MockTool()
        registry.register(tool)

        assert registry.unregister("mock_tool")
        assert not registry.has_tool("mock_tool")

    def test_list_tools(self):
        """Can list all tools."""
        registry = ToolRegistry()
        registry.register(MockTool())

        tools = registry.list_tools()
        assert "mock_tool" in tools

    def test_execute_tool(self):
        """Can execute tool by name."""
        registry = ToolRegistry()
        registry.register(MockTool())

        result = registry.execute("mock_tool", {"input": "test"})
        assert result.success
        assert result.data == "processed: test"

    def test_execute_nonexistent_tool(self):
        """Executing nonexistent tool returns error."""
        registry = ToolRegistry()

        result = registry.execute("nonexistent", {})
        assert not result.success
        assert "not found" in result.error

    def test_list_by_risk(self):
        """Can list tools by risk level."""
        registry = ToolRegistry()
        registry.register(MockTool())

        read_tools = registry.list_by_risk(RiskLevel.READ)
        assert "mock_tool" in read_tools

        dangerous_tools = registry.list_by_risk(RiskLevel.DANGEROUS)
        assert "mock_tool" not in dangerous_tools


class TestToolBase:
    """Tests for Tool base class."""

    def test_validate_params_required(self):
        """Validates required parameters."""
        tool = MockTool()

        is_valid, error = tool.validate_params({})
        assert not is_valid
        assert "Missing required" in error

        is_valid, error = tool.validate_params({"input": "test"})
        assert is_valid
        assert error is None

    def test_safe_execute_validates(self):
        """safe_execute validates parameters."""
        tool = MockTool()

        result = tool.safe_execute()
        assert not result.success
        assert "Missing required" in result.error

    def test_safe_execute_returns_result(self):
        """safe_execute returns result on success."""
        tool = MockTool()

        result = tool.safe_execute(input="test")
        assert result.success
        assert result.data == "processed: test"
        assert result.execution_time > 0

    def test_get_tool_schema(self):
        """Can get full tool schema."""
        tool = MockTool()
        schema = tool.get_tool_schema()

        assert schema.name == "mock_tool"
        assert schema.risk_level == RiskLevel.READ
        assert "input" in schema.parameters["properties"]


class TestBuiltinTools:
    """Tests for builtin tools."""

    def test_discover_tools(self):
        """Can discover builtin tools."""
        registry = ToolRegistry()
        count = registry.discover_tools()

        assert count > 0
        assert registry.has_tool("app_launcher")
        assert registry.has_tool("system_info")

    def test_app_launcher_schema(self):
        """App launcher has correct schema."""
        registry = ToolRegistry()
        registry.discover_tools()

        schema = registry.get_schema("app_launcher")
        assert schema is not None
        assert schema.risk_level == RiskLevel.READ
        assert "app_name" in schema.parameters["properties"]

    def test_system_info_is_read_only(self):
        """System info tool is read-only."""
        registry = ToolRegistry()
        registry.discover_tools()

        schema = registry.get_schema("system_info")
        assert schema.risk_level == RiskLevel.READ

    def test_file_ops_has_write_risk(self):
        """File ops tool has WRITE risk level."""
        registry = ToolRegistry()
        registry.discover_tools()

        schema = registry.get_schema("file_ops")
        assert schema.risk_level == RiskLevel.WRITE
