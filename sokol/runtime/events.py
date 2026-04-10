"""Event bus for agent communication."""

import asyncio
from collections import defaultdict
from concurrent.futures import Future
from typing import Any, Callable, Coroutine

from sokol.core.types import AgentEvent, EventType
from sokol.observability.logging import get_logger

logger = get_logger("sokol.runtime.events")

# Type aliases
EventListener = Callable[[AgentEvent], None | Coroutine[Any, Any, None]]
AsyncEventListener = Callable[[AgentEvent], Coroutine[Any, Any, None]]


class EventBus:
    """Event bus for pub/sub communication."""

    def __init__(self) -> None:
        self._listeners: dict[EventType, list[EventListener]] = defaultdict(list)
        self._async_listeners: dict[EventType, list[AsyncEventListener]] = defaultdict(list)
        self._global_listeners: list[EventListener] = []
        self._event_queue: asyncio.Queue[AgentEvent] | None = None
        self._running = False

    def subscribe(
        self,
        event_type: EventType,
        listener: EventListener,
    ) -> None:
        """Subscribe to a specific event type."""
        self._listeners[event_type].append(listener)
        logger.debug_data(
            "Event listener subscribed",
            {"event_type": event_type.value, "listener": str(listener)},
        )

    def subscribe_async(
        self,
        event_type: EventType,
        listener: AsyncEventListener,
    ) -> None:
        """Subscribe an async listener to a specific event type."""
        self._async_listeners[event_type].append(listener)

    def subscribe_global(self, listener: EventListener) -> None:
        """Subscribe to all events."""
        self._global_listeners.append(listener)

    def unsubscribe(
        self,
        event_type: EventType,
        listener: EventListener,
    ) -> bool:
        """Unsubscribe from a specific event type."""
        if listener in self._listeners[event_type]:
            self._listeners[event_type].remove(listener)
            return True
        return False

    def emit(self, event: AgentEvent) -> None:
        """Emit an event to all subscribers."""
        logger.debug_data(
            "Event emitted",
            {"event_id": event.id, "type": event.type.value, "source": event.source},
        )

        # Notify type-specific listeners
        for listener in self._listeners[event.type]:
            try:
                result = listener(event)
                # Handle coroutine
                if asyncio.iscoroutine(result):
                    # Schedule coroutine if event loop is running
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(result)  # type: ignore[arg-type]
                    except RuntimeError:
                        # No running loop, run synchronously
                        asyncio.run(result)  # type: ignore[arg-type]
            except Exception as e:
                logger.error_data(
                    "Event listener error",
                    {
                        "event_id": event.id,
                        "listener": str(listener),
                        "error": str(e),
                    },
                )

        # Notify global listeners
        for listener in self._global_listeners:
            try:
                result = listener(event)
                if asyncio.iscoroutine(result):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(result)  # type: ignore[arg-type]
                    except RuntimeError:
                        asyncio.run(result)  # type: ignore[arg-type]
            except Exception as e:
                logger.error_data(
                    "Global listener error",
                    {"event_id": event.id, "error": str(e)},
                )

    def emit_async(self, event: AgentEvent) -> Future[None]:
        """Emit event asynchronously (returns Future for async listeners)."""
        future: Future[None] = Future()

        async def _emit() -> None:
            try:
                # Handle async listeners
                for listener in self._async_listeners[event.type]:
                    try:
                        await listener(event)
                    except Exception as e:
                        logger.error_data(
                            "Async listener error",
                            {"event_id": event.id, "error": str(e)},
                        )

                # Also emit to sync listeners
                self.emit(event)
                future.set_result(None)
            except Exception as e:
                future.set_exception(e)

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_emit())
        except RuntimeError:
            # No running loop
            asyncio.run(_emit())

        return future

    def create_and_emit(
        self,
        event_type: EventType,
        source: str,
        data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentEvent:
        """Create and emit an event in one call."""
        event = AgentEvent(
            type=event_type,
            source=source,
            data=data or {},
            metadata=metadata or {},
        )
        self.emit(event)
        return event

    def clear(self) -> None:
        """Clear all listeners."""
        self._listeners.clear()
        self._async_listeners.clear()
        self._global_listeners.clear()

    def listener_count(self, event_type: EventType | None = None) -> int:
        """Count listeners for an event type or total."""
        if event_type:
            return len(self._listeners[event_type]) + len(self._async_listeners[event_type])
        return (
            sum(len(v) for v in self._listeners.values())
            + sum(len(v) for v in self._async_listeners.values())
            + len(self._global_listeners)
        )
