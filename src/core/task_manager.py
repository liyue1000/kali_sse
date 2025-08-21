"""
任务管理器

负责管理命令执行任务的生命周期、状态跟踪和资源分配。
"""

import asyncio
import logging
import time
import uuid
from typing import Dict, Any, List, Optional, Callable
from enum import Enum
from dataclasses import dataclass, field
import threading

from .config_manager import ConfigManager

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class TaskPriority(Enum):
    """任务优先级枚举"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Task:
    """任务数据类"""
    task_id: str
    command: str
    args: List[str] = field(default_factory=list)
    options: Dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    timeout: int = 300
    retry_count: int = 0
    max_retries: int = 0
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    progress: float = 0.0
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    
    @property
    def duration(self) -> Optional[float]:
        """计算任务执行时间"""
        if self.started_at is None:
            return None
        end_time = self.completed_at or time.time()
        return end_time - self.started_at
    
    @property
    def is_active(self) -> bool:
        """检查任务是否活跃"""
        return self.status in [TaskStatus.PENDING, TaskStatus.RUNNING]
    
    @property
    def is_finished(self) -> bool:
        """检查任务是否已完成"""
        return self.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, 
                              TaskStatus.CANCELLED, TaskStatus.TIMEOUT]


class TaskManager:
    """任务管理器"""
    
    def __init__(self, config_manager: ConfigManager):
        """
        初始化任务管理器
        
        Args:
            config_manager: 配置管理器
        """
        self.config_manager = config_manager
        self.config = config_manager.get_execution_config()
        
        # 任务存储
        self.tasks: Dict[str, Task] = {}
        self.task_lock = threading.RLock()
        
        # 任务队列（按优先级排序）
        self.pending_queue: List[str] = []
        self.running_tasks: Dict[str, asyncio.Task] = {}
        
        # 统计信息
        self.stats = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "cancelled_tasks": 0,
            "active_tasks": 0
        }
        
        # 事件回调
        self.event_callbacks: Dict[str, List[Callable]] = {
            "task_created": [],
            "task_started": [],
            "task_progress": [],
            "task_completed": [],
            "task_failed": [],
            "task_cancelled": []
        }
        
        # 清理任务将在需要时启动
        self._cleanup_task_started = False
        
        logger.info("任务管理器初始化完成")

    def start_cleanup_task(self) -> None:
        """启动清理任务"""
        if not self._cleanup_task_started:
            try:
                asyncio.create_task(self._cleanup_task())
                self._cleanup_task_started = True
            except RuntimeError:
                # 如果没有运行的事件循环，稍后再启动
                pass
    
    def create_task(self, command: str, args: Optional[List[str]] = None,
                   options: Optional[Dict[str, Any]] = None,
                   priority: TaskPriority = TaskPriority.NORMAL,
                   user_id: Optional[str] = None,
                   session_id: Optional[str] = None) -> str:
        """
        创建新任务
        
        Args:
            command: 命令
            args: 参数列表
            options: 选项
            priority: 优先级
            user_id: 用户ID
            session_id: 会话ID
            
        Returns:
            任务ID
        """
        task_id = str(uuid.uuid4())
        
        # 处理选项
        options = options or {}
        timeout = options.get("timeout", self.config.default_timeout)
        max_retries = options.get("max_retries", 0)
        
        # 创建任务
        task = Task(
            task_id=task_id,
            command=command,
            args=args or [],
            options=options,
            priority=priority,
            timeout=timeout,
            max_retries=max_retries,
            user_id=user_id,
            session_id=session_id
        )
        
        with self.task_lock:
            self.tasks[task_id] = task
            self._add_to_queue(task_id)
            self.stats["total_tasks"] += 1
            self.stats["active_tasks"] += 1
        
        # 触发事件
        self._trigger_event("task_created", task)
        
        logger.info(f"创建任务: {task_id} - {command}")
        return task_id
    
    def _add_to_queue(self, task_id: str) -> None:
        """
        将任务添加到队列（按优先级排序）
        
        Args:
            task_id: 任务ID
        """
        task = self.tasks[task_id]
        
        # 找到合适的插入位置
        insert_index = 0
        for i, existing_task_id in enumerate(self.pending_queue):
            existing_task = self.tasks[existing_task_id]
            if task.priority.value > existing_task.priority.value:
                insert_index = i
                break
            insert_index = i + 1
        
        self.pending_queue.insert(insert_index, task_id)
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """
        获取任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务对象
        """
        with self.task_lock:
            return self.tasks.get(task_id)
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务状态信息
        """
        task = self.get_task(task_id)
        if not task:
            return None
        
        return {
            "task_id": task.task_id,
            "command": task.command,
            "status": task.status.value,
            "priority": task.priority.value,
            "progress": task.progress,
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
            "duration": task.duration,
            "timeout": task.timeout,
            "retry_count": task.retry_count,
            "max_retries": task.max_retries,
            "user_id": task.user_id,
            "session_id": task.session_id,
            "error": task.error
        }
    
    def update_task_status(self, task_id: str, status: TaskStatus,
                          progress: Optional[float] = None,
                          error: Optional[str] = None,
                          result: Optional[Dict[str, Any]] = None) -> bool:
        """
        更新任务状态
        
        Args:
            task_id: 任务ID
            status: 新状态
            progress: 进度
            error: 错误信息
            result: 结果
            
        Returns:
            是否更新成功
        """
        with self.task_lock:
            task = self.tasks.get(task_id)
            if not task:
                return False
            
            old_status = task.status
            task.status = status
            
            if progress is not None:
                task.progress = max(0.0, min(1.0, progress))
            
            if error is not None:
                task.error = error
            
            if result is not None:
                task.result = result
            
            # 更新时间戳
            current_time = time.time()
            if status == TaskStatus.RUNNING and old_status == TaskStatus.PENDING:
                task.started_at = current_time
                self._trigger_event("task_started", task)
            elif task.is_finished and not task.completed_at:
                task.completed_at = current_time
                self.stats["active_tasks"] -= 1
                
                # 更新统计
                if status == TaskStatus.COMPLETED:
                    self.stats["completed_tasks"] += 1
                    self._trigger_event("task_completed", task)
                elif status == TaskStatus.FAILED:
                    self.stats["failed_tasks"] += 1
                    self._trigger_event("task_failed", task)
                elif status == TaskStatus.CANCELLED:
                    self.stats["cancelled_tasks"] += 1
                    self._trigger_event("task_cancelled", task)
            
            # 触发进度事件
            if progress is not None:
                self._trigger_event("task_progress", task)
        
        logger.debug(f"任务状态更新: {task_id} -> {status.value}")
        return True
    
    def cancel_task(self, task_id: str, force: bool = False) -> bool:
        """
        取消任务
        
        Args:
            task_id: 任务ID
            force: 是否强制取消
            
        Returns:
            是否取消成功
        """
        with self.task_lock:
            task = self.tasks.get(task_id)
            if not task:
                return False
            
            if task.is_finished:
                return False
            
            # 从队列中移除
            if task_id in self.pending_queue:
                self.pending_queue.remove(task_id)
            
            # 取消运行中的任务
            if task_id in self.running_tasks:
                async_task = self.running_tasks[task_id]
                if not async_task.done():
                    async_task.cancel()
                del self.running_tasks[task_id]
            
            # 更新状态
            self.update_task_status(task_id, TaskStatus.CANCELLED)
        
        logger.info(f"任务已取消: {task_id}")
        return True
    
    def get_pending_tasks(self) -> List[str]:
        """
        获取待处理任务列表
        
        Returns:
            任务ID列表
        """
        with self.task_lock:
            return self.pending_queue.copy()
    
    def get_running_tasks(self) -> List[str]:
        """
        获取运行中任务列表
        
        Returns:
            任务ID列表
        """
        with self.task_lock:
            return list(self.running_tasks.keys())
    
    def get_tasks_by_status(self, status: TaskStatus) -> List[str]:
        """
        按状态获取任务列表
        
        Args:
            status: 任务状态
            
        Returns:
            任务ID列表
        """
        with self.task_lock:
            return [task_id for task_id, task in self.tasks.items() 
                   if task.status == status]
    
    def get_tasks_by_user(self, user_id: str) -> List[str]:
        """
        按用户获取任务列表
        
        Args:
            user_id: 用户ID
            
        Returns:
            任务ID列表
        """
        with self.task_lock:
            return [task_id for task_id, task in self.tasks.items() 
                   if task.user_id == user_id]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            统计信息
        """
        with self.task_lock:
            return {
                **self.stats,
                "pending_tasks": len(self.pending_queue),
                "running_tasks": len(self.running_tasks),
                "total_stored_tasks": len(self.tasks)
            }
    
    def add_event_callback(self, event_type: str, callback: Callable) -> None:
        """
        添加事件回调
        
        Args:
            event_type: 事件类型
            callback: 回调函数
        """
        if event_type in self.event_callbacks:
            self.event_callbacks[event_type].append(callback)
    
    def remove_event_callback(self, event_type: str, callback: Callable) -> None:
        """
        移除事件回调
        
        Args:
            event_type: 事件类型
            callback: 回调函数
        """
        if event_type in self.event_callbacks:
            try:
                self.event_callbacks[event_type].remove(callback)
            except ValueError:
                pass
    
    def _trigger_event(self, event_type: str, task: Task) -> None:
        """
        触发事件
        
        Args:
            event_type: 事件类型
            task: 任务对象
        """
        callbacks = self.event_callbacks.get(event_type, [])
        for callback in callbacks:
            try:
                callback(task)
            except Exception as e:
                logger.error(f"事件回调异常 {event_type}: {e}")
    
    async def _cleanup_task(self) -> None:
        """清理任务，定期清理已完成的任务"""
        while True:
            try:
                await asyncio.sleep(3600)  # 每小时清理一次
                
                current_time = time.time()
                max_age = 86400  # 24小时
                
                tasks_to_remove = []
                
                with self.task_lock:
                    for task_id, task in self.tasks.items():
                        if (task.is_finished and 
                            task.completed_at and 
                            current_time - task.completed_at > max_age):
                            tasks_to_remove.append(task_id)
                
                # 清理过期任务
                for task_id in tasks_to_remove:
                    with self.task_lock:
                        del self.tasks[task_id]
                
                if tasks_to_remove:
                    logger.info(f"清理了 {len(tasks_to_remove)} 个过期任务")
                
            except Exception as e:
                logger.error(f"任务清理异常: {e}")
    
    def can_accept_new_task(self) -> bool:
        """
        检查是否可以接受新任务
        
        Returns:
            是否可以接受
        """
        with self.task_lock:
            active_count = len(self.running_tasks) + len(self.pending_queue)
            return active_count < self.config.max_concurrent_tasks
    
    def get_next_task(self) -> Optional[str]:
        """
        获取下一个待执行任务
        
        Returns:
            任务ID
        """
        with self.task_lock:
            if self.pending_queue:
                return self.pending_queue.pop(0)
            return None
    
    def mark_task_running(self, task_id: str, async_task: asyncio.Task) -> None:
        """
        标记任务为运行中
        
        Args:
            task_id: 任务ID
            async_task: 异步任务对象
        """
        with self.task_lock:
            self.running_tasks[task_id] = async_task
            self.update_task_status(task_id, TaskStatus.RUNNING)
