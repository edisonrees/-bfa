"""Data models for mock Instagram auth testing."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import threading
import uuid


@dataclass
class BFaTask:
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    username: str = ""
    usernames: List[str] = field(default_factory=list)
    password_file: str = ""
    passwords: List[str] = field(default_factory=list)
    status: str = "pending"  # pending | processing | completed | failed | cancelled
    progress: int = 0
    total: int = 0
    results: List[Dict[str, Any]] = field(default_factory=list)
    successful_logins: List[Dict[str, Any]] = field(default_factory=list)
    failed_attempts: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error: Optional[str] = None
    replica_id: str = "0"
    stop_on_first: bool = True
    cancel_requested: bool = False
    source: str = "upload"  # upload | paste | sample

    def percent(self) -> float:
        if self.total <= 0:
            return 0.0
        return min(100.0, (self.progress / self.total) * 100.0)

    def elapsed_seconds(self) -> Optional[float]:
        if not self.start_time:
            return None
        end = self.end_time or datetime.now()
        return max(0.0, (end - self.start_time).total_seconds())

    def attempts_per_second(self) -> Optional[float]:
        elapsed = self.elapsed_seconds()
        if not elapsed or elapsed <= 0 or self.progress <= 0:
            return None
        return self.progress / elapsed

    def eta_seconds(self) -> Optional[float]:
        rate = self.attempts_per_second()
        if not rate or self.status != "processing":
            return None
        remaining = max(0, self.total - self.progress)
        return remaining / rate

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "username": self.username,
            "usernames": self.usernames,
            "password_file": self.password_file,
            "password_count": len(self.passwords),
            "status": self.status,
            "progress": self.progress,
            "total": self.total,
            "percent": round(self.percent(), 1),
            "results": self.results[-50:],  # keep payload light
            "result_count": len(self.results),
            "successful_logins": self.successful_logins,
            "failed_attempts": self.failed_attempts,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "elapsed_seconds": round(self.elapsed_seconds() or 0, 2),
            "attempts_per_second": round(self.attempts_per_second() or 0, 2),
            "eta_seconds": round(self.eta_seconds(), 1) if self.eta_seconds() is not None else None,
            "error": self.error,
            "replica_id": self.replica_id,
            "stop_on_first": self.stop_on_first,
            "source": self.source,
        }


@dataclass
class BFaResult:
    task_id: str
    username: str
    password: str
    success: bool
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    error_type: Optional[str] = None
    profile: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "username": self.username,
            "password": self.password if self.success else "***",
            "success": self.success,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "error_type": self.error_type,
            "profile": self.profile,
        }


class TaskManager:
    def __init__(self) -> None:
        self.tasks: Dict[str, BFaTask] = {}
        self.lock = threading.Lock()

    def create_task(
        self,
        username: str = "",
        usernames: Optional[List[str]] = None,
        password_file: str = "",
        passwords: Optional[List[str]] = None,
        stop_on_first: bool = True,
        source: str = "upload",
        replica_id: str = "0",
    ) -> BFaTask:
        names = usernames or ([] if not username else [username])
        pwds = passwords or []
        task = BFaTask(
            username=names[0] if len(names) == 1 else username,
            usernames=names,
            password_file=password_file,
            passwords=pwds,
            total=len(pwds) * max(1, len(names)),
            stop_on_first=stop_on_first,
            source=source,
            replica_id=replica_id,
        )
        with self.lock:
            self.tasks[task.task_id] = task
        return task

    def get_task(self, task_id: str) -> Optional[BFaTask]:
        with self.lock:
            return self.tasks.get(task_id)

    def update_task(self, task: BFaTask) -> bool:
        with self.lock:
            if task.task_id in self.tasks:
                self.tasks[task.task_id] = task
                return True
            return False

    def delete_task(self, task_id: str) -> bool:
        with self.lock:
            if task_id in self.tasks:
                del self.tasks[task_id]
                return True
            return False

    def cancel_task(self, task_id: str) -> Optional[BFaTask]:
        with self.lock:
            task = self.tasks.get(task_id)
            if not task:
                return None
            if task.status in ("completed", "failed", "cancelled"):
                return task
            task.cancel_requested = True
            return task

    def clear_finished(self) -> int:
        with self.lock:
            finished = [
                tid
                for tid, task in self.tasks.items()
                if task.status in ("completed", "failed", "cancelled")
            ]
            for tid in finished:
                del self.tasks[tid]
            return len(finished)

    def get_all_tasks(self) -> List[BFaTask]:
        with self.lock:
            return sorted(
                self.tasks.values(),
                key=lambda t: t.start_time or datetime.min,
                reverse=True,
            )

    def stats(self) -> Dict[str, Any]:
        tasks = self.get_all_tasks()
        return {
            "total_tasks": len(tasks),
            "active": sum(1 for t in tasks if t.status in ("pending", "processing")),
            "completed": sum(1 for t in tasks if t.status == "completed"),
            "failed": sum(1 for t in tasks if t.status == "failed"),
            "cancelled": sum(1 for t in tasks if t.status == "cancelled"),
            "hits": sum(len(t.successful_logins) for t in tasks),
            "attempts": sum(t.progress for t in tasks),
        }


task_manager = TaskManager()
