#!/usr/bin/env python3
"""
MCP STDIO 服务器

符合 MCP 协议标准的 STDIO 服务器实现，用于与 Cursor 等客户端通信。
"""

import asyncio
import json
import logging
import sys
import os
from typing import Dict, Any, List, Optional
import traceback

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config_manager import ConfigManager
from src.core.executor import CommandExecutor
from src.security.command_validator import CommandValidator
from src.intelligence.syntax_checker import SyntaxChecker
from src.protocols.message_parser import MessageParser, MCPMessage, MCPErrorCodes

# 设置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/mcp_server.log'),
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)


class MCPStdioServer:
    """MCP STDIO 服务器"""
    
    def __init__(self):
        """初始化服务器"""
        self.config_manager = ConfigManager()
        self.executor = CommandExecutor(self.config_manager)
        self.validator = CommandValidator(self.config_manager)
        self.syntax_checker = SyntaxChecker(self.config_manager)
        self.message_parser = MessageParser()
        
        # 服务器信息
        self.server_info = {
            "name": "kali-sse-mcp",
            "version": "1.0.0",
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {
                    "listChanged": False
                },
                "resources": {
                    "subscribe": False,
                    "listChanged": False
                },
                "prompts": {
                    "listChanged": False
                },
                "logging": {}
            },
            "serverInfo": {
                "name": "kali-sse-mcp",
                "version": "1.0.0"
            }
        }
        
        # 工具定义
        self.tools = [
            {
                "name": "execute_command",
                "description": "执行Kali Linux安全工具命令",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "要执行的命令"
                        },
                        "args": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "命令参数列表"
                        },
                        "options": {
                            "type": "object",
                            "properties": {
                                "timeout": {"type": "number", "description": "超时时间（秒）"},
                                "async": {"type": "boolean", "description": "是否异步执行"}
                            },
                            "description": "执行选项"
                        }
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
                        "command": {
                            "type": "string",
                            "description": "要验证的命令"
                        }
                    },
                    "required": ["command"]
                }
            },
            {
                "name": "list_supported_tools",
                "description": "列出支持的安全工具",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]
        
        logger.info("MCP STDIO 服务器初始化完成")
    
    async def handle_message(self, message_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        处理消息

        Args:
            message_data: 消息数据

        Returns:
            响应消息（通知不返回响应）
        """
        try:
            # 检查是否是通知（没有id字段）
            if "id" not in message_data:
                # 这是一个通知，处理但不返回响应
                method = message_data.get("method")
                if method == "notifications/initialized":
                    logger.info("收到初始化完成通知")
                    return None
                else:
                    logger.warning(f"未知通知: {method}")
                    return None

            # 解析消息
            message = self.message_parser.parse_message(message_data)

            # 处理请求
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
            logger.error(f"处理消息异常: {e}")
            logger.error(traceback.format_exc())
            return self._create_error_response(
                message_data.get("id"),
                MCPErrorCodes.INTERNAL_ERROR,
                f"内部错误: {str(e)}"
            )
    
    async def _handle_initialize(self, message: MCPMessage) -> Dict[str, Any]:
        """处理初始化请求"""
        logger.info(f"处理初始化请求: {message.params}")

        # 验证客户端协议版本
        client_version = message.params.get("protocolVersion") if message.params else None
        if client_version != "2024-11-05":
            logger.warning(f"协议版本不匹配: 客户端={client_version}, 服务器=2024-11-05")

        return {
            "jsonrpc": "2.0",
            "id": message.id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": self.server_info["capabilities"],
                "serverInfo": self.server_info["serverInfo"]
            }
        }
    
    async def _handle_tools_list(self, message: MCPMessage) -> Dict[str, Any]:
        """处理工具列表请求"""
        logger.info("处理工具列表请求")
        
        return {
            "jsonrpc": "2.0",
            "id": message.id,
            "result": {
                "tools": self.tools
            }
        }
    
    async def _handle_tools_call(self, message: MCPMessage) -> Dict[str, Any]:
        """处理工具调用请求"""
        logger.info(f"处理工具调用请求: {message.params}")
        
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
            logger.error(f"工具调用异常: {e}")
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
            "result": {
                "resources": []
            }
        }
    
    async def _handle_prompts_list(self, message: MCPMessage) -> Dict[str, Any]:
        """处理提示列表请求"""
        return {
            "jsonrpc": "2.0",
            "id": message.id,
            "result": {
                "prompts": []
            }
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
    
    async def run(self):
        """运行服务器"""
        logger.info("启动 MCP STDIO 服务器")
        logger.info(f"Python路径: {sys.path}")
        logger.info(f"工作目录: {os.getcwd()}")

        try:
            while True:
                # 读取输入
                line = await asyncio.get_event_loop().run_in_executor(
                    None, sys.stdin.readline
                )

                if not line:
                    logger.info("输入流结束，退出服务器")
                    break

                line = line.strip()
                if not line:
                    continue

                try:
                    # 解析JSON消息
                    message_data = json.loads(line)
                    logger.info(f"收到消息: {message_data}")

                    # 处理消息
                    response = await self.handle_message(message_data)

                    if response:
                        # 发送响应
                        response_json = json.dumps(response, ensure_ascii=False)
                        print(response_json, flush=True)
                        logger.info(f"发送响应: {response_json}")
                    else:
                        logger.warning("没有生成响应")

                except json.JSONDecodeError as e:
                    logger.error(f"JSON解析错误: {e}, 原始输入: {line}")
                    error_response = self._create_error_response(
                        None, MCPErrorCodes.PARSE_ERROR, f"JSON解析错误: {str(e)}"
                    )
                    print(json.dumps(error_response), flush=True)

                except Exception as e:
                    logger.error(f"处理消息异常: {e}")
                    logger.error(traceback.format_exc())
                    error_response = self._create_error_response(
                        message_data.get("id") if 'message_data' in locals() else None,
                        MCPErrorCodes.INTERNAL_ERROR,
                        f"内部错误: {str(e)}"
                    )
                    print(json.dumps(error_response), flush=True)

        except KeyboardInterrupt:
            logger.info("服务器被用户中断")
        except Exception as e:
            logger.error(f"服务器运行异常: {e}")
            logger.error(traceback.format_exc())

        logger.info("MCP STDIO 服务器已停止")


async def main():
    """主函数"""
    server = MCPStdioServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
