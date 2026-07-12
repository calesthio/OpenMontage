"""Job queue seam.

The default AsyncioJobQueue schedules the pipeline coroutine on the running
event loop (in-process). A future RedisQueue/CeleryQueue implements the same
enqueue() contract and hands the job to a broker + separate workers — no
call-site changes (see interfaces/__init__.get_job_queue).
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


class JobQueue(ABC):
    """Abstract async job queue."""

    name: str = "abstract"

    @abstractmethod
    def enqueue(self, coro_fn: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any) -> None:
        """Schedule an async job function for execution."""


class AsyncioJobQueue(JobQueue):
    """In-process queue: runs the coroutine as a task on the current loop.

    Decoupled from any single request's BackgroundTasks, so a job outlives the
    HTTP response that created it and can also be (re)dispatched from anywhere.
    """

    name = "asyncio"

    def __init__(self) -> None:
        # The event loop only holds a WEAK reference to tasks from create_task,
        # so a fire-and-forget task can be garbage-collected mid-run (the job
        # would just vanish between await points). Hold a strong reference until
        # the task finishes.
        self._tasks: set[asyncio.Task] = set()

    def enqueue(self, coro_fn: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any) -> None:
        loop = asyncio.get_event_loop()
        task = loop.create_task(coro_fn(*args, **kwargs))
        self._tasks.add(task)
        task.add_done_callback(self._on_task_done)

    def _on_task_done(self, task: asyncio.Task) -> None:
        self._tasks.discard(task)
        # run_pipeline_job is currently the only caller and already catches
        # everything internally, but that safety net lives entirely in that
        # one call site — a future second caller of enqueue() whose coroutine
        # raises would otherwise fail silently (asyncio only logs an
        # unretrieved-exception warning if the Task is GC'd, not reliably).
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error("Unhandled exception in queued job", exc_info=exc)
