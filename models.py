"""
Data models for the Instagram BFa application
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
import uuid

@dataclass
class BFaTask:
    """Represents a brute force attack task"""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    username: str = ""
    usernames: List[str] = field(default_factory=list)
    password_file: str = ""
    passwords: List[str] = field(default_factory=list)
    status: str = "pending"  # pending, processing, completed, failed
    progress: int = 0
    total: int = 0
    results: List[Dict[str, Any]] = field(default_factory=list)
    successful_logins: List[Dict[str, Any]] = field(default_factory=list)
    failed_attempts: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error: Optional[str] = None
    replica_id: str = "0"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'task_id': self.task_id,
            'username': self.username,
            'usernames': self.usernames,
            'password_file': self.password_file,
            'password_count': len(self.passwords),
            'status': self.status,
            'progress': self.progress,
            'total': self.total,
            'results': self.results,
            'successful_logins': self.successful_logins,
            'failed_attempts': self.failed_attempts,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'error': self.error,
            'replica_id': self.replica_id
        }

@dataclass
class BFaResult:
    """Represents a single brute force attempt result"""
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
            'task_id': self.task_id,
            'username': self.username,
            'password': self.password if self.success else "***",
            'success': self.success,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
            'error_type': self.error_type,
            'profile': self.profile
        }

class TaskManager:
    """Manages BFa tasks across replicas"""
    
    def __init__(self):
        self.tasks = {}
        self.lock = threading.Lock()
        
    def create_task(self, username: str = "", usernames: List[str] = None, 
                   password_file: str = "", passwords: List[str] = None) -> BFaTask:
        """Create a new BFa task"""
        task = BFaTask(
            username=username,
            usernames=usernames or [],
            password_file=password_file,
            passwords=passwords or []
        )
        
        with self.lock:
            self.tasks[task.task_id] = task
        
        return task
    
    def get_task(self, task_id: str) -> Optional[BFaTask]:
        """Get a task by ID"""
        with self.lock:
            return self.tasks.get(task_id)
    
    def update_task(self, task: BFaTask) -> bool:
        """Update a task"""
        with self.lock:
            if task.task_id in self.tasks:
                self.tasks[task.task_id] = task
                return True
            return False
    
    def delete_task(self, task_id: str) -> bool:
        """Delete a task"""
        with self.lock:
            if task_id in self.tasks:
                del self.tasks[task_id]
                return True
            return False
    
    def get_all_tasks(self) -> List[BFaTask]:
        """Get all tasks"""
        with self.lock:
            return list(self.tasks.values())

import threading
task_manager = TaskManager()
