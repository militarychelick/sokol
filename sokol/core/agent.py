"""
Sokol Agent - The single decision point for all operations.

This is the central orchestrator that coordinates all layers.
There is NO other decision point - everything flows through here.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from .config import Config
from .constants import ActionCategory, AgentState, IntentType, LLMProvider, SafetyLevel
from .exceptions import (
    ExecutionError,
    PermissionDeniedError,
    RestrictedActionError,
    SokolError,
)


@dataclass
class Intent:
    """Parsed user intent with strict structure."""
    action_type: str           # "launch_app", "open_url", "press_hotkey"
    target: str | None         # "chrome", "youtube.com", "ctrl+c"
    params: dict = field(default_factory=dict)  # additional parameters
    safety_level: SafetyLevel = SafetyLevel.SAFE
    complexity: int = 1        # 1-10 scale
    requires_planning: bool = False
    raw_text: str = ""         # original input
    confidence: float = 0.0
    context: dict = field(default_factory=dict)
    
    def is_simple(self) -> bool:
        """Check if intent is simple enough for direct execution."""
        return not self.requires_planning and self.complexity <= 3
    
    def needs_planning(self) -> bool:
        """Check if intent needs planning/decomposition."""
        return self.requires_planning


@dataclass
class Plan:
    """Execution plan for complex tasks."""
    intent: Intent
    steps: list[Step] = field(default_factory=list)
    current_step: int = 0
    status: str = "pending"
    
    def is_complete(self) -> bool:
        return self.current_step >= len(self.steps)


@dataclass
class Step:
    """Single step in a plan."""
    action: str
    action_category: ActionCategory
    params: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    result: Any = None
    error: str | None = None


@dataclass
class ActionResult:
    """Result of an executed action."""
    success: bool
    action: str
    message: str
    data: Any = None
    error: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)


class SokolAgent:
    """
    The Sokol Agent - single decision point for all operations.
    
    This class coordinates all layers but does NOT implement them.
    Each layer is a separate module with clear interfaces.
    """
    
    def __init__(self, config: Config) -> None:
        self.config = config
        self.state = AgentState.IDLE
        self.current_intent: Intent | None = None
        self.current_plan: Plan | None = None
        
        # Layer references (lazy loaded)
        self._voice: Any = None
        self._text: Any = None
        self._intent_parser: Any = None
        self._planner: Any = None
        self._executor: Any = None
        self._policy: Any = None
        self._memory: Any = None
        self._llm_router: Any = None
        self._gui: Any = None
        
        # Callbacks for state changes
        self._state_callbacks: list[Callable[[AgentState], None]] = []
        
        # Shutdown flag
        self._shutdown = False
    
    # --- Layer Properties (lazy loading) ---
    
    @property
    def voice(self) -> Any:
        """Voice layer (lazy loaded)."""
        if self._voice is None:
            from ..voice import VoiceLayer
            self._voice = VoiceLayer(self.config.voice)
        return self._voice
    
    @property
    def text(self) -> Any:
        """Text layer (lazy loaded)."""
        if self._text is None:
            from ..text import TextLayer
            self._text = TextLayer(use_stdin=True)
        return self._text
    
    @property
    def intent_parser(self) -> Any:
        """Intent parser (lazy loaded)."""
        if self._intent_parser is None:
            from ..intent import IntentParser
            self._intent_parser = IntentParser(self.config)
        return self._intent_parser
    
    @property
    def planner(self) -> Any:
        """Task planner (lazy loaded)."""
        if self._planner is None:
            from ..planner import TaskPlanner
            self._planner = TaskPlanner(self.config)
        return self._planner
    
    @property
    def executor(self) -> Any:
        """Action dispatcher (lazy loaded)."""
        if self._executor is None:
            from ..executor import ActionDispatcher
            self._executor = ActionDispatcher()
        return self._executor
    
    @property
    def policy(self) -> Any:
        """Safety policy (lazy loaded)."""
        if self._policy is None:
            from ..policy import SafetyPolicy
            self._policy = SafetyPolicy(self.config.safety)
        return self._policy
    
    @property
    def memory(self) -> Any:
        """Memory system (lazy loaded)."""
        if self._memory is None:
            from ..memory import MemorySystem
            self._memory = MemorySystem(self.config.memory)
        return self._memory
    
    @property
    def llm_router(self) -> Any:
        """LLM router (lazy loaded)."""
        if self._llm_router is None:
            from ..llm import LLMRouter
            self._llm_router = LLMRouter(self.config.llm)
        return self._llm_router
    
    # --- State Management ---
    
    def set_state(self, state: AgentState) -> None:
        """Set agent state and notify callbacks."""
        old_state = self.state
        self.state = state
        
        # Notify callbacks
        for callback in self._state_callbacks:
            try:
                callback(state)
            except Exception:
                pass  # Don't let callback errors break the agent
    
    def on_state_change(self, callback: Callable[[AgentState], None]) -> None:
        """Register a callback for state changes."""
        self._state_callbacks.append(callback)
    
    # --- Main Entry Points ---
    
    async def run(self) -> None:
        """Main agent loop."""
        # Initialize layers
        await self._initialize()
        
        # Start GUI if configured
        if self.config.gui.show_on_start:
            self._start_gui()
        
        try:
            # Main interaction loop
            while not self._shutdown:
                try:
                    await self._interaction_loop()
                except Exception as e:
                    self.set_state(AgentState.ERROR)
                    await self._handle_error(e)
                    self.set_state(AgentState.IDLE)
        finally:
            # Always cleanup
            await self._shutdown()
    
    async def _initialize(self) -> None:
        """Initialize all required components."""
        # Initialize memory (always needed)
        await self.memory.initialize()
        
        # Load user profile
        await self.memory.load_profile()
        
        # Initialize LLM router (optional - can work without it)
        try:
            await self.llm_router.initialize()
        except Exception:
            # LLM not available, will work with patterns only
            pass
        
        # Start stdin reader for text input
        await self.text.start_stdin_reader()
        
        # Initialize voice (optional - may fail without hardware)
        try:
            await self.voice.initialize()
        except Exception:
            # Voice not available, text only
            pass
    
    async def _shutdown(self) -> None:
        """Cleanup all components."""
        # Stop stdin reader
        await self.text.stop_stdin_reader()
        
        # Shutdown voice
        try:
            await self.voice.shutdown()
        except Exception:
            pass
        
        # Shutdown memory
        try:
            await self.memory.shutdown()
        except Exception:
            pass
        
        # Shutdown LLM router
        try:
            await self.llm_router.shutdown()
        except Exception:
            pass
    
    async def _interaction_loop(self) -> None:
        """Single interaction cycle."""
        self.set_state(AgentState.IDLE)
        
        # Wait for input (voice or text)
        user_input = await self._get_input()
        
        if user_input is None:
            return  # No input, continue loop
        
        # Process the input
        await self.process_input(user_input)
    
    async def _get_input(self) -> str | None:
        """Get input from voice or text layer."""
        # Try voice first (primary interface)
        self.set_state(AgentState.LISTENING)
        
        try:
            # Check for voice input (non-blocking check)
            voice_input = await self.voice.listen_for_input()
            if voice_input:
                return voice_input
        except Exception:
            pass  # Voice not available, fall back to text
        
        # Text fallback
        text_input = await self.text.get_input()
        return text_input
    
    # --- Core Processing Flow ---
    
    async def process_input(self, text: str) -> ActionResult:
        """
        Process user input through the complete flow.
        
        This is THE single execution path:
        Input -> Safety -> Intent -> Plan (optional) -> Execute -> Memory -> Response
        """
        self.set_state(AgentState.PROCESSING)
        self.current_intent = None
        self.current_plan = None
        
        try:
            # Step 1: Quick safety check on raw input (before LLM)
            quick_safety = self._quick_safety_check(text)
            if quick_safety == SafetyLevel.DANGEROUS:
                return ActionResult(
                    success=False,
                    action="blocked",
                    message="This action is too dangerous to execute",
                )
            
            # Step 2: Parse intent
            intent = await self._parse_intent(text)
            self.current_intent = intent
            
            # Step 3: Check safety policy on parsed intent
            safety = await self._check_safety(intent)
            
            if safety == SafetyLevel.DANGEROUS:
                # Request explicit permission
                permission = await self._request_permission(intent)
                if not permission:
                    raise PermissionDeniedError(action=intent.action_type)
            
            elif safety == SafetyLevel.CAUTION:
                # Request confirmation
                confirmed = await self._request_confirmation(intent)
                if not confirmed:
                    raise PermissionDeniedError(action=intent.action_type)
            
            # Step 4: Execute (direct or planned)
            if not self.planner.needs_planning(intent):
                result = await self._execute_direct(intent)
            else:
                result = await self._execute_planned(intent)
            
            # Step 5: Store in memory
            await self._store_interaction(text, intent, result)
            
            # Step 6: Respond to user
            await self._respond(result)
            
            return result
            
        except PermissionDeniedError as e:
            await self._speak("Action cancelled.")
            return ActionResult(
                success=False,
                action="permission_denied",
                message=str(e),
            )
        
        except RestrictedActionError as e:
            await self._speak(f"I cannot do that: {e.reason}")
            return ActionResult(
                success=False,
                action="restricted",
                message=str(e),
            )
        
        except SokolError as e:
            await self._handle_error(e)
            return ActionResult(
                success=False,
                action="error",
                message=str(e),
                error=str(e),
            )
        
        finally:
            self.set_state(AgentState.IDLE)
    
    def _quick_safety_check(self, text: str) -> SafetyLevel:
        """Quick safety check on raw input before LLM."""
        text_lower = text.lower()
        
        # Dangerous patterns
        dangerous_patterns = [
            "delete", "remove", "format", "shutdown", "restart",
            "удалить", "форматировать", "выключить", "перезагрузить",
        ]
        
        for pattern in dangerous_patterns:
            if pattern in text_lower:
                return SafetyLevel.DANGEROUS
        
        return SafetyLevel.SAFE
    
    async def _parse_intent(self, text: str) -> Intent:
        """Parse user text into structured intent."""
        self.set_state(AgentState.PROCESSING)
        
        # Get context from memory
        context = await self.memory.get_context()
        
        # Parse intent using LLM or patterns
        intent = await self.intent_parser.parse(text, context)
        
        return intent
    
    async def _check_safety(self, intent: Intent) -> SafetyLevel:
        """Check safety level for intent."""
        # Use the safety level from intent (already set by parser)
        # Or classify if not set
        if intent.safety_level != SafetyLevel.SAFE:
            return intent.safety_level
        
        # Additional classification if needed
        return self.policy.classify_by_action_type(intent.action_type)
    
    async def _request_permission(self, intent: Intent) -> bool:
        """Request explicit permission for dangerous action."""
        self.set_state(AgentState.WAITING_CONFIRMATION)
        
        # Generate permission prompt
        prompt = self.policy.generate_permission_prompt(intent)
        
        # Ask via voice
        await self._speak(prompt)
        
        # Wait for response
        response = await self._get_input()
        
        # Parse response
        if response:
            return self.intent_parser.is_affirmative(response)
        
        return False
    
    async def _request_confirmation(self, intent: Intent) -> bool:
        """Request confirmation for caution-level action."""
        self.set_state(AgentState.WAITING_CONFIRMATION)
        
        # Generate confirmation prompt
        prompt = self.policy.generate_confirmation_prompt(intent)
        
        # Ask via voice
        await self._speak(prompt)
        
        # Wait for response
        response = await self._get_input()
        
        # Parse response
        if response:
            return self.intent_parser.is_affirmative(response)
        
        return False
    
    async def _execute_direct(self, intent: Intent) -> ActionResult:
        """Execute simple intent directly."""
        self.set_state(AgentState.EXECUTING)
        
        result = await self.executor.dispatch_async(intent)
        
        return result
    
    async def _execute_planned(self, intent: Intent) -> ActionResult:
        """Execute complex intent with planning."""
        self.set_state(AgentState.PLANNING)
        
        # Create plan
        plan = await self.planner.create_plan(intent)
        self.current_plan = plan
        
        # Execute steps
        self.set_state(AgentState.EXECUTING)
        
        results = []
        for step in plan.steps:
            step_result = await self.executor.execute_step(step)
            results.append(step_result)
            
            if not step_result.success:
                # Handle failure
                recovery = await self.planner.handle_failure(plan, step, step_result)
                if recovery == "abort":
                    break
        
        # Compile final result
        success = all(r.success for r in results)
        message = self._compile_plan_result(plan, results)
        
        return ActionResult(
            success=success,
            action="planned_execution",
            message=message,
            data={"results": results, "plan": plan},
        )
    
    async def _store_interaction(
        self,
        text: str,
        intent: Intent,
        result: ActionResult,
    ) -> None:
        """Store interaction in memory."""
        await self.memory.store_interaction(
            input_text=text,
            intent=intent,
            result=result,
        )
    
    async def _respond(self, result: ActionResult) -> None:
        """Generate and speak response to user."""
        self.set_state(AgentState.SPEAKING)
        
        # Generate response text
        response = await self._generate_response(result)
        
        # Speak response
        await self._speak(response)
    
    async def _generate_response(self, result: ActionResult) -> str:
        """Generate natural language response."""
        if result.success:
            if result.action == "planned_execution":
                return result.message
            return f"Done. {result.message}"
        else:
            return f"I couldn't complete that. {result.message}"
    
    async def _speak(self, text: str) -> None:
        """Speak text to user (text fallback)."""
        self.set_state(AgentState.SPEAKING)
        
        # Try voice first, fallback to text
        try:
            await self.voice.speak(text)
        except Exception:
            # Voice not available, use text
            await self.text.output(text)
    
    async def _handle_error(self, error: Exception) -> None:
        """Handle an error gracefully."""
        # Log error
        # TODO: Proper logging
        
        # Speak error message
        if isinstance(error, SokolError):
            await self._speak(f"Error: {error.message}")
        else:
            await self._speak("An unexpected error occurred.")
    
    def _compile_plan_result(self, plan: Plan, results: list[ActionResult]) -> str:
        """Compile plan execution results into message."""
        successful = sum(1 for r in results if r.success)
        total = len(results)
        
        if successful == total:
            return f"Completed all {total} steps successfully."
        else:
            return f"Completed {successful} of {total} steps."
    
    def _start_gui(self) -> None:
        """Start GUI in separate thread."""
        # GUI runs in main thread, agent runs in async loop
        # This is handled by the main entry point
        pass
    
    def shutdown(self) -> None:
        """Signal agent to shutdown."""
        self._shutdown = True
    
    # --- Convenience Methods ---
    
    async def execute_command(self, text: str) -> ActionResult:
        """Execute a text command directly (for GUI/text input)."""
        return await self.process_input(text)
    
    async def quick_action(self, action_name: str) -> ActionResult:
        """Execute a predefined quick action."""
        # TODO: Implement quick actions from config
        return ActionResult(
            success=False,
            action=action_name,
            message="Quick actions not yet implemented",
        )
