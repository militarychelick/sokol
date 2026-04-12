"""Tool Intelligence Engine - decision support for tool selection."""

from dataclasses import dataclass
from typing import Any, Optional
from enum import Enum

from sokol.observability.logging import get_logger

logger = get_logger("sokol.runtime.tool_intelligence")


class ToolConfidence(str, Enum):
    """Tool confidence level."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ToolScore:
    """Tool score with reasons."""

    tool: str
    score: float
    reasons: list[str]
    confidence: ToolConfidence = ToolConfidence.MEDIUM


class ToolIntelligenceEngine:
    """
    Tool intelligence engine - evaluates and ranks tools before execution.

    This is a decision support layer that:
    - Scores tools based on multiple factors
    - Ranks tools by score
    - Selects best tool with fallback to LLM choice

    This layer DOES NOT:
    - Change execution logic
    - Change tool execution
    - Block tools (only suggests)
    """

    def __init__(self, tool_registry: Optional[Any] = None, threshold: float = 0.55) -> None:
        """
        Initialize tool intelligence engine.

        Args:
            tool_registry: Optional ToolRegistry for semantic tool graph
            threshold: Minimum score threshold for tool selection
        """
        self._threshold = threshold
        self._tool_success_history: dict[str, list[bool]] = {}
        self._tool_registry = tool_registry

    def score_tool(
        self,
        tool_name: str,
        intent: str,
        context: str = "",
        stability_score: float = 1.0,
    ) -> ToolScore:
        """
        Score a tool for given intent and context.

        Args:
            tool_name: Name of tool to score
            intent: User intent/action description
            context: Memory context string
            stability_score: Stability score from stability layer

        Returns:
            ToolScore with score and reasons
        """
        score = 0.0
        reasons = []

        # 1. Match score (keyword match and semantic similarity)
        match_score = self._compute_match_score(tool_name, intent)
        score += match_score * 0.4
        if match_score > 0.5:
            reasons.append("High intent match")

        # 2. Memory boost (tool used successfully in similar past contexts)
        memory_boost = self._compute_memory_boost(tool_name, context)
        score += memory_boost * 0.2
        if memory_boost > 0:
            reasons.append("Past success in similar context")

        # 3. Stability boost (tool has high success rate)
        stability_boost = self._compute_stability_boost(tool_name, stability_score)
        score += stability_boost * 0.2
        if stability_boost > 0:
            reasons.append("High stability score")

        # 4. Failure penalty (tool previously failed often)
        failure_penalty = self._compute_failure_penalty(tool_name)
        score -= failure_penalty * 0.2
        if failure_penalty > 0.3:
            reasons.append("High past failure rate")

        # 5. Context mismatch penalty
        context_mismatch = self._compute_context_mismatch(tool_name, intent, context)
        score -= context_mismatch * 0.1
        if context_mismatch > 0.2:
            reasons.append("Context mismatch")

        # Clamp to 0.0 - 1.0
        score = max(0.0, min(1.0, score))

        return ToolScore(tool=tool_name, score=score, reasons=reasons)

    def rank_tools(
        self,
        tools: list[str],
        intent: str,
        context: str = "",
        stability_score: float = 1.0,
        tool_success_scores: dict[str, float] | None = None,
    ) -> list[ToolScore]:
        """
        Rank tools by score for given intent and context.

        Args:
            tools: List of tool names to rank
            intent: User intent
            context: Additional context
            stability_score: Current stability score
            tool_success_scores: Optional tool success scores from memory (memory influence)

        Returns:
            List of ToolScore objects, sorted by score descending
        """
        scored = []
        for tool in tools:
            score = self.score_tool(tool, intent, context, stability_score)

            # Apply memory influence (tool success scores)
            if tool_success_scores and tool in tool_success_scores:
                memory_score = tool_success_scores[tool]
                # Blend scores: 80% intelligence, 20% memory
                score.score = 0.8 * score.score + 0.2 * memory_score
                score.reasons.append(f"Memory: success rate {memory_score:.2f}")

            # Apply tool registry influence (capability matching)
            if self._tool_registry:
                capability_tags = self._tool_registry.get_capability_tags(tool)
                if capability_tags:
                    # Check if intent matches capability tags
                    intent_lower = intent.lower()
                    for tag in capability_tags:
                        if tag.lower() in intent_lower:
                            score.score += 0.1
                            score.reasons.append(f"Registry: capability match '{tag}'")

                    # Detect conflicts with other tools in the list
                    conflicts = self._tool_registry.detect_conflicts(tool)
                    for other_tool in tools:
                        if other_tool in conflicts:
                            score.score -= 0.2
                            score.reasons.append(f"Registry: conflict with '{other_tool}'")

            scored.append(score)

        # Sort by score descending
        scored.sort(key=lambda x: x.score, reverse=True)
        return scored

    def select_best_tool(
        self,
        ranked_tools: list[ToolScore],
        fallback_tool: str | None = None,
    ) -> str:
        """
        Select best tool from ranked list.

        Args:
            ranked_tools: List of ranked tools
            fallback_tool: Fallback tool if confidence is low

        Returns:
            Selected tool name
        """
        if not ranked_tools:
            return fallback_tool or ""

        best = ranked_tools[0]

        # Check if score meets threshold
        if best.score >= self._threshold:
            logger.info_data(
                "Tool selected by intelligence engine",
                {"tool": best.tool, "score": best.score, "reasons": best.reasons},
            )
            return best.tool
        else:
            logger.info_data(
                "Tool intelligence below threshold, using fallback",
                {"tool": best.tool, "score": best.score, "threshold": self._threshold},
            )
            return fallback_tool or best.tool

    def record_tool_result(self, tool_name: str, success: bool) -> None:
        """
        Record tool execution result for future scoring.

        Args:
            tool_name: Name of tool executed
            success: Whether execution was successful
        """
        if tool_name not in self._tool_success_history:
            self._tool_success_history[tool_name] = []

        self._tool_success_history[tool_name].append(success)

        # Keep only last 50 results
        if len(self._tool_success_history[tool_name]) > 50:
            self._tool_success_history[tool_name] = self._tool_success_history[tool_name][-50:]

    def _compute_match_score(self, tool_name: str, intent: str) -> float:
        """Compute match score based on keyword and semantic similarity."""
        tool_lower = tool_name.lower()
        intent_lower = intent.lower()

        # Keyword match
        tool_words = tool_lower.replace("_", " ").split()
        intent_words = intent_lower.split()

        matches = sum(1 for word in tool_words if word in intent_words)
        keyword_score = matches / max(len(tool_words), 1)

        # Simple semantic similarity (string overlap)
        overlap = set(tool_words) & set(intent_words)
        semantic_score = len(overlap) / max(len(set(tool_words)), 1)

        return (keyword_score + semantic_score) / 2

    def _compute_memory_boost(self, tool_name: str, context: str) -> float:
        """Compute memory boost based on past success in similar contexts."""
        if tool_name not in self._tool_success_history:
            return 0.0

        history = self._tool_success_history[tool_name]
        if not history:
            return 0.0

        # Success rate
        success_rate = sum(history) / len(history)

        # Boost based on success rate
        return success_rate if success_rate > 0.7 else 0.0

    def _compute_stability_boost(self, tool_name: str, stability_score: float) -> float:
        """Compute stability boost based on stability score."""
        # High stability score gives boost
        return stability_score if stability_score > 0.8 else 0.0

    def _compute_failure_penalty(self, tool_name: str) -> float:
        """Compute failure penalty based on past failure rate."""
        if tool_name not in self._tool_success_history:
            return 0.0

        history = self._tool_success_history[tool_name]
        if not history:
            return 0.0

        # Failure rate
        failure_rate = 1.0 - (sum(history) / len(history))

        # Penalty based on failure rate
        return failure_rate

    def _compute_context_mismatch(self, tool_name: str, intent: str, context: str) -> float:
        """Compute context mismatch penalty."""
        # Simple heuristic: if tool mentions specific domain but context doesn't
        tool_lower = tool_name.lower()
        context_lower = context.lower()

        # Check for domain-specific tools
        file_domains = ["file", "document", "text"]
        app_domains = ["app", "program", "launch"]
        system_domains = ["system", "process", "info"]

        if any(d in tool_lower for d in file_domains):
            # File tool but no file-related context
            if not any(d in context_lower for d in file_domains):
                return 0.3

        if any(d in tool_lower for d in app_domains):
            # App tool but no app-related context
            if not any(d in context_lower for d in app_domains):
                return 0.3

        return 0.0

    def reset_history(self) -> None:
        """Reset tool success history."""
        self._tool_success_history.clear()
