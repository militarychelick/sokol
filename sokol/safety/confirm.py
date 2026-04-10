"""Confirmation flow for dangerous actions."""

import asyncio
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable

from sokol.core.types import ConfirmationRequest, ConfirmationResponse, RiskLevel
from sokol.observability.logging import get_logger

logger = get_logger("sokol.safety.confirm")


class ConfirmationTimeout(Exception):
    """Raised when confirmation request times out."""

    def __init__(self, request_id: str, timeout: float) -> None:
        self.request_id = request_id
        self.timeout = timeout
        super().__init__(f"Confirmation {request_id} timed out after {timeout}s")


class ConfirmationManager:
    """Manages confirmation requests and responses."""

    def __init__(self, default_timeout: float = 60.0) -> None:
        self._default_timeout = default_timeout
        self._pending: dict[str, ConfirmationRequest] = {}
        self._responses: dict[str, ConfirmationResponse] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=1)

        # Callback for UI
        self._on_request_callback: Callable[[ConfirmationRequest], None] | None = None

    def set_callback(self, callback: Callable[[ConfirmationRequest], None]) -> None:
        """Set callback for UI notification."""
        self._on_request_callback = callback

    def create_request(
        self,
        tool_name: str,
        action_description: str,
        risk_level: RiskLevel,
        parameters: dict[str, Any],
        consequences: str,
        timeout: float | None = None,
    ) -> ConfirmationRequest:
        """Create a new confirmation request."""
        request = ConfirmationRequest(
            tool_name=tool_name,
            action_description=action_description,
            risk_level=risk_level,
            parameters=parameters,
            consequences=consequences,
            timeout=timeout or self._default_timeout,
        )

        with self._lock:
            self._pending[request.id] = request

        logger.info_data(
            "Confirmation request created",
            {
                "request_id": request.id,
                "tool": tool_name,
                "risk": risk_level.value,
                "timeout": request.timeout,
            },
        )

        # Notify UI
        if self._on_request_callback:
            self._on_request_callback(request)

        return request

    def respond(self, request_id: str, approved: bool, reason: str | None = None) -> bool:
        """Respond to a confirmation request."""
        with self._lock:
            request = self._pending.get(request_id)
            if not request:
                logger.warning_data(
                    "Confirmation response for unknown request",
                    {"request_id": request_id},
                )
                return False

            response = ConfirmationResponse(
                request_id=request_id,
                approved=approved,
                reason=reason,
            )

            self._responses[request_id] = response
            del self._pending[request_id]

        logger.info_data(
            "Confirmation response received",
            {
                "request_id": request_id,
                "approved": approved,
                "reason": reason,
            },
        )

        return True

    def wait_for_response(
        self,
        request_id: str,
        timeout: float | None = None,
    ) -> ConfirmationResponse:
        """
        Wait for response to a confirmation request.

        Blocks until response is received or timeout.
        """
        request = self._pending.get(request_id)
        if not request:
            raise ValueError(f"Request {request_id} not found")

        timeout = timeout or request.timeout
        elapsed = 0.0
        check_interval = 0.1

        while elapsed < timeout:
            with self._lock:
                if request_id in self._responses:
                    return self._responses[request_id]

            # Check for cancellation
            if request_id not in self._pending:
                raise ConfirmationTimeout(request_id, elapsed)

            threading.Event().wait(check_interval)
            elapsed += check_interval

        # Timeout
        with self._lock:
            if request_id in self._pending:
                del self._pending[request_id]

        raise ConfirmationTimeout(request_id, timeout)

    async def wait_for_response_async(
        self,
        request_id: str,
        timeout: float | None = None,
    ) -> ConfirmationResponse:
        """Async version of wait_for_response."""
        request = self._pending.get(request_id)
        if not request:
            raise ValueError(f"Request {request_id} not found")

        timeout = timeout or request.timeout
        elapsed = 0.0
        check_interval = 0.1

        while elapsed < timeout:
            with self._lock:
                if request_id in self._responses:
                    return self._responses[request_id]

            if request_id not in self._pending:
                raise ConfirmationTimeout(request_id, elapsed)

            await asyncio.sleep(check_interval)
            elapsed += check_interval

        with self._lock:
            if request_id in self._pending:
                del self._pending[request_id]

        raise ConfirmationTimeout(request_id, timeout)

    def get_pending(self) -> list[ConfirmationRequest]:
        """Get all pending confirmation requests."""
        with self._lock:
            return list(self._pending.values())

    def cancel(self, request_id: str) -> bool:
        """Cancel a pending confirmation request."""
        with self._lock:
            if request_id in self._pending:
                del self._pending[request_id]
                logger.info_data(
                    "Confirmation request cancelled",
                    {"request_id": request_id},
                )
                return True
            return False

    def cancel_all(self) -> int:
        """Cancel all pending confirmation requests."""
        with self._lock:
            count = len(self._pending)
            self._pending.clear()
            if count > 0:
                logger.info_data(
                    "All confirmation requests cancelled",
                    {"count": count},
                )
            return count

    def is_pending(self, request_id: str) -> bool:
        """Check if a request is still pending."""
        return request_id in self._pending

    def get_response(self, request_id: str) -> ConfirmationResponse | None:
        """Get response if available."""
        return self._responses.get(request_id)

    def cleanup(self, max_age_seconds: float = 300.0) -> int:
        """Clean up old responses."""
        # For now, just clear all responses
        with self._lock:
            count = len(self._responses)
            self._responses.clear()
            return count

    def shutdown(self) -> None:
        """Shutdown confirmation manager."""
        self.cancel_all()
        self._executor.shutdown(wait=False)
