"""
语法检查器

提供命令语法检查、自动纠错和建议功能。
支持多种安全工具的语法验证和智能提示。
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple
import difflib
from collections import defaultdict

from ..core.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class ToolSyntax:
    """工具语法定义"""
    
    def __init__(self, name: str, patterns: List[str], options: Dict[str, Any]):
        self.name = name
        self.patterns = [re.compile(p, re.IGNORECASE) for p in patterns]
        self.options = options
        self.common_mistakes = options.get("common_mistakes", {})
        self.suggestions = options.get("suggestions", [])


class SyntaxChecker:
    """语法检查器"""
    
    def __init__(self, config_manager: ConfigManager):
        """
        初始化语法检查器
        
        Args:
            config_manager: 配置管理器
        """
        self.config_manager = config_manager
        self.config = config_manager.get_intelligence_config()
        
        # 工具语法定义
        self.tool_syntaxes: Dict[str, ToolSyntax] = {}
        
        # 加载语法规则
        self._load_syntax_rules()
        
        # 统计信息
        self.check_stats = defaultdict(int)
        
        logger.info("语法检查器初始化完成")
    
    def _load_syntax_rules(self) -> None:
        """加载语法规则"""
        
        # Nmap 语法规则
        nmap_patterns = [
            r"^nmap\s+",
            r"nmap\s+(-[a-zA-Z]+\s*)*",
            r"nmap\s+.*\s+\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}",
            r"nmap\s+.*\s+[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}"
        ]
        
        nmap_options = {
            "common_mistakes": {
                "namp": "nmap",
                "-sS -sT": "-sS",  # 不能同时使用多种扫描类型
                "-O -A": "-A",     # -A 已包含 -O
            },
            "suggestions": [
                {
                    "pattern": r"nmap\s+\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$",
                    "suggestion": "考虑添加扫描选项，如 -sS (SYN扫描) 或 -sV (版本检测)",
                    "confidence": 0.8
                },
                {
                    "pattern": r"nmap\s+-p\s*$",
                    "suggestion": "需要指定端口号或端口范围",
                    "confidence": 0.9
                }
            ]
        }
        
        self.tool_syntaxes["nmap"] = ToolSyntax("nmap", nmap_patterns, nmap_options)
        
        # Nikto 语法规则
        nikto_patterns = [
            r"^nikto\s+",
            r"nikto\s+-h\s+",
            r"nikto\s+.*-h\s+\S+"
        ]
        
        nikto_options = {
            "common_mistakes": {
                "nikto -host": "nikto -h",
                "nikto --host": "nikto -h",
            },
            "suggestions": [
                {
                    "pattern": r"nikto\s+\S+$",
                    "suggestion": "使用 -h 参数指定目标主机",
                    "confidence": 0.9
                }
            ]
        }
        
        self.tool_syntaxes["nikto"] = ToolSyntax("nikto", nikto_patterns, nikto_options)
        
        # Dirb 语法规则
        dirb_patterns = [
            r"^dirb\s+",
            r"dirb\s+https?://\S+",
            r"dirb\s+\S+\s+\S+"
        ]
        
        dirb_options = {
            "common_mistakes": {
                "dirb -u": "dirb",  # dirb 不使用 -u 参数
            },
            "suggestions": [
                {
                    "pattern": r"dirb\s+\S+$",
                    "suggestion": "考虑指定字典文件，如 /usr/share/dirb/wordlists/common.txt",
                    "confidence": 0.7
                }
            ]
        }
        
        self.tool_syntaxes["dirb"] = ToolSyntax("dirb", dirb_patterns, dirb_options)
        
        # Gobuster 语法规则
        gobuster_patterns = [
            r"^gobuster\s+",
            r"gobuster\s+(dir|dns|fuzz|s3|gcs)\s+",
            r"gobuster\s+\w+\s+-u\s+\S+"
        ]
        
        gobuster_options = {
            "common_mistakes": {
                "gobuster -u": "gobuster dir -u",  # 需要指定模式
            },
            "suggestions": [
                {
                    "pattern": r"gobuster\s+dir\s+-u\s+\S+$",
                    "suggestion": "需要使用 -w 参数指定字典文件",
                    "confidence": 0.9
                }
            ]
        }
        
        self.tool_syntaxes["gobuster"] = ToolSyntax("gobuster", gobuster_patterns, gobuster_options)
    
    def check_syntax(self, command: str) -> Dict[str, Any]:
        """
        检查命令语法
        
        Args:
            command: 要检查的命令
            
        Returns:
            检查结果
        """
        result = {
            "valid": True,
            "score": 1.0,
            "issues": [],
            "suggestions": [],
            "corrections": []
        }
        
        try:
            self.check_stats["total_checks"] += 1
            
            # 解析命令
            command = command.strip()
            if not command:
                result["valid"] = False
                result["issues"].append("空命令")
                return result
            
            # 提取工具名称
            tool_name = self._extract_tool_name(command)
            
            if not tool_name:
                result["issues"].append("无法识别的工具")
                result["score"] = 0.5
                return result
            
            # 检查工具语法
            if tool_name in self.tool_syntaxes:
                self._check_tool_syntax(command, tool_name, result)
            else:
                result["issues"].append(f"未支持的工具: {tool_name}")
                result["score"] = 0.7
            
            # 通用语法检查
            self._check_general_syntax(command, result)
            
            # 生成建议
            self._generate_suggestions(command, tool_name, result)
            
            # 计算最终分数
            result["score"] = self._calculate_syntax_score(result)
            
            # 更新统计
            if result["valid"]:
                self.check_stats["valid_commands"] += 1
            else:
                self.check_stats["invalid_commands"] += 1
            
            logger.debug(f"语法检查完成: {command} -> {result['score']}")
            
        except Exception as e:
            logger.error(f"语法检查异常: {e}")
            result["valid"] = False
            result["issues"].append(f"检查过程异常: {e}")
            result["score"] = 0.0
        
        return result
    
    def _extract_tool_name(self, command: str) -> Optional[str]:
        """
        提取工具名称
        
        Args:
            command: 命令
            
        Returns:
            工具名称
        """
        parts = command.split()
        if parts:
            tool_name = parts[0].lower()
            # 处理路径形式的命令
            if "/" in tool_name:
                tool_name = tool_name.split("/")[-1]
            return tool_name
        return None
    
    def _check_tool_syntax(self, command: str, tool_name: str, result: Dict[str, Any]) -> None:
        """
        检查特定工具的语法
        
        Args:
            command: 命令
            tool_name: 工具名称
            result: 结果字典
        """
        tool_syntax = self.tool_syntaxes[tool_name]
        
        # 检查语法模式
        pattern_matched = False
        for pattern in tool_syntax.patterns:
            if pattern.search(command):
                pattern_matched = True
                break
        
        if not pattern_matched:
            result["issues"].append(f"{tool_name} 语法不正确")
            result["valid"] = False
        
        # 检查常见错误
        for mistake, correction in tool_syntax.common_mistakes.items():
            if mistake in command:
                result["corrections"].append({
                    "original": mistake,
                    "corrected": correction,
                    "confidence": 0.9
                })
                result["issues"].append(f"常见错误: {mistake} -> {correction}")
    
    def _check_general_syntax(self, command: str, result: Dict[str, Any]) -> None:
        """
        通用语法检查
        
        Args:
            command: 命令
            result: 结果字典
        """
        # 检查引号匹配
        if not self._check_quote_matching(command):
            result["issues"].append("引号不匹配")
            result["valid"] = False
        
        # 检查参数格式
        if not self._check_argument_format(command):
            result["issues"].append("参数格式错误")
            result["score"] *= 0.8
        
        # 检查重复选项
        duplicate_options = self._find_duplicate_options(command)
        if duplicate_options:
            result["issues"].append(f"重复选项: {', '.join(duplicate_options)}")
            result["score"] *= 0.9
    
    def _check_quote_matching(self, command: str) -> bool:
        """
        检查引号匹配
        
        Args:
            command: 命令
            
        Returns:
            是否匹配
        """
        single_quotes = command.count("'")
        double_quotes = command.count('"')
        
        return single_quotes % 2 == 0 and double_quotes % 2 == 0
    
    def _check_argument_format(self, command: str) -> bool:
        """
        检查参数格式
        
        Args:
            command: 命令
            
        Returns:
            是否正确
        """
        # 检查选项格式
        option_pattern = re.compile(r'-[a-zA-Z]+')
        options = option_pattern.findall(command)
        
        for option in options:
            # 检查是否有无效字符
            if not re.match(r'^-[a-zA-Z]+$', option):
                return False
        
        return True
    
    def _find_duplicate_options(self, command: str) -> List[str]:
        """
        查找重复选项
        
        Args:
            command: 命令
            
        Returns:
            重复选项列表
        """
        option_pattern = re.compile(r'-[a-zA-Z]+')
        options = option_pattern.findall(command)
        
        seen = set()
        duplicates = []
        
        for option in options:
            if option in seen:
                duplicates.append(option)
            else:
                seen.add(option)
        
        return duplicates
    
    def _generate_suggestions(self, command: str, tool_name: str, result: Dict[str, Any]) -> None:
        """
        生成建议
        
        Args:
            command: 命令
            tool_name: 工具名称
            result: 结果字典
        """
        if tool_name in self.tool_syntaxes:
            tool_syntax = self.tool_syntaxes[tool_name]
            
            for suggestion_rule in tool_syntax.suggestions:
                pattern = suggestion_rule["pattern"]
                if re.search(pattern, command):
                    result["suggestions"].append({
                        "message": suggestion_rule["suggestion"],
                        "confidence": suggestion_rule["confidence"],
                        "type": "syntax_improvement"
                    })
    
    def _calculate_syntax_score(self, result: Dict[str, Any]) -> float:
        """
        计算语法分数
        
        Args:
            result: 检查结果
            
        Returns:
            语法分数
        """
        if not result["valid"]:
            return 0.0
        
        score = result.get("score", 1.0)
        
        # 根据问题数量调整分数
        issue_count = len(result["issues"])
        if issue_count > 0:
            score *= max(0.1, 1.0 - (issue_count * 0.2))
        
        return max(0.0, min(1.0, score))
    
    def get_suggestions(self, partial_command: str, context: Optional[str] = None,
                       target_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取命令建议
        
        Args:
            partial_command: 部分命令
            context: 上下文
            target_type: 目标类型
            
        Returns:
            建议列表
        """
        suggestions = []
        
        try:
            # 提取工具名称
            tool_name = self._extract_tool_name(partial_command)
            
            if not tool_name:
                # 工具名称建议
                suggestions.extend(self._suggest_tool_names(partial_command))
            else:
                # 参数建议
                suggestions.extend(self._suggest_parameters(partial_command, tool_name, context, target_type))
            
        except Exception as e:
            logger.error(f"生成建议失败: {e}")
        
        return suggestions
    
    def _suggest_tool_names(self, partial: str) -> List[Dict[str, Any]]:
        """
        建议工具名称
        
        Args:
            partial: 部分输入
            
        Returns:
            工具名称建议
        """
        suggestions = []
        tool_names = list(self.tool_syntaxes.keys())
        
        # 使用模糊匹配
        matches = difflib.get_close_matches(partial, tool_names, n=5, cutoff=0.3)
        
        for match in matches:
            confidence = difflib.SequenceMatcher(None, partial, match).ratio()
            suggestions.append({
                "command": match,
                "description": f"{match} - 安全扫描工具",
                "confidence": confidence,
                "type": "tool_name"
            })
        
        return suggestions
    
    def _suggest_parameters(self, command: str, tool_name: str, context: Optional[str],
                           target_type: Optional[str]) -> List[Dict[str, Any]]:
        """
        建议参数
        
        Args:
            command: 当前命令
            tool_name: 工具名称
            context: 上下文
            target_type: 目标类型
            
        Returns:
            参数建议
        """
        suggestions = []
        
        if tool_name == "nmap":
            suggestions.extend(self._suggest_nmap_parameters(command, context, target_type))
        elif tool_name == "nikto":
            suggestions.extend(self._suggest_nikto_parameters(command, context, target_type))
        elif tool_name == "dirb":
            suggestions.extend(self._suggest_dirb_parameters(command, context, target_type))
        elif tool_name == "gobuster":
            suggestions.extend(self._suggest_gobuster_parameters(command, context, target_type))
        
        return suggestions
    
    def _suggest_nmap_parameters(self, command: str, context: Optional[str],
                                target_type: Optional[str]) -> List[Dict[str, Any]]:
        """Nmap 参数建议"""
        suggestions = []
        
        if "-sS" not in command and "-sT" not in command:
            suggestions.append({
                "command": command + " -sS",
                "description": "添加 SYN 扫描选项",
                "confidence": 0.8,
                "type": "parameter"
            })
        
        if "-p" not in command:
            suggestions.append({
                "command": command + " -p 1-1000",
                "description": "扫描常用端口",
                "confidence": 0.7,
                "type": "parameter"
            })
        
        return suggestions
    
    def _suggest_nikto_parameters(self, command: str, context: Optional[str],
                                 target_type: Optional[str]) -> List[Dict[str, Any]]:
        """Nikto 参数建议"""
        suggestions = []
        
        if "-h" not in command:
            suggestions.append({
                "command": command + " -h target.com",
                "description": "指定目标主机",
                "confidence": 0.9,
                "type": "parameter"
            })
        
        return suggestions
    
    def _suggest_dirb_parameters(self, command: str, context: Optional[str],
                                target_type: Optional[str]) -> List[Dict[str, Any]]:
        """Dirb 参数建议"""
        suggestions = []
        
        if len(command.split()) < 3:
            suggestions.append({
                "command": command + " /usr/share/dirb/wordlists/common.txt",
                "description": "使用常用字典文件",
                "confidence": 0.8,
                "type": "parameter"
            })
        
        return suggestions
    
    def _suggest_gobuster_parameters(self, command: str, context: Optional[str],
                                    target_type: Optional[str]) -> List[Dict[str, Any]]:
        """Gobuster 参数建议"""
        suggestions = []
        
        if "dir" not in command and "dns" not in command:
            suggestions.append({
                "command": command.replace("gobuster", "gobuster dir"),
                "description": "使用目录扫描模式",
                "confidence": 0.8,
                "type": "parameter"
            })
        
        return suggestions
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            统计信息
        """
        total = self.check_stats["total_checks"]
        valid = self.check_stats["valid_commands"]
        invalid = self.check_stats["invalid_commands"]
        
        return {
            "total_checks": total,
            "valid_commands": valid,
            "invalid_commands": invalid,
            "success_rate": valid / total if total > 0 else 0.0,
            "supported_tools": len(self.tool_syntaxes)
        }
