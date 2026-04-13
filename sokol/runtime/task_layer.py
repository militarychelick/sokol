"""Task Layer - task/goal system for structured user intent."""

import sqlite3
import json
import os
from dataclasses import dataclass, field, asdict
from typing import Any, Optional, List
from enum import Enum
from datetime import datetime
from pathlib import Path

from sokol.observability.logging import get_logger
from sokol.runtime.result import Result

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

    def __init__(self, db_path: Optional[str] = None) -> None:
        """
        Initialize task manager.
        
        Args:
            db_path: Optional path to SQLite database for task persistence
        """
        self._active_task: Optional[Task] = None
        self._task_history: List[Task] = []
        
        # P0: Task persistence
        self._db_path = db_path or os.path.join(os.path.expanduser("~"), ".sokol", "tasks.db")
        self._conn: Optional[sqlite3.Connection] = None
        
        # Initialize database
        self._init_db()
        
        # Restore active task on startup
        self._restore_active_task()
    
    def _init_db(self) -> None:
        """Initialize SQLite database for task persistence."""
        try:
            # Create directory if it doesn't exist
            db_dir = os.path.dirname(self._db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
            
            # Connect to database
            self._conn = sqlite3.connect(self._db_path, timeout=10.0)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
            
            # Create tasks table
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    goal TEXT NOT NULL,
                    status TEXT NOT NULL,
                    steps TEXT,
                    current_step INTEGER DEFAULT 0,
                    risk_level TEXT DEFAULT 'low',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata TEXT,
                    is_active INTEGER DEFAULT 0
                )
            """)
            
            self._conn.commit()
            logger.info_data("Task persistence database initialized", {"db_path": self._db_path})
            
        except Exception as e:
            logger.error_data("Failed to initialize task database", {"error": str(e)})
            self._conn = None
    
    def _save_task(self, task: Task, is_active: bool = False) -> None:
        """
        Save task to database.
        
        Args:
            task: Task to save
            is_active: Whether this is the active task
        """
        if not self._conn:
            return
        
        try:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO tasks 
                (task_id, goal, status, steps, current_step, risk_level, created_at, updated_at, metadata, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.task_id,
                    task.goal,
                    task.status.value,
                    json.dumps(task.steps),
                    task.current_step,
                    task.risk_level,
                    task.created_at,
                    task.updated_at,
                    json.dumps(task.metadata),
                    1 if is_active else 0
                )
            )
            self._conn.commit()
        except Exception as e:
            logger.error_data("Failed to save task", {"task_id": task.task_id, "error": str(e)})
    
    def _load_task(self, task_id: str) -> Optional[Task]:
        """
        Load task from database.
        
        Args:
            task_id: Task ID to load
        
        Returns:
            Task or None if not found
        """
        if not self._conn:
            from sokol.runtime.errors import ErrorBuilder, ErrorCategory
            raise ErrorBuilder.from_exception(
                ValueError("Database connection not initialized"),
                category=ErrorCategory.INFRASTRUCTURE,
                context={"task_id": task_id}
            )

        try:
            cursor = self._conn.execute(
                "SELECT task_id, goal, status, steps, current_step, risk_level, created_at, updated_at, metadata FROM tasks WHERE task_id = ?",
                (task_id,)
            )
            row = cursor.fetchone()

            if not row:
                from sokol.runtime.errors import ErrorBuilder, ErrorCategory
                raise ErrorBuilder.from_exception(
                    ValueError(f"Task not found: {task_id}"),
                    category=ErrorCategory.VALIDATION,
                    context={"task_id": task_id}
                )
            
            return Task(
                task_id=row[0],
                goal=row[1],
                status=TaskStatus(row[2]),
                steps=json.loads(row[3]) if row[3] else [],
                current_step=row[4],
                risk_level=row[5],
                created_at=row[6],
                updated_at=row[7],
                metadata=json.loads(row[8]) if row[8] else {}
            )
        except Exception as e:
            logger.error_data("Failed to load task", {"task_id": task_id, "error": str(e)})
            return None
    
    def _restore_active_task(self) -> None:
        """Restore active task from database on startup."""
        if not self._conn:
            return
        
        try:
            cursor = self._conn.execute(
                "SELECT task_id FROM tasks WHERE is_active = 1 LIMIT 1"
            )
            row = cursor.fetchone()
            
            if row:
                task_id = row[0]
                task = self._load_task(task_id)
                if task and task.status in [TaskStatus.CREATED, TaskStatus.IN_PROGRESS, TaskStatus.WAITING_CONFIRMATION]:
                    self._active_task = task
                    self._task_history.append(task)
                    logger.info_data("Active task restored", {"task_id": task_id, "status": task.status.value})
                else:
                    # Clear active flag if task is completed/failed
                    self._conn.execute("UPDATE tasks SET is_active = 0 WHERE task_id = ?", (task_id,))
                    self._conn.commit()
        except Exception as e:
            logger.error_data("Failed to restore active task", {"error": str(e)})
    
    def _clear_active_flag(self) -> None:
        """Clear active flag from all tasks in database."""
        if not self._conn:
            return
        
        try:
            self._conn.execute("UPDATE tasks SET is_active = 0")
            self._conn.commit()
        except Exception as e:
            logger.error_data("Failed to clear active flag", {"error": str(e)})

    def create_task(
        self,
        goal: str,
        steps: List[str] | None = None,
        risk_level: str = "low",
    ) -> Result[Task]:
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

        # P0: Persist task
        self._clear_active_flag()
        self._save_task(task, is_active=True)

        logger.info_data(
            "Task created",
            {"task_id": task_id, "goal": goal, "risk_level": risk_level},
        )

        return Result.ok(task)

    def get_active_task(self) -> Result[Task | None]:
        """
        Get the currently active task.

        Returns:
            Active task or None
        """
        return Result.ok(self._active_task)

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        current_step: Optional[int] = None,
    ) -> Result[Task]:
        """
        Update task status.

        Args:
            task_id: Task ID
            status: New status
            current_step: Optional current step index

        Returns:
            Updated task or error if not found
        """
        task = self._find_task(task_id)
        if not task:
            from sokol.runtime.errors import ErrorBuilder, ErrorCategory
            raise ErrorBuilder.from_exception(
                ValueError(f"Task not found: {task_id}"),
                category=ErrorCategory.VALIDATION,
                context={"task_id": task_id}
            )

        task.status = status
        task.updated_at = datetime.now().isoformat()

        if current_step is not None:
            task.current_step = current_step

        # P0: Persist task update
        is_active = (self._active_task and self._active_task.task_id == task_id)
        self._save_task(task, is_active=is_active)

        logger.info_data(
            "Task status updated",
            {"task_id": task_id, "status": status.value},
        )

        return Result.ok(task)

    def complete_task(self, task_id: str) -> Result[Task]:
        """
        Mark task as completed.

        Args:
            task_id: Task ID

        Returns:
            Completed task or error if not found
        """
        task_result = self.update_task_status(task_id, TaskStatus.COMPLETED)
        if task_result.is_ok():
            task = task_result.unwrap()
            # Clear active task if it was the one completed
            if self._active_task and self._active_task.task_id == task_id:
                self._active_task = None
                # P0: Clear active flag in database
                self._conn.execute("UPDATE tasks SET is_active = 0 WHERE task_id = ?", (task_id,))
                self._conn.commit()
            return task_result
        return task_result

    def fail_task(self, task_id: str, reason: str = "") -> Result[Task]:
        """
        Mark task as failed.

        Args:
            task_id: Task ID
            reason: Failure reason

        Returns:
            Failed task or error if not found
        """
        task_result = self.update_task_status(task_id, TaskStatus.FAILED)
        if task_result.is_ok():
            task = task_result.unwrap()
            task.metadata["failure_reason"] = reason
            # Clear active task if it was the one failed
            if self._active_task and self._active_task.task_id == task_id:
                self._active_task = None
                # P0: Clear active flag in database
                self._conn.execute("UPDATE tasks SET is_active = 0 WHERE task_id = ?", (task_id,))
                self._conn.commit()
            return task_result
        return task_result

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
            from sokol.runtime.errors import ErrorBuilder, ErrorCategory
            raise ErrorBuilder.from_exception(
                ValueError(f"Task not found: {task_id}"),
                category=ErrorCategory.VALIDATION,
                context={"task_id": task_id}
            )

        task.status = TaskStatus.IN_PROGRESS
        task.updated_at = datetime.now().isoformat()
        self._active_task = task
        
        # P0: Persist task continuation
        self._clear_active_flag()
        self._save_task(task, is_active=True)

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
            from sokol.runtime.errors import ErrorBuilder, ErrorCategory
            raise ErrorBuilder.from_exception(
                ValueError(f"Task not found: {task_id}"),
                category=ErrorCategory.VALIDATION,
                context={"task_id": task_id}
            )

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

    def get_active_task(self) -> Result[Task | None]:
        """Get currently active task."""
        return Result.ok(self._active_task)

    def cancel_all(self, reason: str = "cancelled") -> int:
        """
        Cancel all tasks.

        Args:
            reason: Reason for cancellation

        Returns:
            Number of tasks cancelled
        """
        cancelled = 0
        if self._active_task:
            self._active_task = None
            logger.info_data("Active task cancelled", {"reason": reason})
            cancelled = 1
        # P0: Clear active flag in database
        self._clear_active_flag()
        return cancelled
    
    def shutdown(self) -> None:
        """Shutdown task manager and close database connection."""
        if self._conn:
            try:
                self._conn.close()
                logger.info("Task manager shutdown, database connection closed")
            except Exception as e:
                logger.error_data("Failed to close database connection", {"error": str(e)})

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
