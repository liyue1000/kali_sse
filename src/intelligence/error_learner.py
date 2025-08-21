"""
错误学习器

从命令执行错误中学习，提供智能化的错误预防和修复建议。
"""

import json
import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict, Counter
import pickle
from pathlib import Path

logger = logging.getLogger(__name__)


class ErrorPattern:
    """错误模式"""
    
    def __init__(self, command_pattern: str, error_pattern: str, 
                 suggestion: str, confidence: float = 0.5):
        self.command_pattern = command_pattern
        self.error_pattern = error_pattern
        self.suggestion = suggestion
        self.confidence = confidence
        self.occurrence_count = 1
        self.last_seen = time.time()
    
    def update_confidence(self, success: bool) -> None:
        """更新置信度"""
        if success:
            self.confidence = min(0.95, self.confidence + 0.1)
        else:
            self.confidence = max(0.1, self.confidence - 0.05)
        
        self.last_seen = time.time()
        self.occurrence_count += 1


class ErrorLearner:
    """错误学习器"""
    
    def __init__(self, model_file: str = "/var/lib/kali_sse/error_model.pkl"):
        """
        初始化错误学习器
        
        Args:
            model_file: 模型文件路径
        """
        self.model_file = Path(model_file)
        self.error_patterns: List[ErrorPattern] = []
        self.command_errors: Dict[str, List[str]] = defaultdict(list)
        self.error_frequency: Counter = Counter()
        
        # 学习参数
        self.learning_rate = 0.1
        self.min_confidence = 0.3
        self.max_patterns = 1000
        
        # 加载已有模型
        self._load_model()
        
        logger.info("错误学习器初始化完成")
    
    def _load_model(self) -> None:
        """加载错误学习模型"""
        try:
            if self.model_file.exists():
                with open(self.model_file, 'rb') as f:
                    data = pickle.load(f)
                    self.error_patterns = data.get('patterns', [])
                    self.command_errors = data.get('command_errors', defaultdict(list))
                    self.error_frequency = data.get('error_frequency', Counter())
                logger.info(f"加载错误学习模型: {len(self.error_patterns)} 个模式")
        except Exception as e:
            logger.warning(f"加载错误学习模型失败: {e}")
    
    def _save_model(self) -> None:
        """保存错误学习模型"""
        try:
            self.model_file.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'patterns': self.error_patterns,
                'command_errors': dict(self.command_errors),
                'error_frequency': self.error_frequency
            }
            
            with open(self.model_file, 'wb') as f:
                pickle.dump(data, f)
            
            logger.debug("错误学习模型已保存")
        except Exception as e:
            logger.error(f"保存错误学习模型失败: {e}")
    
    def learn_from_error(self, command: str, error_message: str, 
                        suggestion: Optional[str] = None) -> None:
        """
        从错误中学习
        
        Args:
            command: 执行的命令
            error_message: 错误消息
            suggestion: 修复建议
        """
        try:
            # 记录命令错误
            self.command_errors[command].append(error_message)
            self.error_frequency[error_message] += 1
            
            # 生成或更新错误模式
            if suggestion:
                self._update_or_create_pattern(command, error_message, suggestion)
            else:
                # 尝试自动生成建议
                auto_suggestion = self._generate_suggestion(command, error_message)
                if auto_suggestion:
                    self._update_or_create_pattern(command, error_message, auto_suggestion)
            
            # 定期保存模型
            if len(self.error_patterns) % 10 == 0:
                self._save_model()
            
            logger.debug(f"学习错误: {command} -> {error_message}")
            
        except Exception as e:
            logger.error(f"错误学习失败: {e}")
    
    def _update_or_create_pattern(self, command: str, error: str, suggestion: str) -> None:
        """更新或创建错误模式"""
        # 查找现有模式
        for pattern in self.error_patterns:
            if (self._match_command_pattern(command, pattern.command_pattern) and
                self._match_error_pattern(error, pattern.error_pattern)):
                pattern.update_confidence(True)
                return
        
        # 创建新模式
        if len(self.error_patterns) < self.max_patterns:
            new_pattern = ErrorPattern(
                command_pattern=self._generalize_command(command),
                error_pattern=self._generalize_error(error),
                suggestion=suggestion
            )
            self.error_patterns.append(new_pattern)
    
    def _generalize_command(self, command: str) -> str:
        """泛化命令模式"""
        # 简单的泛化：替换IP地址、域名、文件路径等
        import re
        
        # 替换IP地址
        command = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '<IP>', command)
        
        # 替换域名
        command = re.sub(r'\b[a-zA-Z0-9\-]+\.[a-zA-Z]{2,}\b', '<DOMAIN>', command)
        
        # 替换文件路径
        command = re.sub(r'/[^\s]+', '<PATH>', command)
        
        # 替换端口号
        command = re.sub(r'\b\d{1,5}\b', '<PORT>', command)
        
        return command
    
    def _generalize_error(self, error: str) -> str:
        """泛化错误模式"""
        # 移除具体的文件名、IP地址等
        import re
        
        error = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '<IP>', error)
        error = re.sub(r'/[^\s]+', '<PATH>', error)
        error = re.sub(r'\b\d+\b', '<NUMBER>', error)
        
        return error
    
    def _match_command_pattern(self, command: str, pattern: str) -> bool:
        """匹配命令模式"""
        # 简单的模式匹配
        generalized = self._generalize_command(command)
        return generalized == pattern
    
    def _match_error_pattern(self, error: str, pattern: str) -> bool:
        """匹配错误模式"""
        generalized = self._generalize_error(error)
        return generalized == pattern
    
    def _generate_suggestion(self, command: str, error: str) -> Optional[str]:
        """自动生成修复建议"""
        # 基于常见错误模式生成建议
        suggestions = {
            "command not found": f"请检查命令是否正确安装: {command.split()[0]}",
            "permission denied": "请检查文件权限或使用sudo",
            "no such file": "请检查文件路径是否正确",
            "connection refused": "请检查目标主机是否可达",
            "timeout": "请增加超时时间或检查网络连接",
            "invalid option": "请检查命令选项是否正确"
        }
        
        error_lower = error.lower()
        for pattern, suggestion in suggestions.items():
            if pattern in error_lower:
                return suggestion
        
        return None
    
    def get_suggestions(self, command: str, error: str) -> List[Dict[str, Any]]:
        """
        获取错误修复建议
        
        Args:
            command: 命令
            error: 错误消息
            
        Returns:
            建议列表
        """
        suggestions = []
        
        # 从学习的模式中查找建议
        for pattern in self.error_patterns:
            if (pattern.confidence >= self.min_confidence and
                self._match_command_pattern(command, pattern.command_pattern) and
                self._match_error_pattern(error, pattern.error_pattern)):
                
                suggestions.append({
                    "suggestion": pattern.suggestion,
                    "confidence": pattern.confidence,
                    "source": "learned_pattern",
                    "occurrence_count": pattern.occurrence_count
                })
        
        # 添加自动生成的建议
        auto_suggestion = self._generate_suggestion(command, error)
        if auto_suggestion:
            suggestions.append({
                "suggestion": auto_suggestion,
                "confidence": 0.6,
                "source": "auto_generated",
                "occurrence_count": 1
            })
        
        # 按置信度排序
        suggestions.sort(key=lambda x: x["confidence"], reverse=True)
        
        return suggestions[:5]  # 返回前5个建议
    
    def get_common_errors(self, limit: int = 10) -> List[Tuple[str, int]]:
        """
        获取常见错误
        
        Args:
            limit: 返回数量限制
            
        Returns:
            错误和频次的列表
        """
        return self.error_frequency.most_common(limit)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取学习统计信息
        
        Returns:
            统计信息
        """
        return {
            "total_patterns": len(self.error_patterns),
            "total_commands_with_errors": len(self.command_errors),
            "total_error_occurrences": sum(self.error_frequency.values()),
            "high_confidence_patterns": len([p for p in self.error_patterns if p.confidence >= 0.8]),
            "most_common_errors": self.get_common_errors(5)
        }
    
    def cleanup_old_patterns(self, max_age_days: int = 30) -> None:
        """
        清理过期的错误模式
        
        Args:
            max_age_days: 最大保留天数
        """
        current_time = time.time()
        max_age_seconds = max_age_days * 24 * 3600
        
        old_patterns = []
        for pattern in self.error_patterns:
            if current_time - pattern.last_seen > max_age_seconds:
                old_patterns.append(pattern)
        
        for pattern in old_patterns:
            self.error_patterns.remove(pattern)
        
        if old_patterns:
            logger.info(f"清理了 {len(old_patterns)} 个过期错误模式")
            self._save_model()
