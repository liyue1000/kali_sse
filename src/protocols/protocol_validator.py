"""
协议验证器

验证 MCP 协议的合规性和消息格式。
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from .message_parser import MCPMessage, MessageParser, MCPErrorCodes

logger = logging.getLogger(__name__)


class ProtocolValidator:
    """协议验证器"""
    
    def __init__(self):
        """初始化协议验证器"""
        self.message_parser = MessageParser()
        self.supported_methods = {
            "execute_command",
            "get_task_status", 
            "cancel_task",
            "list_supported_tools",
            "validate_command",
            "get_command_suggestions"
        }
        self.protocol_version = "2.0"
        
        logger.info("协议验证器初始化完成")
    
    def validate_message(self, message: MCPMessage) -> Tuple[bool, Optional[str]]:
        """
        验证消息格式
        
        Args:
            message: 消息对象
            
        Returns:
            (是否有效, 错误信息)
        """
        try:
            # 验证协议版本
            if message.jsonrpc != self.protocol_version:
                return False, f"不支持的协议版本: {message.jsonrpc}"
            
            # 验证请求消息
            if self.message_parser.is_request(message):
                return self._validate_request(message)
            
            # 验证响应消息
            elif self.message_parser.is_response(message):
                return self._validate_response(message)
            
            else:
                return False, "无效的消息类型"
                
        except Exception as e:
            return False, f"消息验证异常: {e}"
    
    def _validate_request(self, message: MCPMessage) -> Tuple[bool, Optional[str]]:
        """
        验证请求消息
        
        Args:
            message: 请求消息
            
        Returns:
            (是否有效, 错误信息)
        """
        # 检查方法名
        if not message.method:
            return False, "缺少方法名"
        
        # 检查是否支持该方法
        if message.method not in self.supported_methods:
            return False, f"不支持的方法: {message.method}"
        
        # 验证参数
        params = message.params or {}
        if not self.message_parser.validate_method_params(message.method, params):
            return False, f"方法参数无效: {message.method}"
        
        # 验证特定方法的参数
        validation_result = self._validate_method_specific_params(message.method, params)
        if not validation_result[0]:
            return validation_result
        
        return True, None
    
    def _validate_response(self, message: MCPMessage) -> Tuple[bool, Optional[str]]:
        """
        验证响应消息
        
        Args:
            message: 响应消息
            
        Returns:
            (是否有效, 错误信息)
        """
        # 检查ID
        if message.id is None:
            return False, "响应消息必须包含ID"
        
        # 检查结果或错误
        has_result = message.result is not None
        has_error = message.error is not None
        
        if has_result and has_error:
            return False, "响应不能同时包含结果和错误"
        
        if not has_result and not has_error:
            return False, "响应必须包含结果或错误"
        
        # 验证错误格式
        if has_error:
            error_validation = self._validate_error_format(message.error)
            if not error_validation[0]:
                return error_validation
        
        return True, None
    
    def _validate_method_specific_params(self, method: str, 
                                       params: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        验证特定方法的参数
        
        Args:
            method: 方法名
            params: 参数
            
        Returns:
            (是否有效, 错误信息)
        """
        if method == "execute_command":
            return self._validate_execute_command_params(params)
        elif method == "get_task_status":
            return self._validate_get_task_status_params(params)
        elif method == "cancel_task":
            return self._validate_cancel_task_params(params)
        elif method == "validate_command":
            return self._validate_validate_command_params(params)
        elif method == "get_command_suggestions":
            return self._validate_get_command_suggestions_params(params)
        
        return True, None
    
    def _validate_execute_command_params(self, params: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """验证 execute_command 参数"""
        if "command" not in params:
            return False, "缺少必需参数: command"
        
        command = params["command"]
        if not isinstance(command, str) or not command.strip():
            return False, "command 必须是非空字符串"
        
        # 验证可选参数
        if "args" in params:
            args = params["args"]
            if not isinstance(args, list):
                return False, "args 必须是数组"
            
            for arg in args:
                if not isinstance(arg, str):
                    return False, "args 中的所有元素必须是字符串"
        
        if "options" in params:
            options = params["options"]
            if not isinstance(options, dict):
                return False, "options 必须是对象"
            
            # 验证选项
            if "timeout" in options:
                timeout = options["timeout"]
                if not isinstance(timeout, (int, float)) or timeout <= 0:
                    return False, "timeout 必须是正数"
            
            if "async" in options:
                async_exec = options["async"]
                if not isinstance(async_exec, bool):
                    return False, "async 必须是布尔值"
        
        return True, None
    
    def _validate_get_task_status_params(self, params: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """验证 get_task_status 参数"""
        if "task_id" not in params:
            return False, "缺少必需参数: task_id"
        
        task_id = params["task_id"]
        if not isinstance(task_id, str) or not task_id.strip():
            return False, "task_id 必须是非空字符串"
        
        return True, None
    
    def _validate_cancel_task_params(self, params: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """验证 cancel_task 参数"""
        if "task_id" not in params:
            return False, "缺少必需参数: task_id"
        
        task_id = params["task_id"]
        if not isinstance(task_id, str) or not task_id.strip():
            return False, "task_id 必须是非空字符串"
        
        if "force" in params:
            force = params["force"]
            if not isinstance(force, bool):
                return False, "force 必须是布尔值"
        
        return True, None
    
    def _validate_validate_command_params(self, params: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """验证 validate_command 参数"""
        if "command" not in params:
            return False, "缺少必需参数: command"
        
        command = params["command"]
        if not isinstance(command, str) or not command.strip():
            return False, "command 必须是非空字符串"
        
        if "check_syntax" in params:
            check_syntax = params["check_syntax"]
            if not isinstance(check_syntax, bool):
                return False, "check_syntax 必须是布尔值"
        
        if "check_security" in params:
            check_security = params["check_security"]
            if not isinstance(check_security, bool):
                return False, "check_security 必须是布尔值"
        
        return True, None
    
    def _validate_get_command_suggestions_params(self, params: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """验证 get_command_suggestions 参数"""
        if "partial_command" not in params:
            return False, "缺少必需参数: partial_command"
        
        partial_command = params["partial_command"]
        if not isinstance(partial_command, str):
            return False, "partial_command 必须是字符串"
        
        if "context" in params:
            context = params["context"]
            if context is not None and not isinstance(context, str):
                return False, "context 必须是字符串或null"
        
        if "target_type" in params:
            target_type = params["target_type"]
            if target_type is not None and not isinstance(target_type, str):
                return False, "target_type 必须是字符串或null"
        
        return True, None
    
    def _validate_error_format(self, error: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        验证错误格式
        
        Args:
            error: 错误对象
            
        Returns:
            (是否有效, 错误信息)
        """
        if not isinstance(error, dict):
            return False, "错误必须是对象"
        
        if "code" not in error:
            return False, "错误缺少 code 字段"
        
        if "message" not in error:
            return False, "错误缺少 message 字段"
        
        code = error["code"]
        if not isinstance(code, int):
            return False, "错误代码必须是整数"
        
        message = error["message"]
        if not isinstance(message, str):
            return False, "错误消息必须是字符串"
        
        return True, None
    
    def create_error_response(self, request_id: Any, error_code: int, 
                            error_message: str, error_data: Any = None) -> MCPMessage:
        """
        创建标准错误响应
        
        Args:
            request_id: 请求ID
            error_code: 错误代码
            error_message: 错误消息
            error_data: 错误数据
            
        Returns:
            错误响应消息
        """
        return self.message_parser.create_error_response(
            request_id, error_code, error_message, error_data
        )
    
    def get_supported_methods(self) -> List[str]:
        """
        获取支持的方法列表
        
        Returns:
            方法名列表
        """
        return list(self.supported_methods)
    
    def is_method_supported(self, method: str) -> bool:
        """
        检查方法是否支持
        
        Args:
            method: 方法名
            
        Returns:
            是否支持
        """
        return method in self.supported_methods
    
    def add_supported_method(self, method: str) -> None:
        """
        添加支持的方法
        
        Args:
            method: 方法名
        """
        self.supported_methods.add(method)
        logger.info(f"添加支持的方法: {method}")
    
    def remove_supported_method(self, method: str) -> None:
        """
        移除支持的方法
        
        Args:
            method: 方法名
        """
        self.supported_methods.discard(method)
        logger.info(f"移除支持的方法: {method}")
    
    def validate_protocol_compliance(self, messages: List[MCPMessage]) -> Dict[str, Any]:
        """
        验证协议合规性
        
        Args:
            messages: 消息列表
            
        Returns:
            合规性报告
        """
        report = {
            "total_messages": len(messages),
            "valid_messages": 0,
            "invalid_messages": 0,
            "errors": [],
            "warnings": [],
            "compliance_score": 0.0
        }
        
        for i, message in enumerate(messages):
            is_valid, error_msg = self.validate_message(message)
            
            if is_valid:
                report["valid_messages"] += 1
            else:
                report["invalid_messages"] += 1
                report["errors"].append({
                    "message_index": i,
                    "error": error_msg,
                    "message_type": "request" if self.message_parser.is_request(message) else "response"
                })
        
        # 计算合规性分数
        if report["total_messages"] > 0:
            report["compliance_score"] = report["valid_messages"] / report["total_messages"]
        
        return report
