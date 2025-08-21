"""
协议模块

实现 MCP (Model Context Protocol) 协议和 SSE (Server-Sent Events) 支持。
包含：
- MCP 服务器实现
- SSE 事件处理
- 消息解析和验证
- 协议合规性检查
"""

from .mcp_server import MCPServer
from .sse_handler import SSEHandler
from .message_parser import MessageParser
from .protocol_validator import ProtocolValidator

__all__ = [
    "MCPServer",
    "SSEHandler", 
    "MessageParser",
    "ProtocolValidator"
]
