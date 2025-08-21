"""
命令验证器

负责验证命令的安全性和合法性。
包括白名单检查、参数验证、危险模式检测等。
"""

import re
import logging
import os
from typing import Dict, Any, List, Optional, Set
from pathlib import Path
import shlex

from ..core.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class CommandValidator:
    """命令验证器"""
    
    def __init__(self, config_manager: ConfigManager):
        """
        初始化命令验证器
        
        Args:
            config_manager: 配置管理器
        """
        self.config_manager = config_manager
        self.config = config_manager.get_config()
        
        # 加载验证规则
        self._load_validation_rules()
        
        logger.info("命令验证器初始化完成")
    
    def _load_validation_rules(self) -> None:
        """加载验证规则"""
        # 获取安全配置
        security_config = self.config.security

        # 危险命令列表 - 提供默认值
        default_dangerous_commands = [
            # 文件删除命令
            "rm", "rmdir", "unlink", "shred",
            # 磁盘操作命令
            "dd", "mkfs", "fdisk", "parted", "cfdisk",
            # 系统修改命令
            "passwd", "usermod", "userdel", "groupdel",
            # 网络危险命令
            "iptables", "ufw", "systemctl",
            # 进程控制命令
            "killall", "pkill", "kill",
            # 权限提升命令
            "sudo", "su"
        ]

        self.dangerous_commands = getattr(security_config, 'dangerous_commands', default_dangerous_commands)

        # 危险模式列表 - 提供默认值
        default_dangerous_patterns = [
            r"rm\s+-rf\s+/",  # 删除根目录
            r"dd\s+.*of=/dev/",  # 写入设备
            r"mkfs\.",  # 格式化
            r"chmod\s+777\s+/",  # 危险权限
            r">\s*/etc/",  # 重定向到系统配置
            r">\s*/boot/",  # 重定向到启动目录
        ]

        self.dangerous_patterns = getattr(security_config, 'dangerous_patterns', default_dangerous_patterns)

        # 安全目录列表
        self.safe_directories = getattr(security_config, 'safe_directories', ['/tmp', '/var/tmp'])

        # 安全等级
        self.security_level = getattr(security_config, 'security_level', 'MEDIUM')

        # 编译正则表达式模式
        import re
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.dangerous_patterns]

        logger.info(f"加载了 {len(self.dangerous_commands)} 个危险命令")
        logger.debug(f"危险命令列表: {self.dangerous_commands}")

        # 合并额外的危险模式
        additional_patterns = [
            r";\s*rm\s+-rf",           # 删除命令
            r";\s*dd\s+if=",           # 磁盘操作
            r"\|\s*sh\s*",             # 管道到shell
            r"&&\s*rm\s+",             # 链式删除
            r"`.*`",                   # 命令替换
            r"\$\(.*\)",               # 命令替换
            r";\s*wget\s+",            # 下载命令
            r";\s*curl\s+",            # 下载命令
            r"chown\s+root",           # 所有者变更
            r"/bin/sh",                # 直接shell调用
            r"/bin/bash",              # 直接bash调用
        ]

        # 合并所有危险模式
        all_patterns = self.dangerous_patterns + additional_patterns

        # 编译正则表达式
        self.dangerous_regex = [re.compile(pattern, re.IGNORECASE) for pattern in all_patterns]
        
        # 输入验证规则
        self.validation_rules = {
            "ip_address": re.compile(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$"),
            "domain_name": re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$"),
            "port_range": re.compile(r"^[1-9][0-9]{0,4}(-[1-9][0-9]{0,4})?$"),
            "file_path": re.compile(r"^[a-zA-Z0-9\/_\-\.]+$"),
            "url": re.compile(r"^https?:\/\/[^\s]+$"),
        }
        
        # 禁止的字符
        self.forbidden_chars = {';', '|', '&', '`', '$', '(', ')', '{', '}', '<', '>'}
        
        # 最大限制
        self.max_command_length = 1000
        self.max_args_count = 50
    
    def validate_command(self, command: str) -> Dict[str, Any]:
        """
        验证命令
        
        Args:
            command: 要验证的命令
            
        Returns:
            验证结果
        """
        result = {
            "valid": True,
            "score": 1.0,
            "issues": [],
            "warnings": []
        }
        
        try:
            # 基本检查
            if not self._basic_validation(command, result):
                return result
            
            # 解析命令
            try:
                cmd_parts = shlex.split(command)
            except ValueError as e:
                result["valid"] = False
                result["issues"].append({
                    "type": "parse_error",
                    "message": f"命令解析失败: {e}",
                    "severity": "high"
                })
                return result
            
            if not cmd_parts:
                result["valid"] = False
                result["issues"].append({
                    "type": "empty_command",
                    "message": "空命令",
                    "severity": "high"
                })
                return result
            
            # 危险命令检查（替代工具白名单）
            tool_name = cmd_parts[0]
            if not self._check_dangerous_command(tool_name, cmd_parts[1:], result):
                return result
            
            # 危险模式检查
            if not self._check_dangerous_patterns(command, result):
                return result
            
            # 参数验证
            if not self._validate_arguments(cmd_parts[1:], result):
                return result
            
            # 计算安全分数
            result["score"] = self._calculate_security_score(result)
            
            logger.debug(f"命令验证完成: {command} -> {result['valid']}")
            
        except Exception as e:
            logger.error(f"命令验证异常: {e}")
            result["valid"] = False
            result["issues"].append({
                "type": "validation_error",
                "message": f"验证过程异常: {e}",
                "severity": "high"
            })
        
        return result
    
    def _basic_validation(self, command: str, result: Dict[str, Any]) -> bool:
        """
        基本验证
        
        Args:
            command: 命令
            result: 结果字典
            
        Returns:
            是否通过基本验证
        """
        # 长度检查
        if len(command) > self.max_command_length:
            result["valid"] = False
            result["issues"].append({
                "type": "command_too_long",
                "message": f"命令长度超过限制 ({self.max_command_length})",
                "severity": "high"
            })
            return False
        
        # 空命令检查
        if not command.strip():
            result["valid"] = False
            result["issues"].append({
                "type": "empty_command",
                "message": "空命令",
                "severity": "high"
            })
            return False
        
        # 禁止字符检查
        forbidden_found = []
        for char in self.forbidden_chars:
            if char in command:
                forbidden_found.append(char)
        
        if forbidden_found:
            result["valid"] = False
            result["issues"].append({
                "type": "forbidden_characters",
                "message": f"包含禁止字符: {', '.join(forbidden_found)}",
                "severity": "high"
            })
            return False
        
        return True
    
    def _check_dangerous_command(self, tool_name: str, args: List[str], result: Dict[str, Any]) -> bool:
        """
        检查危险命令

        Args:
            tool_name: 工具名称
            args: 参数列表
            result: 结果字典

        Returns:
            是否安全（True表示安全，False表示危险）
        """
        # 检查是否为危险命令
        if tool_name in self.dangerous_commands:
            result["valid"] = False
            result["issues"].append({
                "type": "dangerous_command",
                "message": f"危险命令被阻止: {tool_name}",
                "severity": "critical"
            })
            return False

        # 检查危险参数组合
        full_command = f"{tool_name} {' '.join(args)}"

        # 检查参数数量
        if len(args) > self.max_args_count:
            result["valid"] = False
            result["issues"].append({
                "type": "too_many_args",
                "message": f"参数数量超过限制 ({self.max_args_count})",
                "severity": "high"
            })
            return False

        # 检查危险参数模式
        dangerous_arg_patterns = [
            r"-rf\s+/",  # rm -rf /
            r"--force.*--recursive",  # 强制递归删除
            r"of=/dev/",  # dd写入设备
            r">/dev/",   # 重定向到设备
        ]

        for pattern in dangerous_arg_patterns:
            if re.search(pattern, full_command, re.IGNORECASE):
                result["valid"] = False
                result["issues"].append({
                    "type": "dangerous_arguments",
                    "message": f"检测到危险参数模式: {pattern}",
                    "severity": "critical"
                })
                return False

        return True
    
    def _check_tool_exists(self, tool_path: str) -> bool:
        """
        检查工具是否存在
        
        Args:
            tool_path: 工具路径
            
        Returns:
            是否存在
        """
        try:
            path = Path(tool_path)
            return path.exists() and path.is_file() and os.access(path, os.X_OK)
        except Exception:
            return False
    
    def _check_dangerous_patterns(self, command: str, result: Dict[str, Any]) -> bool:
        """
        检查危险模式
        
        Args:
            command: 命令
            result: 结果字典
            
        Returns:
            是否通过危险模式检查
        """
        for pattern_regex in self.dangerous_regex:
            match = pattern_regex.search(command)
            if match:
                result["valid"] = False
                result["issues"].append({
                    "type": "dangerous_pattern",
                    "message": f"检测到危险模式: {match.group()}",
                    "severity": "critical"
                })
                return False
        
        return True
    
    def _validate_arguments(self, args: List[str], result: Dict[str, Any]) -> bool:
        """
        验证参数
        
        Args:
            args: 参数列表
            result: 结果字典
            
        Returns:
            是否通过参数验证
        """
        for arg in args:
            # 跳过选项参数
            if arg.startswith("-"):
                continue
            
            # 检查参数格式
            if not self._validate_argument_format(arg):
                result["warnings"].append({
                    "type": "suspicious_argument",
                    "message": f"可疑参数格式: {arg}",
                    "severity": "low"
                })
        
        return True
    
    def _validate_argument_format(self, arg: str) -> bool:
        """
        验证参数格式
        
        Args:
            arg: 参数
            
        Returns:
            是否有效
        """
        # IP地址检查
        if self.validation_rules["ip_address"].match(arg):
            return True
        
        # 域名检查
        if self.validation_rules["domain_name"].match(arg):
            return True
        
        # 端口范围检查
        if self.validation_rules["port_range"].match(arg):
            return True
        
        # 文件路径检查
        if self.validation_rules["file_path"].match(arg):
            return True
        
        # URL检查
        if self.validation_rules["url"].match(arg):
            return True
        
        # 其他常见格式
        if re.match(r"^[a-zA-Z0-9\-\._:/]+$", arg):
            return True
        
        return False
    
    def _calculate_security_score(self, result: Dict[str, Any]) -> float:
        """
        计算安全分数
        
        Args:
            result: 验证结果
            
        Returns:
            安全分数 (0.0-1.0)
        """
        if not result["valid"]:
            return 0.0
        
        score = 1.0
        
        # 根据问题严重性扣分
        for issue in result["issues"]:
            severity = issue.get("severity", "low")
            if severity == "critical":
                score -= 0.5
            elif severity == "high":
                score -= 0.3
            elif severity == "medium":
                score -= 0.2
            elif severity == "low":
                score -= 0.1
        
        # 根据警告扣分
        for warning in result["warnings"]:
            severity = warning.get("severity", "low")
            if severity == "medium":
                score -= 0.1
            elif severity == "low":
                score -= 0.05
        
        return max(0.0, score)
    
    def get_allowed_tools(self) -> List[str]:
        """
        获取常见安全工具列表（用于兼容性）

        Returns:
            工具名称列表
        """
        # 返回常见的安全工具列表
        common_security_tools = [
            "nmap", "nikto", "dirb", "gobuster", "wfuzz", "hydra",
            "john", "hashcat", "sqlmap", "burpsuite", "metasploit",
            "nessus", "openvas", "nuclei", "masscan", "zmap",
            "tcpdump", "wireshark", "tshark", "aircrack-ng",
            "whois", "dig", "nslookup", "host", "ping", "traceroute",
            "curl", "wget", "nc", "netcat", "socat", "ssh",
            "echo", "cat", "grep", "awk", "sed", "sort", "uniq"
        ]
        return [tool for tool in common_security_tools if tool not in self.dangerous_commands]

    def is_tool_allowed(self, tool_name: str) -> bool:
        """
        检查工具是否被允许（基于黑名单）

        Args:
            tool_name: 工具名称

        Returns:
            是否被允许
        """
        return tool_name not in self.dangerous_commands

    def get_tool_config(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        获取工具配置（简化版）

        Args:
            tool_name: 工具名称

        Returns:
            工具配置
        """
        if self.is_tool_allowed(tool_name):
            return {
                "name": tool_name,
                "allowed": True,
                "description": f"{tool_name} - 安全工具",
                "timeout_limit": 3600
            }
        return None
    
    def add_custom_pattern(self, pattern: str, description: str = "") -> None:
        """
        添加自定义危险模式
        
        Args:
            pattern: 正则表达式模式
            description: 描述
        """
        try:
            compiled_pattern = re.compile(pattern, re.IGNORECASE)
            self.dangerous_regex.append(compiled_pattern)
            logger.info(f"添加自定义危险模式: {pattern}")
        except re.error as e:
            logger.error(f"无效的正则表达式模式 {pattern}: {e}")
            raise
    
    def validate_batch(self, commands: List[str]) -> List[Dict[str, Any]]:
        """
        批量验证命令
        
        Args:
            commands: 命令列表
            
        Returns:
            验证结果列表
        """
        results = []
        for command in commands:
            result = self.validate_command(command)
            results.append(result)
        
        return results
