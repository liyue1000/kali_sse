"""
Kali SSE MCP 命令执行器

符合 Model Context Protocol (MCP) 规范的智能化 Kali Linux 命令执行系统。
通过 Server-Sent Events (SSE) 提供实时命令执行能力，具备完整的安全机制和智能化功能。
"""

__version__ = "1.0.0"
__author__ = "Kali SSE MCP Team"
__email__ = "team@kali-sse-mcp.com"
__license__ = "MIT"
__description__ = "符合MCP规范的智能化Kali Linux命令执行器"

# 导出主要组件
from .core.config_manager import ConfigManager
from .core.executor import CommandExecutor
from .protocols.mcp_server import MCPServer
from .security.command_validator import CommandValidator
from .intelligence.syntax_checker import SyntaxChecker

# 版本信息
VERSION_INFO = {
    "major": 1,
    "minor": 0,
    "patch": 0,
    "pre_release": None,
    "build": None
}

# 支持的工具列表
SUPPORTED_TOOLS = [
    "nmap", "nikto", "dirb", "gobuster", "sqlmap", 
    "wpscan", "ffuf", "masscan", "nuclei", "subfinder"
]

# 默认配置
DEFAULT_CONFIG = {
    "server": {
        "host": "0.0.0.0",
        "port": 8000,
        "debug": False
    },
    "security": {
        "authentication": {"enabled": True},
        "command_validation": {"enabled": True}
    },
    "execution": {
        "default_timeout": 300,
        "max_concurrent_tasks": 20
    }
}

# 模块级别的配置管理器实例
_config_manager = None

def get_config_manager():
    """获取全局配置管理器实例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager

def get_version():
    """获取版本字符串"""
    version = f"{VERSION_INFO['major']}.{VERSION_INFO['minor']}.{VERSION_INFO['patch']}"
    if VERSION_INFO['pre_release']:
        version += f"-{VERSION_INFO['pre_release']}"
    if VERSION_INFO['build']:
        version += f"+{VERSION_INFO['build']}"
    return version

# 设置模块级别的日志
import logging
logging.getLogger(__name__).addHandler(logging.NullHandler())

# 导出所有公共接口
__all__ = [
    "__version__",
    "__author__", 
    "__email__",
    "__license__",
    "__description__",
    "VERSION_INFO",
    "SUPPORTED_TOOLS",
    "DEFAULT_CONFIG",
    "ConfigManager",
    "CommandExecutor", 
    "MCPServer",
    "CommandValidator",
    "SyntaxChecker",
    "get_config_manager",
    "get_version"
]
