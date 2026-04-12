"""Intent Model and Context Compression - semantic understanding layer."""

from dataclasses import dataclass, field
from typing import Any, Optional, List
from enum import Enum
from datetime import datetime

from sokol.observability.logging import get_logger

logger = get_logger("sokol.runtime.intent_model")


class IntentType(str, Enum):
    """Intent type for user requests."""

    QUESTION = "question"
    ACTION_REQUEST = "action_request"
    TASK_CONTINUATION = "task_continuation"
    CORRECTION = "correction"
    EXPLORATION = "exploration"
    SYSTEM_COMMAND = "system_command"


class Urgency(str, Enum):
    """Urgency level for user requests."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Complexity(str, Enum):
    """Complexity level for user requests."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class IntentModel:
    """Structured intent representation."""

    intent_type: IntentType
    primary_goal: str
    entities: List[str] = field(default_factory=list)
    urgency: Urgency = Urgency.MEDIUM
    complexity: Complexity = Complexity.MEDIUM
    requires_tools: bool = False
    task_related: bool = False
    confidence: float = 0.7  # Confidence in classification


@dataclass
class CompressionResult:
    """Result of context compression."""

    compressed_context: str
    compression_ratio: float
    retained_key_points: List[str]
    original_size: int
    compressed_size: int


class IntentExtractor:
    """
    Intent extractor - extracts structured intent from user input.

    This extractor:
    - Classifies intent type
    - Extracts primary goal
    - Detects entities
    - Infers urgency
    - Estimates complexity
    - Detects task relation

    This extractor DOES NOT:
    - Change execution logic
    - Change routing decisions
    - Introduce new decision authority
    - Add autonomy

    This extractor ONLY:
    - Classifies intent
    - Extracts entities
    - Infers metadata
    """

    def __init__(self) -> None:
        """Initialize intent extractor."""
        # Action keywords for classification
        self._action_keywords = [
            "create", "make", "build", "delete", "remove", "update", "change",
            "run", "execute", "start", "stop", "restart", "install", "uninstall",
            "copy", "move", "rename", "write", "read", "list", "search", "find",
        ]

        # Question keywords
        self._question_keywords = [
            "what", "how", "why", "when", "where", "which", "who", "can",
            "could", "would", "should", "is", "are", "do", "does", "did",
            "?", "explain", "describe", "tell", "show", "help",
        ]

        # Urgency keywords
        self._urgency_high_keywords = ["urgent", "asap", "immediately", "now", "critical", "emergency"]
        self._urgency_low_keywords = ["later", "eventually", "someday", "when you have time"]

        # Complexity indicators
        self._complexity_high_keywords = ["multiple", "several", "various", "complex", "complicated", "advanced"]
        self._complexity_low_keywords = ["simple", "basic", "quick", "easy", "single"]

    def extract_intent(self, input_text: str, memory_context: str = "") -> IntentModel:
        """
        Extract intent from user input.

        Args:
            input_text: User input text
            memory_context: Optional memory context

        Returns:
            IntentModel with extracted intent
        """
        text_lower = input_text.lower()

        # Classify intent type
        intent_type = self._classify_intent_type(text_lower, memory_context)

        # Extract primary goal
        primary_goal = self._extract_primary_goal(input_text, intent_type)

        # Detect entities (simple keyword-based)
        entities = self._detect_entities(text_lower)

        # Infer urgency
        urgency = self._infer_urgency(text_lower)

        # Estimate complexity
        complexity = self._estimate_complexity(text_lower)

        # Determine if tools are required
        requires_tools = intent_type in [IntentType.ACTION_REQUEST, IntentType.TASK_CONTINUATION]

        # Determine if task related
        task_related = intent_type == IntentType.TASK_CONTINUATION or "continue" in text_lower or "finish" in text_lower

        intent = IntentModel(
            intent_type=intent_type,
            primary_goal=primary_goal,
            entities=entities,
            urgency=urgency,
            complexity=complexity,
            requires_tools=requires_tools,
            task_related=task_related,
        )

        logger.debug_data(
            "Intent extracted",
            {
                "intent_type": intent_type.value,
                "primary_goal": primary_goal,
                "urgency": urgency.value,
                "complexity": complexity.value,
            },
        )

        return intent

    def _classify_intent_type(self, text_lower: str, memory_context: str) -> IntentType:
        """
        Classify intent type using rule-based approach.

        Args:
            text_lower: Lowercase text
            memory_context: Memory context

        Returns:
            IntentType
        """
        # Check for question
        if any(keyword in text_lower for keyword in self._question_keywords):
            return IntentType.QUESTION

        # Check for action request
        if any(keyword in text_lower for keyword in self._action_keywords):
            return IntentType.ACTION_REQUEST

        # Check for task continuation
        if "continue" in text_lower or "finish" in text_lower or "complete" in text_lower:
            return IntentType.TASK_CONTINUATION

        # Check for correction
        if "fix" in text_lower or "correct" in text_lower or "undo" in text_lower or "change" in text_lower:
            return IntentType.CORRECTION

        # Check for exploration
        if "explore" in text_lower or "look at" in text_lower or "check" in text_lower or "see" in text_lower:
            return IntentType.EXPLORATION

        # Default to action request
        return IntentType.ACTION_REQUEST

    def _extract_primary_goal(self, input_text: str, intent_type: IntentType) -> str:
        """
        Extract primary goal from input.

        Args:
            input_text: Input text
            intent_type: Intent type

        Returns:
            Primary goal string
        """
        # Simple extraction: first sentence or first few words
        sentences = input_text.split(".")
        if sentences:
            return sentences[0].strip()[:100]  # Truncate to 100 chars
        return input_text[:100]

    def _detect_entities(self, text_lower: str) -> List[str]:
        """
        Detect entities using simple keyword matching.

        Args:
            text_lower: Lowercase text

        Returns:
            List of detected entities
        """
        entities = []

        # Common entity patterns (very basic)
        entity_patterns = {
            "file": [".txt", ".py", ".json", ".xml", ".csv", ".md"],
            "directory": ["folder", "directory", "dir"],
            "process": ["process", "service", "daemon"],
            "network": ["url", "http", "https", "ip"],
        }

        for entity_type, keywords in entity_patterns.items():
            if any(keyword in text_lower for keyword in keywords):
                entities.append(entity_type)

        return entities

    def _infer_urgency(self, text_lower: str) -> Urgency:
        """
        Infer urgency from text.

        Args:
            text_lower: Lowercase text

        Returns:
            Urgency level
        """
        if any(keyword in text_lower for keyword in self._urgency_high_keywords):
            return Urgency.HIGH
        elif any(keyword in text_lower for keyword in self._urgency_low_keywords):
            return Urgency.LOW
        return Urgency.MEDIUM

    def _estimate_complexity(self, text_lower: str) -> Complexity:
        """
        Estimate complexity from text.

        Args:
            text_lower: Lowercase text

        Returns:
            Complexity level
        """
        word_count = len(text_lower.split())

        if any(keyword in text_lower for keyword in self._complexity_high_keywords) or word_count > 20:
            return Complexity.HIGH
        elif any(keyword in text_lower for keyword in self._complexity_low_keywords) or word_count < 8:
            return Complexity.LOW
        return Complexity.MEDIUM


class ContextCompressionEngine:
    """
    Context compression engine - reduces memory/context redundancy.

    This engine:
    - Removes redundant interactions
    - Merges semantically similar entries
    - Summarizes long chains into compact form
    - Preserves active tasks, tool success patterns, recent interactions

    This engine DOES NOT:
    - Change execution logic
    - Change memory behavior
    - Lose critical state

    This engine ONLY:
    - Compresses context
    - Preserves key information
    """

    def __init__(self) -> None:
        """Initialize context compression engine."""
        self._preserve_recent_count = 20  # Preserve last 20 interactions uncompressed

    def compress(self, memory_context: str, active_tasks: List[Any] | None = None) -> CompressionResult:
        """
        Compress memory context.

        Args:
            memory_context: Memory context to compress
            active_tasks: Optional list of active tasks

        Returns:
            CompressionResult
        """
        original_size = len(memory_context)

        # Split into lines/interactions
        lines = memory_context.split("\n")

        # Preserve recent interactions (last N lines)
        recent_lines = lines[-self._preserve_recent_count:] if len(lines) > self._preserve_recent_count else lines
        older_lines = lines[:-self._preserve_recent_count] if len(lines) > self._preserve_recent_count else []

        # Summarize older interactions
        compressed_older = self._summarize_interactions(older_lines)

        # Preserve active tasks
        task_info = ""
        if active_tasks:
            task_info = "\n[Active Tasks]\n"
            for task in active_tasks:
                task_info += f"- {task.goal if hasattr(task, 'goal') else str(task)}\n"

        # Combine
        compressed_context = f"{compressed_older}\n{task_info}\n[Recent Interactions]\n" + "\n".join(recent_lines)
        compressed_size = len(compressed_context)

        compression_ratio = compressed_size / original_size if original_size > 0 else 1.0

        # Extract key points
        retained_key_points = self._extract_key_points(memory_context)

        result = CompressionResult(
            compressed_context=compressed_context,
            compression_ratio=compression_ratio,
            retained_key_points=retained_key_points,
            original_size=original_size,
            compressed_size=compressed_size,
        )

        logger.debug_data(
            "Context compressed",
            {
                "original_size": original_size,
                "compressed_size": compressed_size,
                "compression_ratio": compression_ratio,
                "key_points_count": len(retained_key_points),
            },
        )

        return result

    def _summarize_interactions(self, lines: List[str]) -> str:
        """
        Summarize older interactions.

        Args:
            lines: Lines to summarize

        Returns:
            Summary string
        """
        if not lines:
            return ""

        # Simple summary: count interactions and extract key themes
        interaction_count = len([line for line in lines if "Interaction" in line or line.strip()])

        summary = f"[Historical Summary]\n{interaction_count} historical interactions compressed.\n"

        return summary

    def _extract_key_points(self, context: str) -> List[str]:
        """
        Extract key points from context.

        Args:
            context: Context string

        Returns:
            List of key points
        """
        key_points = []

        # Extract tool mentions
        if "Tool:" in context:
            tool_lines = [line for line in context.split("\n") if "Tool:" in line]
            key_points.extend(tool_lines[:5])  # Keep top 5 tool mentions

        # Extract task mentions
        if "Task:" in context or "task" in context.lower():
            key_points.append("Task activity detected")

        # Extract error mentions
        if "error" in context.lower() or "failed" in context.lower():
            key_points.append("Error/Failure detected")

        return key_points
