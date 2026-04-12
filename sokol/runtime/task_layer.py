"""Task Layer - task/goal system for structured user intent."""

from dataclasses import dataclass, field
from typing import Any, Optional, List
from enum import Enum
from datetime import datetime

from sokol.observability.logging import get_logger

logger = get_logger("sokol.runtime.task_layer")


class TaskStatus(str, Enum):
    """Task status."""

    CREATED = "created"
    IN_PROGRESS = "in_progress"
    WAITING_CONFIRMATION = "waiting_confirmation"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    """Task object representing a user goal."""

    task_id: str
    goal: str
    status: TaskStatus = TaskStatus.CREATED
    steps: List[str] = field(default_factory=list)
    current_step: int = 0
    risk_level: str = "low"  # low/medium/high
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)


class TaskManager:
    """
    Task manager - manages tasks and their lifecycle.

    This manager:
    - Creates tasks from user requests
    - Tracks task state
    - Continues tasks across interactions
    - Integrates with memory layer for persistence
    - Integrates with control layer for risk assessment

    This manager DOES NOT:
    - Change execution engine
    - Bypass control layer
    - Introduce autonomy
    - Run tasks in background
    - Execute outside pipeline
    """

    def __init__(self) -> None:
        """Initialize task manager."""
        self._active_task: Optional[Task] = None
        self._task_history: List[Task] = []

    def create_task(
        self,
        goal: str,
        steps: List[str] | None = None,
        risk_level: str = "low",
    ) -> Task:
        """
        Create a new task.

        Args:
            goal: Task goal
            steps: Optional steps for the task
            risk_level: Risk level (low/medium/high)

        Returns:
            Created Task
        """
        task_id = self._generate_task_id()
        task = Task(
            task_id=task_id,
            goal=goal,
            steps=steps or [],
            risk_level=risk_level,
        )

        self._active_task = task
        self._task_history.append(task)

        logger.info_data(
            "Task created",
            {"task_id": task_id, "goal": goal, "risk_level": risk_level},
        )

        return task

    def get_active_task(self) -> Optional[Task]:
        """
        Get the currently active task.

        Returns:
            Active task or None
        """
        return self._active_task

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        current_step: Optional[int] = None,
    ) -> Optional[Task]:
        """
        Update task status.

        Args:
            task_id: Task ID
            status: New status
            current_step: Optional current step index

        Returns:
            Updated task or None if not found
        """
        task = self._find_task(task_id)
        if not task:
            return None

        task.status = status
        task.updated_at = datetime.now().isoformat()

        if current_step is not None:
            task.current_step = current_step

        logger.info_data(
            "Task status updated",
            {"task_id": task_id, "status": status.value},
        )

        return task

    def complete_task(self, task_id: str) -> Optional[Task]:
        """
        Mark task as completed.

        Args:
            task_id: Task ID

        Returns:
            Completed task or None if not found
        """
        task = self.update_task_status(task_id, TaskStatus.COMPLETED)
        if task:
            # Clear active task if it was the one completed
            if self._active_task and self._active_task.task_id == task_id:
                self._active_task = None

        return task

    def fail_task(self, task_id: str, reason: str = "") -> Optional[Task]:
        """
        Mark task as failed.

        Args:
            task_id: Task ID
            reason: Failure reason

        Returns:
            Failed task or None if not found
        """
        task = self.update_task_status(task_id, TaskStatus.FAILED)
        if task:
            task.metadata["failure_reason"] = reason
            # Clear active task if it was the one failed
            if self._active_task and self._active_task.task_id == task_id:
                self._active_task = None

        return task

    def is_request_related_to_task(
        self,
        request: str,
        task: Task,
    ) -> bool:
        """
        Check if a request is related to an active task.

        Args:
            request: User request
            task: Active task

        Returns:
            True if related, False otherwise
        """
        # Lightweight keyword matching
        request_lower = request.lower()
        task_goal_lower = task.goal.lower()

        # Check if request contains goal keywords
        request_words = set(request_lower.split())
        task_words = set(task_goal_lower.split())

        # If 30% or more words overlap, consider related
        if len(task_words) > 0:
            overlap = len(request_words & task_words)
            ratio = overlap / len(task_words)
            if ratio >= 0.3:
                return True

        # Check if request mentions task context
        if any(word in request_lower for word in task_words):
            return True

        return False

    def continue_task(self, task_id: str) -> Optional[Task]:
        """
        Continue a task (set to in_progress).

        Args:
            task_id: Task ID

        Returns:
            Task or None if not found
        """
        task = self._find_task(task_id)
        if not task:
            return None

        task.status = TaskStatus.IN_PROGRESS
        task.updated_at = datetime.now().isoformat()
        self._active_task = task

        logger.info_data(
            "Task continued",
            {"task_id": task_id},
        )

        return task

    def get_task_summary(self, task_id: str) -> Optional[dict[str, Any]]:
        """
        Get task summary for memory integration.

        Args:
            task_id: Task ID

        Returns:
            Task summary dict or None
        """
        task = self._find_task(task_id)
        if not task:
            return None

        return {
            "task_id": task.task_id,
            "goal": task.goal,
            "status": task.status.value,
            "current_step": task.current_step,
            "total_steps": len(task.steps),
            "risk_level": task.risk_level,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
        }

    def clear_active_task(self) -> None:
        """Clear the active task."""
        self._active_task = None

    def _find_task(self, task_id: str) -> Optional[Task]:
        """
        Find task by ID.

        Args:
            task_id: Task ID

        Returns:
            Task or None
        """
        # Check active task first
        if self._active_task and self._active_task.task_id == task_id:
            return self._active_task

        # Search history
        for task in self._task_history:
            if task.task_id == task_id:
                return task

        return None

    def _generate_task_id(self) -> str:
        """Generate unique task ID."""
        import uuid
        return f"task_{uuid.uuid4().hex[:8]}"
