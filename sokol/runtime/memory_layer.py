"""Memory Layer - long-term memory and context retrieval for Sokol."""

from dataclasses import dataclass, field
from typing import Any, Optional, List
from datetime import datetime

from sokol.observability.logging import get_logger
from sokol.runtime.user_model import UserModel

logger = get_logger("sokol.runtime.memory_layer")


@dataclass
class MemoryInteraction:
    """Single interaction stored in memory."""

    timestamp: str
    source: str  # voice/ui
    input_text: str
    response_text: str
    tool_used: Optional[str] = None
    tool_success: bool = True
    risk_level: Optional[str] = None
    mode: str = "standard"
    voice_confidence: Optional[float] = None
    screen_context: Optional[dict] = None
    tool_decision: Optional[dict] = None


@dataclass
class MemoryContext:
    """Retrieved context for current interaction."""

    relevant_interactions: List[dict[str, Any]] = field(default_factory=list)
    tool_memory: dict[str, float] = field(default_factory=dict)
    user_bias: dict[str, Any] = field(default_factory=dict)
    summary: str = ""


class MemoryLayer:
    """
    Memory Layer - long-term memory and context retrieval.

    This layer:
    - Stores interactions in short-term buffer
    - Maintains long-term compressed memory
    - Tracks tool success patterns per user
    - Retrieves relevant context for interactions

    This layer DOES NOT:
    - Change execution logic
    - Change tool execution
    - Change router or control logic
    - Introduce autonomy
    - Store sensitive data (privacy-safe)
    """

    def __init__(self, user_model: UserModel, tool_registry: Optional[Any] = None, task_manager: Optional[Any] = None, context_compression_engine: Optional[Any] = None) -> None:
        """
        Initialize memory layer.

        Args:
            user_model: UserModel instance to update
            tool_registry: Optional ToolRegistry for capability group tracking
            task_manager: Optional TaskManager for task persistence
            context_compression_engine: Optional ContextCompressionEngine for context compression
        """
        self._user_model = user_model
        self._tool_registry = tool_registry
        self._task_manager = task_manager
        self._context_compression_engine = context_compression_engine

        # Short-term memory buffer (last N interactions)
        self._short_term_buffer: List[MemoryInteraction] = []
        self._buffer_size = 20  # Keep last 20 interactions

        # Long-term memory summary (compressed)
        self._long_term_summary = ""

        # Tool memory (success/failure patterns)
        self._tool_memory: dict[str, dict[str, Any]] = {}

        # Capability group memory (track usage by capability group)
        self._capability_memory: dict[str, dict[str, Any]] = {}

        # Task memory (track active tasks)
        self._task_memory: dict[str, dict[str, Any]] = {}

    def store_interaction(
        self,
        source: str,
        input_text: str,
        response_text: str,
        tool_used: Optional[str] = None,
        tool_success: bool = True,
        risk_level: Optional[str] = None,
        mode: str = "standard",
        voice_confidence: Optional[float] = None,
        screen_context: Optional[dict] = None,
        tool_decision: Optional[dict] = None,
    ) -> None:
        """
        Store interaction in memory.

        Args:
            source: Interaction source (voice/ui)
            input_text: User input text
            response_text: System response text
            tool_used: Tool name if any
            tool_success: Whether tool succeeded
            risk_level: Risk level of action
            mode: Response mode used
            voice_confidence: Voice transcription confidence (if voice input)
            screen_context: Screen context metadata (if screen input)
            tool_decision: Tool selection decision metadata
        """
        # Create interaction record
        interaction = MemoryInteraction(
            timestamp=datetime.now().isoformat(),
            source=source,
            input_text=input_text[:200],  # Compress input
            response_text=response_text[:200],  # Compress response
            tool_used=tool_used,
            tool_success=tool_success,
            risk_level=risk_level,
            mode=mode,
        )

        # Add to short-term buffer
        self._short_term_buffer.append(interaction)

        # Maintain buffer size
        if len(self._short_term_buffer) > self._buffer_size:
            self._short_term_buffer.pop(0)

        # Update tool memory
        if tool_used:
            if tool_used not in self._tool_memory:
                self._tool_memory[tool_used] = {
                    "success_count": 0,
                    "failure_count": 0,
                    "last_used": interaction.timestamp,
                }

            if tool_success:
                self._tool_memory[tool_used]["success_count"] += 1
            else:
                self._tool_memory[tool_used]["failure_count"] += 1

            self._tool_memory[tool_used]["last_used"] = interaction.timestamp

            # Update capability group memory (if tool_registry is available)
            if self._tool_registry:
                capability_tags = self._tool_registry.get_capability_tags(tool_used)
                for tag in capability_tags:
                    if tag not in self._capability_memory:
                        self._capability_memory[tag] = {
                            "success_count": 0,
                            "failure_count": 0,
                            "usage_count": 0,
                        }

                    self._capability_memory[tag]["usage_count"] += 1
                    if tool_success:
                        self._capability_memory[tag]["success_count"] += 1
                    else:
                        self._capability_memory[tag]["failure_count"] += 1

        # Update task memory (if task_manager is available)
        if self._task_manager:
            active_task = self._task_manager.get_active_task()
            if active_task:
                task_id = active_task.task_id
                if task_id not in self._task_memory:
                    self._task_memory[task_id] = {
                        "goal": active_task.goal,
                        "status": active_task.status.value,
                        "interactions": 0,
                    }

                self._task_memory[task_id]["interactions"] += 1
                self._task_memory[task_id]["status"] = active_task.status.value

        # Update user model
        self._user_model.update_from_interaction(
            source=source,
            mode=mode,
            tool_used=tool_used,
            tool_success=tool_success,
            risk_level=risk_level,
        )

        # Update long-term summary periodically
        if len(self._short_term_buffer) % 5 == 0:
            self._compress_long_term_memory()

        logger.debug_data(
            "Interaction stored in memory",
            {
                "source": source,
                "tool_used": tool_used,
                "buffer_size": len(self._short_term_buffer),
            },
        )

    def retrieve_context(self, query: str, limit: int = 5) -> MemoryContext:
        """
        Retrieve relevant context for a query.

        Args:
            query: Query string
            limit: Maximum number of interactions to return

        Returns:
            MemoryContext with relevant interactions and summary
        """
        # Simple retrieval: return last N interactions (semantic matching would be better)
        relevant_interactions = self._short_term_buffer[-limit:] if len(self._short_term_buffer) > limit else self._short_term_buffer

        # Build summary
        summary = self._build_summary()

        # Compress context if compression engine is available
        if self._context_compression_engine and summary:
            active_tasks = [self._task_manager.get_active_task()] if self._task_manager else None
            compression_result = self._context_compression_engine.compress(summary, active_tasks)
            summary = compression_result.compressed_context

        # Extract tool memory for context
        tool_memory = self._tool_memory.copy()

        return MemoryContext(
            relevant_interactions=relevant_interactions,
            summary=summary,
            tool_memory=tool_memory,
            user_bias=self._user_model.get_bias(),
        )

    def update_user_model(self) -> None:
        """
        Update user model from memory.

        This is called periodically to ensure user model is up-to-date.
        """
        # User model is already updated in store_interaction
        # This is a hook for future batch updates
        pass

    def _build_summary(self) -> str:
        """
        Build summary from short-term buffer.

        Returns:
            Summary string
        """
        if not self._short_term_buffer:
            return ""

        # Count interaction types
        voice_count = sum(1 for i in self._short_term_buffer if i.source == "voice")
        ui_count = sum(1 for i in self._short_term_buffer if i.source == "ui")
        tool_count = sum(1 for i in self._short_term_buffer if i.tool_used)

        # Get summary from user model
        user_summary = self._user_model.summarize_history()

        summary = f"{user_summary}. Последние: {len(self._short_term_buffer)} взаимодействий (голос: {voice_count}, UI: {ui_count}, инструменты: {tool_count})."
        return summary

    def _compress_long_term_memory(self) -> None:
        """Compress short-term buffer into long-term summary."""
        if not self._short_term_buffer:
            return

        # Count interaction types
        voice_count = sum(1 for i in self._short_term_buffer if i.source == "voice")
        ui_count = sum(1 for i in self._short_term_buffer if i.source == "ui")
        tool_count = sum(1 for i in self._short_term_buffer if i.tool_used)

        # Get summary from user model
        user_summary = self._user_model.summarize_history()

        self._long_term_summary = f"{user_summary}. Последние: {len(self._short_term_buffer)} взаимодействий (голос: {voice_count}, UI: {ui_count}, инструменты: {tool_count})."

        logger.debug_data(
            "Long-term memory compressed",
            {"summary_length": len(self._long_term_summary)},
        )

    def get_tool_success_rate(self, tool_name: str) -> float:
        """
        Get success rate for a specific tool.

        Args:
            tool_name: Tool name

        Returns:
            Success rate (0.0 - 1.0)
        """
        if tool_name not in self._tool_memory:
            return 0.5

        tool_data = self._tool_memory[tool_name]
        success_count = tool_data["success_count"]
        failure_count = tool_data["failure_count"]
        total = success_count + failure_count

        if total == 0:
            return 0.5

        return success_count / total

    def clear_short_term_memory(self) -> None:
        """Clear short-term memory buffer."""
        self._short_term_buffer.clear()
        logger.debug("Short-term memory cleared")

    def get_memory_stats(self) -> dict[str, Any]:
        """
        Get memory statistics.

        Returns:
            Dictionary with memory stats
        """
        return {
            "total_interactions": len(self._short_term_buffer),
            "total_tools": len(self._tool_memory),
            "total_capabilities": len(self._capability_memory),
            "total_tasks": len(self._task_memory),
            "buffer_size": self._buffer_size,
            "long_term_summary_length": len(self._long_term_summary),
        }

    def get_active_task_context(self) -> dict[str, Any] | None:
        """
        Get active task context from memory.

        Returns:
            Active task context or None
        """
        # PHASE 2 FIX: Return empty dict instead of None (no None runtime)
        if not self._task_manager:
            return {}

        active_task = self._task_manager.get_active_task()
        if not active_task:
            return {}

        # Get task summary from memory
        task_memory = self._task_memory.get(active_task.task_id, {})

        return {
            "task_id": active_task.task_id,
            "goal": active_task.goal,
            "status": active_task.status.value,
            "current_step": active_task.current_step,
            "total_steps": len(active_task.steps),
            "risk_level": active_task.risk_level,
            "interactions": task_memory.get("interactions", 0),
        }
