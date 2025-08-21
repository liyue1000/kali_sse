"""
结果格式化器

负责格式化命令执行结果，支持多种输出格式。
"""

import json
import logging
import time
from typing import Dict, Any, Optional, List, Union
from enum import Enum
import xml.etree.ElementTree as ET
import csv
import io

logger = logging.getLogger(__name__)


class OutputFormat(Enum):
    """输出格式枚举"""
    JSON = "json"
    XML = "xml"
    CSV = "csv"
    TEXT = "text"
    HTML = "html"


class ResultFormatter:
    """结果格式化器"""
    
    def __init__(self):
        """初始化结果格式化器"""
        self.formatters = {
            OutputFormat.JSON: self._format_json,
            OutputFormat.XML: self._format_xml,
            OutputFormat.CSV: self._format_csv,
            OutputFormat.TEXT: self._format_text,
            OutputFormat.HTML: self._format_html
        }
        
        logger.info("结果格式化器初始化完成")
    
    def format_result(self, result: Dict[str, Any], 
                     format_type: OutputFormat = OutputFormat.JSON,
                     options: Optional[Dict[str, Any]] = None) -> str:
        """
        格式化结果
        
        Args:
            result: 执行结果
            format_type: 输出格式
            options: 格式化选项
            
        Returns:
            格式化后的字符串
        """
        try:
            formatter = self.formatters.get(format_type)
            if not formatter:
                raise ValueError(f"不支持的格式类型: {format_type}")
            
            options = options or {}
            return formatter(result, options)
            
        except Exception as e:
            logger.error(f"结果格式化失败: {e}")
            # 返回基本的JSON格式作为后备
            return json.dumps(result, ensure_ascii=False, indent=2)
    
    def _format_json(self, result: Dict[str, Any], options: Dict[str, Any]) -> str:
        """格式化为JSON"""
        indent = options.get("indent", 2)
        ensure_ascii = options.get("ensure_ascii", False)
        sort_keys = options.get("sort_keys", False)
        
        return json.dumps(
            result,
            indent=indent,
            ensure_ascii=ensure_ascii,
            sort_keys=sort_keys,
            default=self._json_serializer
        )
    
    def _format_xml(self, result: Dict[str, Any], options: Dict[str, Any]) -> str:
        """格式化为XML"""
        root_name = options.get("root_name", "result")
        
        root = ET.Element(root_name)
        self._dict_to_xml(result, root)
        
        # 格式化XML
        self._indent_xml(root)
        return ET.tostring(root, encoding='unicode')
    
    def _format_csv(self, result: Dict[str, Any], options: Dict[str, Any]) -> str:
        """格式化为CSV"""
        output = io.StringIO()
        
        # 提取表格数据
        if "output" in result and "stdout" in result["output"]:
            # 尝试解析命令输出为表格
            lines = result["output"]["stdout"].strip().split('\n')
            if lines:
                writer = csv.writer(output)
                
                # 添加元数据行
                writer.writerow(["# Task ID", result.get("task_id", "")])
                writer.writerow(["# Command", result.get("command", "")])
                writer.writerow(["# Status", "Success" if result.get("success") else "Failed"])
                writer.writerow(["# Duration", f"{result.get('duration', 0):.2f}s"])
                writer.writerow([])  # 空行
                
                # 添加输出数据
                writer.writerow(["Line", "Content"])
                for i, line in enumerate(lines, 1):
                    writer.writerow([i, line])
        else:
            # 通用格式
            writer = csv.writer(output)
            writer.writerow(["Key", "Value"])
            for key, value in result.items():
                if isinstance(value, (dict, list)):
                    value = json.dumps(value)
                writer.writerow([key, str(value)])
        
        return output.getvalue()
    
    def _format_text(self, result: Dict[str, Any], options: Dict[str, Any]) -> str:
        """格式化为纯文本"""
        lines = []
        
        # 标题
        lines.append("=" * 60)
        lines.append("命令执行结果")
        lines.append("=" * 60)
        
        # 基本信息
        lines.append(f"任务ID: {result.get('task_id', 'N/A')}")
        lines.append(f"命令: {result.get('command', 'N/A')}")
        lines.append(f"状态: {'成功' if result.get('success') else '失败'}")
        lines.append(f"返回码: {result.get('return_code', 'N/A')}")
        lines.append(f"执行时间: {result.get('duration', 0):.2f}秒")
        
        if result.get('start_time'):
            start_time = time.strftime('%Y-%m-%d %H:%M:%S', 
                                     time.localtime(result['start_time']))
            lines.append(f"开始时间: {start_time}")
        
        # 输出内容
        if "output" in result:
            output = result["output"]
            
            if output.get("stdout"):
                lines.append("\n" + "-" * 30)
                lines.append("标准输出:")
                lines.append("-" * 30)
                lines.append(output["stdout"])
            
            if output.get("stderr"):
                lines.append("\n" + "-" * 30)
                lines.append("标准错误:")
                lines.append("-" * 30)
                lines.append(output["stderr"])
        
        # 错误信息
        if result.get("error"):
            lines.append("\n" + "-" * 30)
            lines.append("错误信息:")
            lines.append("-" * 30)
            lines.append(result["error"])
        
        # 元数据
        if "metadata" in result:
            metadata = result["metadata"]
            lines.append("\n" + "-" * 30)
            lines.append("元数据:")
            lines.append("-" * 30)
            for key, value in metadata.items():
                lines.append(f"{key}: {value}")
        
        return "\n".join(lines)
    
    def _format_html(self, result: Dict[str, Any], options: Dict[str, Any]) -> str:
        """格式化为HTML"""
        template = options.get("template", "default")
        
        if template == "minimal":
            return self._format_html_minimal(result)
        else:
            return self._format_html_default(result)
    
    def _format_html_default(self, result: Dict[str, Any]) -> str:
        """默认HTML格式"""
        html_parts = []
        
        # HTML头部
        html_parts.append("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>命令执行结果</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background-color: #f0f0f0; padding: 10px; border-radius: 5px; }
        .success { color: green; }
        .error { color: red; }
        .output { background-color: #f8f8f8; padding: 10px; border-left: 3px solid #ccc; margin: 10px 0; }
        .metadata { font-size: 0.9em; color: #666; }
        pre { white-space: pre-wrap; word-wrap: break-word; }
    </style>
</head>
<body>
        """)
        
        # 标题和基本信息
        status_class = "success" if result.get("success") else "error"
        status_text = "成功" if result.get("success") else "失败"
        
        html_parts.append(f"""
    <div class="header">
        <h1>命令执行结果</h1>
        <p><strong>任务ID:</strong> {result.get('task_id', 'N/A')}</p>
        <p><strong>命令:</strong> <code>{result.get('command', 'N/A')}</code></p>
        <p><strong>状态:</strong> <span class="{status_class}">{status_text}</span></p>
        <p><strong>返回码:</strong> {result.get('return_code', 'N/A')}</p>
        <p><strong>执行时间:</strong> {result.get('duration', 0):.2f}秒</p>
    </div>
        """)
        
        # 输出内容
        if "output" in result:
            output = result["output"]
            
            if output.get("stdout"):
                html_parts.append(f"""
    <h2>标准输出</h2>
    <div class="output">
        <pre>{self._escape_html(output["stdout"])}</pre>
    </div>
                """)
            
            if output.get("stderr"):
                html_parts.append(f"""
    <h2>标准错误</h2>
    <div class="output error">
        <pre>{self._escape_html(output["stderr"])}</pre>
    </div>
                """)
        
        # 错误信息
        if result.get("error"):
            html_parts.append(f"""
    <h2>错误信息</h2>
    <div class="output error">
        <pre>{self._escape_html(result["error"])}</pre>
    </div>
            """)
        
        # 元数据
        if "metadata" in result:
            metadata = result["metadata"]
            html_parts.append("<h2>元数据</h2><div class='metadata'><ul>")
            for key, value in metadata.items():
                html_parts.append(f"<li><strong>{key}:</strong> {self._escape_html(str(value))}</li>")
            html_parts.append("</ul></div>")
        
        # HTML尾部
        html_parts.append("</body></html>")
        
        return "".join(html_parts)
    
    def _format_html_minimal(self, result: Dict[str, Any]) -> str:
        """最小HTML格式"""
        status = "成功" if result.get("success") else "失败"
        output = result.get("output", {}).get("stdout", "")
        
        return f"""
<div class="command-result">
    <div class="status">状态: {status}</div>
    <div class="command">命令: {result.get('command', '')}</div>
    <div class="output"><pre>{self._escape_html(output)}</pre></div>
</div>
        """.strip()
    
    def _dict_to_xml(self, data: Any, parent: ET.Element) -> None:
        """将字典转换为XML元素"""
        if isinstance(data, dict):
            for key, value in data.items():
                # 清理键名，确保是有效的XML标签名
                clean_key = self._clean_xml_tag_name(str(key))
                child = ET.SubElement(parent, clean_key)
                self._dict_to_xml(value, child)
        elif isinstance(data, list):
            for i, item in enumerate(data):
                child = ET.SubElement(parent, f"item_{i}")
                self._dict_to_xml(item, child)
        else:
            parent.text = str(data)
    
    def _clean_xml_tag_name(self, name: str) -> str:
        """清理XML标签名"""
        # 移除无效字符，确保以字母开头
        import re
        name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
        if name and not name[0].isalpha():
            name = 'tag_' + name
        return name or 'tag'
    
    def _indent_xml(self, elem: ET.Element, level: int = 0) -> None:
        """格式化XML缩进"""
        i = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for child in elem:
                self._indent_xml(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i
    
    def _escape_html(self, text: str) -> str:
        """转义HTML特殊字符"""
        return (text.replace("&", "&amp;")
                   .replace("<", "&lt;")
                   .replace(">", "&gt;")
                   .replace('"', "&quot;")
                   .replace("'", "&#x27;"))
    
    def _json_serializer(self, obj: Any) -> Any:
        """JSON序列化器，处理特殊类型"""
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        else:
            return str(obj)
    
    def format_task_summary(self, tasks: List[Dict[str, Any]], 
                           format_type: OutputFormat = OutputFormat.JSON) -> str:
        """
        格式化任务摘要
        
        Args:
            tasks: 任务列表
            format_type: 输出格式
            
        Returns:
            格式化后的摘要
        """
        summary = {
            "total_tasks": len(tasks),
            "completed": len([t for t in tasks if t.get("status") == "completed"]),
            "failed": len([t for t in tasks if t.get("status") == "failed"]),
            "running": len([t for t in tasks if t.get("status") == "running"]),
            "pending": len([t for t in tasks if t.get("status") == "pending"]),
            "tasks": tasks
        }
        
        return self.format_result(summary, format_type)
    
    def format_error(self, error: Exception, task_id: Optional[str] = None,
                    format_type: OutputFormat = OutputFormat.JSON) -> str:
        """
        格式化错误信息
        
        Args:
            error: 异常对象
            task_id: 任务ID
            format_type: 输出格式
            
        Returns:
            格式化后的错误信息
        """
        error_result = {
            "success": False,
            "error": str(error),
            "error_type": type(error).__name__,
            "timestamp": time.time()
        }
        
        if task_id:
            error_result["task_id"] = task_id
        
        return self.format_result(error_result, format_type)
