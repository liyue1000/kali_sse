"""
MCP SSE 端点

实现基于 SSE 的 MCP 协议通信端点。
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Dict, Any, List, Optional, AsyncGenerator
from fastapi import Request, HTTPException
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from .protocols.message_parser import MessageParser, MCPMessage, MCPErrorCodes
from .core.executor import CommandExecutor
from .security.command_validator import CommandValidator
from .intelligence.syntax_checker import SyntaxChecker

logger = logging.getLogger(__name__)


class MCPSSEConnection:
    """MCP SSE 连接"""
    
    def __init__(self, connection_id: str, request: Request):
        self.connection_id = connection_id
        self.request = request
        self.created_at = time.time()
        self.last_activity = time.time()
        self.active = True
        self.initialized = False
        
        # MCP 组件
        self.message_parser = MessageParser()
        self.executor = None  # 将在初始化时设置
        self.validator = None
        self.syntax_checker = None
        
        # 消息队列
        self.outbound_queue: asyncio.Queue = asyncio.Queue()
        self.pending_requests: Dict[str, asyncio.Future] = {}
        
        logger.info(f"创建 MCP SSE 连接: {connection_id}")
    
    def set_components(self, executor: CommandExecutor, validator: CommandValidator, 
                      syntax_checker: SyntaxChecker):
        """设置MCP组件"""
        self.executor = executor
        self.validator = validator
        self.syntax_checker = syntax_checker
    
    async def send_message(self, message: Dict[str, Any]) -> None:
        """发送消息到客户端"""
        if not self.active:
            return
        
        try:
            await self.outbound_queue.put(message)
            self.last_activity = time.time()
        except Exception as e:
            logger.error(f"发送消息失败 [{self.connection_id}]: {e}")
    
    async def handle_message(self, message_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """处理收到的消息"""
        try:
            self.last_activity = time.time()
            
            # 解析消息
            message = self.message_parser.parse_message(message_data)
            
            # 处理不同类型的请求
            if message.method == "initialize":
                return await self._handle_initialize(message)
            elif message.method == "tools/list":
                return await self._handle_tools_list(message)
            elif message.method == "tools/call":
                return await self._handle_tools_call(message)
            elif message.method == "resources/list":
                return await self._handle_resources_list(message)
            elif message.method == "prompts/list":
                return await self._handle_prompts_list(message)
            else:
                return self._create_error_response(
                    message.id,
                    MCPErrorCodes.METHOD_NOT_FOUND,
                    f"未知方法: {message.method}"
                )
                
        except Exception as e:
            logger.error(f"处理消息异常 [{self.connection_id}]: {e}")
            return self._create_error_response(
                message_data.get("id"),
                MCPErrorCodes.INTERNAL_ERROR,
                f"内部错误: {str(e)}"
            )
    
    async def _handle_initialize(self, message: MCPMessage) -> Dict[str, Any]:
        """处理初始化请求"""
        logger.info(f"处理初始化请求 [{self.connection_id}]: {message.params}")
        
        # 验证协议版本
        client_version = message.params.get("protocolVersion") if message.params else None
        if client_version != "2024-11-05":
            logger.warning(f"协议版本不匹配 [{self.connection_id}]: 客户端={client_version}")
        
        self.initialized = True
        
        return {
            "jsonrpc": "2.0",
            "id": message.id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"subscribe": False, "listChanged": False},
                    "prompts": {"listChanged": False},
                    "logging": {}
                },
                "serverInfo": {
                    "name": "kali-sse-mcp",
                    "version": "1.0.0"
                }
            }
        }
    
    async def _handle_tools_list(self, message: MCPMessage) -> Dict[str, Any]:
        """处理工具列表请求"""
        logger.info(f"处理工具列表请求 [{self.connection_id}]")
        
        tools = [
            {
                "name": "execute_command",
                "description": "执行Kali Linux安全工具命令",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "要执行的命令"},
                        "args": {"type": "array", "items": {"type": "string"}, "description": "命令参数"},
                        "options": {"type": "object", "description": "执行选项"}
                    },
                    "required": ["command"]
                }
            },
            {
                "name": "validate_command",
                "description": "验证命令的安全性和语法",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "要验证的命令"}
                    },
                    "required": ["command"]
                }
            },
            {
                "name": "list_supported_tools",
                "description": "列出支持的安全工具",
                "inputSchema": {"type": "object", "properties": {}}
            }
        ]
        
        return {
            "jsonrpc": "2.0",
            "id": message.id,
            "result": {"tools": tools}
        }
    
    async def _handle_tools_call(self, message: MCPMessage) -> Dict[str, Any]:
        """处理工具调用请求"""
        logger.info(f"处理工具调用请求 [{self.connection_id}]: {message.params}")
        
        try:
            params = message.params or {}
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            if tool_name == "execute_command":
                result = await self._execute_command(arguments)
            elif tool_name == "validate_command":
                result = await self._validate_command(arguments)
            elif tool_name == "list_supported_tools":
                result = await self._list_supported_tools(arguments)
            else:
                return self._create_error_response(
                    message.id,
                    MCPErrorCodes.INVALID_PARAMS,
                    f"未知工具: {tool_name}"
                )
            
            return {
                "jsonrpc": "2.0",
                "id": message.id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, ensure_ascii=False, indent=2)
                        }
                    ]
                }
            }
            
        except Exception as e:
            logger.error(f"工具调用异常 [{self.connection_id}]: {e}")
            return self._create_error_response(
                message.id,
                MCPErrorCodes.INTERNAL_ERROR,
                f"工具调用失败: {str(e)}"
            )
    
    async def _handle_resources_list(self, message: MCPMessage) -> Dict[str, Any]:
        """处理资源列表请求"""
        return {
            "jsonrpc": "2.0",
            "id": message.id,
            "result": {"resources": []}
        }
    
    async def _handle_prompts_list(self, message: MCPMessage) -> Dict[str, Any]:
        """处理提示列表请求"""
        return {
            "jsonrpc": "2.0",
            "id": message.id,
            "result": {"prompts": []}
        }
    
    async def _execute_command(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """执行命令"""
        command = arguments.get("command")
        args = arguments.get("args", [])
        options = arguments.get("options", {})
        
        if not command:
            raise ValueError("缺少命令参数")
        
        # 构建完整命令
        full_command = command
        if args:
            full_command += " " + " ".join(args)
        
        # 安全验证
        validation_result = self.validator.validate_command(full_command)
        if not validation_result["valid"]:
            return {
                "success": False,
                "error": "命令验证失败",
                "details": validation_result["issues"]
            }
        
        # 执行命令
        timeout = options.get("timeout", 300)
        result = self.executor.execute(full_command, timeout=timeout)
        
        return {
            "success": result["success"],
            "command": full_command,
            "output": {
                "stdout": result.get("stdout", ""),
                "stderr": result.get("stderr", ""),
                "return_code": result.get("return_code", -1)
            },
            "metadata": {
                "duration": result.get("duration", 0),
                "start_time": result.get("start_time"),
                "end_time": result.get("end_time")
            }
        }
    
    async def _validate_command(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """验证命令"""
        command = arguments.get("command")
        
        if not command:
            raise ValueError("缺少命令参数")
        
        # 安全验证
        security_result = self.validator.validate_command(command)
        
        # 语法检查
        syntax_result = self.syntax_checker.check_syntax(command)
        
        return {
            "command": command,
            "security": {
                "valid": security_result["valid"],
                "score": security_result["score"],
                "issues": security_result.get("issues", [])
            },
            "syntax": {
                "valid": syntax_result["valid"],
                "score": syntax_result["score"],
                "suggestions": syntax_result.get("suggestions", [])
            }
        }
    
    async def _list_supported_tools(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """列出支持的工具"""
        tools = self.validator.get_allowed_tools()

        tool_info = []
        for tool_name in tools:
            config = self.validator.get_tool_config(tool_name)
            if config:
                tool_info.append({
                    "name": tool_name,
                    "description": config.get("description", f"{tool_name} - 安全工具"),
                    "allowed": config.get("allowed", True),
                    "timeout_limit": config.get("timeout_limit", 3600),
                    "category": self._get_tool_category(tool_name)
                })

        return {
            "tools": tool_info,
            "total_count": len(tool_info),
            "security_level": getattr(self.validator, 'security_level', 'MEDIUM'),
            "dangerous_commands_blocked": len(getattr(self.validator, 'dangerous_commands', []))
        }

    def _get_tool_category(self, tool_name: str) -> str:
        """获取工具分类"""
        categories = {
            "nmap": "网络扫描",
            "nikto": "Web扫描",
            "dirb": "目录扫描",
            "gobuster": "目录扫描",
            "hydra": "密码破解",
            "john": "密码破解",
            "sqlmap": "SQL注入",
            "burpsuite": "Web安全",
            "metasploit": "渗透框架",
            "wireshark": "网络分析",
            "tcpdump": "网络分析",
            "curl": "网络工具",
            "wget": "网络工具",
            "echo": "基础工具"
        }
        return categories.get(tool_name, "其他工具")
    
    def _create_error_response(self, request_id: Any, error_code: int, 
                             error_message: str) -> Dict[str, Any]:
        """创建错误响应"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": error_code,
                "message": error_message
            }
        }
    
    def close(self):
        """关闭连接"""
        self.active = False
        logger.info(f"关闭 MCP SSE 连接: {self.connection_id}")


class MCPSSEHandler:
    """MCP SSE 处理器"""
    
    def __init__(self, executor: CommandExecutor, validator: CommandValidator, 
                 syntax_checker: SyntaxChecker):
        self.executor = executor
        self.validator = validator
        self.syntax_checker = syntax_checker
        self.connections: Dict[str, MCPSSEConnection] = {}
        
        logger.info("MCP SSE 处理器初始化完成")
    
    async def create_connection(self, request: Request) -> StreamingResponse:
        """创建新的MCP SSE连接"""
        connection_id = str(uuid.uuid4())
        connection = MCPSSEConnection(connection_id, request)
        connection.set_components(self.executor, self.validator, self.syntax_checker)
        
        self.connections[connection_id] = connection
        
        async def event_stream():
            try:
                # 发送连接建立事件
                await connection.send_message({
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                    "params": {
                        "connection_id": connection_id,
                        "timestamp": time.time(),
                        "message": "MCP SSE connection established"
                    }
                })
                
                while connection.active:
                    try:
                        # 等待消息
                        message = await asyncio.wait_for(
                            connection.outbound_queue.get(), 
                            timeout=30.0
                        )
                        
                        # 发送消息
                        yield {
                            "event": "message",
                            "data": json.dumps(message, ensure_ascii=False)
                        }
                        
                    except asyncio.TimeoutError:
                        # 发送心跳
                        yield {
                            "event": "ping",
                            "data": json.dumps({"timestamp": time.time()})
                        }
                        
            except Exception as e:
                logger.error(f"SSE 流异常 [{connection_id}]: {e}")
            finally:
                connection.close()
                if connection_id in self.connections:
                    del self.connections[connection_id]
        
        return EventSourceResponse(event_stream())
    
    async def handle_message(self, connection_id: str, message_data: Dict[str, Any]) -> None:
        """处理收到的消息"""
        connection = self.connections.get(connection_id)
        if not connection:
            logger.warning(f"未找到连接: {connection_id}")
            return

        response = await connection.handle_message(message_data)
        if response:
            await connection.send_message(response)

    async def handle_direct_message(self, message_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """直接处理消息（用于POST请求）"""
        try:
            # 创建临时连接来处理消息
            temp_connection = MCPSSEConnection("temp", None)
            temp_connection.set_components(self.executor, self.validator, self.syntax_checker)

            # 处理消息
            response = await temp_connection.handle_message(message_data)
            return response

        except Exception as e:
            logger.error(f"直接处理消息失败: {e}")
            return {
                "jsonrpc": "2.0",
                "id": message_data.get("id"),
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
