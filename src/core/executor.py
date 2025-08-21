"""
命令执行引擎

负责安全地执行 Kali Linux 安全工具命令。
支持同步/异步执行、超时控制、资源限制等功能。
"""

import asyncio
import logging
import os
import signal
import subprocess
import time
import threading
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
import psutil
import shlex

from .config_manager import ConfigManager

logger = logging.getLogger(__name__)


class ExecutionContext:
    """执行上下文"""
    
    def __init__(self, task_id: str, command: str, timeout: int = 300):
        self.task_id = task_id
        self.command = command
        self.timeout = timeout
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.process: Optional[subprocess.Popen] = None
        self.cancelled = False
        self.stdout_data = ""
        self.stderr_data = ""
        self.return_code: Optional[int] = None


class CommandExecutor:
    """命令执行引擎"""
    
    def __init__(self, config_manager: ConfigManager):
        """
        初始化命令执行引擎
        
        Args:
            config_manager: 配置管理器
        """
        self.config_manager = config_manager
        self.config = config_manager.get_execution_config()
        
        # 执行上下文管理
        self.active_contexts: Dict[str, ExecutionContext] = {}
        self.context_lock = threading.Lock()
        
        # 创建工作目录
        self._ensure_working_directory()
        
        logger.info("命令执行引擎初始化完成")
    
    def _ensure_working_directory(self) -> None:
        """确保工作目录存在"""
        work_dir = Path(self.config.working_directory)
        try:
            work_dir.mkdir(parents=True, exist_ok=True)
            # 设置权限
            os.chmod(work_dir, 0o755)
            logger.info(f"工作目录已准备: {work_dir}")
        except Exception as e:
            logger.error(f"创建工作目录失败: {e}")
            raise
    
    def execute(self, command: str, timeout: Optional[int] = None, 
                task_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        执行命令（同步）
        
        Args:
            command: 要执行的命令
            timeout: 超时时间（秒）
            task_id: 任务ID
            **kwargs: 其他参数
            
        Returns:
            执行结果
        """
        # 生成任务ID
        if not task_id:
            task_id = f"sync_{int(time.time())}_{id(threading.current_thread())}"
        
        # 设置超时
        if timeout is None:
            timeout = self.config.default_timeout
        timeout = min(timeout, self.config.max_timeout)
        
        # 创建执行上下文
        context = ExecutionContext(task_id, command, timeout)
        
        try:
            with self.context_lock:
                self.active_contexts[task_id] = context
            
            logger.info(f"开始执行命令 [{task_id}]: {command}")
            
            # 执行命令
            result = self._execute_command(context)
            
            logger.info(f"命令执行完成 [{task_id}]: 返回码={result['return_code']}")
            
            return result
            
        except Exception as e:
            logger.error(f"命令执行异常 [{task_id}]: {e}")
            return self._create_error_result(context, str(e))
        
        finally:
            # 清理上下文
            with self.context_lock:
                self.active_contexts.pop(task_id, None)
    
    async def execute_async(self, command: str, timeout: Optional[int] = None,
                           task_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        执行命令（异步）
        
        Args:
            command: 要执行的命令
            timeout: 超时时间（秒）
            task_id: 任务ID
            **kwargs: 其他参数
            
        Returns:
            执行结果
        """
        # 在线程池中执行同步方法
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.execute, command, timeout, task_id
        )
    
    def _execute_command(self, context: ExecutionContext) -> Dict[str, Any]:
        """
        执行命令的核心逻辑
        
        Args:
            context: 执行上下文
            
        Returns:
            执行结果
        """
        try:
            # 解析命令
            cmd_parts = self._parse_command(context.command)
            
            # 设置执行环境
            env = self._prepare_environment()
            
            # 启动进程
            context.process = subprocess.Popen(
                cmd_parts,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                env=env,
                cwd=self.config.working_directory,
                shell=False,  # 安全：不使用shell
                preexec_fn=self._setup_process_limits,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # 等待进程完成或超时
            try:
                stdout, stderr = context.process.communicate(timeout=context.timeout)
                context.stdout_data = stdout
                context.stderr_data = stderr
                context.return_code = context.process.returncode
                
            except subprocess.TimeoutExpired:
                # 超时处理
                logger.warning(f"命令执行超时 [{context.task_id}]: {context.timeout}秒")
                self._terminate_process(context.process)
                context.stdout_data = "命令执行超时"
                context.stderr_data = f"执行超时 ({context.timeout}秒)"
                context.return_code = -1
            
            context.end_time = time.time()
            
            # 创建结果
            return self._create_success_result(context)
            
        except Exception as e:
            context.end_time = time.time()
            logger.error(f"命令执行失败 [{context.task_id}]: {e}")
            return self._create_error_result(context, str(e))
    
    def _parse_command(self, command: str) -> List[str]:
        """
        安全地解析命令
        
        Args:
            command: 命令字符串
            
        Returns:
            命令部分列表
        """
        try:
            # 使用 shlex 安全解析命令
            parts = shlex.split(command)
            
            if not parts:
                raise ValueError("空命令")
            
            # 验证命令路径
            cmd_name = parts[0]
            if not self._is_valid_command(cmd_name):
                raise ValueError(f"无效的命令: {cmd_name}")
            
            return parts
            
        except Exception as e:
            logger.error(f"命令解析失败: {e}")
            raise
    
    def _is_valid_command(self, cmd_name: str) -> bool:
        """
        验证命令是否有效
        
        Args:
            cmd_name: 命令名称
            
        Returns:
            是否有效
        """
        # 检查是否为绝对路径
        if os.path.isabs(cmd_name):
            return os.path.isfile(cmd_name) and os.access(cmd_name, os.X_OK)
        
        # 在PATH中查找命令
        for path_dir in os.environ.get("PATH", "").split(os.pathsep):
            if path_dir:
                cmd_path = os.path.join(path_dir, cmd_name)
                if os.path.isfile(cmd_path) and os.access(cmd_path, os.X_OK):
                    return True
        
        return False
    
    def _prepare_environment(self) -> Dict[str, str]:
        """
        准备执行环境
        
        Returns:
            环境变量字典
        """
        # 复制当前环境
        env = os.environ.copy()
        
        # 添加配置的环境变量
        if hasattr(self.config, 'environment'):
            env.update(self.config.environment)
        
        # 安全设置
        env["LC_ALL"] = "C"  # 避免本地化问题
        env["LANG"] = "C"
        
        # 限制PATH
        safe_paths = [
            "/usr/local/sbin",
            "/usr/local/bin", 
            "/usr/sbin",
            "/usr/bin",
            "/sbin",
            "/bin"
        ]
        env["PATH"] = ":".join(safe_paths)
        
        return env
    
    def _setup_process_limits(self) -> None:
        """设置进程资源限制"""
        try:
            import resource
            
            # 设置内存限制
            if hasattr(self.config, 'resource_limits'):
                limits = self.config.resource_limits
                
                # 内存限制
                if 'max_memory' in limits:
                    max_memory = limits['max_memory']
                    resource.setrlimit(resource.RLIMIT_AS, (max_memory, max_memory))
                
                # CPU时间限制
                if 'max_cpu_time' in limits:
                    max_cpu = limits['max_cpu_time']
                    resource.setrlimit(resource.RLIMIT_CPU, (max_cpu, max_cpu))
                
                # 文件大小限制
                if 'max_file_size' in limits:
                    max_file = limits['max_file_size']
                    resource.setrlimit(resource.RLIMIT_FSIZE, (max_file, max_file))
                
                # 进程数限制
                if 'max_processes' in limits:
                    max_proc = limits['max_processes']
                    resource.setrlimit(resource.RLIMIT_NPROC, (max_proc, max_proc))
            
            # 设置进程组，便于终止子进程
            os.setpgrp()
            
        except Exception as e:
            logger.warning(f"设置进程限制失败: {e}")
    
    def _terminate_process(self, process: subprocess.Popen) -> None:
        """
        终止进程
        
        Args:
            process: 要终止的进程
        """
        try:
            if process.poll() is None:  # 进程仍在运行
                # 首先尝试优雅终止
                process.terminate()
                
                # 等待一段时间
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # 强制终止
                    process.kill()
                    process.wait()
                
                logger.info(f"进程已终止: PID={process.pid}")
                
        except Exception as e:
            logger.error(f"终止进程失败: {e}")
    
    def _create_success_result(self, context: ExecutionContext) -> Dict[str, Any]:
        """
        创建成功结果
        
        Args:
            context: 执行上下文
            
        Returns:
            结果字典
        """
        duration = (context.end_time or time.time()) - context.start_time
        
        return {
            "success": context.return_code == 0,
            "task_id": context.task_id,
            "command": context.command,
            "stdout": context.stdout_data,
            "stderr": context.stderr_data,
            "return_code": context.return_code,
            "start_time": context.start_time,
            "end_time": context.end_time,
            "duration": duration,
            "cancelled": context.cancelled,
            "timeout": context.timeout
        }
    
    def _create_error_result(self, context: ExecutionContext, error: str) -> Dict[str, Any]:
        """
        创建错误结果
        
        Args:
            context: 执行上下文
            error: 错误信息
            
        Returns:
            结果字典
        """
        duration = (context.end_time or time.time()) - context.start_time
        
        return {
            "success": False,
            "task_id": context.task_id,
            "command": context.command,
            "stdout": context.stdout_data,
            "stderr": context.stderr_data or error,
            "return_code": context.return_code or -1,
            "start_time": context.start_time,
            "end_time": context.end_time,
            "duration": duration,
            "error": error,
            "cancelled": context.cancelled,
            "timeout": context.timeout
        }
    
    def cancel_task(self, task_id: str, force: bool = False) -> bool:
        """
        取消任务
        
        Args:
            task_id: 任务ID
            force: 是否强制取消
            
        Returns:
            是否成功取消
        """
        with self.context_lock:
            context = self.active_contexts.get(task_id)
            
            if not context:
                logger.warning(f"任务不存在: {task_id}")
                return False
            
            if context.process and context.process.poll() is None:
                try:
                    context.cancelled = True
                    
                    if force:
                        context.process.kill()
                    else:
                        context.process.terminate()
                    
                    logger.info(f"任务已取消: {task_id}")
                    return True
                    
                except Exception as e:
                    logger.error(f"取消任务失败 {task_id}: {e}")
                    return False
            
            return True
    
    def get_active_tasks(self) -> List[str]:
        """
        获取活动任务列表
        
        Returns:
            活动任务ID列表
        """
        with self.context_lock:
            return list(self.active_contexts.keys())
    
    def get_task_info(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务信息
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务信息
        """
        with self.context_lock:
            context = self.active_contexts.get(task_id)
            
            if not context:
                return None
            
            return {
                "task_id": context.task_id,
                "command": context.command,
                "start_time": context.start_time,
                "timeout": context.timeout,
                "cancelled": context.cancelled,
                "running": context.process and context.process.poll() is None
            }
    
    def cleanup_completed_tasks(self) -> None:
        """清理已完成的任务"""
        with self.context_lock:
            completed_tasks = []
            
            for task_id, context in self.active_contexts.items():
                if context.process and context.process.poll() is not None:
                    completed_tasks.append(task_id)
            
            for task_id in completed_tasks:
                del self.active_contexts[task_id]
            
            if completed_tasks:
                logger.info(f"清理了 {len(completed_tasks)} 个已完成任务")
    
    def get_system_stats(self) -> Dict[str, Any]:
        """
        获取系统统计信息
        
        Returns:
            系统统计信息
        """
        try:
            return {
                "active_tasks": len(self.active_contexts),
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_usage": psutil.disk_usage(self.config.working_directory).percent,
                "load_average": os.getloadavg() if hasattr(os, 'getloadavg') else None
            }
        except Exception as e:
            logger.error(f"获取系统统计失败: {e}")
            return {"error": str(e)}
