"""Task manager for current and background tasks."""

import asyncio
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from typing import Any, Callable

from sokol.core.types import TaskInfo
from sokol.observability.logging import get_logger

logger = get_logger("sokol.runtime.tasks")


class TaskCancelledError(Exception):
    """Raised when a task is cancelled."""

    def __init__(self, task_id: str, reason: str = "cancelled") -> None:
        self.task_id = task_id
        self.reason = reason
        super().__init__(f"Task {task_id} cancelled: {reason}")


class TaskManager:
    """Manages current and background tasks with cancellation support."""

    def __init__(self, max_workers: int = 4) -> None:
        self._tasks: dict[str, TaskInfo] = {}
        self._current_task: TaskInfo | None = None
        self._background_tasks: dict[str, asyncio.Task[Any]] = {}
        self._thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        self._lock = threading.Lock()
        self._cancel_event = threading.Event()
        self._async_cancel_events: dict[str, asyncio.Event] = {}

    @property
    def current_task(self) -> TaskInfo | None:
        """Current foreground task."""
        return self._current_task

    @property
    def background_tasks(self) -> dict[str, TaskInfo]:
        """All background tasks."""
        return {k: v for k, v in self._tasks.items() if v.is_background}

    def create_task(
        self,
        tool_name: str,
        is_background: bool = False,
        cancellable: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> TaskInfo:
        """Create a new task."""
        task = TaskInfo(
            tool_name=tool_name,
            is_background=is_background,
            cancellable=cancellable,
            metadata=metadata or {},
        )

        with self._lock:
            self._tasks[task.id] = task
            if not is_background:
                self._current_task = task

        logger.info_data(
            "Task created",
            {
                "task_id": task.id,
                "tool": tool_name,
                "is_background": is_background,
            },
        )

        return task

    def update_task(
        self,
        task_id: str,
        status: str | None = None,
        progress: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TaskInfo | None:
        """Update task status/progress."""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                from sokol.runtime.errors import ErrorBuilder, ErrorCategory
                raise ErrorBuilder.from_exception(
                    ValueError(f"Task not found: {task_id}"),
                    category=ErrorCategory.VALIDATION,
                    context={"task_id": task_id}
                )

            if status:
                task.status = status
            if progress is not None:
                task.progress = min(1.0, max(0.0, progress))
            if metadata:
                task.metadata.update(metadata)

            # Clear current task if completed/cancelled/failed
            if (
                self._current_task
                and self._current_task.id == task_id
                and status in ("completed", "cancelled", "failed")
            ):
                self._current_task = None

        return task

    def cancel_task(self, task_id: str, reason: str = "user_request") -> bool:
        """Cancel a specific task."""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False

            if not task.cancellable:
                logger.warning_data(
                    "Cannot cancel non-cancellable task",
                    {"task_id": task_id},
                )
                return False

            task.status = "cancelled"
            if self._current_task and self._current_task.id == task_id:
                self._current_task = None

            # Cancel async task if exists
            if task_id in self._async_cancel_events:
                self._async_cancel_events[task_id].set()

            # Cancel thread pool future if exists
            # (handled via cancel_event in execute)

        logger.info_data(
            "Task cancelled",
            {"task_id": task_id, "reason": reason},
        )

        return True

    def cancel_all(self, reason: str = "emergency_stop") -> int:
        """
        Cancel all tasks (current + background).

        Returns number of tasks cancelled.
        """
        cancelled_count = 0

        # Set global cancel event
        self._cancel_event.set()

        with self._lock:
            for task_id, task in list(self._tasks.items()):
                if task.status == "running" and task.cancellable:
                    task.status = "cancelled"
                    cancelled_count += 1

                    # Cancel async tasks
                    if task_id in self._async_cancel_events:
                        self._async_cancel_events[task_id].set()

            self._current_task = None

        # Clear cancel event for future tasks
        self._cancel_event.clear()

        logger.warning_data(
            "All tasks cancelled",
            {"count": cancelled_count, "reason": reason},
        )

        return cancelled_count

    def is_cancelled(self, task_id: str | None = None) -> bool:
        """Check if a specific task or any task is cancelled."""
        if self._cancel_event.is_set():
            return True

        if task_id:
            with self._lock:
                task = self._tasks.get(task_id)
                return task is not None and task.status == "cancelled"

        return False

    def execute(
        self,
        task_id: str,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Future[Any]:
        """Execute a function in thread pool with cancellation support."""
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        def _wrapped() -> Any:
            if self.is_cancelled(task_id):
                raise TaskCancelledError(task_id)

            task.status = "running"
            try:
                result = func(*args, **kwargs)
                if self.is_cancelled(task_id):
                    raise TaskCancelledError(task_id)
                self.update_task(task_id, status="completed", progress=1.0)
                return result
            except TaskCancelledError:
                self.update_task(task_id, status="cancelled")
                raise
            except Exception as e:
                self.update_task(task_id, status="failed")
                raise

        return self._thread_pool.submit(_wrapped)

    async def execute_async(
        self,
        task_id: str,
        coro: Callable[..., asyncio.Task[Any]],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute an async coroutine with cancellation support."""
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        # Create cancel event for this task
        cancel_event = asyncio.Event()
        self._async_cancel_events[task_id] = cancel_event

        task.status = "running"

        try:
            # Create the actual task
            async_task = asyncio.create_task(coro(*args, **kwargs))

            # Wait for either completion or cancellation
            done, pending = await asyncio.wait(
                {async_task, cancel_event.wait()},
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel pending tasks
            for t in pending:
                t.cancel()

            if cancel_event.is_set() or self._cancel_event.is_set():
                self.update_task(task_id, status="cancelled")
                raise TaskCancelledError(task_id)

            # Get result from completed task
            result = await async_task
            self.update_task(task_id, status="completed", progress=1.0)
            return result

        except asyncio.CancelledError:
            self.update_task(task_id, status="cancelled")
            raise TaskCancelledError(task_id)
        except Exception as e:
            self.update_task(task_id, status="failed")
            raise
        finally:
            self._async_cancel_events.pop(task_id, None)

    def get_task(self, task_id: str) -> TaskInfo | None:
        """Get task by ID."""
        task = self._tasks.get(task_id)
        if not task:
            from sokol.runtime.errors import ErrorBuilder, ErrorCategory
            raise ErrorBuilder.from_exception(
                ValueError(f"Task not found: {task_id}"),
                category=ErrorCategory.VALIDATION,
                context={"task_id": task_id}
            )
        return task

    def get_all_tasks(self) -> list[TaskInfo]:
        """Get all tasks."""
        return list(self._tasks.values())

    def cleanup_completed(self, max_age_seconds: int = 300) -> int:
        """Remove completed/failed/cancelled tasks older than max_age."""
        now = datetime.now()
        to_remove = []

        with self._lock:
            for task_id, task in self._tasks.items():
                if task.status in ("completed", "failed", "cancelled"):
                    age = (now - task.started_at).total_seconds()
                    if age > max_age_seconds:
                        to_remove.append(task_id)

            for task_id in to_remove:
                del self._tasks[task_id]

        return len(to_remove)

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown task manager."""
        self.cancel_all("shutdown")
        self._thread_pool.shutdown(wait=wait)
