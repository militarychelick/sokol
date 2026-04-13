"""
PHASE 8: Single Execution Contract

This module defines the unified Result[T] contract for all core runtime functions.
All functions in the SOKOL runtime must return Result[T] to ensure:
- Single return type contract
- Explicit success/failure
- Structured error handling
- Type-safe execution flow
"""

from dataclasses import dataclass
from typing import Generic, TypeVar, Optional
from sokol.runtime.errors import ErrorInfo

T = TypeVar('T')


@dataclass(frozen=True)
class Result(Generic[T]):
    """
    Unified execution result contract.
    
    INVARIANTS:
    - success=True → value must be non-None
    - success=False → error must be non-None
    - Never both None simultaneously
    - Frozen (immutable) for thread safety
    
    Usage:
        # Success case
        result = Result.ok(AgentResponse(...))
        
        # Error case
        result = Result.error(ErrorInfo(...))
        
        # Pattern matching
        if result.success:
            value = result.value
        else:
            error = result.error
    """
    success: bool
    value: Optional[T]
    error: Optional[ErrorInfo]
    
    def __post_init__(self) -> None:
        """Validate Result invariants."""
        if self.success and self.value is None:
            raise ValueError("Result.success=True requires non-None value")
        if not self.success and self.error is None:
            raise ValueError("Result.success=False requires non-None error")
    
    @staticmethod
    def ok(value: T) -> 'Result[T]':
        """
        Create a successful Result.
        
        Args:
            value: The successful result value
            
        Returns:
            Result with success=True and the provided value
        """
        return Result(success=True, value=value, error=None)
    
    @staticmethod
    def error(error: ErrorInfo) -> 'Result[T]':
        """
        Create a failed Result.
        
        Args:
            error: Structured error information
            
        Returns:
            Result with success=False and the provided error
        """
        return Result(success=False, value=None, error=error)
    
    def map(self, fn) -> 'Result':
        """
        Transform the value if success, propagate error if failure.
        
        Args:
            fn: Function to transform the value
            
        Returns:
            New Result with transformed value or propagated error
        """
        if self.success:
            try:
                return Result.ok(fn(self.value))
            except Exception as e:
                from sokol.runtime.errors import ErrorBuilder, ErrorCategory
                error = ErrorBuilder.from_exception(
                    e,
                    category=ErrorCategory.INFRASTRUCTURE,
                    context={"operation": "Result.map"}
                )
                return Result.error(error)
        return Result.error(self.error)
    
    def and_then(self, fn) -> 'Result':
        """
        Chain operations that return Result.
        
        Args:
            fn: Function that takes value and returns Result
            
        Returns:
            Result from fn if success, error if failure
        """
        if self.success:
            return fn(self.value)
        return Result.error(self.error)
    
    def unwrap_or(self, default: T) -> T:
        """
        Get value or default if error.
        
        Args:
            default: Default value if Result is error
            
        Returns:
            value if success, default otherwise
        """
        return self.value if self.success else default
    
    def is_ok(self) -> bool:
        """Check if Result is successful."""
        return self.success
    
    def is_error(self) -> bool:
        """Check if Result is error."""
        return not self.success


# Type aliases for common Result types
ResultAgentResponse = Result['AgentResponse']
ResultDict = Result[dict]
ResultBool = Result[bool]
ResultNone = Result[None]
