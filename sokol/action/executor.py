"""Action executor - wrapper for action execution with safety checks."""

from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
import threading

from sokol.action.uia_automation import UIAExecutor
from sokol.action.browser_automation import BrowserExecutor
from sokol.action.ocr_fallback import OCRFallback
from sokol.observability.logging import get_logger

logger = get_logger("sokol.action.executor")


@dataclass
class ActionResult:
    """Result of an action execution."""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    method_used: str = ""


class ActionExecutor:
    """
    Main action executor with priority system.

    Priority: UIA > Browser DOM > OCR (fallback)
    """

    def __init__(self) -> None:
        self._uia_executor = UIAExecutor()
        self._browser_executor = BrowserExecutor()
        self._ocr_fallback = OCRFallback()

        self._emergency_stop_callback: Optional[Callable[[], bool]] = None
        self._lock = threading.Lock()

        logger.info_data(
            "Action executor initialized",
            {
                "uia": self._uia_executor.is_available(),
                "browser": self._browser_executor.is_available(),
                "ocr": self._ocr_fallback.is_available(),
            },
        )

    def set_emergency_stop_callback(self, callback: Callable[[], bool]) -> None:
        """Set callback to check for emergency stop during execution."""
        self._emergency_stop_callback = callback

    def execute(
        self,
        action_type: str,
        target: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> ActionResult:
        """
        Execute an action with automatic fallback.

        Args:
            action_type: Type of action (click, type, select, etc.)
            target: Target element or locator
            params: Additional parameters

        Returns:
            ActionResult with execution details
        """
        params = params or {}

        logger.info_data(
            "Executing action",
            {
                "action_type": action_type,
                "target": target,
            },
        )

        # Check for emergency stop
        if self._emergency_stop_callback and self._emergency_stop_callback():
            logger.warning("Action execution aborted - emergency stop")
            return ActionResult(
                success=False,
                error="Emergency stop triggered",
            )

        # Determine execution method based on target
        if self._is_browser_target(target):
            return self._execute_browser(action_type, target, params)
        else:
            return self._execute_uia(action_type, target, params)

    def _is_browser_target(self, target: str) -> bool:
        """Check if target is a browser element."""
        # Simple heuristic: if target contains URL or browser-related terms
        browser_keywords = ["http://", "https://", "chrome", "firefox", "edge", "browser"]
        target_lower = target.lower()
        return any(kw in target_lower for kw in browser_keywords)

    def _execute_uia(
        self,
        action_type: str,
        target: str,
        params: Dict[str, Any],
    ) -> ActionResult:
        """Execute action using UIA."""
        if not self._uia_executor.is_available():
            logger.warning("UIA not available, trying OCR fallback")
            return self._execute_ocr_fallback(action_type, target, params)

        try:
            result = self._uia_executor.execute(action_type, target, params)
            return result
        except Exception as e:
            logger.error_data("UIA execution failed", {"error": str(e)})
            # Fallback to OCR
            return self._execute_ocr_fallback(action_type, target, params)

    def _execute_browser(
        self,
        action_type: str,
        target: str,
        params: Dict[str, Any],
    ) -> ActionResult:
        """Execute action using browser DOM automation."""
        if not self._browser_executor.is_available():
            logger.warning("Browser automation not available, trying OCR fallback")
            return self._execute_ocr_fallback(action_type, target, params)

        try:
            result = self._browser_executor.execute(action_type, target, params)
            return result
        except Exception as e:
            logger.error_data("Browser execution failed", {"error": str(e)})
            # Fallback to OCR
            return self._execute_ocr_fallback(action_type, target, params)

    def _execute_ocr_fallback(
        self,
        action_type: str,
        target: str,
        params: Dict[str, Any],
    ) -> ActionResult:
        """Execute action using OCR as last resort."""
        # Check if action type is supported by OCR fallback
        supported_ocr_actions = ["click", "find_text", "screenshot", "get_text"]
        if action_type not in supported_ocr_actions:
            logger.error_data(
                "OCR fallback does not support this action type",
                {"action_type": action_type, "supported": supported_ocr_actions}
            )
            return ActionResult(
                success=False,
                error=f"Action '{action_type}' not supported in OCR fallback mode. Supported: {supported_ocr_actions}",
                method_used="ocr_fallback_rejected"
            )
        
        if not self._ocr_fallback.is_available():
            logger.error("OCR fallback not available, action failed")
            return ActionResult(
                success=False,
                error="All execution methods failed",
            )

        try:
            result = self._ocr_fallback.execute(action_type, target, params)
            return result
        except Exception as e:
            logger.error_data("OCR fallback failed", {"error": str(e)})
            return ActionResult(
                success=False,
                error=f"All execution methods failed: {str(e)}",
            )

    def click(self, target: str) -> ActionResult:
        """Click on target element."""
        return self.execute("click", target)

    def type_text(self, target: str, text: str) -> ActionResult:
        """Type text into target element."""
        return self.execute("type", target, {"text": text})

    def select(self, target: str, value: str) -> ActionResult:
        """Select option from dropdown."""
        return self.execute("select", target, {"value": value})

    def get_text(self, target: str) -> ActionResult:
        """Get text from target element."""
        return self.execute("get_text", target)

    def wait_for_element(self, target: str, timeout: float = 10.0) -> ActionResult:
        """Wait for element to appear."""
        return self.execute("wait", target, {"timeout": timeout})

    def is_available(self) -> bool:
        """Check if any execution method is available."""
        return (
            self._uia_executor.is_available()
            or self._browser_executor.is_available()
            or self._ocr_fallback.is_available()
        )
