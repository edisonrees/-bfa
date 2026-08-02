"""Data models for mock Instagram auth testing."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Deque, Dict, List, Optional, Tuple
import threading
import uuid


@dataclass
class BFaTask:
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    username: str = ""
    usernames: List[str] = field(default_factory=list)
    password_file: str = ""
    passwords: List[str] = field(default_factory=list)
    wordlist_path: Optional[str] = None
    stream: bool = False
    status: str = "pending"  # pending | processing | completed | failed | cancelled
    progress: int = 0
    total: int = 0
    global_total: int = 0
    results: List[Dict[str, Any]] = field(default_factory=list)
    successful_logins: List[Dict[str, Any]] = field(default_factory=list)
    failed_attempts: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error: Optional[str] = None
    replica_id: str = "0"
    replica_index: int = 0
    total_replicas: int = 1
    stop_on_first: bool = True
    cancel_requested: bool = False
    source: str = "upload"  # upload | paste | sample
    _rate_window: Deque[Tuple[float, int]] = field(default_factory=deque, repr=False)

    def note_progress(self, now_ts: Optional[float] = None) -> None:
        """Record progress sample for rolling ETA."""
        import time as _time

        ts = now_ts if now_ts is not None else _time.time()
        self._rate_window.append((ts, self.progress))
        while len(self._rate_window) > 40:
            self._rate_window.popleft()

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
        if len(self._rate_window) >= 2:
            t0, p0 = self._rate_window[0]
            t1, p1 = self._rate_window[-1]
            dt = t1 - t0
            dp = p1 - p0
            if dt > 0 and dp >= 0:
                return dp / dt
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

    def cluster_eta_seconds(self) -> Optional[float]:
        """ETA for full job assuming even shard split across replicas."""
        eta = self.eta_seconds()
        if eta is None:
            return None
        # Each replica works ~1/N; local ETA already reflects shard remaining.
        return eta

    def format_eta(self) -> Optional[str]:
        seconds = self.eta_seconds()
        if seconds is None:
            return None
        seconds = int(round(seconds))
        if seconds < 60:
            return f"{seconds}s"
        if seconds < 3600:
            return f"{seconds // 60}m {seconds % 60}s"
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"

    def to_dict(self) -> Dict[str, Any]:
        rate = self.attempts_per_second()
        eta = self.eta_seconds()
        return {
            "task_id": self.task_id,
            "username": self.username,
            "usernames": self.usernames,
            "password_file": self.password_file,
            "password_count": self.global_total // max(1, len(self.usernames))
            if self.global_total and self.usernames
            else len(self.passwords),
            "status": self.status,
            "progress": self.progress,
            "total": self.total,
            "global_total": self.global_total or self.total,
            "percent": round(self.percent(), 1),
            "results": self.results[-30:],
            "recent_results": self.results[-12:],
            "result_count": len(self.results),
            "successful_logins": self.successful_logins,
            "hit_count": len(self.successful_logins),
            "failed_attempts": self.failed_attempts,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "elapsed_seconds": round(self.elapsed_seconds() or 0, 2),
            "attempts_per_second": round(rate or 0, 2),
            "eta_seconds": round(eta, 1) if eta is not None else None,
            "eta_human": self.format_eta(),
            "cluster_eta_seconds": round(self.cluster_eta_seconds(), 1)
            if self.cluster_eta_seconds() is not None
            else None,
            "error": self.error,
            "replica_id": self.replica_id,
            "replica_index": self.replica_index,
            "total_replicas": self.total_replicas,
            "shard_label": f"{self.replica_index + 1}/{self.total_replicas}",
            "stop_on_first": self.stop_on_first,
            "source": self.source,
            "stream": self.stream,
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
        self.lock = threading.RLock()
        self._persist = True

    def _snapshot(self, task: BFaTask) -> None:
        if not self._persist:
            return
        try:
            from task_store import save_snapshot

            save_snapshot(task.task_id, task.to_dict())
        except Exception:
            pass

    def create_task(
        self,
        username: str = "",
        usernames: Optional[List[str]] = None,
        password_file: str = "",
        passwords: Optional[List[str]] = None,
        stop_on_first: bool = True,
        source: str = "upload",
        replica_id: str = "0",
        replica_index: int = 0,
        total_replicas: int = 1,
        wordlist_path: Optional[str] = None,
        stream: bool = False,
        password_count: Optional[int] = None,
        shard_total: Optional[int] = None,
    ) -> BFaTask:
        names = usernames or ([] if not username else [username])
        pwds = passwords or []
        count = password_count if password_count is not None else len(pwds)
        if shard_total is not None:
            local_pw = shard_total
        elif total_replicas > 1:
            local_pw = (count + total_replicas - 1 - replica_index) // total_replicas
        else:
            local_pw = count
        total = local_pw * max(1, len(names))
        task = BFaTask(
            username=names[0] if len(names) == 1 else username,
            usernames=names,
            password_file=password_file,
            passwords=pwds,
            wordlist_path=wordlist_path,
            stream=stream,
            total=total,
            global_total=count * max(1, len(names)),
            stop_on_first=stop_on_first,
            source=source,
            replica_id=str(replica_id),
            replica_index=replica_index,
            total_replicas=max(1, total_replicas),
        )
        with self.lock:
            self.tasks[task.task_id] = task
            self._snapshot(task)
        return task

    def get_task(self, task_id: str) -> Optional[BFaTask]:
        with self.lock:
            return self.tasks.get(task_id)

    def update_task(self, task: BFaTask) -> bool:
        with self.lock:
            if task.task_id in self.tasks:
                self.tasks[task.task_id] = task
                self._snapshot(task)
                return True
            return False

    def delete_task(self, task_id: str) -> bool:
        with self.lock:
            if task_id in self.tasks:
                del self.tasks[task_id]
                try:
                    from task_store import delete_snapshot

                    delete_snapshot(task_id)
                except Exception:
                    pass
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
            self._snapshot(task)
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
            try:
                from task_store import clear_finished_snapshots

                clear_finished_snapshots()
            except Exception:
                pass
            return len(finished)

    def get_all_tasks(self) -> List[BFaTask]:
        with self.lock:
            live = list(self.tasks.values())
        # Merge any persisted snapshots not in memory (other thread/process wrote them)
        try:
            from task_store import load_all_snapshots

            known = {t.task_id for t in live}
            extras = []
            for snap in load_all_snapshots():
                tid = snap.get("task_id")
                if tid and tid not in known:
                    extras.append(snap)
            # Prefer live objects; append orphan snapshots as dict-backed shells via adapter
            if extras:
                # return live first; API layer can also serve snapshots
                pass
        except Exception:
            pass
        return sorted(
            live,
            key=lambda t: t.start_time or datetime.min,
            reverse=True,
        )

    def list_payloads(self) -> List[Dict[str, Any]]:
        """SQLite is source of truth for UI; live memory overlays fresher fields."""
        store_map: Dict[str, Dict[str, Any]] = {}
        try:
            from task_store import load_all_snapshots

            for snap in load_all_snapshots():
                tid = snap.get("task_id")
                if tid:
                    store_map[tid] = snap
        except Exception:
            pass

        with self.lock:
            for task in self.tasks.values():
                live = task.to_dict()
                tid = task.task_id
                prev = store_map.get(tid)
                if not prev:
                    store_map[tid] = live
                    continue
                # Prefer whichever is ahead on progress / hits
                live_hits = len(live.get("successful_logins") or [])
                prev_hits = len(prev.get("successful_logins") or [])
                if (live.get("progress") or 0) >= (prev.get("progress") or 0) and live_hits >= prev_hits:
                    store_map[tid] = live
                elif live_hits > prev_hits:
                    store_map[tid] = live

        def sort_key(item: Dict[str, Any]):
            return item.get("start_time") or item.get("end_time") or ""

        return sorted(store_map.values(), key=sort_key, reverse=True)

    def stats(self) -> Dict[str, Any]:
        payloads = self.list_payloads()
        return {
            "total_tasks": len(payloads),
            "active": sum(1 for t in payloads if t.get("status") in ("pending", "processing")),
            "completed": sum(1 for t in payloads if t.get("status") == "completed"),
            "failed": sum(1 for t in payloads if t.get("status") == "failed"),
            "cancelled": sum(1 for t in payloads if t.get("status") == "cancelled"),
            "hits": sum(len(t.get("successful_logins") or []) for t in payloads),
            "attempts": sum(t.get("progress") or 0 for t in payloads),
        }


task_manager = TaskManager()
