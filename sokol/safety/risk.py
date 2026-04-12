"""Risk assessment for tools and actions."""

import re
from typing import Any

from sokol.core.config import get_config
from sokol.core.types import RiskLevel, ToolSchema
from sokol.observability.logging import get_logger

logger = get_logger("sokol.safety.risk")


# Patterns that indicate dangerous operations
DANGEROUS_PATTERNS = [
    r"\bdelete\b",
    r"\bremove\b",
    r"\brm\b",  # Unix rm command
    r"\bwipe\b",
    r"\bdestroy\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\brestart\b",
    r"\bkill\b",
    r"\bterminate\b",
    r"\bformat\b",
    r"\bdrop\b",  # SQL drop
    r"\btruncate\b",
    r"\boverwrite\b",
    r"\bmodify\b.*\bsystem\b",
    r"\bmodify\b.*\bregistry\b",
    r"\bmodify\b.*\bconfig\b",
    r"\bexec\b",  # Code execution
    r"\beval\b",  # Code evaluation
    r"\bexecute\b.*\bcode\b",
    r"\brun\b.*\bscript\b",
    r"\bsudo\b",  # Privilege escalation
    r"\badmin\b.*\bmode\b",
    r"\belevated\b.*\bprivileges\b",
    r"\bpassword\b",  # Credential exposure
    r"\bcredential\b",
    r"\bsecret\b",
    r"\bapi[_-]?key\b",
    r"\btoken\b",
    r"\bfactory\b.*\breset\b",
    r"\buninstall\b",
]

# Safe operation patterns (override dangerous patterns)
SAFE_PATTERNS = [
    r"\bread\b",
    r"\blist\b",
    r"\bshow\b",
    r"\bget\b",
    r"\bquery\b",
    r"\bfind\b",
    r"\bsearch\b",
    r"\bopen\b",  # Opening apps is usually safe
]


class RiskAssessor:
    """Assesses risk level of tools and actions."""

    def __init__(self) -> None:
        self._config = get_config()
        self._dangerous_tools = set(self._config.safety.dangerous_tools)
        self._dangerous_patterns = [re.compile(p, re.IGNORECASE) for p in DANGEROUS_PATTERNS]
        self._safe_patterns = [re.compile(p, re.IGNORECASE) for p in SAFE_PATTERNS]

    def assess_tool(self, tool: ToolSchema) -> RiskLevel:
        """Assess risk level of a tool from its schema."""
        # Trust the tool's declared risk level first
        if tool.risk_level == RiskLevel.DANGEROUS:
            return RiskLevel.DANGEROUS
        if tool.risk_level == RiskLevel.WRITE:
            return RiskLevel.WRITE
        return RiskLevel.READ

    def assess_action(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        description: str | None = None,
    ) -> RiskLevel:
        """Assess risk level of a specific action."""
        # Check if tool is in dangerous list
        if tool_name in self._dangerous_tools:
            logger.info_data(
                "Tool in dangerous list",
                {"tool": tool_name, "risk": "dangerous"},
            )
            return RiskLevel.DANGEROUS

        # Check description for dangerous patterns
        text_to_check = description or ""
        if parameters:
            text_to_check += " " + " ".join(str(v) for v in parameters.values())

        # First check for safe patterns
        for pattern in self._safe_patterns:
            if pattern.search(text_to_check):
                # Safe pattern found, but still check for dangerous
                break

        # Check for dangerous patterns
        for pattern in self._dangerous_patterns:
            if pattern.search(text_to_check):
                logger.info_data(
                    "Dangerous pattern detected",
                    {"tool": tool_name, "pattern": pattern.pattern, "text": text_to_check[:100]},
                )
                return RiskLevel.DANGEROUS

        # Check parameters for dangerous indicators
        if self._has_dangerous_params(parameters):
            return RiskLevel.DANGEROUS

        # Check for write operations
        if self._is_write_operation(tool_name, parameters):
            return RiskLevel.WRITE

        return RiskLevel.READ

    def _has_dangerous_params(self, parameters: dict[str, Any]) -> bool:
        """Check if parameters indicate dangerous operation."""
        dangerous_keys = ["delete", "remove", "force", "overwrite", "kill"]
        for key in dangerous_keys:
            if key in parameters.lower() if isinstance(parameters, str) else key in parameters:
                return True
        return False

    def _is_write_operation(self, tool_name: str, parameters: dict[str, Any]) -> bool:
        """Check if operation is a write operation."""
        write_indicators = [
            "write" in tool_name.lower(),
            "save" in tool_name.lower(),
            "create" in tool_name.lower(),
            "update" in tool_name.lower(),
            "modify" in tool_name.lower(),
            "mode" in parameters and parameters.get("mode") in ("w", "write", "a", "append"),
        ]
        return any(write_indicators)

    def requires_confirmation(self, risk_level: RiskLevel) -> bool:
        """Check if risk level requires confirmation."""
        if not self._config.safety.confirm_dangerous:
            return False

        return risk_level == RiskLevel.DANGEROUS

    def get_risk_description(self, risk_level: RiskLevel) -> str:
        """Get human-readable risk description."""
        descriptions = {
            RiskLevel.READ: "Read-only operation - safe to execute",
            RiskLevel.WRITE: "Write operation - may modify data",
            RiskLevel.DANGEROUS: "Dangerous operation - irreversible or high impact",
        }
        return descriptions.get(risk_level, "Unknown risk level")


def assess_tool_risk(
    tool_name: str,
    parameters: dict[str, Any],
    description: str | None = None,
) -> RiskLevel:
    """Convenience function to assess tool risk."""
    assessor = RiskAssessor()
    return assessor.assess_action(tool_name, parameters, description)
