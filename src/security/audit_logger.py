"""
审计日志器

记录系统的安全事件和操作审计。
"""

import json
import logging
import time
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class AuditLogger:
    """审计日志器"""
    
    def __init__(self, log_file: str = "/var/log/kali_sse/audit.log"):
        """
        初始化审计日志器
        
        Args:
            log_file: 日志文件路径
        """
        self.log_file = Path(log_file)
        self._ensure_log_directory()
        
        # 配置审计日志记录器
        self.audit_logger = logging.getLogger("audit")
        self.audit_logger.setLevel(logging.INFO)
        
        # 创建文件处理器
        handler = logging.FileHandler(self.log_file)
        formatter = logging.Formatter(
            '%(asctime)s - AUDIT - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        self.audit_logger.addHandler(handler)
        
        logger.info("审计日志器初始化完成")
    
    def _ensure_log_directory(self) -> None:
        """确保日志目录存在"""
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
    
    def log_event(self, event_type: str, user_id: Optional[str] = None,
                  details: Optional[Dict[str, Any]] = None) -> None:
        """
        记录审计事件
        
        Args:
            event_type: 事件类型
            user_id: 用户ID
            details: 事件详情
        """
        audit_record = {
            "timestamp": time.time(),
            "event_type": event_type,
            "user_id": user_id,
            "details": details or {}
        }
        
        self.audit_logger.info(json.dumps(audit_record, ensure_ascii=False))
    
    def log_command_execution(self, user_id: str, command: str, 
                            success: bool, task_id: str) -> None:
        """记录命令执行事件"""
        self.log_event("command_execution", user_id, {
            "command": command,
            "success": success,
            "task_id": task_id
        })
    
    def log_authentication(self, user_id: str, success: bool, 
                          ip_address: Optional[str] = None) -> None:
        """记录认证事件"""
        self.log_event("authentication", user_id, {
            "success": success,
            "ip_address": ip_address
        })
    
    def log_security_violation(self, user_id: Optional[str], violation_type: str,
                             details: Dict[str, Any]) -> None:
        """记录安全违规事件"""
        self.log_event("security_violation", user_id, {
            "violation_type": violation_type,
            **details
        })
