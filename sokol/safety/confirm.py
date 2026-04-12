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
        
        # P0: Event-driven wait mechanism (remove polling)
        self._wait_events: dict[str, threading.Event] = {}

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
            # P0: Create wait event for this request
            self._wait_events[request.id] = threading.Event()

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
            
            # P0: Signal wait event
            if request_id in self._wait_events:
                self._wait_events[request_id].set()

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

        Blocks until response is received or timeout (event-driven, no polling).
        """
        with self._lock:
            request = self._pending.get(request_id)
            wait_event = self._wait_events.get(request_id)
            if not request or not wait_event:
                raise ValueError(f"Request {request_id} not found or invalid")

        timeout = timeout or request.timeout
        
        # P0: Event-driven wait (no polling)
        if wait_event.wait(timeout=timeout):
            # Event was set, response is available
            with self._lock:
                if request_id in self._responses:
                    response = self._responses[request_id]
                    # Clean up wait event
                    if request_id in self._wait_events:
                        del self._wait_events[request_id]
                    return response
        
        # Timeout
        with self._lock:
            if request_id in self._pending:
                del self._pending[request_id]
            # Clean up wait event
            if request_id in self._wait_events:
                del self._wait_events[request_id]

        raise ConfirmationTimeout(request_id, timeout)

    async def wait_for_response_async(
        self,
        request_id: str,
        timeout: float | None = None,
    ) -> ConfirmationResponse:
        """Async version of wait_for_response (event-driven, no polling)."""
        with self._lock:
            request = self._pending.get(request_id)
            if not request:
                raise ValueError(f"Request {request_id} not found")

        timeout = timeout or request.timeout
        
        # P0: Create asyncio.Event for async wait
        async_event = asyncio.Event()
        
        # Set the async event when the thread event is set
        def set_async_event():
            if request_id in self._wait_events:
                # Wait for thread event in background thread
                if self._wait_events[request_id].wait(timeout=timeout):
                    # Schedule async event set on event loop
                    try:
                        loop = asyncio.get_running_loop()
                        loop.call_soon_threadsafe(async_event.set)
                    except RuntimeError:
                        pass
        
        # Start thread to monitor thread event
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(set_async_event)
        
        # P0: Event-driven wait (no polling)
        try:
            await asyncio.wait_for(async_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            # Timeout
            with self._lock:
                if request_id in self._pending:
                    del self._pending[request_id]
                # Clean up wait event
                if request_id in self._wait_events:
                    del self._wait_events[request_id]
            raise ConfirmationTimeout(request_id, timeout)
        
        # Response is available
        with self._lock:
            if request_id in self._responses:
                response = self._responses[request_id]
                # Clean up wait event
                if request_id in self._wait_events:
                    del self._wait_events[request_id]
                return response
        
        # Clean up wait event if no response
        with self._lock:
            if request_id in self._wait_events:
                del self._wait_events[request_id]
        
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
                # P0: Clean up wait event
                if request_id in self._wait_events:
                    self._wait_events[request_id].set()
                    del self._wait_events[request_id]
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
            # P0: Clean up all wait events
            for event in self._wait_events.values():
                event.set()
            self._wait_events.clear()
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
        # P0: Clean up all remaining wait events
        with self._lock:
            for event in self._wait_events.values():
                event.set()
            self._wait_events.clear()
        self._executor.shutdown(wait=False)
