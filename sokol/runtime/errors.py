"""Structured error model for SOKOL runtime.

This module provides a structured, diagnostic error model that:
- Categorizes errors by type and severity
- Preserves error context and origin
- Separates logging from user-facing messages
- Prevents raw exception leakage
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ErrorCategory(str, Enum):
    """High-level error categories for diagnostic purposes."""

    ROUTING = "routing"  # Intent routing failures
    TOOL_EXECUTION = "tool_execution"  # Tool execution failures
    MEMORY = "memory"  # Memory read/write failures
    VALIDATION = "validation"  # Input/safety validation failures
    INFRASTRUCTURE = "infrastructure"  # System/LLM/external failures
    TIMEOUT = "timeout"  # Operation timeout
    PERMISSION = "permission"  # Permission/confirmation failures
    UNKNOWN = "unknown"  # Unclassified errors


class ErrorSeverity(str, Enum):
    """Error severity levels."""

    CRITICAL = "critical"  # System failure, requires intervention
    HIGH = "high"  # Operation failed, user action may be needed
    MEDIUM = "medium"  # Partial failure, degraded functionality
    LOW = "low"  # Non-critical, informational


@dataclass(frozen=True)
class ErrorInfo:
    """Structured error information.

    This provides diagnostic context while preventing raw exception leakage
    to user-facing output.
    """

    category: ErrorCategory
    severity: ErrorSeverity
    user_message: str  # Safe, user-friendly message
    technical_message: str  # More detailed technical message
    error_code: str  # Machine-readable error code
    context: dict[str, Any] = field(default_factory=dict)
    recoverable: bool = True  # Whether the error is recoverable

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/serialization."""
        return {
            "category": self.category.value,
            "severity": self.severity.value,
            "user_message": self.user_message,
            "technical_message": self.technical_message,
            "error_code": self.error_code,
            "context": self.context,
            "recoverable": self.recoverable,
        }


class ErrorBuilder:
    """Builder for creating structured ErrorInfo objects."""

    @staticmethod
    def routing_failure(reason: str, context: Optional[dict] = None) -> ErrorInfo:
        """Create routing error."""
        return ErrorInfo(
            category=ErrorCategory.ROUTING,
            severity=ErrorSeverity.HIGH,
            user_message="Не удалось определить действие. Попробуйте переформулировать запрос.",
            technical_message=f"Routing failed: {reason}",
            error_code="ROUTING_001",
            context=context or {},
            recoverable=True,
        )

    @staticmethod
    def tool_execution_failure(tool_name: str, reason: str, context: Optional[dict] = None) -> ErrorInfo:
        """Create tool execution error."""
        return ErrorInfo(
            category=ErrorCategory.TOOL_EXECUTION,
            severity=ErrorSeverity.HIGH,
            user_message=f"Ошибка выполнения инструмента: {tool_name}",
            technical_message=f"Tool execution failed for {tool_name}: {reason}",
            error_code="TOOL_001",
            context=context or {},
            recoverable=True,
        )

    @staticmethod
    def memory_failure(operation: str, reason: str, context: Optional[dict] = None) -> ErrorInfo:
        """Create memory error."""
        return ErrorInfo(
            category=ErrorCategory.MEMORY,
            severity=ErrorSeverity.MEDIUM,
            user_message="Ошибка работы с памятью. Контекст может быть неполным.",
            technical_message=f"Memory {operation} failed: {reason}",
            error_code="MEMORY_001",
            context=context or {},
            recoverable=True,
        )

    @staticmethod
    def validation_failure(reason: str, context: Optional[dict] = None) -> ErrorInfo:
        """Create validation error."""
        return ErrorInfo(
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.HIGH,
            user_message=f"Ошибка проверки: {reason}",
            technical_message=f"Validation failed: {reason}",
            error_code="VALIDATION_001",
            context=context or {},
            recoverable=True,
        )

    @staticmethod
    def infrastructure_failure(component: str, reason: str, context: Optional[dict] = None) -> ErrorInfo:
        """Create infrastructure error."""
        return ErrorInfo(
            category=ErrorCategory.INFRASTRUCTURE,
            severity=ErrorSeverity.CRITICAL,
            user_message="Системная ошибка. Попробуйте позже.",
            technical_message=f"Infrastructure failure in {component}: {reason}",
            error_code="INFRA_001",
            context=context or {},
            recoverable=False,
        )

    @staticmethod
    def timeout_failure(operation: str, timeout_seconds: float, context: Optional[dict] = None) -> ErrorInfo:
        """Create timeout error."""
        return ErrorInfo(
            category=ErrorCategory.TIMEOUT,
            severity=ErrorSeverity.HIGH,
            user_message=f"Превышено время ожидания: {operation}",
            technical_message=f"Timeout after {timeout_seconds}s for {operation}",
            error_code="TIMEOUT_001",
            context=context or {},
            recoverable=True,
        )

    @staticmethod
    def permission_failure(reason: str, context: Optional[dict] = None) -> ErrorInfo:
        """Create permission error."""
        return ErrorInfo(
            category=ErrorCategory.PERMISSION,
            severity=ErrorSeverity.HIGH,
            user_message=f"Ошибка прав доступа: {reason}",
            technical_message=f"Permission denied: {reason}",
            error_code="PERMISSION_001",
            context=context or {},
            recoverable=True,
        )

    @staticmethod
    def from_exception(
        exception: Exception,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        context: Optional[dict] = None,
    ) -> ErrorInfo:
        """Create error from exception with safe message extraction."""
        exception_type = type(exception).__name__
        exception_message = str(exception)

        # Safe user message - never include raw exception details
        user_message = "Произошла ошибка. Подробности записаны в лог."

        # Technical message includes exception type and safe message
        technical_message = f"{exception_type}: {exception_message}"

        return ErrorInfo(
            category=category,
            severity=ErrorSeverity.HIGH,
            user_message=user_message,
            technical_message=technical_message,
            error_code=f"{category.value.upper()}_EXCEPTION",
            context=context or {},
            recoverable=True,
        )
