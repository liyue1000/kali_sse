"""
注入检测器

检测和防护各种注入攻击。
"""

import re
import logging
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)


class InjectionDetector:
    """注入检测器"""
    
    def __init__(self):
        """初始化注入检测器"""
        self.patterns = self._load_injection_patterns()
        logger.info("注入检测器初始化完成")
    
    def _load_injection_patterns(self) -> Dict[str, List[re.Pattern]]:
        """加载注入攻击模式"""
        return {
            "command_injection": [
                re.compile(r";\s*\w+", re.IGNORECASE),
                re.compile(r"\|\s*\w+", re.IGNORECASE),
                re.compile(r"&&\s*\w+", re.IGNORECASE),
                re.compile(r"\$\([^)]*\)", re.IGNORECASE),
                re.compile(r"`[^`]*`", re.IGNORECASE),
            ],
            "path_traversal": [
                re.compile(r"\.\./", re.IGNORECASE),
                re.compile(r"\.\.\\", re.IGNORECASE),
                re.compile(r"%2e%2e%2f", re.IGNORECASE),
                re.compile(r"%2e%2e\\", re.IGNORECASE),
            ],
            "sql_injection": [
                re.compile(r"'\s*(or|and)\s*'", re.IGNORECASE),
                re.compile(r"union\s+select", re.IGNORECASE),
                re.compile(r"drop\s+table", re.IGNORECASE),
            ]
        }
    
    def detect_injection(self, input_text: str) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        检测注入攻击
        
        Args:
            input_text: 输入文本
            
        Returns:
            (是否检测到注入, 检测结果列表)
        """
        detections = []
        
        for injection_type, patterns in self.patterns.items():
            for pattern in patterns:
                matches = pattern.finditer(input_text)
                for match in matches:
                    detections.append({
                        "type": injection_type,
                        "pattern": pattern.pattern,
                        "match": match.group(),
                        "position": match.span(),
                        "severity": self._get_severity(injection_type)
                    })
        
        return len(detections) > 0, detections
    
    def _get_severity(self, injection_type: str) -> str:
        """获取注入类型的严重性级别"""
        severity_map = {
            "command_injection": "critical",
            "path_traversal": "high",
            "sql_injection": "high"
        }
        return severity_map.get(injection_type, "medium")
