"""Planner - task decomposition and plan generation."""

import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime

from sokol.planning.plan import Plan, PlanStep, StepStatus
from sokol.integrations.llm import LLMManager, LLMMessage
from sokol.core.config import get_config
from sokol.observability.logging import get_logger

logger = get_logger("sokol.planning.planner")


class Planner:
    """
    Task decomposition and plan generation.

    For simple tasks, returns a single-step plan.
    For complex tasks, decomposes into multiple steps.
    """

    def __init__(self) -> None:
        self._llm_manager = LLMManager(get_config())
        self._simple_task_threshold = 1  # Steps count for "simple" tasks

    def create_plan(self, goal: str, context: Optional[Dict[str, Any]] = None) -> Plan:
        """
        Create a plan for the given goal.

        Returns a Plan with one or more steps.
        """
        logger.info_data("Creating plan", {"goal": goal})

        context = context or {}

        # Try to decompose into steps
        steps = self._decompose_task(goal, context)

        # If decomposition failed or returned single step, use simple plan
        if not steps or len(steps) <= self._simple_task_threshold:
            steps = self._create_simple_plan(goal)

        plan = Plan(
            id=str(uuid.uuid4()),
            goal=goal,
            steps=steps,
            metadata={"context": context},
        )

        logger.info_data(
            "Plan created",
            {
                "plan_id": plan.id,
                "steps_count": len(plan.steps),
            },
        )

        return plan

    def _decompose_task(self, goal: str, context: Dict[str, Any]) -> List[PlanStep]:
        """
        Decompose a complex task into steps using LLM.

        Returns list of PlanStep or empty list if decomposition fails.
        """
        try:
            system_prompt = self._build_decomposition_prompt()

            messages = [
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=f"Task: {goal}"),
            ]

            response = self._llm_manager.complete(messages, use_fallback=True)

            # Parse the LLM response into steps
            steps = self._parse_decomposition(response.content)

            if steps:
                logger.info_data(
                    "Task decomposed into steps",
                    {"steps_count": len(steps)},
                )
                return steps
            else:
                logger.warning("LLM decomposition returned no steps")
                return []

        except Exception as e:
            logger.error_data("Task decomposition failed", {"error": str(e)})
            return []

    def _build_decomposition_prompt(self) -> str:
        """Build system prompt for task decomposition."""
        return """You are a task planner for a Windows AI assistant.

Break down the user's task into specific steps. Each step should be:
1. Specific and actionable
2. Dependent on previous steps if needed
3. Use available tools: app_launcher, file_ops, system_info, window_manager

Respond with valid JSON:
{
  "steps": [
    {
      "id": "step_1",
      "description": "Step description",
      "action_type": "tool_call",
      "tool": "tool_name",
      "args": {"param": "value"},
      "depends_on": []
    }
  ]
}

For simple tasks (1-2 steps), return empty steps list to indicate simple mode."""

    def _parse_decomposition(self, content: str) -> List[PlanStep]:
        """Parse LLM response into PlanStep list."""
        import json

        try:
            # Strip markdown code blocks
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            parsed = json.loads(content)

            if "steps" not in parsed:
                return []

            steps = []
            for i, step_data in enumerate(parsed["steps"]):
                step = PlanStep(
                    id=step_data.get("id", f"step_{i}"),
                    description=step_data.get("description", ""),
                    action_type=step_data.get("action_type", "tool_call"),
                    tool=step_data.get("tool"),
                    args=step_data.get("args", {}),
                    depends_on=step_data.get("depends_on", []),
                )
                steps.append(step)

            return steps

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning_data("Failed to parse decomposition", {"error": str(e)})
            return []

    def _create_simple_plan(self, goal: str) -> List[PlanStep]:
        """
        Create a simple single-step plan.

        Used for simple tasks or when decomposition fails.
        """
        step = PlanStep(
            id="step_1",
            description=goal,
            action_type="tool_call",
            tool=None,  # Will be determined by IntentRouter
            args={},
        )
        return [step]

    def refine_plan(self, plan: Plan, feedback: str) -> Plan:
        """
        Refine an existing plan based on feedback.

        Returns a new plan with adjusted steps.
        """
        logger.info_data("Refining plan", {"plan_id": plan.id, "feedback": feedback})

        # For now, just return the original plan
        # In production, this would use LLM to adjust the plan
        return plan

    def estimate_complexity(self, goal: str) -> str:
        """
        Estimate task complexity.

        Returns: "simple", "medium", or "complex"
        """
        # Simple heuristic based on task length and keywords
        complex_keywords = [
            "and then", "after that", "followed by",
            "multiple", "several", "batch", "all",
        ]

        goal_lower = goal.lower()
        keyword_count = sum(1 for kw in complex_keywords if kw in goal_lower)

        if keyword_count >= 2 or len(goal) > 100:
            return "complex"
        elif keyword_count == 1 or len(goal) > 50:
            return "medium"
        else:
            return "simple"
