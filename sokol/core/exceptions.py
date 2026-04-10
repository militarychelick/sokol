"""
Custom exceptions for Sokol v2
"""


class SokolError(Exception):
    """Base exception for all Sokol errors."""
    
    def __init__(self, message: str, details: str | None = None) -> None:
        self.message = message
        self.details = details
        super().__init__(self.message)
    
    def __str__(self) -> str:
        if self.details:
            return f"{self.message}: {self.details}"
        return self.message


class ConfigurationError(SokolError):
    """Configuration loading/validation error."""
    pass


class VoiceError(SokolError):
    """Voice input/output error."""
    pass


class IntentError(SokolError):
    """Intent parsing/classification error."""
    pass


class ExecutionError(SokolError):
    """Action execution error."""
    pass


class SafetyError(SokolError):
    """Safety policy violation."""
    
    def __init__(
        self,
        message: str,
        action: str | None = None,
        reason: str | None = None,
    ) -> None:
        self.action = action
        self.reason = reason
        details = f"Action: {action}, Reason: {reason}" if action else reason
        super().__init__(message, details)


class MemoryError(SokolError):
    """Memory storage/retrieval error."""
    pass


class LLMError(SokolError):
    """LLM communication error."""
    
    def __init__(
        self,
        message: str,
        provider: str | None = None,
        model: str | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        details = f"Provider: {provider}, Model: {model}" if provider else None
        super().__init__(message, details)


class PermissionDeniedError(SafetyError):
    """User denied permission for action."""
    
    def __init__(self, action: str) -> None:
        super().__init__(
            "Permission denied by user",
            action=action,
            reason="user_rejected",
        )


class RestrictedActionError(SafetyError):
    """Action is hard-restricted and cannot be performed."""
    
    def __init__(self, action: str, reason: str) -> None:
        super().__init__(
            "Action is restricted and cannot be performed",
            action=action,
            reason=reason,
        )
