"""Automation tools using ActionExecutor for UIA/Browser/OCR automation."""

from typing import Any

from sokol.action.executor import ActionExecutor
from sokol.core.types import RiskLevel
from sokol.observability.logging import get_logger
from sokol.runtime.result import Result
from sokol.tools.base import Tool, ToolResult

logger = get_logger("sokol.tools.builtin.automation")


class UIAClickTool(Tool[dict[str, Any]]):
    """Click on Windows UI element using UIA."""

    @property
    def name(self) -> str:
        return "uia_click"

    @property
    def description(self) -> str:
        return "Click on a Windows UI element using UI Automation"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.WRITE

    @property
    def undo_support(self) -> bool:
        return False

    @property
    def examples(self) -> list[str]:
        return [
            "click on Notepad",
            "click Save button",
            "click OK",
        ]

    def get_schema(self) -> Result[dict]:
        return Result.ok({
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Target element to click on",
                },
            },
            "required": ["target"],
        })

    def execute(self, target: str) -> Result[ToolResult[dict[str, Any]]]:
        """Click on target element."""
        try:
            executor = ActionExecutor()
            result = executor.click(target)

            if result.success:
                return Result.ok(
                    ToolResult(
                        success=True,
                        data={"method": result.method_used, "target": target},
                    )
                )
            else:
                return Result.ok(
                    ToolResult(
                        success=False,
                        error=result.error or "Click failed",
                    )
                )
        except Exception as e:
            logger.error_data("UIA click failed", {"error": str(e)})
            return Result.ok(ToolResult(success=False, error=str(e)))


class UIATypeTool(Tool[dict[str, Any]]):
    """Type text into Windows UI element using UIA."""

    @property
    def name(self) -> str:
        return "uia_type"

    @property
    def description(self) -> str:
        return "Type text into a Windows UI element using UI Automation"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.WRITE

    @property
    def undo_support(self) -> bool:
        return False

    @property
    def examples(self) -> list[str]:
        return [
            "type Hello into Notepad",
            "type username into field",
            "type text into search box",
        ]

    def get_schema(self) -> Result[dict]:
        return Result.ok({
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Target element to type into",
                },
                "text": {
                    "type": "string",
                    "description": "Text to type",
                },
            },
            "required": ["target", "text"],
        })

    def execute(self, target: str, text: str) -> Result[ToolResult[dict[str, Any]]]:
        """Type text into target element."""
        try:
            executor = ActionExecutor()
            result = executor.type_text(target, text)

            if result.success:
                return Result.ok(
                    ToolResult(
                        success=True,
                        data={"method": result.method_used, "target": target, "text": text},
                    )
                )
            else:
                return Result.ok(
                    ToolResult(
                        success=False,
                        error=result.error or "Type failed",
                    )
                )
        except Exception as e:
            logger.error_data("UIA type failed", {"error": str(e)})
            return Result.ok(ToolResult(success=False, error=str(e)))


class BrowserNavigateTool(Tool[dict[str, Any]]):
    """Navigate browser to URL using DOM automation."""

    @property
    def name(self) -> str:
        return "browser_navigate"

    @property
    def description(self) -> str:
        return "Navigate browser to URL using DOM automation"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.READ

    @property
    def undo_support(self) -> bool:
        return False

    @property
    def examples(self) -> list[str]:
        return [
            "navigate to https://google.com",
            "open https://github.com",
            "go to https://example.com",
        ]

    def get_schema(self) -> Result[dict]:
        return Result.ok({
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to navigate to",
                },
            },
            "required": ["url"],
        })

    def execute(self, url: str) -> Result[ToolResult[dict[str, Any]]]:
        """Navigate to URL."""
        try:
            executor = ActionExecutor()
            result = executor.execute("navigate", url)

            if result.success:
                return Result.ok(
                    ToolResult(
                        success=True,
                        data={"url": url},
                    )
                )
            else:
                return Result.ok(
                    ToolResult(
                        success=False,
                        error=result.error or "Navigation failed",
                    )
                )
        except Exception as e:
            logger.error_data("Browser navigation failed", {"error": str(e)})
            return Result.ok(ToolResult(success=False, error=str(e)))


class BrowserClickTool(Tool[dict[str, Any]]):
    """Click on browser element using DOM automation."""

    @property
    def name(self) -> str:
        return "browser_click"

    @property
    def description(self) -> str:
        return "Click on browser element using DOM automation"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.WRITE

    @property
    def undo_support(self) -> bool:
        return False

    @property
    def examples(self) -> list[str]:
        return [
            "click on button",
            "click submit button",
            "click search button",
        ]

    def get_schema(self) -> Result[dict]:
        return Result.ok({
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector of element to click",
                },
            },
            "required": ["selector"],
        })

    def execute(self, selector: str) -> Result[ToolResult[dict[str, Any]]]:
        """Click on element by selector."""
        try:
            executor = ActionExecutor()
            result = executor.execute("click", selector)

            if result.success:
                return Result.ok(
                    ToolResult(
                        success=True,
                        data={"selector": selector},
                    )
                )
            else:
                return Result.ok(
                    ToolResult(
                        success=False,
                        error=result.error or "Click failed",
                    )
                )
        except Exception as e:
            logger.error_data("Browser click failed", {"error": str(e)})
            return Result.ok(ToolResult(success=False, error=str(e)))


class OCRFindTool(Tool[dict[str, Any]]):
    """Find text on screen using OCR."""

    @property
    def name(self) -> str:
        return "ocr_find"

    @property
    def description(self) -> str:
        return "Find text on screen using OCR (fallback when UIA fails)"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.READ

    @property
    def undo_support(self) -> bool:
        return False

    @property
    def examples(self) -> list[str]:
        return [
            "find Save button on screen",
            "find OK button",
            "find text on screen",
        ]

    def get_schema(self) -> Result[dict]:
        return Result.ok({
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to find on screen",
                },
            },
            "required": ["text"],
        })

    def execute(self, text: str) -> Result[ToolResult[dict[str, Any]]]:
        """Find text on screen using OCR."""
        try:
            executor = ActionExecutor()
            result = executor.execute("find_text", text)

            if result.success:
                return Result.ok(
                    ToolResult(
                        success=True,
                        data={"text": text, "location": result.data},
                    )
                )
            else:
                return Result.ok(
                    ToolResult(
                        success=False,
                        error=result.error or "OCR find failed",
                    )
                )
        except Exception as e:
            logger.error_data("OCR find failed", {"error": str(e)})
            return Result.ok(ToolResult(success=False, error=str(e)))
