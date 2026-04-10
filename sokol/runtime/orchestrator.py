"""Main orchestrator - agent event loop."""

import asyncio
import signal
import threading
from typing import Any, Callable

from sokol.core.config import Config, get_config
from sokol.core.types import AgentEvent, AgentState, EventType
from sokol.observability.logging import get_logger, setup_logging
from sokol.runtime.events import EventBus
from sokol.runtime.state import AgentStateMachine
from sokol.runtime.tasks import TaskManager

logger = get_logger("sokol.runtime.orchestrator")


class Orchestrator:
    """
    Main orchestrator for the agent.

    Coordinates:
    - State machine
    - Event bus
    - Task manager
    - Emergency stop
    """

    def __init__(self, config: Config | None = None) -> None:
        self._config = config or get_config()
        self._state_machine = AgentStateMachine()
        self._event_bus = EventBus()
        self._task_manager = TaskManager()

        # Wire state machine to event bus
        self._state_machine.set_event_callback(self._on_state_change)

        # Running state
        self._running = False
        self._main_loop: asyncio.AbstractEventLoop | None = None
        self._shutdown_event = threading.Event()

        # Callbacks
        self._on_input_callback: Callable[[str], None] | None = None
        self._on_response_callback: Callable[[str], None] | None = None
        self._on_confirm_callback: Callable[[Any], bool] | None = None

        # Register emergency stop handler
        self._event_bus.subscribe(
            EventType.EMERGENCY_STOP,
            self._handle_emergency_stop,
        )

    @property
    def state(self) -> AgentState:
        """Current agent state."""
        return self._state_machine.state

    @property
    def state_machine(self) -> AgentStateMachine:
        """State machine instance."""
        return self._state_machine

    @property
    def event_bus(self) -> EventBus:
        """Event bus instance."""
        return self._event_bus

    @property
    def task_manager(self) -> TaskManager:
        """Task manager instance."""
        return self._task_manager

    def setup(self) -> None:
        """Setup logging and other infrastructure."""
        setup_logging(
            level=self._config.logging.level,
            log_file=self._config.logging.file,
            max_size=self._config.logging.max_size,
            backup_count=self._config.logging.backup_count,
            use_json=self._config.logging.format == "json",
        )

        logger.info_data(
            "Orchestrator setup complete",
            {
                "agent_name": self._config.agent.name,
                "llm_provider": self._config.llm.provider,
            },
        )

    def start(self) -> None:
        """Start the orchestrator."""
        if self._running:
            logger.warning("Orchestrator already running")
            return

        self._running = True
        self._shutdown_event.clear()

        logger.info("Orchestrator started")

        # Setup signal handlers
        self._setup_signal_handlers()

    def stop(self, reason: str = "shutdown") -> None:
        """Stop the orchestrator."""
        if not self._running:
            return

        logger.info_data("Orchestrator stopping", {"reason": reason})

        # Cancel all tasks
        self._task_manager.cancel_all(reason)

        # Set shutdown event
        self._shutdown_event.set()

        self._running = False

        # Transition to idle
        self._state_machine.force_transition(AgentState.IDLE, reason)

    def emergency_stop(self, reason: str = "user_triggered") -> None:
        """
        Emergency stop - immediately halt all activity.

        This is the critical safety feature.
        """
        logger.warning_data(
            "EMERGENCY STOP triggered",
            {"reason": reason, "current_state": self.state.value},
        )

        # Cancel ALL tasks immediately
        cancelled = self._task_manager.cancel_all(f"emergency_stop:{reason}")

        # Force state to idle
        self._state_machine.force_transition(AgentState.IDLE, "emergency_stop")

        # Emit emergency stop event
        self._event_bus.create_and_emit(
            EventType.EMERGENCY_STOP,
            "orchestrator",
            {"reason": reason, "tasks_cancelled": cancelled},
        )

    def process_input(self, text: str, source: str = "user") -> None:
        """Process user input (text or voice transcription)."""
        if not self._state_machine.can_accept_input():
            logger.warning_data(
                "Input ignored - agent busy",
                {"state": self.state.value, "input": text[:50]},
            )
            return

        logger.info_data(
            "Processing input",
            {"source": source, "text": text[:100]},
        )

        # Emit input event
        self._event_bus.create_and_emit(
            EventType.USER_INPUT,
            source,
            {"text": text},
        )

        # Transition to thinking
        self._state_machine.transition(AgentState.THINKING, "user_input")

        # Call input callback if set
        if self._on_input_callback:
            self._on_input_callback(text)

    def emit_response(self, text: str, source: str = "agent") -> None:
        """Emit a response to the user."""
        logger.info_data(
            "Emitting response",
            {"source": source, "text": text[:100]},
        )

        if self._on_response_callback:
            self._on_response_callback(text)

    def request_confirmation(self, request: Any) -> bool:
        """Request user confirmation for dangerous action."""
        self._state_machine.transition(
            AgentState.WAITING_CONFIRM,
            f"tool:{request.tool_name}",
        )

        self._event_bus.create_and_emit(
            EventType.CONFIRM_REQUEST,
            "orchestrator",
            {"request": request.model_dump() if hasattr(request, "model_dump") else str(request)},
        )

        # Call confirm callback if set
        if self._on_confirm_callback:
            return self._on_confirm_callback(request)

        # Default: deny dangerous actions without callback
        return False

    def set_callbacks(
        self,
        on_input: Callable[[str], None] | None = None,
        on_response: Callable[[str], None] | None = None,
        on_confirm: Callable[[Any], bool] | None = None,
    ) -> None:
        """Set callbacks for UI integration."""
        self._on_input_callback = on_input
        self._on_response_callback = on_response
        self._on_confirm_callback = on_confirm

    def _on_state_change(self, event: AgentEvent) -> None:
        """Handle state change events."""
        logger.debug_data(
            "State change event",
            event.data,
        )

    def _handle_emergency_stop(self, event: AgentEvent) -> None:
        """Handle emergency stop event from any source."""
        self.emergency_stop(event.data.get("reason", "event"))

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum: int, frame: Any) -> None:
            logger.info_data("Signal received", {"signal": signum})
            self.stop(f"signal_{signum}")

        # Only works in main thread
        try:
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        except ValueError:
            # Not in main thread
            pass

    def run_forever(self) -> None:
        """Run the main loop (blocking)."""
        self.start()
        try:
            self._shutdown_event.wait()
        except KeyboardInterrupt:
            self.stop("keyboard_interrupt")

    async def run_async(self) -> None:
        """Run the main loop (async)."""
        self._main_loop = asyncio.get_running_loop()
        self.start()

        try:
            while self._running:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            self.stop("async_cancel")

    def __repr__(self) -> str:
        return f"Orchestrator(state={self.state.value}, running={self._running})"
