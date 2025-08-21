"""
MCP 服务器实现

基于 FastMCP 实现符合 MCP 协议标准的服务器端。
提供工具注册、消息处理、协议合规性等功能。
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Dict, Any, List, Optional, Callable
from fastapi import FastAPI, Request, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ..core.config_manager import ConfigManager
from ..core.executor import CommandExecutor
from ..core.task_manager import TaskManager, TaskPriority
from ..core.result_formatter import ResultFormatter
from ..security.command_validator import CommandValidator
from ..intelligence.syntax_checker import SyntaxChecker
from .sse_handler import SSEHandler
from .message_parser import MessageParser, MCPErrorCodes
from .protocol_validator import ProtocolValidator
from ..mcp_sse_endpoint import MCPSSEHandler

logger = logging.getLogger(__name__)


class CommandRequest(BaseModel):
    """命令请求模型"""
    command: str = Field(..., description="要执行的命令")
    args: Optional[List[str]] = Field(default=None, description="命令参数列表")
    options: Optional[Dict[str, Any]] = Field(default=None, description="执行选项")
    context: Optional[Dict[str, Any]] = Field(default=None, description="执行上下文")


class TaskStatusRequest(BaseModel):
    """任务状态请求模型"""
    task_id: str = Field(..., description="任务ID")


class CancelTaskRequest(BaseModel):
    """取消任务请求模型"""
    task_id: str = Field(..., description="任务ID")
    force: bool = Field(default=False, description="是否强制取消")


class CommandValidationRequest(BaseModel):
    """命令验证请求模型"""
    command: str = Field(..., description="要验证的命令")
    check_syntax: bool = Field(default=True, description="是否检查语法")
    check_security: bool = Field(default=True, description="是否检查安全性")


class CommandSuggestionRequest(BaseModel):
    """命令建议请求模型"""
    partial_command: str = Field(..., description="部分命令")
    context: Optional[str] = Field(default=None, description="上下文")
    target_type: Optional[str] = Field(default=None, description="目标类型")


class MCPServer:
    """MCP 服务器"""

    def __init__(self, config_manager: ConfigManager):
        """
        初始化 MCP 服务器

        Args:
            config_manager: 配置管理器
        """
        self.config_manager = config_manager
        self.config = config_manager.get_config()

        # 初始化组件
        self.executor = CommandExecutor(config_manager)
        self.validator = CommandValidator(config_manager)
        self.syntax_checker = SyntaxChecker(config_manager)
        self.task_manager = TaskManager(config_manager)
        self.result_formatter = ResultFormatter()
        self.sse_handler = SSEHandler(config_manager)
        self.message_parser = MessageParser()
        self.protocol_validator = ProtocolValidator()

        # 初始化 MCP SSE 处理器
        self.mcp_sse_handler = MCPSSEHandler(
            self.executor,
            self.validator,
            self.syntax_checker
        )

        # 创建 FastAPI 应用
        self.app = FastAPI(
            title="Kali SSE MCP Server",
            description="符合MCP规范的智能化Kali Linux命令执行器",
            version="1.0.0"
        )

        # 配置CORS
        self._setup_cors()

        # 注册路由
        self._register_routes()

        # 设置事件回调
        self._setup_event_callbacks()

        # 启动清理任务
        self.task_manager.start_cleanup_task()
        self.sse_handler.start_cleanup_task()

        logger.info("MCP 服务器初始化完成")
    
    def _setup_cors(self) -> None:
        """设置CORS"""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # 在生产环境中应该限制具体域名
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _register_routes(self) -> None:
        """注册路由"""

        @self.app.get("/health")
        async def health_check():
            """健康检查"""
            return {
                "status": "healthy",
                "version": "1.0.0",
                "timestamp": time.time(),
                "active_tasks": len(self.task_manager.get_running_tasks()),
                "pending_tasks": len(self.task_manager.get_pending_tasks())
            }

        @self.app.get("/sse/connect")
        async def sse_connect(
            request: Request,
            events: str = Query(default="*", description="订阅的事件类型，用逗号分隔")
        ):
            """SSE连接端点"""
            event_types = [e.strip() for e in events.split(",") if e.strip()]
            connection_id = await self.sse_handler.create_connection(request, event_types)

            return StreamingResponse(
                self.sse_handler.event_stream(connection_id),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Cache-Control"
                }
            )

        @self.app.get("/mcp/sse")
        async def mcp_sse_connect(request: Request):
            """MCP SSE连接端点"""
            return await self.mcp_sse_handler.create_connection(request)

        @self.app.post("/mcp/sse")
        async def mcp_sse_message(request: Request):
            """MCP SSE消息端点 - 处理Cursor的POST请求"""
            try:
                # 读取请求体
                body = await request.body()
                if body:
                    message_data = json.loads(body.decode())

                    # 处理消息并返回响应
                    response = await self.mcp_sse_handler.handle_direct_message(message_data)

                    if response:
                        return response
                    else:
                        return {"jsonrpc": "2.0", "id": message_data.get("id"), "result": {}}
                else:
                    return {"error": "Empty request body"}

            except Exception as e:
                logger.error(f"处理MCP SSE POST请求失败: {e}")
                return {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32603,
                        "message": f"Internal error: {str(e)}"
                    }
                }

        @self.app.post("/api/v1/execute")
        async def execute_command(request: CommandRequest):
            """执行命令API"""
            try:
                result = await self._execute_command_async(request)
                return result
            except Exception as e:
                logger.error(f"命令执行API异常: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "error_type": "api_error"
                }

        @self.app.get("/api/v1/tasks/{task_id}")
        async def get_task_status(task_id: str):
            """获取任务状态API"""
            status = self.task_manager.get_task_status(task_id)
            if status:
                return {"success": True, **status}
            else:
                return {
                    "success": False,
                    "error": "任务不存在",
                    "error_type": "task_not_found"
                }

        @self.app.delete("/api/v1/tasks/{task_id}")
        async def cancel_task(task_id: str, force: bool = False):
            """取消任务API"""
            success = self.task_manager.cancel_task(task_id, force)
            if success:
                return {
                    "success": True,
                    "task_id": task_id,
                    "message": "任务已取消"
                }
            else:
                return {
                    "success": False,
                    "error": "任务取消失败",
                    "error_type": "cancellation_error"
                }

        @self.app.get("/api/v1/tools")
        async def list_supported_tools():
            """列出支持的工具API"""
            return self._list_supported_tools()

        @self.app.post("/api/v1/validate")
        async def validate_command(request: CommandValidationRequest):
            """验证命令API"""
            return self._validate_command(request)

        @self.app.post("/api/v1/suggestions")
        async def get_command_suggestions(request: CommandSuggestionRequest):
            """获取命令建议API"""
            return self._get_command_suggestions(request)

        @self.app.get("/api/v1/tasks")
        async def list_tasks(status: str = None, user_id: str = None):
            """列出任务API"""
            if status:
                from ..core.task_manager import TaskStatus
                try:
                    task_status = TaskStatus(status)
                    task_ids = self.task_manager.get_tasks_by_status(task_status)
                except ValueError:
                    return {"success": False, "error": "无效的状态值"}
            elif user_id:
                task_ids = self.task_manager.get_tasks_by_user(user_id)
            else:
                # 返回所有活跃任务
                task_ids = (self.task_manager.get_pending_tasks() +
                           self.task_manager.get_running_tasks())

            tasks = []
            for task_id in task_ids:
                task_status = self.task_manager.get_task_status(task_id)
                if task_status:
                    tasks.append(task_status)

            return {
                "success": True,
                "tasks": tasks,
                "total": len(tasks)
            }

        @self.app.get("/api/v1/stats")
        async def get_statistics():
            """获取统计信息API"""
            return {
                "success": True,
                "task_stats": self.task_manager.get_statistics(),
                "sse_stats": self.sse_handler.get_connection_stats(),
                "system_stats": self.executor.get_system_stats()
            }

        logger.info("API 路由注册完成")

    def _setup_event_callbacks(self) -> None:
        """设置事件回调"""

        def on_task_started(task):
            asyncio.create_task(self.sse_handler.send_task_started(
                task.task_id, task.command
            ))

        def on_task_progress(task):
            asyncio.create_task(self.sse_handler.send_task_progress(
                task.task_id, task.progress, task.status.value
            ))

        def on_task_completed(task):
            output = task.result.get("stdout", "") if task.result else ""
            return_code = task.result.get("return_code", -1) if task.result else -1
            duration = task.duration or 0

            asyncio.create_task(self.sse_handler.send_task_completed(
                task.task_id, task.status.value, output, return_code, duration
            ))

        def on_task_failed(task):
            error = task.error or "未知错误"
            output = task.result.get("stdout", "") if task.result else ""

            asyncio.create_task(self.sse_handler.send_task_failed(
                task.task_id, error, "execution_error", output
            ))

        # 注册回调
        self.task_manager.add_event_callback("task_started", on_task_started)
        self.task_manager.add_event_callback("task_progress", on_task_progress)
        self.task_manager.add_event_callback("task_completed", on_task_completed)
        self.task_manager.add_event_callback("task_failed", on_task_failed)

    async def _execute_command_async(self, request: CommandRequest) -> Dict[str, Any]:
        """
        异步执行命令
        
        Args:
            request: 命令请求
            
        Returns:
            执行结果
        """
        try:
            # 构建完整命令
            command = request.command
            args = request.args or []

            # 获取执行选项
            options = request.options or {}
            timeout = options.get("timeout", self.config.execution.default_timeout)
            async_exec = options.get("async", False)
            priority_str = options.get("priority", "normal")

            # 转换优先级
            priority_map = {
                "low": TaskPriority.LOW,
                "normal": TaskPriority.NORMAL,
                "high": TaskPriority.HIGH,
                "critical": TaskPriority.CRITICAL
            }
            priority = priority_map.get(priority_str, TaskPriority.NORMAL)

            # 构建完整命令字符串用于验证
            full_command = command
            if args:
                full_command += " " + " ".join(args)

            # 安全验证
            validation_result = self.validator.validate_command(full_command)
            if not validation_result["valid"]:
                # 发送安全警报
                await self.sse_handler.send_security_alert(
                    "command_validation_failed",
                    "high",
                    full_command,
                    f"验证失败: {validation_result['issues']}"
                )

                return {
                    "success": False,
                    "error": "命令验证失败",
                    "details": validation_result["issues"],
                    "error_type": "validation_error"
                }

            # 检查是否可以接受新任务
            if not self.task_manager.can_accept_new_task():
                return {
                    "success": False,
                    "error": "系统负载过高，无法接受新任务",
                    "error_type": "system_overload"
                }

            # 创建任务
            task_id = self.task_manager.create_task(
                command=command,
                args=args,
                options=options,
                priority=priority,
                user_id=request.context.get("user_id") if request.context else None,
                session_id=request.context.get("session_id") if request.context else None
            )

            # 执行任务
            if async_exec:
                # 异步执行
                asyncio.create_task(self._execute_task_async(task_id))

                return {
                    "success": True,
                    "task_id": task_id,
                    "status": "started",
                    "message": "任务已启动，使用 get_task_status 查看进度"
                }
            else:
                # 同步执行
                result = await self._execute_task_async(task_id)
                return result
                
        except Exception as e:
            logger.error(f"命令执行失败: {e}")
            return {
                "success": False,
                "task_id": task_id if 'task_id' in locals() else None,
                "error": str(e),
                "error_type": "execution_error"
            }
    
    async def _execute_task_async(self, task_id: str) -> Dict[str, Any]:
        """
        异步执行任务

        Args:
            task_id: 任务ID

        Returns:
            执行结果
        """
        try:
            # 获取任务
            task = self.task_manager.get_task(task_id)
            if not task:
                return {
                    "success": False,
                    "task_id": task_id,
                    "error": "任务不存在",
                    "error_type": "task_not_found"
                }

            # 构建完整命令
            command = task.command
            if task.args:
                command += " " + " ".join(task.args)

            # 标记任务为运行中
            from ..core.task_manager import TaskStatus
            self.task_manager.update_task_status(task_id, TaskStatus.RUNNING)

            # 执行命令
            result = await asyncio.to_thread(
                self.executor.execute,
                command,
                timeout=task.timeout,
                task_id=task_id
            )

            # 更新任务状态和结果
            if result["success"]:
                self.task_manager.update_task_status(
                    task_id, TaskStatus.COMPLETED,
                    progress=1.0, result=result
                )
            else:
                self.task_manager.update_task_status(
                    task_id, TaskStatus.FAILED,
                    error=result.get("error", "执行失败"),
                    result=result
                )

            return {
                "success": result["success"],
                "task_id": task_id,
                "status": "completed" if result["success"] else "failed",
                "output": {
                    "stdout": result.get("stdout", ""),
                    "stderr": result.get("stderr", ""),
                    "return_code": result.get("return_code", -1)
                },
                "metadata": {
                    "start_time": result.get("start_time"),
                    "end_time": result.get("end_time"),
                    "duration": result.get("duration", 0),
                    "command": command
                }
            }

        except Exception as e:
            logger.error(f"任务执行失败 {task_id}: {e}")

            # 更新任务状态
            from ..core.task_manager import TaskStatus
            self.task_manager.update_task_status(
                task_id, TaskStatus.FAILED,
                error=str(e)
            )

            return {
                "success": False,
                "task_id": task_id,
                "status": "failed",
                "error": str(e),
                "error_type": "execution_error"
            }
    
    def _get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        获取任务状态

        Args:
            task_id: 任务ID

        Returns:
            任务状态
        """
        status = self.task_manager.get_task_status(task_id)
        if not status:
            return {
                "success": False,
                "error": "任务不存在",
                "error_type": "task_not_found"
            }

        return {
            "success": True,
            **status
        }
    
    async def _cancel_task_async(self, request: CancelTaskRequest) -> Dict[str, Any]:
        """
        异步取消任务

        Args:
            request: 取消任务请求

        Returns:
            取消结果
        """
        task_id = request.task_id
        force = request.force

        success = self.task_manager.cancel_task(task_id, force)

        if success:
            return {
                "success": True,
                "task_id": task_id,
                "status": "cancelled",
                "message": "任务已取消"
            }
        else:
            return {
                "success": False,
                "task_id": task_id,
                "error": "任务取消失败",
                "error_type": "cancellation_error"
            }
    
    def _list_supported_tools(self) -> Dict[str, Any]:
        """
        列出支持的工具
        
        Returns:
            支持的工具列表
        """
        # 这里应该从配置或工具检测中获取实际的工具列表
        tools = [
            {
                "name": "nmap",
                "version": "7.94",
                "description": "Network exploration tool and security scanner",
                "categories": ["network", "scanning"],
                "common_options": ["-sS", "-sV", "-O", "-A"]
            },
            {
                "name": "nikto",
                "version": "2.5.0", 
                "description": "Web server scanner",
                "categories": ["web", "vulnerability"],
                "common_options": ["-h", "-p", "-ssl"]
            },
            {
                "name": "dirb",
                "version": "2.22",
                "description": "Web content scanner",
                "categories": ["web", "enumeration"],
                "common_options": ["-r", "-S", "-w"]
            }
        ]
        
        return {
            "success": True,
            "tools": tools,
            "total_count": len(tools)
        }
    
    def _validate_command(self, request: CommandValidationRequest) -> Dict[str, Any]:
        """
        验证命令
        
        Args:
            request: 命令验证请求
            
        Returns:
            验证结果
        """
        try:
            # 安全验证
            security_result = self.validator.validate_command(request.command)
            
            # 语法检查
            syntax_result = {"valid": True, "score": 1.0, "suggestions": []}
            if request.check_syntax:
                syntax_result = self.syntax_checker.check_syntax(request.command)
            
            return {
                "success": True,
                "valid": security_result["valid"] and syntax_result["valid"],
                "syntax_score": syntax_result.get("score", 1.0),
                "security_score": security_result.get("score", 1.0),
                "issues": security_result.get("issues", []),
                "suggestions": syntax_result.get("suggestions", [])
            }
            
        except Exception as e:
            logger.error(f"命令验证失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "validation_error"
            }
    
    def _get_command_suggestions(self, request: CommandSuggestionRequest) -> Dict[str, Any]:
        """
        获取命令建议
        
        Args:
            request: 命令建议请求
            
        Returns:
            命令建议
        """
        try:
            suggestions = self.syntax_checker.get_suggestions(
                request.partial_command,
                context=request.context,
                target_type=request.target_type
            )
            
            return {
                "success": True,
                "suggestions": suggestions
            }
            
        except Exception as e:
            logger.error(f"获取命令建议失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "suggestion_error"
            }
    
    def get_app(self) -> FastAPI:
        """获取 FastAPI 应用实例"""
        return self.app

    def get_sse_handler(self) -> SSEHandler:
        """获取 SSE 处理器"""
        return self.sse_handler

    def get_task_manager(self) -> TaskManager:
        """获取任务管理器"""
        return self.task_manager


def create_server(config_manager: ConfigManager) -> MCPServer:
    """
    创建 MCP 服务器实例
    
    Args:
        config_manager: 配置管理器
        
    Returns:
        MCP 服务器实例
    """
    return MCPServer(config_manager)
