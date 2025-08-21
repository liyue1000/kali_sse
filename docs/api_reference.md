# Kali SSE MCP API 参考文档

## 1. MCP 协议接口

### 1.1 工具注册

#### 1.1.1 execute_command
执行 Kali Linux 安全工具命令

**参数**:
```json
{
  "command": "string",           // 要执行的命令
  "args": ["string"],           // 命令参数列表 (可选)
  "options": {                  // 执行选项 (可选)
    "timeout": 300,             // 超时时间(秒)
    "async": true,              // 是否异步执行
    "priority": "normal",       // 优先级: low|normal|high
    "working_dir": "/tmp",      // 工作目录
    "env_vars": {}              // 环境变量
  }
}
```

**返回**:
```json
{
  "success": true,
  "task_id": "task_123456",
  "status": "running|completed|failed",
  "output": {
    "stdout": "string",
    "stderr": "string", 
    "return_code": 0
  },
  "metadata": {
    "start_time": "2025-01-01T00:00:00Z",
    "end_time": "2025-01-01T00:05:00Z",
    "duration": 300.0,
    "command_line": "nmap -sS target.com"
  }
}
```

#### 1.1.2 get_task_status
获取任务执行状态

**参数**:
```json
{
  "task_id": "task_123456"
}
```

**返回**:
```json
{
  "task_id": "task_123456",
  "status": "running|completed|failed|cancelled",
  "progress": 0.75,
  "current_output": "string",
  "estimated_remaining": 60
}
```

#### 1.1.3 cancel_task
取消正在执行的任务

**参数**:
```json
{
  "task_id": "task_123456",
  "force": false
}
```

**返回**:
```json
{
  "success": true,
  "task_id": "task_123456",
  "status": "cancelled"
}
```

#### 1.1.4 list_supported_tools
列出支持的安全工具

**参数**: 无

**返回**:
```json
{
  "tools": [
    {
      "name": "nmap",
      "version": "7.94",
      "description": "Network exploration tool and security scanner",
      "categories": ["network", "scanning"],
      "common_options": ["-sS", "-sV", "-O", "-A"]
    },
    {
      "name": "nikto",
      "version": "2.5.0",
      "description": "Web server scanner",
      "categories": ["web", "vulnerability"],
      "common_options": ["-h", "-p", "-ssl"]
    }
  ]
}
```

### 1.2 智能化接口

#### 1.2.1 validate_command
验证命令语法和安全性

**参数**:
```json
{
  "command": "nmap -sS target.com",
  "check_syntax": true,
  "check_security": true
}
```

**返回**:
```json
{
  "valid": true,
  "syntax_score": 0.95,
  "security_score": 0.90,
  "issues": [],
  "suggestions": [
    "Consider adding -T4 for faster scanning"
  ]
}
```

#### 1.2.2 get_command_suggestions
获取命令建议

**参数**:
```json
{
  "partial_command": "nmap -s",
  "context": "network_scanning",
  "target_type": "web_server"
}
```

**返回**:
```json
{
  "suggestions": [
    {
      "command": "nmap -sS",
      "description": "TCP SYN scan",
      "confidence": 0.95
    },
    {
      "command": "nmap -sV",
      "description": "Version detection scan", 
      "confidence": 0.85
    }
  ]
}
```

## 2. SSE 事件接口

### 2.1 事件类型

#### 2.1.1 task_started
任务开始执行

```json
{
  "event": "task_started",
  "data": {
    "task_id": "task_123456",
    "command": "nmap -sS target.com",
    "timestamp": "2025-01-01T00:00:00Z"
  }
}
```

#### 2.1.2 task_progress
任务执行进度

```json
{
  "event": "task_progress", 
  "data": {
    "task_id": "task_123456",
    "progress": 0.45,
    "status": "running",
    "partial_output": "Scanning 192.168.1.1...",
    "timestamp": "2025-01-01T00:02:30Z"
  }
}
```

#### 2.1.3 task_completed
任务执行完成

```json
{
  "event": "task_completed",
  "data": {
    "task_id": "task_123456", 
    "status": "completed",
    "final_output": "Scan completed successfully",
    "return_code": 0,
    "duration": 150.5,
    "timestamp": "2025-01-01T00:02:30Z"
  }
}
```

#### 2.1.4 task_failed
任务执行失败

```json
{
  "event": "task_failed",
  "data": {
    "task_id": "task_123456",
    "error": "Command execution timeout",
    "error_code": "TIMEOUT",
    "partial_output": "Partial scan results...",
    "timestamp": "2025-01-01T00:05:00Z"
  }
}
```

#### 2.1.5 security_alert
安全警报

```json
{
  "event": "security_alert",
  "data": {
    "alert_type": "suspicious_command",
    "severity": "high",
    "command": "rm -rf /",
    "reason": "Potentially destructive command detected",
    "timestamp": "2025-01-01T00:00:00Z"
  }
}
```

### 2.2 SSE 连接

#### 2.2.1 连接端点
```
GET /api/v1/events
Accept: text/event-stream
Authorization: Bearer <token>
```

#### 2.2.2 连接参数
- `task_filter`: 过滤特定任务的事件
- `event_types`: 订阅特定类型的事件
- `heartbeat`: 心跳间隔(秒)

示例:
```
GET /api/v1/events?task_filter=task_123456&event_types=task_progress,task_completed&heartbeat=30
```

## 3. REST API 接口

### 3.1 基础信息

#### 3.1.1 服务状态
```
GET /api/v1/health
```

**返回**:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime": 3600,
  "active_tasks": 5,
  "system_load": 0.75
}
```

#### 3.1.2 系统信息
```
GET /api/v1/system/info
```

**返回**:
```json
{
  "os": "Kali Linux 2024.1",
  "kernel": "6.1.0-kali7-amd64",
  "python_version": "3.11.2",
  "available_tools": 25,
  "memory_usage": "45%",
  "disk_usage": "60%"
}
```

### 3.2 任务管理

#### 3.2.1 获取任务列表
```
GET /api/v1/tasks?status=running&limit=10&offset=0
```

**返回**:
```json
{
  "tasks": [
    {
      "task_id": "task_123456",
      "command": "nmap -sS target.com",
      "status": "running",
      "progress": 0.45,
      "start_time": "2025-01-01T00:00:00Z"
    }
  ],
  "total": 1,
  "limit": 10,
  "offset": 0
}
```

#### 3.2.2 获取任务详情
```
GET /api/v1/tasks/{task_id}
```

#### 3.2.3 删除任务
```
DELETE /api/v1/tasks/{task_id}
```

### 3.3 配置管理

#### 3.3.1 获取配置
```
GET /api/v1/config
```

#### 3.3.2 更新配置
```
PUT /api/v1/config
Content-Type: application/json

{
  "security": {
    "command_whitelist": ["nmap", "nikto"],
    "max_concurrent_tasks": 5
  }
}
```

## 4. 错误代码

| 代码 | 名称 | 描述 |
|------|------|------|
| 1000 | INVALID_COMMAND | 无效的命令 |
| 1001 | COMMAND_NOT_ALLOWED | 命令不在白名单中 |
| 1002 | INSUFFICIENT_PERMISSIONS | 权限不足 |
| 1003 | COMMAND_TIMEOUT | 命令执行超时 |
| 1004 | TASK_NOT_FOUND | 任务不存在 |
| 1005 | SYSTEM_OVERLOAD | 系统负载过高 |
| 1006 | SECURITY_VIOLATION | 安全策略违规 |

## 5. 使用示例

### 5.1 Python 客户端示例
```python
import asyncio
from kali_sse_client import KaliSSEClient

async def main():
    client = KaliSSEClient("http://localhost:8000")
    
    # 执行命令
    result = await client.execute_command(
        "nmap -sS 192.168.1.1",
        options={"async": True}
    )
    
    # 监听事件
    async for event in client.listen_events():
        print(f"Event: {event}")

asyncio.run(main())
```

### 5.2 JavaScript 客户端示例
```javascript
const client = new KaliSSEClient('http://localhost:8000');

// 执行命令
const result = await client.executeCommand('nmap -sS 192.168.1.1', {
  async: true
});

// 监听事件
client.addEventListener('task_progress', (event) => {
  console.log('Progress:', event.data.progress);
});
```
