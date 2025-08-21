"""
消息解析器

负责解析和验证 MCP 协议消息。
"""

import json
import logging
from typing import Dict, Any, Optional, Union
from pydantic import BaseModel, ValidationError
import jsonschema

logger = logging.getLogger(__name__)


class MCPMessage(BaseModel):
    """MCP 消息基类"""
    jsonrpc: str = "2.0"
    id: Optional[Union[str, int]] = None
    method: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None


class MessageParser:
    """消息解析器"""
    
    def __init__(self):
        """初始化消息解析器"""
        self.message_schemas = self._load_schemas()
        logger.info("消息解析器初始化完成")
    
    def _load_schemas(self) -> Dict[str, Dict[str, Any]]:
        """加载消息模式定义"""
        return {
            "request": {
                "type": "object",
                "properties": {
                    "jsonrpc": {"type": "string", "enum": ["2.0"]},
                    "id": {"oneOf": [{"type": "string"}, {"type": "number"}]},
                    "method": {"type": "string"},
                    "params": {"type": "object"}
                },
                "required": ["jsonrpc", "method"],
                "additionalProperties": False
            },
            "response": {
                "type": "object",
                "properties": {
                    "jsonrpc": {"type": "string", "enum": ["2.0"]},
                    "id": {"oneOf": [{"type": "string"}, {"type": "number"}]},
                    "result": {},
                    "error": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "integer"},
                            "message": {"type": "string"},
                            "data": {}
                        },
                        "required": ["code", "message"]
                    }
                },
                "required": ["jsonrpc", "id"],
                "oneOf": [
                    {"required": ["result"]},
                    {"required": ["error"]}
                ],
                "additionalProperties": False
            }
        }
    
    def parse_message(self, raw_message: Union[str, bytes, Dict[str, Any]]) -> MCPMessage:
        """
        解析消息
        
        Args:
            raw_message: 原始消息
            
        Returns:
            解析后的消息对象
            
        Raises:
            ValueError: 消息格式错误
        """
        try:
            # 处理不同类型的输入
            if isinstance(raw_message, (str, bytes)):
                message_dict = json.loads(raw_message)
            elif isinstance(raw_message, dict):
                message_dict = raw_message
            else:
                raise ValueError(f"不支持的消息类型: {type(raw_message)}")
            
            # 验证基本结构
            self._validate_message_structure(message_dict)
            
            # 创建消息对象
            message = MCPMessage(**message_dict)
            
            logger.debug(f"解析消息成功: {message.method or 'response'}")
            return message
            
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON 解析失败: {e}")
        except ValidationError as e:
            raise ValueError(f"消息验证失败: {e}")
        except Exception as e:
            raise ValueError(f"消息解析异常: {e}")
    
    def _validate_message_structure(self, message_dict: Dict[str, Any]) -> None:
        """
        验证消息结构
        
        Args:
            message_dict: 消息字典
            
        Raises:
            ValueError: 结构验证失败
        """
        # 确定消息类型
        if "method" in message_dict:
            schema = self.message_schemas["request"]
        elif "result" in message_dict or "error" in message_dict:
            schema = self.message_schemas["response"]
        else:
            raise ValueError("无法确定消息类型")
        
        # 验证结构
        try:
            jsonschema.validate(message_dict, schema)
        except jsonschema.ValidationError as e:
            raise ValueError(f"消息结构验证失败: {e.message}")
    
    def create_request(self, method: str, params: Optional[Dict[str, Any]] = None,
                      request_id: Optional[Union[str, int]] = None) -> MCPMessage:
        """
        创建请求消息
        
        Args:
            method: 方法名
            params: 参数
            request_id: 请求ID
            
        Returns:
            请求消息
        """
        return MCPMessage(
            method=method,
            params=params or {},
            id=request_id
        )
    
    def create_response(self, request_id: Union[str, int], 
                       result: Optional[Any] = None,
                       error: Optional[Dict[str, Any]] = None) -> MCPMessage:
        """
        创建响应消息
        
        Args:
            request_id: 请求ID
            result: 结果
            error: 错误信息
            
        Returns:
            响应消息
        """
        if result is not None and error is not None:
            raise ValueError("result 和 error 不能同时存在")
        
        if result is None and error is None:
            raise ValueError("result 和 error 必须有一个")
        
        return MCPMessage(
            id=request_id,
            result=result,
            error=error
        )
    
    def create_error_response(self, request_id: Union[str, int], 
                            error_code: int, error_message: str,
                            error_data: Optional[Any] = None) -> MCPMessage:
        """
        创建错误响应
        
        Args:
            request_id: 请求ID
            error_code: 错误代码
            error_message: 错误消息
            error_data: 错误数据
            
        Returns:
            错误响应消息
        """
        error = {
            "code": error_code,
            "message": error_message
        }
        
        if error_data is not None:
            error["data"] = error_data
        
        return self.create_response(request_id, error=error)
    
    def serialize_message(self, message: MCPMessage) -> str:
        """
        序列化消息
        
        Args:
            message: 消息对象
            
        Returns:
            JSON 字符串
        """
        try:
            # 转换为字典，排除 None 值
            message_dict = message.dict(exclude_none=True)
            
            # 序列化为 JSON
            return json.dumps(message_dict, ensure_ascii=False, separators=(',', ':'))
            
        except Exception as e:
            raise ValueError(f"消息序列化失败: {e}")
    
    def is_request(self, message: MCPMessage) -> bool:
        """
        检查是否为请求消息
        
        Args:
            message: 消息对象
            
        Returns:
            是否为请求
        """
        return message.method is not None
    
    def is_response(self, message: MCPMessage) -> bool:
        """
        检查是否为响应消息
        
        Args:
            message: 消息对象
            
        Returns:
            是否为响应
        """
        return message.result is not None or message.error is not None
    
    def is_notification(self, message: MCPMessage) -> bool:
        """
        检查是否为通知消息（无ID的请求）
        
        Args:
            message: 消息对象
            
        Returns:
            是否为通知
        """
        return message.method is not None and message.id is None
    
    def extract_method(self, message: MCPMessage) -> Optional[str]:
        """
        提取方法名
        
        Args:
            message: 消息对象
            
        Returns:
            方法名
        """
        return message.method
    
    def extract_params(self, message: MCPMessage) -> Dict[str, Any]:
        """
        提取参数
        
        Args:
            message: 消息对象
            
        Returns:
            参数字典
        """
        return message.params or {}
    
    def extract_result(self, message: MCPMessage) -> Any:
        """
        提取结果
        
        Args:
            message: 消息对象
            
        Returns:
            结果
        """
        return message.result
    
    def extract_error(self, message: MCPMessage) -> Optional[Dict[str, Any]]:
        """
        提取错误信息
        
        Args:
            message: 消息对象
            
        Returns:
            错误信息
        """
        return message.error
    
    def validate_method_params(self, method: str, params: Dict[str, Any]) -> bool:
        """
        验证方法参数
        
        Args:
            method: 方法名
            params: 参数
            
        Returns:
            是否有效
        """
        # 这里可以添加特定方法的参数验证逻辑
        method_schemas = {
            "execute_command": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "args": {"type": "array", "items": {"type": "string"}},
                    "options": {"type": "object"}
                },
                "required": ["command"]
            },
            "get_task_status": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"}
                },
                "required": ["task_id"]
            },
            "cancel_task": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "force": {"type": "boolean"}
                },
                "required": ["task_id"]
            }
        }
        
        schema = method_schemas.get(method)
        if not schema:
            # 未知方法，跳过验证
            return True
        
        try:
            jsonschema.validate(params, schema)
            return True
        except jsonschema.ValidationError as e:
            logger.warning(f"方法参数验证失败 {method}: {e.message}")
            return False


# 错误代码常量
class MCPErrorCodes:
    """MCP 错误代码"""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    
    # 自定义错误代码
    COMMAND_VALIDATION_ERROR = -32001
    COMMAND_EXECUTION_ERROR = -32002
    SECURITY_VIOLATION = -32003
    TASK_NOT_FOUND = -32004
    SYSTEM_OVERLOAD = -32005
