"""Main orchestrator - agent event loop."""

import asyncio
import signal
import threading
import time
from typing import Any, Callable

from sokol.core.config import Config, get_config
from sokol.core.types import AgentEvent, AgentState, EventType
from sokol.observability.logging import get_logger, setup_logging
from sokol.runtime.events import EventBus
from sokol.runtime.state import AgentStateMachine
from sokol.runtime.tasks import TaskManager
from sokol.runtime.intent import RuleBasedIntentHandler, Intent
from sokol.runtime.router import IntentRouter, ProposedAction, DecisionSource
from sokol.integrations.llm import LLMManager, LLMMessage
from sokol.tools.registry import get_registry

logger = get_logger("sokol.runtime.orchestrator")

# Watchdog timeout for stuck states (seconds)
WATCHDOG_TIMEOUT = 30.0


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

        # Unified intent router (replaces LLM + intent handler)
        self._intent_router = IntentRouter()
        self._tool_registry = get_registry()

        # Conversation history (for LLM context)
        self._conversation_history: list[LLMMessage] = []

        # Watchdog state tracking
        self._state_enter_time: float = 0.0
        self._watchdog_running = False
        self._watchdog_thread: threading.Thread | None = None
        self._lock = threading.Lock()

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

        # Start watchdog
        self._start_watchdog()

        logger.info("Orchestrator started")

        # Setup signal handlers
        self._setup_signal_handlers()

    def stop(self, reason: str = "shutdown") -> None:
        """Stop the orchestrator."""
        if not self._running:
            return

        logger.info_data("Orchestrator stopping", {"reason": reason})

        # Stop watchdog
        self._stop_watchdog()

        # Cancel all tasks
        self._task_manager.cancel_all(reason)

        # Set shutdown event
        self._shutdown_event.set()

        self._running = False

        # Force transition to idle
        self._state_machine.force_transition(AgentState.IDLE, reason)

    def _start_watchdog(self) -> None:
        """Start watchdog thread to monitor for stuck states."""
        if self._watchdog_running:
            return

        self._watchdog_running = True
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop, daemon=True, name="Watchdog"
        )
        self._watchdog_thread.start()
        logger.info("Watchdog started")

    def _stop_watchdog(self) -> None:
        """Stop watchdog thread."""
        self._watchdog_running = False
        if self._watchdog_thread:
            self._watchdog_thread.join(timeout=2.0)
        logger.info("Watchdog stopped")

    def _watchdog_loop(self) -> None:
        """Watchdog loop that monitors state for stuck conditions."""
        while self._watchdog_running:
            time.sleep(1.0)

            with self._lock:
                current_state = self._state_machine.state

                # Check if in a busy state for too long
                if current_state != AgentState.IDLE:
                    elapsed = time.time() - self._state_enter_time

                    if elapsed > WATCHDOG_TIMEOUT:
                        logger.error_data(
                            "Watchdog timeout - forcing state reset",
                            {"state": current_state.value, "elapsed": elapsed},
                        )
                        self._state_machine.force_transition(
                            AgentState.IDLE, "watchdog_timeout"
                        )
                        self._state_enter_time = time.time()

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
        """
        Process user input (text or voice transcription).

        Strict execution loop:
        1. Validate input acceptance
        2. Transition to THINKING
        3. Execute LLM processing (with timeout)
        4. Parse and execute tools if needed
        5. Emit response
        6. Always return to IDLE or ERROR
        """
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

        # STRICT: Ensure state always returns to IDLE/ERROR
        try:
            self._execute_agent_loop(text)
        finally:
            # Safety fallback: force to IDLE if not already there
            if self._state_machine.state not in (AgentState.IDLE, AgentState.ERROR):
                logger.warning_data(
                    "State cleanup in finally block",
                    {"current_state": self._state_machine.state.value},
                )
                self._state_machine.force_transition(AgentState.IDLE, "finally_cleanup")

    def _execute_agent_loop(self, user_input: str) -> None:
        """
        Strict agent execution loop with clear phases.

        Phases:
        1. Route input through IntentRouter (LLM > rule-based > rejected)
        2. Safety validation for tool calls
        3. Execute tool (if validated)
        4. Emit response
        5. State transition to IDLE
        """
        try:
            # PHASE 1: Route input through IntentRouter
            proposed_action = self._intent_router.route(user_input)

            # PHASE 2: Safety validation for tool calls
            if proposed_action.action_type == "tool_call":
                if not self._validate_safety(proposed_action):
                    final_response = "Action denied by safety layer"
                else:
                    # PHASE 3: Execute tool
                    tool_result = self._execute_tool_action(proposed_action)

                    # Generate final response
                    final_response = self._format_tool_result(tool_result)
            else:
                # Direct response (final_answer or clarification)
                final_response = proposed_action.text or "No response"

            # PHASE 4: Emit response
            self.emit_response(final_response)

            # PHASE 5: Transition to IDLE
            self._state_machine.transition(AgentState.IDLE, "agent_loop_complete")

        except Exception as e:
            logger.error_data("Agent loop failed", {"error": str(e)})
            self.emit_response(f"Error: {str(e)}")
            self._state_machine.transition(AgentState.ERROR, "agent_loop_error")

    def _validate_safety(self, action: ProposedAction) -> bool:
        """
        Validate proposed action through safety layer.

        Returns True if action is safe to execute.
        """
        # Import safety layer
        from sokol.safety.risk import RiskAssessor, assess_tool_risk

        if not action.tool:
            return True  # Text responses are always safe

        # Assess risk
        risk_level = assess_tool_risk(action.tool, action.args or {})

        # If dangerous, require confirmation (simplified: deny for now)
        from sokol.core.types import RiskLevel
        if risk_level == RiskLevel.DANGEROUS:
            logger.warning_data(
                "Dangerous action denied",
                {"tool": action.tool, "risk": risk_level.value},
            )
            return False

        return True

    def _execute_tool_action(self, action: ProposedAction) -> dict[str, Any]:
        """
        Execute tool action with state transition.

        Returns tool result dict.
        """
        tool_name = action.tool
        args = action.args or {}

        logger.info_data(
            "Executing tool",
            {"tool": tool_name, "source": action.source.value, "args": str(args)[:100]},
        )

        # Transition to EXECUTING
        self._state_machine.transition(AgentState.EXECUTING, f"tool:{tool_name}")

        try:
            result = self._tool_registry.execute(tool_name, args)

            return {
                "success": result.success,
                "data": result.data if result.success else None,
                "error": result.error if not result.success else None,
            }
        except Exception as e:
            logger.error_data("Tool execution error", {"error": str(e)})
            return {
                "success": False,
                "error": str(e),
            }

    def _format_tool_result(self, result: dict[str, Any]) -> str:
        """Format tool result for user."""
        if result["success"]:
            data = result.get("data")
            if isinstance(data, dict):
                return f"Success: {data}"
            return f"Success: {data}"
        else:
            return f"Failed: {result.get('error', 'Unknown error')}"

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
        with self._lock:
            # Update state enter time for watchdog
            self._state_enter_time = time.time()

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
