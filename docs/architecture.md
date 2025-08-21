# Kali SSE MCP 命令执行器架构设计

## 1. 系统架构概览

### 1.1 整体架构
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   MCP Client    │    │   MCP Server    │    │  Kali System    │
│                 │    │                 │    │                 │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │ Client SDK  │ │◄──►│ │ MCP Handler │ │◄──►│ │ Command     │ │
│ └─────────────┘ │    │ └─────────────┘ │    │ │ Executor    │ │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ └─────────────┘ │
│ │ SSE Client  │ │◄──►│ │ SSE Handler │ │    │ ┌─────────────┐ │
│ └─────────────┘ │    │ └─────────────┘ │    │ │ Security    │ │
└─────────────────┘    └─────────────────┘    │ │ Validator   │ │
                                              │ └─────────────┘ │
                                              └─────────────────┘
```

### 1.2 核心组件
- **MCP 协议层**: 处理 MCP 标准通信
- **SSE 事件层**: 提供实时事件流
- **安全验证层**: 命令安全检查和权限控制
- **执行引擎层**: 命令执行和结果处理
- **智能化层**: 错误学习和策略优化

## 2. 模块设计

### 2.1 协议模块 (protocols/)
```python
protocols/
├── __init__.py
├── mcp_server.py          # MCP 服务器实现
├── sse_handler.py         # SSE 事件处理
├── message_parser.py      # 消息解析器
└── protocol_validator.py  # 协议验证器
```

**职责**:
- 实现 MCP 协议标准
- 处理客户端连接和消息路由
- 管理 SSE 事件流
- 验证协议合规性

### 2.2 核心模块 (core/)
```python
core/
├── __init__.py
├── executor.py            # 命令执行引擎
├── task_manager.py        # 任务管理器
├── result_formatter.py    # 结果格式化器
└── config_manager.py      # 配置管理器
```

**职责**:
- 管理命令执行生命周期
- 处理同步/异步执行
- 格式化执行结果
- 管理系统配置

### 2.3 安全模块 (security/)
```python
security/
├── __init__.py
├── command_validator.py   # 命令验证器
├── access_controller.py   # 访问控制器
├── audit_logger.py        # 审计日志器
└── injection_detector.py  # 注入检测器
```

**职责**:
- 验证命令安全性
- 实施访问控制策略
- 记录审计日志
- 检测和防止注入攻击

### 2.4 智能化模块 (intelligence/)
```python
intelligence/
├── __init__.py
├── syntax_checker.py      # 语法检查器
├── error_learner.py       # 错误学习器
├── strategy_tree.py       # 策略树
└── task_chain.py          # 任务链
```

**职责**:
- 自动语法检查和纠错
- 从错误中学习和改进
- 实施智能决策策略
- 管理自动化任务链

### 2.5 工具模块 (utils/)
```python
utils/
├── __init__.py
├── logger.py              # 日志工具
├── crypto.py              # 加密工具
├── network.py             # 网络工具
└── file_handler.py        # 文件处理工具
```

## 3. 数据流设计

### 3.1 命令执行流程
```
Client Request → MCP Parser → Security Validator → Command Executor → Result Formatter → Client Response
                     ↓              ↓                    ↓                ↓
                SSE Events ← Audit Logger ← Task Manager ← Intelligence Layer
```

### 3.2 数据结构

#### 3.2.1 命令请求格式
```json
{
  "id": "unique_request_id",
  "method": "execute_command",
  "params": {
    "command": "nmap -sS target.com",
    "options": {
      "timeout": 300,
      "async": true,
      "priority": "high"
    },
    "context": {
      "user_id": "user123",
      "session_id": "session456"
    }
  }
}
```

#### 3.2.2 命令响应格式
```json
{
  "id": "unique_request_id",
  "result": {
    "success": true,
    "task_id": "task789",
    "status": "completed",
    "output": {
      "stdout": "command output",
      "stderr": "",
      "return_code": 0
    },
    "metadata": {
      "start_time": "2025-01-01T00:00:00Z",
      "end_time": "2025-01-01T00:05:00Z",
      "duration": 300.0,
      "command": "nmap -sS target.com"
    },
    "intelligence": {
      "syntax_valid": true,
      "security_score": 0.95,
      "recommendations": []
    }
  }
}
```

#### 3.2.3 SSE 事件格式
```json
{
  "event": "command_progress",
  "data": {
    "task_id": "task789",
    "status": "running",
    "progress": 0.6,
    "partial_output": "Scanning ports...",
    "timestamp": "2025-01-01T00:03:00Z"
  }
}
```

## 4. 安全架构

### 4.1 多层安全防护
```
┌─────────────────────────────────────────┐
│              应用层安全                   │
│  ┌─────────────┐  ┌─────────────────┐   │
│  │ 命令白名单   │  │ 参数验证        │   │
│  └─────────────┘  └─────────────────┘   │
└─────────────────────────────────────────┘
┌─────────────────────────────────────────┐
│              协议层安全                   │
│  ┌─────────────┐  ┌─────────────────┐   │
│  │ MCP 验证    │  │ 消息完整性      │   │
│  └─────────────┘  └─────────────────┘   │
└─────────────────────────────────────────┘
┌─────────────────────────────────────────┐
│              传输层安全                   │
│  ┌─────────────┐  ┌─────────────────┐   │
│  │ TLS 加密    │  │ 身份认证        │   │
│  └─────────────┘  └─────────────────┘   │
└─────────────────────────────────────────┘
```

### 4.2 权限控制模型
- **角色定义**: Admin, Operator, Viewer
- **权限矩阵**: 基于角色的命令执行权限
- **会话管理**: 安全的会话生命周期管理
- **审计跟踪**: 完整的操作审计记录

## 5. 性能设计

### 5.1 异步处理架构
- **事件循环**: 基于 asyncio 的异步处理
- **任务队列**: 优先级队列管理
- **资源池**: 连接池和进程池管理
- **缓存策略**: 智能结果缓存

### 5.2 扩展性设计
- **水平扩展**: 支持多实例部署
- **负载均衡**: 智能任务分发
- **状态管理**: 无状态服务设计
- **监控指标**: 完整的性能监控

## 6. 部署架构

### 6.1 单机部署
```
┌─────────────────────────────────────┐
│           Kali Linux Host           │
│  ┌─────────────────────────────┐   │
│  │     Kali SSE MCP Server     │   │
│  │  ┌─────────┐ ┌─────────────┐ │   │
│  │  │ MCP API │ │ SSE Handler │ │   │
│  │  └─────────┘ └─────────────┘ │   │
│  └─────────────────────────────┘   │
│  ┌─────────────────────────────┐   │
│  │      Security Tools         │   │
│  │ nmap | nikto | dirb | ...   │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
```

### 6.2 分布式部署
```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Load        │    │ MCP Server  │    │ Execution   │
│ Balancer    │◄──►│ Cluster     │◄──►│ Nodes       │
│             │    │             │    │             │
└─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │
       ▼                   ▼                   ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ SSL/TLS     │    │ Redis       │    │ Kali Tools  │
│ Termination │    │ Cache       │    │ Execution   │
└─────────────┘    └─────────────┘    └─────────────┘
```

这个架构设计为后续的具体实现提供了清晰的指导方向。
