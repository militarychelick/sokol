"""
Sokol v2 - Main agent orchestration
"""

from __future__ import annotations

import asyncio
from enum import Enum
from typing import Any, Callable

from .config import Config
from .intent import Intent, SafetyLevel
from .result import ActionResult


class AgentState(Enum):
    """Agent execution states."""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    EXECUTING = "executing"
    WAITING_CONFIRMATION = "waiting_confirmation"
    SPEAKING = "speaking"
    ERROR = "error"


class SokolAgent:
    """
    The Sokol Agent - single decision point for all operations.
    
    Single execution flow:
    Input → Intent → Safety → Planner (optional) → Dispatcher → Action → Result → Memory → Response
    """
    
    def __init__(self, config: Config) -> None:
        self.config = config
        self.state = AgentState.IDLE
        self.current_intent: Intent | None = None
        
        # Layer references (lazy loaded)
        self._intent_parser: Any = None
        self._planner: Any = None
        self._dispatcher: Any = None
        self._safety_policy: Any = None
        self._memory: Any = None
        self._llm_router: Any = None
        self._voice_io: Any = None
        self._text_io: Any = None
        
        # Callbacks for state changes
        self._state_callbacks: list[Callable[[AgentState], None]] = []
        
        # Shutdown flag
        self._shutdown = False
    
    # --- Layer Properties (lazy loading) ---
    
    @property
    def intent_parser(self) -> Any:
        """Intent parser (lazy loaded)."""
        if self._intent_parser is None:
            from ..intent.parser import IntentParser
            self._intent_parser = IntentParser(self.config)
        return self._intent_parser
    
    @property
    def planner(self) -> Any:
        """Task planner (lazy loaded)."""
        if self._planner is None:
            from ..planner.task_planner import TaskPlanner
            self._planner = TaskPlanner(self.config)
        return self._planner
    
    @property
    def dispatcher(self) -> Any:
        """Action dispatcher (lazy loaded)."""
        if self._dispatcher is None:
            from ..executor.dispatcher import ActionDispatcher
            self._dispatcher = ActionDispatcher()
        return self._dispatcher
    
    @property
    def safety_policy(self) -> Any:
        """Safety policy (lazy loaded)."""
        if self._safety_policy is None:
            from ..safety.policy import SafetyPolicy
            self._safety_policy = SafetyPolicy(self.config.safety)
        return self._safety_policy
    
    @property
    def memory(self) -> Any:
        """Memory system (lazy loaded)."""
        if self._memory is None:
            from ..memory.memory import MemorySystem
            self._memory = MemorySystem(self.config.memory)
        return self._memory
    
    @property
    def llm_router(self) -> Any:
        """LLM router (lazy loaded)."""
        if self._llm_router is None:
            from ..llm.router import LLMRouter
            self._llm_router = LLMRouter(self.config.llm)
        return self._llm_router
    
    @property
    def voice_io(self) -> Any:
        """Voice I/O (lazy loaded)."""
        if self._voice_io is None:
            from ..input.voice import VoiceIO
            self._voice_io = VoiceIO(self.config.voice)
        return self._voice_io
    
    @property
    def text_io(self) -> Any:
        """Text I/O (lazy loaded)."""
        if self._text_io is None:
            from ..input.text import TextIO
            self._text_io = TextIO()
        return self._text_io
    
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
        await self._initialize()
        
        try:
            while not self._shutdown:
                await self._interaction_loop()
        finally:
            await self._shutdown()
    
    async def _initialize(self) -> None:
        """Initialize required components."""
        try:
            await self.memory.initialize()
        except Exception:
            pass  # Memory optional
        
        try:
            await self.llm_router.initialize()
        except Exception:
            pass  # LLM optional
    
    async def _shutdown(self) -> None:
        """Cleanup components."""
        pass
    
    async def _interaction_loop(self) -> None:
        """Single interaction cycle."""
        self.set_state(AgentState.IDLE)
        
        # Get input (text-first, voice optional)
        user_input = await self._get_input()
        
        if user_input is None:
            return
        
        # Process input
        await self.process_input(user_input)
    
    async def _get_input(self) -> str | None:
        """Get input from text (primary) or voice (optional)."""
        # Text input (primary)
        try:
            return await self.text_io.get_input()
        except Exception:
            pass
        
        # Voice fallback (optional)
        try:
            return await self.voice_io.listen()
        except Exception:
            pass
        
        return None
    
    # --- Core Processing Flow ---
    
    async def process_input(self, text: str) -> ActionResult:
        """
        Single execution flow:
        Input → Intent → Safety → Planner (optional) → Dispatcher → Action → Result → Memory → Response
        """
        self.set_state(AgentState.PROCESSING)
        
        try:
            # Parse intent
            intent = await self.intent_parser.parse(text)
            
            # Safety check
            safety = self.safety_policy.classify(intent)
            if safety == SafetyLevel.DANGEROUS:
                return ActionResult(
                    success=False,
                    action="blocked",
                    message="Action too dangerous",
                )
            
            # Planning (optional)
            if self.planner.needs_planning(intent):
                result = await self._execute_planned(intent)
            else:
                result = await self._execute_direct(intent)
            
            # Memory
            try:
                await self.memory.store(text, intent, result)
            except Exception:
                pass
            
            # Response
            await self._respond(result)
            
            return result
            
        except Exception as e:
            return ActionResult(
                success=False,
                action="error",
                message=str(e),
                error=str(e),
            )
        
        finally:
            self.set_state(AgentState.IDLE)
    
    async def _execute_direct(self, intent: Intent) -> ActionResult:
        """Execute intent directly."""
        self.set_state(AgentState.EXECUTING)
        return await self.dispatcher.dispatch_async(intent)
    
    async def _execute_planned(self, intent: Intent) -> ActionResult:
        """Execute intent with planning."""
        self.set_state(AgentState.PLANNING)
        # For v2, minimal planning - just direct execution
        return await self._execute_direct(intent)
    
    async def _respond(self, result: ActionResult) -> None:
        """Respond to user."""
        self.set_state(AgentState.SPEAKING)
        
        try:
            await self.voice_io.speak(result.message)
        except Exception:
            # Text fallback
            print(result.message)
    
    def shutdown(self) -> None:
        """Signal shutdown."""
        self._shutdown = True
