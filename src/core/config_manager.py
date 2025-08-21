"""
配置管理器

负责加载、验证和管理系统配置。
支持多种配置源：文件、环境变量、命令行参数等。
"""

import json
import os
import logging
from typing import Dict, Any, Optional, Union, List
from pathlib import Path
import yaml
from pydantic import BaseModel, ValidationError, Field
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class ServerConfig(BaseModel):
    """服务器配置"""
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    reload: bool = False
    workers: int = 1
    max_connections: int = 100
    keepalive_timeout: int = 30


class SecurityConfig(BaseModel):
    """安全配置"""
    authentication_enabled: bool = True
    authorization_enabled: bool = True
    command_validation_enabled: bool = True
    rate_limiting_enabled: bool = True
    audit_enabled: bool = True

    # 新增安全策略配置
    security_level: str = "MEDIUM"  # LOW, MEDIUM, HIGH, CRITICAL
    dangerous_commands: List[str] = Field(default_factory=lambda: [
        # 文件删除命令
        "rm", "rmdir", "unlink", "shred",
        # 磁盘操作命令
        "dd", "mkfs", "fdisk", "parted", "cfdisk",
        # 系统修改命令
        "passwd", "usermod", "userdel", "groupdel",
        # 网络危险命令
        "iptables -F", "ufw disable", "systemctl stop",
        # 进程控制命令
        "killall", "pkill -9", "kill -9",
        # 权限提升命令
        "sudo su", "sudo -i", "su -"
    ])
    dangerous_patterns: List[str] = Field(default_factory=lambda: [
        r"rm\s+-rf\s+/",  # 删除根目录
        r"dd\s+.*of=/dev/",  # 写入设备
        r"mkfs\.",  # 格式化
        r"chmod\s+777\s+/",  # 危险权限
        r">\s*/etc/",  # 重定向到系统配置
        r">\s*/boot/",  # 重定向到启动目录
    ])
    safe_directories: List[str] = Field(default_factory=lambda: [
        "/tmp", "/var/tmp", "/home/kali", "/opt/pentest"
    ])
    max_command_length: int = 1000


class ExecutionConfig(BaseModel):
    """执行配置"""
    default_timeout: int = 300
    max_timeout: int = 3600
    max_concurrent_tasks: int = 20
    working_directory: str = "/tmp/kali_sse"
    cleanup_interval: int = 3600
    preserve_output: bool = True
    output_max_size: int = 10485760


class IntelligenceConfig(BaseModel):
    """智能化配置"""
    enabled: bool = True
    syntax_checking_enabled: bool = True
    error_learning_enabled: bool = True
    strategy_optimization_enabled: bool = True
    task_chaining_enabled: bool = True


class AppConfig(BaseSettings):
    """应用配置"""
    server: ServerConfig = ServerConfig()
    security: SecurityConfig = SecurityConfig()
    execution: ExecutionConfig = ExecutionConfig()
    intelligence: IntelligenceConfig = IntelligenceConfig()
    
    class Config:
        env_prefix = "KALI_SSE_"
        env_nested_delimiter = "__"
        case_sensitive = False


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self._config: Optional[AppConfig] = None
        self._raw_config: Dict[str, Any] = {}
        
        # 默认配置文件搜索路径
        self.default_config_paths = [
            "config/config.json",
            "config/config.yaml", 
            "config/config.yml",
            "/etc/kali_sse/config.json",
            "/etc/kali_sse/config.yaml",
            os.path.expanduser("~/.kali_sse/config.json"),
            os.path.expanduser("~/.kali_sse/config.yaml"),
        ]
        
        self.load_config()
    
    def load_config(self) -> None:
        """加载配置"""
        try:
            # 1. 加载文件配置
            self._load_file_config()
            
            # 2. 加载环境变量配置
            self._load_env_config()
            
            # 3. 验证和创建配置对象
            self._validate_config()
            
            logger.info("配置加载成功")
            
        except Exception as e:
            logger.error(f"配置加载失败: {e}")
            # 使用默认配置
            self._config = AppConfig()
            logger.warning("使用默认配置")
    
    def _load_file_config(self) -> None:
        """加载文件配置"""
        config_file = self._find_config_file()
        
        if not config_file:
            logger.warning("未找到配置文件，将使用默认配置")
            return
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                if config_file.suffix.lower() in ['.yaml', '.yml']:
                    self._raw_config = yaml.safe_load(f)
                else:
                    self._raw_config = json.load(f)
            
            logger.info(f"从文件加载配置: {config_file}")
            
        except Exception as e:
            logger.error(f"读取配置文件失败 {config_file}: {e}")
            raise
    
    def _find_config_file(self) -> Optional[Path]:
        """查找配置文件"""
        # 如果指定了配置文件路径
        if self.config_path:
            config_path = Path(self.config_path)
            if config_path.exists():
                return config_path
            else:
                raise FileNotFoundError(f"指定的配置文件不存在: {config_path}")
        
        # 搜索默认路径
        for path_str in self.default_config_paths:
            path = Path(path_str)
            if path.exists():
                return path
        
        return None
    
    def _load_env_config(self) -> None:
        """加载环境变量配置"""
        # 环境变量会在 Pydantic Settings 中自动处理
        pass
    
    def _validate_config(self) -> None:
        """验证配置"""
        try:
            # 使用原始配置创建配置对象
            self._config = AppConfig(**self._raw_config)
            
        except ValidationError as e:
            logger.error(f"配置验证失败: {e}")
            raise
    
    def get_config(self) -> AppConfig:
        """获取配置对象"""
        if self._config is None:
            raise RuntimeError("配置未初始化")
        return self._config
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            key: 配置键，支持点号分隔的嵌套键
            default: 默认值
            
        Returns:
            配置值
        """
        try:
            config = self.get_config()
            
            # 处理嵌套键
            keys = key.split('.')
            value = config
            
            for k in keys:
                if hasattr(value, k):
                    value = getattr(value, k)
                else:
                    return default
            
            return value
            
        except Exception:
            return default
    
    def set(self, key: str, value: Any) -> None:
        """
        设置配置值（运行时）
        
        Args:
            key: 配置键
            value: 配置值
        """
        # 注意：这只会修改运行时配置，不会持久化
        keys = key.split('.')
        config_dict = self._config.dict()
        
        # 导航到正确的嵌套位置
        current = config_dict
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        # 设置值
        current[keys[-1]] = value
        
        # 重新创建配置对象
        try:
            self._config = AppConfig(**config_dict)
            logger.info(f"运行时配置已更新: {key} = {value}")
        except ValidationError as e:
            logger.error(f"配置更新失败: {e}")
            raise
    
    def reload(self) -> None:
        """重新加载配置"""
        logger.info("重新加载配置...")
        self._raw_config = {}
        self._config = None
        self.load_config()
    
    def save_config(self, path: Optional[Union[str, Path]] = None) -> None:
        """
        保存配置到文件
        
        Args:
            path: 保存路径，如果为None则使用原配置文件路径
        """
        if not self._config:
            raise RuntimeError("配置未初始化")
        
        save_path = Path(path) if path else self._find_config_file()
        if not save_path:
            raise ValueError("未指定保存路径且未找到原配置文件")
        
        try:
            config_dict = self._config.dict()
            
            with open(save_path, 'w', encoding='utf-8') as f:
                if save_path.suffix.lower() in ['.yaml', '.yml']:
                    yaml.dump(config_dict, f, default_flow_style=False, indent=2)
                else:
                    json.dump(config_dict, f, indent=2, ensure_ascii=False)
            
            logger.info(f"配置已保存到: {save_path}")
            
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            raise
    
    def get_server_config(self) -> ServerConfig:
        """获取服务器配置"""
        return self.get_config().server
    
    def get_security_config(self) -> SecurityConfig:
        """获取安全配置"""
        return self.get_config().security
    
    def get_execution_config(self) -> ExecutionConfig:
        """获取执行配置"""
        return self.get_config().execution
    
    def get_intelligence_config(self) -> IntelligenceConfig:
        """获取智能化配置"""
        return self.get_config().intelligence
    
    def is_debug_mode(self) -> bool:
        """是否为调试模式"""
        return self.get_config().server.debug
    
    def get_log_level(self) -> str:
        """获取日志级别"""
        return "DEBUG" if self.is_debug_mode() else "INFO"
    
    def validate_tool_config(self, tool_name: str) -> bool:
        """
        验证工具配置
        
        Args:
            tool_name: 工具名称
            
        Returns:
            是否配置有效
        """
        try:
            # 这里可以添加具体的工具配置验证逻辑
            # 例如检查工具路径是否存在等
            return True
        except Exception as e:
            logger.error(f"工具配置验证失败 {tool_name}: {e}")
            return False
    
    def __str__(self) -> str:
        """字符串表示"""
        if self._config:
            return f"ConfigManager(server={self._config.server.host}:{self._config.server.port})"
        return "ConfigManager(未初始化)"
    
    def __repr__(self) -> str:
        """详细字符串表示"""
        return self.__str__()
