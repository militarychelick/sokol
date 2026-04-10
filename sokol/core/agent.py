"""
Sokol v2 - Main agent orchestration (LLM-based)
"""

from __future__ import annotations

import asyncio
from enum import Enum
from typing import Any, Callable

from .config import Config


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
    Sokol Agent - LLM-powered voice assistant.
    
    Execution flow:
    Wake Word → Voice Input → LLM (Intent + Planning) → Safety → Execution → Memory → Response
    """
    
    def __init__(self, config: Config) -> None:
        self.config = config
        self.state = AgentState.IDLE
        
        # Layer references (lazy loaded)
        self._llm_client: Any = None
        self._llm_reasoning: Any = None
        self._llm_router: Any = None
        self._voice_io: Any = None
        self._text_io: Any = None
        self._uia: Any = None
        self._api: Any = None
        self._hotkeys: Any = None
        self._safety_checker: Any = None
        self._memory_store: Any = None
        self._user_profile: Any = None
        
        # Callbacks for state changes
        self._state_callbacks: list[Callable[[AgentState], None]] = []
        
        # Shutdown flag
        self._shutdown = False
    
    # --- Layer Properties (lazy loading) ---
    
    @property
    def llm_client(self) -> Any:
        """LLM client (lazy loaded)."""
        if self._llm_client is None:
            from ..brain.llm import LLMClient
            self._llm_client = LLMClient(self.config)
        return self._llm_client
    
    @property
    def llm_reasoning(self) -> Any:
        """LLM reasoning (lazy loaded)."""
        if self._llm_reasoning is None:
            from ..brain.reasoning import LLMReasoning
            self._llm_reasoning = LLMReasoning(self.config, self.llm_client)
        return self._llm_reasoning
    
    @property
    def llm_router(self) -> Any:
        """LLM router (lazy loaded)."""
        if self._llm_router is None:
            from ..brain.router import LLMRouter
            self._llm_router = LLMRouter(self.config, self.llm_client)
        return self._llm_router
    
    @property
    def voice_io(self) -> Any:
        """Voice I/O (lazy loaded)."""
        if self._voice_io is None:
            from ..input.voice import VoiceIO
            self._voice_io = VoiceIO(self.config)
        return self._voice_io
    
    @property
    def text_io(self) -> Any:
        """Text I/O (lazy loaded)."""
        if self._text_io is None:
            from ..input.text import TextIO
            self._text_io = TextIO()
        return self._text_io
    
    @property
    def uia(self) -> Any:
        """UI Automation (lazy loaded)."""
        if self._uia is None:
            from ..execution.uia import UIA
            self._uia = UIA()
        return self._uia
    
    @property
    def api(self) -> Any:
        """API integrations (lazy loaded)."""
        if self._api is None:
            from ..execution.api import API
            self._api = API()
        return self._api
    
    @property
    def hotkeys(self) -> Any:
        """Hotkeys (lazy loaded)."""
        if self._hotkeys is None:
            from ..execution.hotkeys import Hotkeys
            self._hotkeys = Hotkeys()
        return self._hotkeys
    
    @property
    def safety_checker(self) -> Any:
        """Safety checker (lazy loaded)."""
        if self._safety_checker is None:
            from ..safety.checker import SafetyChecker
            self._safety_checker = SafetyChecker(self.config)
        return self._safety_checker
    
    @property
    def memory_store(self) -> Any:
        """Memory store (lazy loaded)."""
        if self._memory_store is None:
            from ..memory.store import MemoryStore
            self._memory_store = MemoryStore(self.config)
        return self._memory_store
    
    @property
    def user_profile(self) -> Any:
        """User profile (lazy loaded)."""
        if self._user_profile is None:
            from ..memory.profile import UserProfile
            self._user_profile = UserProfile(self.config)
        return self._user_profile
    
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
            await self.memory_store.initialize()
        except Exception:
            pass  # Memory optional
        
        try:
            await self.user_profile.load()
        except Exception:
            pass  # Profile optional
        
        try:
            await self.voice_io.initialize()
        except Exception:
            pass  # Voice optional
    
    async def _shutdown(self) -> None:
        """Cleanup components."""
        try:
            await self.llm_client.shutdown()
        except Exception:
            pass
        try:
            await self.voice_io.shutdown()
        except Exception:
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
    
    async def process_input(self, text: str) -> dict[str, Any]:
        """
        LLM-based execution flow:
        Input → LLM (Intent + Planning) → Safety → Execution → Memory → Response
        """
        self.set_state(AgentState.PROCESSING)
        
        try:
            # LLM understanding
            intent = await self.llm_reasoning.understand_command(text)
            
            # Safety check
            safety_level = self.safety_checker.check_action(
                intent.get("action", ""), intent.get("params", {})
            )
            
            if self.safety_checker.requires_confirmation(safety_level):
                # For MVP, auto-approve safe actions
                if safety_level != "dangerous":
                    pass
                else:
                    return {
                        "success": False,
                        "action": intent.get("action", ""),
                        "message": "Action too dangerous, confirmation required",
                    }
            
            # Execute action
            result = await self._execute_action(intent)
            
            # Memory
            try:
                await self.memory_store.store_interaction(text, intent, result)
            except Exception:
                pass
            
            # Response
            await self._respond(result)
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "action": "error",
                "message": str(e),
                "error": str(e),
            }
        
        finally:
            self.set_state(AgentState.IDLE)
    
    async def _execute_action(self, intent: dict[str, Any]) -> dict[str, Any]:
        """Execute action based on LLM intent."""
        self.set_state(AgentState.EXECUTING)
        
        action = intent.get("action", "")
        params = intent.get("params", {})
        
        try:
            if action == "launch_app":
                app = params.get("app", "")
                success = self.uia.launch_app(app)
                return {
                    "success": success,
                    "action": action,
                    "message": f"Launched: {app}" if success else f"Failed to launch: {app}",
                }
            elif action == "open_url":
                url = params.get("url", "")
                success = self.api.open_url(url)
                return {
                    "success": success,
                    "action": action,
                    "message": f"Opened: {url}" if success else f"Failed to open: {url}",
                }
            elif action == "press_hotkey":
                keys = params.get("keys", [])
                success = self.hotkeys.press(keys)
                return {
                    "success": success,
                    "action": action,
                    "message": f"Pressed: {'+'.join(keys)}" if success else "Failed to press keys",
                }
            elif action == "manage_window":
                window_action = params.get("window_action", "")
                if window_action == "minimize":
                    success = self.uia.minimize_window()
                elif window_action == "maximize":
                    success = self.uia.maximize_window()
                elif window_action == "close":
                    success = self.uia.close_window()
                else:
                    success = False
                return {
                    "success": success,
                    "action": action,
                    "message": f"Window {window_action}" if success else "Failed window action",
                }
            elif action == "chat":
                # Chat response
                message = intent.get("params", {}).get("message", "")
                response = await self.llm_router.route(message, system_prompt="Ты — Сокол, дружелюбный помощник.")
                return {
                    "success": True,
                    "action": action,
                    "message": response,
                }
            else:
                return {
                    "success": False,
                    "action": action,
                    "message": f"Unknown action: {action}",
                }
        except Exception as e:
            return {
                "success": False,
                "action": action,
                "message": f"Execution failed: {str(e)}",
                "error": str(e),
            }
    
    async def _respond(self, result: dict[str, Any]) -> None:
        """Respond to user."""
        self.set_state(AgentState.SPEAKING)
        
        message = result.get("message", "")
        
        try:
            await self.voice_io.speak(message)
        except Exception:
            # Text fallback
            print(message)
    
    def shutdown(self) -> None:
        """Signal shutdown."""
        self._shutdown = True
