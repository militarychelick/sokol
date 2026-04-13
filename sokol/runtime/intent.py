"""Rule-based intent handler for LLM-free mode."""

import re
from typing import Any
from dataclasses import dataclass

from sokol.observability.logging import get_logger
from sokol.runtime.result import Result
from sokol.tools.registry import get_registry
from sokol.core.types import RiskLevel

logger = get_logger("sokol.runtime.intent")


@dataclass
class Intent:
    """Parsed intent from user input."""

    action: str
    tool: str | None = None
    args: dict[str, Any] | None = None
    confidence: float = 1.0


class RuleBasedIntentHandler:
    """
    Rule-based intent handler for LLM-free mode.

    Supports basic commands without LLM:
    - open app
    - system info
    - file operations (safe subset)
    """

    def __init__(self) -> None:
        self._tool_registry = get_registry()
        self._patterns = self._build_patterns()

    def _build_patterns(self) -> list[dict[str, Any]]:
        """Build regex patterns for intent recognition."""
        return [
            # Open app
            {
                "pattern": r"(?:open|launch|start)\s+(?:the\s+)?(?:app\s+)?(.+)",
                "action": "open_app",
                "tool": "app_launcher",
                "arg_key": "app_name",
            },
            # System info
            {
                "pattern": r"(?:system\s+)?info|what(?:'s|\s+is)\s+my\s+system",
                "action": "system_info",
                "tool": "system_info",
                "arg_key": None,
            },
            # CPU info
            {
                "pattern": r"(?:cpu|processor)\s+info",
                "action": "cpu_info",
                "tool": "system_info",
                "arg_key": None,
            },
            # Memory info
            {
                "pattern": r"(?:memory|ram)\s+info",
                "action": "memory_info",
                "tool": "system_info",
                "arg_key": None,
            },
            # Disk info
            {
                "pattern": r"(?:disk|storage)\s+info",
                "action": "disk_info",
                "tool": "system_info",
                "arg_key": None,
            },
            # List files (safe)
            {
                "pattern": r"(?:list|show)\s+(?:files?|contents?)\s+(?:in\s+)?(.+)",
                "action": "list_files",
                "tool": "file_ops",
                "arg_key": "path",
            },
            # Read file (safe)
            {
                "pattern": r"(?:read|show|cat)\s+(?:file\s+)?(.+)",
                "action": "read_file",
                "tool": "file_ops",
                "arg_key": "path",
            },
            # List windows
            {
                "pattern": r"(?:list|show)\s+(?:windows?|apps?)",
                "action": "list_windows",
                "tool": "window_manager",
                "arg_key": None,
            },
            # Help
            {
                "pattern": r"(?:help|what\s+can\s+you\s+do)",
                "action": "help",
                "tool": None,
                "arg_key": None,
            },
        ]

    def parse_intent(self, text: str) -> Result[Intent]:
        """
        Parse intent from user text.

        Returns default Intent if no intent matches.
        """
        text = text.strip().lower()

        for pattern_info in self._patterns:
            match = re.search(pattern_info["pattern"], text, re.IGNORECASE)
            if match:
                action = pattern_info["action"]
                tool = pattern_info["tool"]
                arg_key = pattern_info["arg_key"]

                args = {}
                if arg_key and match.groups():
                    args[arg_key] = match.group(1).strip()

                # Special handling for system info
                if action == "cpu_info":
                    args = {"info_type": "cpu"}
                elif action == "memory_info":
                    args = {"info_type": "memory"}
                elif action == "disk_info":
                    args = {"info_type": "disk"}
                elif action == "system_info":
                    args = {"info_type": "basic"}

                logger.info_data(
                    "Intent matched",
                    {"action": action, "tool": tool, "args": str(args)},
                )

                return Result.ok(Intent(action=action, tool=tool, args=args))

        # PHASE 2 FIX: Return default Intent instead of None (no None runtime)
        return Result.ok(Intent(action="no_action", tool=None, args={}))

    def execute_intent(self, intent: Intent) -> Result[tuple[bool, str]]:
        """
        Execute intent using tool registry.

        Returns (success, result_text).
        """
        if not intent.tool:
            return Result.ok((False, f"Cannot execute intent: {intent.action}"))

        try:
            result = self._tool_registry.execute(intent.tool, intent.args or {})

            if result.is_ok():
                tool_result = result.unwrap()
                if tool_result.success:
                    return Result.ok((True, self._format_result(intent.action, tool_result.data)))
                else:
                    return Result.ok((False, f"Execution failed: {tool_result.error}"))
            else:
                return Result.ok((False, f"Execution failed: {result.error()}"))

        except Exception as e:
            logger.error_data("Intent execution failed", {"error": str(e)})
            return Result.ok((False, f"Error: {str(e)}"))

    def propose_action(self, intent: Intent) -> Result[dict[str, Any]]:
        """
        Propose action from intent (does NOT execute).

        Returns action proposal dict for safety validation.
        """
        if not intent.tool:
            return Result.ok({
                "action_type": "text_response",
                "text": f"Cannot execute intent: {intent.action}",
            })

        return Result.ok({
            "action_type": "tool_call",
            "tool": intent.tool,
            "args": intent.args or {},
            "source": "rule_based",
        })

    def _format_result(self, action: str, data: Any) -> str:
        """Format tool result for user."""
        if action == "system_info":
            if isinstance(data, dict):
                return f"System: {data.get('system', 'Unknown')}, " \
                       f"CPU: {data.get('cpu', 'Unknown')}, " \
                       f"Memory: {data.get('memory', 'Unknown')}"
            return str(data)

        elif action == "list_windows":
            if isinstance(data, list):
                return "Windows: " + ", ".join(data[:5])
            return str(data)

        elif action in ["list_files", "read_file"]:
            if isinstance(data, str):
                return data
            return str(data)

        elif action == "open_app":
            return f"Opened: {data}"

        return str(data)

    def get_help(self) -> str:
        """Get help text for available commands."""
        commands = [
            "open [app name] - Launch application",
            "system info - Show system information",
            "cpu info - Show CPU information",
            "memory info - Show memory information",
            "disk info - Show disk information",
            "list files [path] - List files in directory",
            "read file [path] - Read file contents",
            "list windows - Show open windows",
            "help - Show this help",
        ]
        return "Available commands:\n" + "\n".join(f"  - {c}" for c in commands)
