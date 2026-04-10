"""Unified Intent Router - single decision pipeline."""

from typing import Any
from dataclasses import dataclass
from enum import Enum

from sokol.observability.logging import get_logger
from sokol.runtime.intent import RuleBasedIntentHandler
from sokol.integrations.llm import LLMManager, LLMMessage
from sokol.core.config import get_config

logger = get_logger("sokol.runtime.router")


class DecisionSource(str, Enum):
    """Source of the decision."""

    LLM = "llm"
    RULE_BASED = "rule_based"
    REJECTED = "rejected"


@dataclass
class ProposedAction:
    """Proposed action from intent router."""

    source: DecisionSource
    action_type: str  # tool_call, final_answer, clarification
    tool: str | None = None
    args: dict[str, Any] | None = None
    text: str | None = None
    confidence: float = 1.0


class IntentRouter:
    """
    Unified intent router with priority system.

    Priority: LLM > Rule-Based > Rejected

    Only proposes actions, does NOT execute.
    All proposals must pass through Safety layer before execution.
    """

    def __init__(self) -> None:
        config = get_config()

        self._llm_manager = LLMManager(config)
        self._rule_handler = RuleBasedIntentHandler()

        # Priority: LLM first, then rule-based
        self._priority = [DecisionSource.LLM, DecisionSource.RULE_BASED]

    def route(self, user_input: str) -> ProposedAction:
        """
        Route user input through decision pipeline.

        Returns proposed action from highest priority source.
        """
        logger.info("Routing input through intent router")

        # Try each source in priority order
        for source in self._priority:
            if source == DecisionSource.LLM:
                action = self._try_llm(user_input)
                if action:
                    logger.info_data("LLM proposed action", {"action": action.action_type})
                    return action

            elif source == DecisionSource.RULE_BASED:
                action = self._try_rule_based(user_input)
                if action:
                    logger.info_data("Rule-based proposed action", {"action": action.action_type})
                    return action

        # All sources failed
        logger.warning("No source could process input")
        return ProposedAction(
            source=DecisionSource.REJECTED,
            action_type="final_answer",
            text="I couldn't understand that command. Type 'help' for available commands.",
        )

    def _try_llm(self, user_input: str) -> ProposedAction | None:
        """Try to get action from LLM."""
        import json

        try:
            # Build system prompt
            system_prompt = self._build_system_prompt()

            # Build messages
            messages = [
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=user_input),
            ]

            # Call LLM
            logger.info("Calling LLM for routing")
            response = self._llm_manager.complete(messages, use_fallback=True)

            # Parse JSON response
            try:
                parsed = json.loads(response.content.strip())

                if "type" not in parsed:
                    logger.warning("LLM response missing type field")
                    return None

                # Convert to ProposedAction
                action_type = parsed["type"]

                if action_type == "tool_call":
                    return ProposedAction(
                        source=DecisionSource.LLM,
                        action_type="tool_call",
                        tool=parsed.get("tool"),
                        args=parsed.get("args", {}),
                        confidence=0.9,
                    )
                elif action_type == "final_answer":
                    return ProposedAction(
                        source=DecisionSource.LLM,
                        action_type="final_answer",
                        text=parsed.get("text"),
                        confidence=0.9,
                    )
                elif action_type == "clarification":
                    return ProposedAction(
                        source=DecisionSource.LLM,
                        action_type="clarification",
                        text=parsed.get("question"),
                        confidence=0.9,
                    )

            except json.JSONDecodeError as e:
                logger.warning_data("LLM response not valid JSON", {"error": str(e)})
                return None

        except Exception as e:
            logger.error_data("LLM routing failed", {"error": str(e)})
            return None

    def _try_rule_based(self, user_input: str) -> ProposedAction | None:
        """Try to get action from rule-based handler."""
        try:
            intent = self._rule_handler.parse_intent(user_input)

            if intent and intent.tool:
                # Convert to ProposedAction
                return ProposedAction(
                    source=DecisionSource.RULE_BASED,
                    action_type="tool_call",
                    tool=intent.tool,
                    args=intent.args,
                    confidence=intent.confidence,
                )

            # Check for help command
            if "help" in user_input.lower():
                help_text = self._rule_handler.get_help()
                return ProposedAction(
                    source=DecisionSource.RULE_BASED,
                    action_type="final_answer",
                    text=help_text,
                    confidence=1.0,
                )

        except Exception as e:
            logger.error_data("Rule-based routing failed", {"error": str(e)})

        return None

    def _build_system_prompt(self) -> str:
        """Build system prompt for LLM routing."""
        return """You are a Windows AI assistant.

You MUST respond with valid JSON only:

1. Tool Call (when you need to execute a tool):
{
  "type": "tool_call",
  "tool": "tool_name",
  "args": {"param": "value"}
}

2. Final Answer (when no tool needed):
{
  "type": "final_answer",
  "text": "Your response"
}

3. Clarification (when you need more info):
{
  "type": "clarification",
  "question": "Your question"
}

IMPORTANT: Always return valid JSON. Never include text outside the JSON object."""
