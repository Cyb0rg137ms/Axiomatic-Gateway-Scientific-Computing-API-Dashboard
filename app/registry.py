"""
registry.py
===========
Tracks background work.

* :class:`JobRunner` executes real callables (proofs, SAT solves) on a bounded
  thread pool and records status/result/error honestly.
* :class:`SimulationRegistry` keeps the v1 *manual-progress* API
  (``update_all_tasks`` advances progress by 20%) for clients that drive progress
  themselves. v1 attached a fabricated result (``residual_energy: 0.0042``) on
  completion; v2 attaches only a note saying no computation was run.
"""

from __future__ import annotations

import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional


class SimulationTask:
    """Runtime state of a background task."""

    def __init__(self, name: str, params: Dict[str, Any], kind: str = "manual"):
        self.task_id = str(uuid.uuid4())
        self.name = name
        self.params = params
        self.kind = kind
        self.status = "queued"  # queued, running, completed, failed
        self.progress = 0.0  # 0.0 to 100.0
        self.result: Any = None
        self.error: Optional[str] = None
        self.started_at = time.time()
        self.finished_at: Optional[float] = None

    def update_progress(self, step: float) -> None:
        """Increments progress and updates status (manual tasks only)."""
        self.progress = min(100.0, self.progress + step)
        if self.progress >= 100.0:
            self.status = "completed"
            self.finished_at = time.time()
        elif self.progress > 0.0:
            self.status = "running"

    def to_dict(self) -> Dict[str, Any]:
        end = self.finished_at or time.time()
        return {
            "task_id": self.task_id,
            "name": self.name,
            "kind": self.kind,
            "params": self.params,
            "status": self.status,
            "progress": self.progress,
            "result": self.result,
            "error": self.error,
            "elapsed_seconds": end - self.started_at,
        }


class SimulationRegistry:
    """Task table plus a bounded worker pool for real jobs."""

    def __init__(self, max_workers: int = 2, max_tasks: int = 10_000):
        self.tasks: Dict[str, SimulationTask] = {}
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="axiomatic-job")
        self.max_tasks = max_tasks

    def _add(self, task: SimulationTask) -> SimulationTask:
        with self._lock:
            if len(self.tasks) >= self.max_tasks:  # drop the oldest finished task
                victim = next((k for k, t in self.tasks.items() if t.status in ("completed", "failed")), None)
                if victim is None:
                    raise RuntimeError("task table full")
                del self.tasks[victim]
            self.tasks[task.task_id] = task
        return task

    def register_task(self, name: str, params: Dict[str, Any]) -> SimulationTask:
        """Register a manual-progress task (v1 behaviour, no computation attached)."""
        return self._add(SimulationTask(name, params))

    def submit(self, name: str, params: Dict[str, Any], fn: Callable[[], Any]) -> SimulationTask:
        """Run ``fn`` in the worker pool; status/result/error reflect what actually happened."""
        task = self._add(SimulationTask(name, params, kind="job"))

        def run() -> None:
            task.status = "running"
            try:
                task.result = fn()
                task.status = "completed"
            except Exception as exc:
                task.error = f"{type(exc).__name__}: {exc}"
                task.status = "failed"
                traceback.print_exc()
            finally:
                task.progress = 100.0
                task.finished_at = time.time()

        self._pool.submit(run)
        return task

    def get_task(self, task_id: str) -> Optional[SimulationTask]:
        return self.tasks.get(task_id)

    def update_all_tasks(self) -> None:
        """Advance every *manual* task by 20% (v1 API)."""
        for task in list(self.tasks.values()):
            if task.kind == "manual" and task.status in ("queued", "running"):
                task.update_progress(20.0)
                if task.status == "completed":
                    task.result = {"note": "manual-progress task; no computation was attached", "steps": 5}

    def shutdown(self) -> None:
        self._pool.shutdown(wait=True)
