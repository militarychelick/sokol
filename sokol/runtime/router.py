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
class ToolChainStep:
    """Single step in a tool chain."""

    tool: str
    params: dict[str, Any]
    condition: dict[str, Any] | None = None  # Minimal condition for branching
    next_step_override: int | None = None  # Override next step index (for branching)


@dataclass
class ToolChain:
    """Lightweight tool chain representation."""

    steps: list[ToolChainStep]

    def __post_init__(self) -> None:
        """Validate chain constraints."""
        if len(self.steps) > 3:
            raise ValueError(f"Tool chain exceeds maximum of 3 steps: {len(self.steps)}")

    @property
    def step_count(self) -> int:
        """Return number of steps in chain."""
        return len(self.steps)


class ConditionEvaluator:
    """
    Minimal condition evaluator for tool chain branching.

    Supports:
    - success / failure of previous tool
    - presence of data
    - simple value checks (string contains / empty / not empty)
    """

    def evaluate(
        self,
        condition: dict[str, Any] | None,
        tool_result: Any,
    ) -> tuple[bool, str]:
        """
        Evaluate condition against tool result.

        Args:
            condition: Condition dictionary
            tool_result: Result from previous tool execution

        Returns:
            (condition_met, reason) tuple
        """
        if not condition:
            return True, "no_condition"

        condition_type = condition.get("type")

        if condition_type == "success":
            # Condition: previous tool succeeded
            success = tool_result.success if hasattr(tool_result, "success") else True
            return success, f"success_check: {success}"

        elif condition_type == "failure":
            # Condition: previous tool failed
            success = tool_result.success if hasattr(tool_result, "success") else True
            return not success, f"failure_check: {not success}"

        elif condition_type == "data_present":
            # Condition: data is present in result
            data = tool_result.data if hasattr(tool_result, "data") else None
            has_data = data is not None and data != {}
            return has_data, f"data_present: {has_data}"

        elif condition_type == "data_empty":
            # Condition: data is empty or None
            data = tool_result.data if hasattr(tool_result, "data") else None
            is_empty = data is None or data == {}
            return is_empty, f"data_empty: {is_empty}"

        elif condition_type == "contains":
            # Condition: string contains substring
            substring = condition.get("value", "")
            result_str = str(tool_result) if tool_result else ""
            contains = substring in result_str
            return contains, f"contains '{substring}': {contains}"

        elif condition_type == "equals":
            # Condition: value equals expected
            expected = condition.get("value", "")
            result_str = str(tool_result) if tool_result else ""
            equals = result_str == expected
            return equals, f"equals '{expected}': {equals}"

        else:
            # Unknown condition type - treat as not met
            return False, f"unknown_condition_type: {condition_type}"


@dataclass
class ProposedAction:
    """Proposed action from intent router."""

    source: DecisionSource
    action_type: str  # tool_call, final_answer, clarification
    tool: str | None = None
    args: dict[str, Any] | None = None
    text: str | None = None
    confidence: float = 1.0
    tool_chain: ToolChain | None = None  # Optional tool chain for sequential execution


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

        # All sources failed - return simple response instead of REJECTED
        logger.warning("No source could process input, returning simple response")
        return ProposedAction(
            source=DecisionSource.RULE_BASED,
            action_type="final_answer",
            text=f"Я получил ваш запрос: '{user_input}'. LLM недоступен, поэтому я не могу обработать это сообщение. Пожалуйста, запустите Ollama или настройте Google AI API.",
            confidence=1.0,
        )

    def _try_llm(self, user_input: str) -> ProposedAction | None:
        """Try to get action from LLM with validation and retry."""
        import json

        max_retries = 2
        retry_count = 0

        while retry_count < max_retries:
            try:
                # Build system prompt
                system_prompt = self._build_system_prompt()

                # Build messages
                messages = [
                    LLMMessage(role="system", content=system_prompt),
                    LLMMessage(role="user", content=user_input),
                ]

                # Call LLM
                logger.info_data("Calling LLM for routing", {"retry": retry_count})
                response = self._llm_manager.complete(messages, use_fallback=True)

                # Parse and validate JSON response
                parsed = self._validate_llm_response(response.content)

                if parsed is None:
                    # Validation failed, retry
                    retry_count += 1
                    logger.warning_data(
                        "LLM response validation failed, retrying",
                        {"retry": retry_count, "max_retries": max_retries}
                    )
                    continue

                # Convert to ProposedAction
                action_type = parsed["type"]

                if action_type == "tool_call":
                    if not parsed.get("tool"):
                        logger.warning("LLM tool_call missing tool field")
                        retry_count += 1
                        continue

                    return ProposedAction(
                        source=DecisionSource.LLM,
                        action_type="tool_call",
                        tool=parsed["tool"],
                        args=parsed.get("args", {}),
                        confidence=0.9,
                    )
                elif action_type == "final_answer":
                    if not parsed.get("text"):
                        logger.warning("LLM final_answer missing text field")
                        retry_count += 1
                        continue

                    return ProposedAction(
                        source=DecisionSource.LLM,
                        action_type="final_answer",
                        text=parsed["text"],
                        confidence=0.9,
                    )
                elif action_type == "clarification":
                    if not parsed.get("question"):
                        logger.warning("LLM clarification missing question field")
                        retry_count += 1
                        continue

                    return ProposedAction(
                        source=DecisionSource.LLM,
                        action_type="clarification",
                        text=parsed["question"],
                        confidence=0.9,
                    )
                else:
                    logger.warning_data("LLM response has invalid action type", {"type": action_type})
                    retry_count += 1
                    continue

            except Exception as e:
                logger.error_data("LLM routing failed", {"error": str(e), "retry": retry_count})
                retry_count += 1

        # All retries exhausted
        logger.error_data("LLM routing failed after retries", {"retries": max_retries})
        return None

    def _validate_llm_response(self, content: str) -> dict[str, Any] | None:
        """
        Validate LLM response structure.

        Returns parsed dict if valid, None otherwise.
        """
        import json

        try:
            # Strip whitespace and markdown code blocks
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            # Parse JSON
            parsed = json.loads(content)

            # Validate it's a dict
            if not isinstance(parsed, dict):
                logger.warning_data("LLM response is not a dict", {"type": type(parsed).__name__})
                return None

            # Validate required type field
            if "type" not in parsed:
                logger.warning("LLM response missing type field")
                return None

            # Validate type field is a string
            if not isinstance(parsed["type"], str):
                logger.warning_data("LLM type field is not a string", {"type": type(parsed["type"]).__name__})
                return None

            # Validate type is one of the expected values
            valid_types = ["tool_call", "final_answer", "clarification"]
            if parsed["type"] not in valid_types:
                logger.warning_data("LLM response has invalid type", {"type": parsed["type"], "valid": valid_types})
                return None

            return parsed

        except json.JSONDecodeError as e:
            logger.warning_data("LLM response not valid JSON", {"error": str(e), "content_preview": content[:200]})
            return None
        except Exception as e:
            logger.error_data("LLM response validation error", {"error": str(e)})
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
