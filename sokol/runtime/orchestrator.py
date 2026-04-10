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

        # LLM and tools
        self._llm_manager = LLMManager(config)
        self._tool_registry = get_registry()

        # LLM-free fallback
        self._intent_handler = RuleBasedIntentHandler()

        # Conversation history
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
        1. LLM call (with timeout) - returns JSON
        2. Parse response type
        3. Handle based on type (tool_call, final_answer, clarification)
        4. Emit response
        5. State transition to IDLE
        """
        try:
            # PHASE 1: LLM Call with timeout - returns parsed JSON
            llm_response = self._call_llm_with_timeout(user_input)

            # PHASE 2: Parse response type
            response_type = llm_response.get("type")

            # PHASE 3: Handle based on type
            if response_type == "tool_call":
                # Execute tool
                tool_name = llm_response.get("tool")
                args = llm_response.get("args", {})

                tool_result = self._execute_tool({"tool_name": tool_name, "params": args})

                # Generate final response with tool result
                final_response = self._generate_final_response(tool_result)

            elif response_type == "final_answer":
                # Direct response to user
                final_response = llm_response.get("text", "No response text")

            elif response_type == "clarification":
                # Ask user for clarification
                question = llm_response.get("question", "")
                final_response = f"Question: {question}"

            else:
                # Unknown type, fallback
                logger.warning_data(
                    "Unknown response type",
                    {"type": response_type},
                )
                final_response = llm_response.get("text", "Unknown response type")

            # PHASE 4: Emit response
            self.emit_response(final_response)

            # PHASE 5: Transition to IDLE
            self._state_machine.transition(AgentState.IDLE, "agent_loop_complete")

        except Exception as e:
            logger.error_data("Agent loop failed", {"error": str(e)})
            self.emit_response(f"Error: {str(e)}")
            self._state_machine.transition(AgentState.ERROR, "agent_loop_error")

    def _call_llm_with_timeout(self, user_input: str) -> dict[str, Any]:
        """
        Call LLM with timeout safety and JSON parsing.

        Falls back to rule-based intent handler if LLM fails.

        Returns parsed JSON response dict with type field.
        """
        import json

        # Add user message to history
        self._conversation_history.append(
            LLMMessage(role="user", content=user_input)
        )

        # Build system prompt with available tools
        system_prompt = self._build_system_prompt()

        # Add system message
        messages = [LLMMessage(role="system", content=system_prompt)]
        messages.extend(self._conversation_history)

        # Get response from LLM with timeout and retry for invalid JSON
        logger.info("Calling LLM...")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Use fallback timeout from config
                response = self._llm_manager.complete(messages, use_fallback=True)

                logger.info_data(
                    "LLM response received",
                    {
                        "provider": response.provider,
                        "latency_ms": response.latency_ms,
                        "attempt": attempt + 1,
                    },
                )

                # Try to parse JSON
                try:
                    parsed = json.loads(response.content.strip())

                    # Validate JSON has required type field
                    if "type" not in parsed:
                        raise ValueError("Missing 'type' field in JSON response")

                    # Add to history
                    self._conversation_history.append(
                        LLMMessage(role="assistant", content=response.content)
                    )

                    return parsed

                except json.JSONDecodeError as e:
                    logger.warning_data(
                        "LLM response is not valid JSON",
                        {"attempt": attempt + 1, "error": str(e)},
                    )

                    if attempt < max_retries - 1:
                        # Retry with error feedback
                        messages.append(
                            LLMMessage(
                                role="system",
                                content=f"Error: Your response was not valid JSON. Please respond with valid JSON only. Error: {str(e)}",
                            )
                        )
                        continue
                    else:
                        # Fallback to intent handler
                        logger.warning("All JSON parsing attempts failed, using intent handler fallback")
                        return self._fallback_to_intent_handler(user_input)

            except Exception as e:
                logger.error_data("LLM call failed", {"error": str(e)})
                # Fallback to intent handler
                logger.warning("LLM call failed, using intent handler fallback")
                return self._fallback_to_intent_handler(user_input)

        # Should not reach here
        return self._fallback_to_intent_handler(user_input)

    def _fallback_to_intent_handler(self, user_input: str) -> dict[str, Any]:
        """
        Fallback to rule-based intent handler when LLM fails.

        Returns JSON response in the same format as LLM would.
        """
        logger.info("Using LLM-free intent handler")

        # Try to parse intent
        intent = self._intent_handler.parse_intent(user_input)

        if intent and intent.tool:
            # Execute intent
            success, result_text = self._intent_handler.execute_intent(intent)

            if success:
                return {
                    "type": "final_answer",
                    "text": result_text,
                }
            else:
                return {
                    "type": "final_answer",
                    "text": f"Failed to execute command: {result_text}",
                }
        else:
            # No intent matched
            help_text = self._intent_handler.get_help()
            return {
                "type": "final_answer",
                "text": f"I couldn't understand that command. {help_text}",
            }

    def _execute_tool(self, tool_call: dict[str, Any]) -> str:
        """
        Execute tool with state transition.

        Returns tool result string.
        """
        tool_name = tool_call["tool_name"]
        params = tool_call["params"]

        logger.info_data(
            "Executing tool",
            {"tool": tool_name, "params": str(params)[:100]},
        )

        # Transition to EXECUTING
        self._state_machine.transition(AgentState.EXECUTING, f"tool:{tool_name}")

        try:
            result = self._tool_registry.execute(tool_name, params)

            if result.success:
                return f"Tool {tool_name} succeeded: {str(result.data)[:200]}"
            else:
                return f"Tool {tool_name} failed: {result.error}"
        except Exception as e:
            logger.error_data("Tool execution error", {"error": str(e)})
            return f"Tool {tool_name} error: {str(e)}"

    def _generate_final_response(self, tool_result: str) -> str:
        """
        Generate final response after tool execution.

        Sends tool result back to LLM for final response.
        """
        # Build messages with tool result
        system_prompt = self._build_system_prompt()
        messages = [LLMMessage(role="system", content=system_prompt)]
        messages.extend(self._conversation_history)

        # Add tool result
        messages.append(
            LLMMessage(role="system", content=f"Tool result: {tool_result}")
        )

        try:
            final_response = self._llm_manager.complete(messages, use_fallback=True)

            # Parse JSON response
            import json
            parsed = json.loads(final_response.content.strip())

            # Add to history
            self._conversation_history.append(
                LLMMessage(role="assistant", content=final_response.content)
            )

            # Return text from final_answer type
            if parsed.get("type") == "final_answer":
                return parsed.get("text", f"Tool executed. Result: {tool_result}")
            else:
                # Fallback
                return f"Tool executed. Result: {tool_result}"

        except Exception as e:
            logger.error_data("Final response generation failed", {"error": str(e)})
            # Fallback to simple response
            return f"Tool executed. Result: {tool_result}"

    def _build_system_prompt(self) -> str:
        """Build system prompt with available tools and strict JSON schema."""
        tool_schemas = self._tool_registry.list_schemas()

        tools_desc = "Available tools:\n"
        for schema in tool_schemas:
            tools_desc += f"- {schema.name}: {schema.description}\n"
            tools_desc += f"  Parameters (JSON Schema): {schema.parameters}\n"
            tools_desc += f"  Risk: {schema.risk_level.value}\n"

        base_prompt = f"""You are {self._config.agent.name}, a Windows AI assistant.

Your role:
- Help users manage their Windows PC through text commands
- Use available tools to accomplish tasks
- Ask for confirmation before dangerous operations
- Provide brief, clear responses

{tools_desc}

STRICT OUTPUT FORMAT:
You MUST respond with valid JSON only. No free-form text allowed.

Response formats:

1. Tool Call (when you need to execute a tool):
{{
  "type": "tool_call",
  "tool": "tool_name",
  "args": {{"param": "value"}}
}}

2. Final Answer (when no tool needed):
{{
  "type": "final_answer",
  "text": "Your response text"
}}

3. Clarification (when you need more info):
{{
  "type": "clarification",
  "question": "Your question"
}}

Examples:
- To open notepad: {{"type": "tool_call", "tool": "app_launcher", "args": {{"app_name": "notepad"}}}}
- To answer a question: {{"type": "final_answer", "text": "Here's the information..."}}
- To ask for more info: {{"type": "clarification", "question": "Which file do you want to read?"}}

IMPORTANT: Always return valid JSON. Never include text outside the JSON object.
"""
        return base_prompt

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
