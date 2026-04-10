"""Window manager tool - manage windows."""

from typing import Any

from sokol.core.types import RiskLevel
from sokol.observability.debug import dry_run_mode
from sokol.observability.logging import get_logger
from sokol.tools.base import Tool, ToolResult

logger = get_logger("sokol.tools.builtin.window_manager")

# Import pywinauto conditionally
try:
    import pywinauto
    from pywinauto import Desktop, findwindows

    PYWINAUTO_AVAILABLE = True
except ImportError:
    PYWINAUTO_AVAILABLE = False
    logger.warning("pywinauto not available, window management limited")


class WindowManager(Tool[dict[str, Any]]):
    """Manage Windows windows."""

    @property
    def name(self) -> str:
        return "window_manager"

    @property
    def description(self) -> str:
        return "Manage windows: minimize, maximize, close, list, focus"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.WRITE  # Modifies window state

    @property
    def undo_support(self) -> bool:
        return True

    @property
    def examples(self) -> list[str]:
        return [
            "list windows",
            "minimize notepad",
            "maximize chrome",
            "close calculator",
        ]

    def get_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "minimize", "maximize", "restore", "close", "focus"],
                    "description": "Action to perform",
                },
                "window_title": {
                    "type": "string",
                    "description": "Window title or partial match",
                },
            },
            "required": ["action"],
        }

    def execute(
        self,
        action: str,
        window_title: str | None = None,
    ) -> ToolResult[dict[str, Any]]:
        """Execute window action."""
        if not PYWINAUTO_AVAILABLE:
            return ToolResult(
                success=False,
                error="pywinauto not available",
                risk_level=self.risk_level,
            )

        # Dry run mode
        if dry_run_mode():
            logger.info(f"DRY RUN: Would {action} window")
            return ToolResult(
                success=True,
                data={"action": action, "window_title": window_title, "dry_run": True},
                risk_level=self.risk_level,
            )

        try:
            if action == "list":
                return self._list_windows()

            if not window_title:
                return ToolResult(
                    success=False,
                    error=f"Window title required for action: {action}",
                    risk_level=self.risk_level,
                )

            return self._window_action(action, window_title)

        except Exception as e:
            logger.error_data("Window action failed", {"error": str(e)})
            return ToolResult(
                success=False,
                error=str(e),
                risk_level=self.risk_level,
            )

    def _list_windows(self) -> ToolResult[dict[str, Any]]:
        """List all visible windows."""
        desktop = Desktop(backend="uia")
        windows = desktop.windows()

        window_list = []
        for w in windows:
            try:
                title = w.window_text()
                if title:  # Only windows with titles
                    window_list.append({
                        "title": title,
                        "handle": w.handle,
                        "visible": w.is_visible(),
                    })
            except Exception:
                pass

        return ToolResult(
            success=True,
            data={"windows": window_list, "count": len(window_list)},
            risk_level=RiskLevel.READ,
        )

    def _window_action(self, action: str, window_title: str) -> ToolResult[dict[str, Any]]:
        """Perform action on a window."""
        desktop = Desktop(backend="uia")

        # Find window by title
        try:
            window = desktop.window(title_re=f".*{window_title}.*")
            if not window.exists():
                return ToolResult(
                    success=False,
                    error=f"Window not found: {window_title}",
                    risk_level=self.risk_level,
                )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Error finding window: {str(e)}",
                risk_level=self.risk_level,
            )

        # Store undo info
        original_state = {
            "title": window.window_text(),
            "minimized": window.is_minimized(),
            "maximized": window.is_maximized(),
        }
        self._undo_info = {"action": action, "original_state": original_state}

        # Perform action
        if action == "minimize":
            window.minimize()
        elif action == "maximize":
            window.maximize()
        elif action == "restore":
            window.restore()
        elif action == "close":
            window.close()
        elif action == "focus":
            window.set_focus()

        return ToolResult(
            success=True,
            data={
                "action": action,
                "window_title": original_state["title"],
            },
            undo_available=True,
            undo_info=self._undo_info,
            risk_level=self.risk_level,
        )

    def undo(self, undo_info: dict[str, Any] | None = None) -> ToolResult[bool]:
        """Undo window action."""
        if not PYWINAUTO_AVAILABLE:
            return ToolResult(success=False, error="pywinauto not available")

        undo_info = undo_info or self._undo_info
        if not undo_info:
            return ToolResult(success=False, error="No undo info")

        action = undo_info.get("action")
        original_state = undo_info.get("original_state", {})

        try:
            desktop = Desktop(backend="uia")
            window = desktop.window(title=original_state.get("title", ""))

            if not window.exists():
                return ToolResult(success=False, error="Window no longer exists")

            # Restore original state
            if action == "minimize" and original_state.get("minimized") is False:
                window.restore()
            elif action == "maximize" and original_state.get("maximized") is False:
                window.restore()
            elif action == "close":
                # Can't undo close
                return ToolResult(success=False, error="Cannot undo window close")

            return ToolResult(success=True, data=True)

        except Exception as e:
            return ToolResult(success=False, error=str(e))
