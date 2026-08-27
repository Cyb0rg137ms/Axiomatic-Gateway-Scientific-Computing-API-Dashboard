"""
registry.py
===========
Registry for tracking and managing active computational and physics simulations.
"""

import uuid
import time
from typing import Dict, Any, Optional

class SimulationTask:
    """Represents the runtime state of a background simulation."""
    
    def __init__(self, name: str, params: Dict[str, Any]):
        self.task_id = str(uuid.uuid4())
        self.name = name
        self.params = params
        self.status = "queued"  # queued, running, completed, failed
        self.progress = 0.0     # 0.0 to 100.0
        self.result = None
        self.started_at = time.time()

    def update_progress(self, step: float):
        """Increments progress and updates status."""
        self.progress = min(100.0, self.progress + step)
        if self.progress >= 100.0:
            self.status = "completed"
        elif self.progress > 0.0:
            self.status = "running"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "params": self.params,
            "status": self.status,
            "progress": self.progress,
            "result": self.result,
            "elapsed_seconds": time.time() - self.started_at
        }

class SimulationRegistry:
    """Manages active tasks, allowing starting, polling, and telemetry updates."""
    
    def __init__(self):
        self.tasks: Dict[str, SimulationTask] = {}

    def register_task(self, name: str, params: Dict[str, Any]) -> SimulationTask:
        task = SimulationTask(name, params)
        self.tasks[task.task_id] = task
        return task

    def get_task(self, task_id: str) -> Optional[SimulationTask]:
        return self.tasks.get(task_id)

    def update_all_tasks(self):
        """Simulates background progress updates for testing/telemetry."""
        for task in self.tasks.values():
            if task.status in ["queued", "running"]:
                task.update_progress(20.0)  # Add 20% progress per call
                if task.status == "completed":
                    # Mock result generation
                    task.result = {
                        "derived_consensuses": True,
                        "nodes_processed": 50,
                        "residual_energy": 0.0042
                    }
