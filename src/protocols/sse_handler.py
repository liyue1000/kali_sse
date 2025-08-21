"""
SSE 事件处理器

提供 Server-Sent Events 支持，用于实时推送命令执行状态和结果。
"""

import asyncio
import json
import logging
import time
from typing import Dict, Any, List, Optional, AsyncGenerator
from fastapi import Request
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
import uuid

from ..core.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class SSEConnection:
    """SSE连接管理"""
    
    def __init__(self, connection_id: str, request: Request):
        self.connection_id = connection_id
        self.request = request
        self.created_at = time.time()
        self.last_ping = time.time()
        self.subscriptions: set = set()
        self.queue: asyncio.Queue = asyncio.Queue()
        self.active = True
    
    async def send_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """发送事件到客户端"""
        if not self.active:
            return
        
        try:
            event = {
                "event": event_type,
                "data": data,
                "timestamp": time.time(),
                "connection_id": self.connection_id
            }
            await self.queue.put(event)
        except Exception as e:
            logger.error(f"发送事件失败 [{self.connection_id}]: {e}")
    
    def subscribe(self, event_type: str) -> None:
        """订阅事件类型"""
        self.subscriptions.add(event_type)
    
    def unsubscribe(self, event_type: str) -> None:
        """取消订阅事件类型"""
        self.subscriptions.discard(event_type)
    
    def is_subscribed(self, event_type: str) -> bool:
        """检查是否订阅了事件类型"""
        return event_type in self.subscriptions or "*" in self.subscriptions
    
    def close(self) -> None:
        """关闭连接"""
        self.active = False


class SSEHandler:
    """SSE 事件处理器"""
    
    def __init__(self, config_manager: ConfigManager):
        """
        初始化 SSE 处理器
        
        Args:
            config_manager: 配置管理器
        """
        self.config_manager = config_manager
        self.config = config_manager.get_config()
        
        # 连接管理
        self.connections: Dict[str, SSEConnection] = {}
        self.connection_lock = asyncio.Lock()
        
        # 事件统计
        self.event_stats = {
            "total_connections": 0,
            "active_connections": 0,
            "events_sent": 0,
            "events_failed": 0
        }
        
        # 清理任务将在需要时启动
        self._cleanup_task_started = False
        
        logger.info("SSE 事件处理器初始化完成")

    def start_cleanup_task(self) -> None:
        """启动清理任务"""
        if not self._cleanup_task_started:
            try:
                asyncio.create_task(self._cleanup_task())
                self._cleanup_task_started = True
            except RuntimeError:
                # 如果没有运行的事件循环，稍后再启动
                pass
    
    async def create_connection(self, request: Request, 
                              event_types: Optional[List[str]] = None) -> str:
        """
        创建 SSE 连接
        
        Args:
            request: FastAPI 请求对象
            event_types: 订阅的事件类型列表
            
        Returns:
            连接ID
        """
        connection_id = str(uuid.uuid4())
        
        async with self.connection_lock:
            connection = SSEConnection(connection_id, request)
            
            # 订阅事件类型
            if event_types:
                for event_type in event_types:
                    connection.subscribe(event_type)
            else:
                # 默认订阅所有事件
                connection.subscribe("*")
            
            self.connections[connection_id] = connection
            
            # 更新统计
            self.event_stats["total_connections"] += 1
            self.event_stats["active_connections"] += 1
        
        logger.info(f"创建 SSE 连接: {connection_id}")
        return connection_id
    
    async def close_connection(self, connection_id: str) -> None:
        """
        关闭 SSE 连接
        
        Args:
            connection_id: 连接ID
        """
        async with self.connection_lock:
            connection = self.connections.get(connection_id)
            if connection:
                connection.close()
                del self.connections[connection_id]
                self.event_stats["active_connections"] -= 1
                logger.info(f"关闭 SSE 连接: {connection_id}")
    
    async def broadcast_event(self, event_type: str, data: Dict[str, Any],
                            target_connections: Optional[List[str]] = None) -> None:
        """
        广播事件到所有订阅的连接
        
        Args:
            event_type: 事件类型
            data: 事件数据
            target_connections: 目标连接ID列表，None表示广播到所有连接
        """
        if not self.connections:
            return
        
        async with self.connection_lock:
            connections_to_send = []
            
            if target_connections:
                # 发送到指定连接
                for conn_id in target_connections:
                    if conn_id in self.connections:
                        connections_to_send.append(self.connections[conn_id])
            else:
                # 发送到所有订阅的连接
                for connection in self.connections.values():
                    if connection.is_subscribed(event_type):
                        connections_to_send.append(connection)
        
        # 并发发送事件
        if connections_to_send:
            tasks = []
            for connection in connections_to_send:
                task = asyncio.create_task(connection.send_event(event_type, data))
                tasks.append(task)
            
            try:
                await asyncio.gather(*tasks, return_exceptions=True)
                self.event_stats["events_sent"] += len(connections_to_send)
            except Exception as e:
                logger.error(f"广播事件失败: {e}")
                self.event_stats["events_failed"] += 1
    
    async def send_to_connection(self, connection_id: str, event_type: str,
                               data: Dict[str, Any]) -> bool:
        """
        发送事件到指定连接
        
        Args:
            connection_id: 连接ID
            event_type: 事件类型
            data: 事件数据
            
        Returns:
            是否发送成功
        """
        connection = self.connections.get(connection_id)
        if not connection:
            return False
        
        try:
            await connection.send_event(event_type, data)
            self.event_stats["events_sent"] += 1
            return True
        except Exception as e:
            logger.error(f"发送事件到连接失败 [{connection_id}]: {e}")
            self.event_stats["events_failed"] += 1
            return False
    
    async def event_stream(self, connection_id: str) -> AsyncGenerator[str, None]:
        """
        生成 SSE 事件流
        
        Args:
            connection_id: 连接ID
            
        Yields:
            SSE 格式的事件字符串
        """
        connection = self.connections.get(connection_id)
        if not connection:
            logger.error(f"连接不存在: {connection_id}")
            return
        
        try:
            # 发送连接确认事件
            await connection.send_event("connection_established", {
                "connection_id": connection_id,
                "timestamp": time.time(),
                "message": "SSE connection established"
            })
            
            # 心跳间隔
            heartbeat_interval = 30  # 30秒
            last_heartbeat = time.time()
            
            while connection.active:
                try:
                    # 等待事件或超时
                    event = await asyncio.wait_for(
                        connection.queue.get(),
                        timeout=1.0
                    )
                    
                    # 格式化 SSE 事件
                    sse_data = self._format_sse_event(event)
                    yield sse_data
                    
                except asyncio.TimeoutError:
                    # 检查是否需要发送心跳
                    current_time = time.time()
                    if current_time - last_heartbeat > heartbeat_interval:
                        heartbeat_event = {
                            "event": "heartbeat",
                            "data": {"timestamp": current_time},
                            "timestamp": current_time,
                            "connection_id": connection_id
                        }
                        sse_data = self._format_sse_event(heartbeat_event)
                        yield sse_data
                        last_heartbeat = current_time
                    
                    continue
                
                except Exception as e:
                    logger.error(f"事件流处理异常 [{connection_id}]: {e}")
                    break
        
        finally:
            # 清理连接
            await self.close_connection(connection_id)
    
    def _format_sse_event(self, event: Dict[str, Any]) -> str:
        """
        格式化 SSE 事件
        
        Args:
            event: 事件数据
            
        Returns:
            SSE 格式字符串
        """
        event_type = event.get("event", "message")
        data = event.get("data", {})
        event_id = event.get("id", str(uuid.uuid4()))
        
        # 构建 SSE 格式
        sse_lines = []
        
        if event_id:
            sse_lines.append(f"id: {event_id}")
        
        sse_lines.append(f"event: {event_type}")
        
        # 处理数据，支持多行
        data_json = json.dumps(data, ensure_ascii=False)
        for line in data_json.split('\n'):
            sse_lines.append(f"data: {line}")
        
        sse_lines.append("")  # 空行表示事件结束
        
        return "\n".join(sse_lines) + "\n"
    
    async def _cleanup_task(self) -> None:
        """清理任务，定期清理无效连接"""
        while True:
            try:
                await asyncio.sleep(60)  # 每分钟清理一次
                
                current_time = time.time()
                connections_to_remove = []
                
                async with self.connection_lock:
                    for conn_id, connection in self.connections.items():
                        # 检查连接是否超时（5分钟无活动）
                        if current_time - connection.last_ping > 300:
                            connections_to_remove.append(conn_id)
                        
                        # 检查连接是否仍然活跃
                        if not connection.active:
                            connections_to_remove.append(conn_id)
                
                # 清理无效连接
                for conn_id in connections_to_remove:
                    await self.close_connection(conn_id)
                
                if connections_to_remove:
                    logger.info(f"清理了 {len(connections_to_remove)} 个无效连接")
                
            except Exception as e:
                logger.error(f"连接清理任务异常: {e}")
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """
        获取连接统计信息
        
        Returns:
            统计信息
        """
        return {
            **self.event_stats,
            "connections": {
                conn_id: {
                    "created_at": conn.created_at,
                    "last_ping": conn.last_ping,
                    "subscriptions": list(conn.subscriptions),
                    "queue_size": conn.queue.qsize()
                }
                for conn_id, conn in self.connections.items()
            }
        }
    
    async def ping_connection(self, connection_id: str) -> bool:
        """
        Ping 连接以保持活跃状态
        
        Args:
            connection_id: 连接ID
            
        Returns:
            是否成功
        """
        connection = self.connections.get(connection_id)
        if connection:
            connection.last_ping = time.time()
            return True
        return False
    
    # 预定义的事件类型
    async def send_task_started(self, task_id: str, command: str, 
                              connection_ids: Optional[List[str]] = None) -> None:
        """发送任务开始事件"""
        await self.broadcast_event("task_started", {
            "task_id": task_id,
            "command": command,
            "timestamp": time.time()
        }, connection_ids)
    
    async def send_task_progress(self, task_id: str, progress: float, 
                               status: str, partial_output: str = "",
                               connection_ids: Optional[List[str]] = None) -> None:
        """发送任务进度事件"""
        await self.broadcast_event("task_progress", {
            "task_id": task_id,
            "progress": progress,
            "status": status,
            "partial_output": partial_output,
            "timestamp": time.time()
        }, connection_ids)
    
    async def send_task_completed(self, task_id: str, status: str, 
                                final_output: str, return_code: int,
                                duration: float,
                                connection_ids: Optional[List[str]] = None) -> None:
        """发送任务完成事件"""
        await self.broadcast_event("task_completed", {
            "task_id": task_id,
            "status": status,
            "final_output": final_output,
            "return_code": return_code,
            "duration": duration,
            "timestamp": time.time()
        }, connection_ids)
    
    async def send_task_failed(self, task_id: str, error: str, 
                             error_code: str, partial_output: str = "",
                             connection_ids: Optional[List[str]] = None) -> None:
        """发送任务失败事件"""
        await self.broadcast_event("task_failed", {
            "task_id": task_id,
            "error": error,
            "error_code": error_code,
            "partial_output": partial_output,
            "timestamp": time.time()
        }, connection_ids)
    
    async def send_security_alert(self, alert_type: str, severity: str,
                                command: str, reason: str,
                                connection_ids: Optional[List[str]] = None) -> None:
        """发送安全警报事件"""
        await self.broadcast_event("security_alert", {
            "alert_type": alert_type,
            "severity": severity,
            "command": command,
            "reason": reason,
            "timestamp": time.time()
        }, connection_ids)
