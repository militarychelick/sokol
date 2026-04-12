"""Plan data structures."""

from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Optional
from datetime import datetime


class PlanStatus(str, Enum):
    """Plan execution status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    """Plan step execution status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PlanStep:
    """Single step in a plan."""
    id: str
    description: str
    action_type: str  # tool_call, final_answer, clarification
    tool: Optional[str] = None
    args: dict[str, Any] = field(default_factory=dict)
    status: StepStatus = StepStatus.PENDING
    depends_on: list[str] = field(default_factory=list)  # Step IDs this depends on
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "description": self.description,
            "action_type": self.action_type,
            "tool": self.tool,
            "args": self.args,
            "status": self.status.value,
            "depends_on": self.depends_on,
            "result": self.result,
            "error": self.error,
            "execution_time": self.execution_time,
        }


@dataclass
class Plan:
    """Execution plan for complex tasks."""
    id: str
    goal: str
    steps: list[PlanStep] = field(default_factory=list)
    status: PlanStatus = PlanStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    current_step_index: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_step(self, step: PlanStep) -> None:
        """Add a step to the plan."""
        self.steps.append(step)

    def get_current_step(self) -> Optional[PlanStep]:
        """Get the current step to execute."""
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None

    def advance_step(self) -> Optional[PlanStep]:
        """Advance to the next step."""
        if self.current_step_index < len(self.steps):
            self.current_step_index += 1
            return self.get_current_step()
        return None

    def get_step_by_id(self, step_id: str) -> Optional[PlanStep]:
        """Get step by ID."""
        for step in self.steps:
            if step.id == step_id:
                return step
        return None

    def get_pending_steps(self) -> list[PlanStep]:
        """Get all pending steps."""
        return [s for s in self.steps if s.status == StepStatus.PENDING]

    def get_completed_steps(self) -> list[PlanStep]:
        """Get all completed steps."""
        return [s for s in self.steps if s.status == StepStatus.COMPLETED]

    def get_failed_steps(self) -> list[PlanStep]:
        """Get all failed steps."""
        return [s for s in self.steps if s.status == StepStatus.FAILED]

    def is_complete(self) -> bool:
        """Check if plan is complete."""
        return all(s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED) for s in self.steps)

    def is_failed(self) -> bool:
        """Check if plan has failed."""
        return any(s.status == StepStatus.FAILED for s in self.steps)

    def progress(self) -> float:
        """Get plan progress (0.0 to 1.0)."""
        if not self.steps:
            return 1.0
        completed = len(self.get_completed_steps())
        return completed / len(self.steps)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "goal": self.goal,
            "steps": [s.to_dict() for s in self.steps],
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "current_step_index": self.current_step_index,
            "metadata": self.metadata,
            "progress": self.progress(),
        }
