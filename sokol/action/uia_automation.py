"""UIA automation - Windows automation using UIA."""

from typing import Optional, Dict, Any
import time

from sokol.observability.logging import get_logger

logger = get_logger("sokol.action.uia_automation")


class UIAExecutor:
    """
    Windows automation using UI Automation (UIA).

    Primary method for Windows automation.
    """

    def __init__(self) -> None:
        self._available = self._check_availability()
        logger.info_data(
            "UIA executor initialized",
            {"available": self._available},
        )

    def _check_availability(self) -> bool:
        """Check if UIA is available."""
        try:
            import pywinauto
            return True
        except ImportError:
            return False

    def is_available(self) -> bool:
        """Check if UIA executor is available."""
        return self._available

    def execute(
        self,
        action_type: str,
        target: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute UIA action.

        Args:
            action_type: Type of action (click, type, select, etc.)
            target: Target element (window title, control text, etc.)
            params: Additional parameters

        Returns:
            Dict with success status and result data
        """
        params = params or {}

        try:
            if action_type == "click":
                return self._click(target, params)
            elif action_type == "type":
                return self._type(target, params)
            elif action_type == "select":
                return self._select(target, params)
            elif action_type == "get_text":
                return self._get_text(target, params)
            elif action_type == "wait":
                return self._wait(target, params)
            elif action_type == "focus":
                return self._focus(target, params)
            else:
                return {
                    "success": False,
                    "error": f"Unknown action type: {action_type}",
                }
        except Exception as e:
            logger.error_data(
                "UIA execution failed",
                {"action": action_type, "target": target, "error": str(e)},
            )
            return {
                "success": False,
                "error": str(e),
            }

    def _click(self, target: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Click on target element."""
        from pywinauto import Desktop

        desktop = Desktop(backend="uia")

        # Try to find element by text
        window = desktop.window(title_re=f".*{target}.*")
        if window.exists():
            window.click()
            return {"success": True, "method": "window_click"}

        # Try to find as control
        for win in desktop.windows():
            try:
                control = win.child_window(title=target)
                if control.exists():
                    control.click()
                    return {"success": True, "method": "control_click"}
            except Exception:
                pass

        return {"success": False, "error": f"Element not found: {target}"}

    def _type(self, target: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Type text into target element."""
        text = params.get("text", "")

        from pywinauto import Desktop

        desktop = Desktop(backend="uia")

        # Try to find window
        window = desktop.window(title_re=f".*{target}.*")
        if window.exists():
            window.set_focus()
            window.type_keys(text)
            return {"success": True, "method": "window_type"}

        # Try to find as control
        for win in desktop.windows():
            try:
                control = win.child_window(title=target, control_type="Edit")
                if control.exists():
                    control.set_focus()
                    control.type_keys(text)
                    return {"success": True, "method": "control_type"}
            except Exception:
                pass

        return {"success": False, "error": f"Element not found: {target}"}

    def _select(self, target: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Select option from dropdown."""
        value = params.get("value", "")

        from pywinauto import Desktop

        desktop = Desktop(backend="uia")

        # Find dropdown by text
        for win in desktop.windows():
            try:
                control = win.child_window(title=target, control_type="ComboBox")
                if control.exists():
                    control.select(value)
                    return {"success": True, "method": "combo_select"}
            except Exception:
                pass

        return {"success": False, "error": f"Dropdown not found: {target}"}

    def _get_text(self, target: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get text from target element."""
        from pywinauto import Desktop

        desktop = Desktop(backend="uia")

        # Try to find window
        window = desktop.window(title_re=f".*{target}.*")
        if window.exists():
            text = window.window_text()
            return {"success": True, "text": text, "method": "window_text"}

        # Try to find as control
        for win in desktop.windows():
            try:
                control = win.child_window(title=target)
                if control.exists():
                    text = control.window_text()
                    return {"success": True, "text": text, "method": "control_text"}
            except Exception:
                pass

        return {"success": False, "error": f"Element not found: {target}"}

    def _wait(self, target: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Wait for element to appear."""
        timeout = params.get("timeout", 10.0)
        start_time = time.time()

        from pywinauto import Desktop

        desktop = Desktop(backend="uia")

        while time.time() - start_time < timeout:
            window = desktop.window(title_re=f".*{target}.*")
            if window.exists():
                return {"success": True, "elapsed": time.time() - start_time}
            time.sleep(0.5)

        return {"success": False, "error": f"Element not found within timeout: {target}"}

    def _focus(self, target: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Focus on target element."""
        from pywinauto import Desktop

        desktop = Desktop(backend="uia")

        window = desktop.window(title_re=f".*{target}.*")
        if window.exists():
            window.set_focus()
            return {"success": True, "method": "window_focus"}

        return {"success": False, "error": f"Element not found: {target}"}
