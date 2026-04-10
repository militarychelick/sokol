"""
Permission handler - Request and process user confirmations
"""

from __future__ import annotations

from typing import Callable

from ..core.agent import Intent
from ..core.constants import SafetyLevel


class PermissionHandler:
    """
    Handles permission requests for caution and dangerous actions.
    
    Coordinates with voice/text layers to get user confirmation.
    """
    
    def __init__(self) -> None:
        self._confirmation_callback: Callable[[str], bool] | None = None
        self._permission_callback: Callable[[str], bool] | None = None
    
    def set_confirmation_callback(
        self,
        callback: Callable[[str], bool],
    ) -> None:
        """Set callback for confirmation requests (CAUTION level)."""
        self._confirmation_callback = callback
    
    def set_permission_callback(
        self,
        callback: Callable[[str], bool],
    ) -> None:
        """Set callback for permission requests (DANGEROUS level)."""
        self._permission_callback = callback
    
    async def request_confirmation(
        self,
        intent: Intent,
        prompt: str,
    ) -> bool:
        """
        Request user confirmation for caution-level action.
        
        Args:
            intent: The action requiring confirmation
            prompt: Confirmation prompt text
        
        Returns:
            True if user confirmed, False otherwise
        """
        if self._confirmation_callback is None:
            # Default: require explicit "yes"
            return False
        
        return await self._confirmation_callback(prompt)
    
    async def request_permission(
        self,
        intent: Intent,
        prompt: str,
    ) -> bool:
        """
        Request explicit permission for dangerous action.
        
        Args:
            intent: The action requiring permission
            prompt: Permission prompt text
        
        Returns:
            True if user granted permission, False otherwise
        """
        if self._permission_callback is None:
            # Default: deny dangerous actions
            return False
        
        return await self._permission_callback(prompt)
    
    def is_affirmative(self, response: str) -> bool:
        """
        Check if response is affirmative.
        
        Args:
            response: User response text
        
        Returns:
            True if response means "yes"
        """
        affirmative = {
            "yes", "yeah", "yep", "yup", "sure", "ok", "okay",
            "go ahead", "proceed", "do it", "confirm",
            "da", "davai", "konechno",  # Russian
        }
        return response.lower().strip() in affirmative
    
    def is_negative(self, response: str) -> bool:
        """
        Check if response is negative.
        
        Args:
            response: User response text
        
        Returns:
            True if response means "no"
        """
        negative = {
            "no", "nope", "nah", "cancel", "abort", "stop",
            "net", "otmena",  # Russian
        }
        return response.lower().strip() in negative
