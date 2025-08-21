# Kali SSE MCP 安全指南

## 1. 安全架构概述

### 1.1 安全设计原则
- **最小权限原则**: 用户和进程仅获得完成任务所需的最小权限
- **深度防御**: 多层安全控制，确保单点失效不会导致系统妥协
- **零信任模型**: 对所有请求进行验证，不信任任何默认权限
- **审计透明**: 所有操作都有完整的审计跟踪记录

### 1.2 威胁模型
```
┌─────────────────────────────────────────────────────────┐
│                    威胁向量分析                          │
├─────────────────────────────────────────────────────────┤
│ 1. 命令注入攻击 → 输入验证 + 参数化执行                   │
│ 2. 权限提升攻击 → RBAC + 最小权限                       │
│ 3. 拒绝服务攻击 → 速率限制 + 资源管理                   │
│ 4. 数据泄露风险 → 加密传输 + 访问控制                   │
│ 5. 会话劫持攻击 → 安全会话 + 令牌管理                   │
└─────────────────────────────────────────────────────────┘
```

## 2. 命令安全验证

### 2.1 命令白名单机制

#### 2.1.1 工具白名单
```json
{
  "allowed_tools": {
    "nmap": {
      "path": "/usr/bin/nmap",
      "allowed_options": [
        "-sS", "-sT", "-sU", "-sV", "-O", "-A",
        "-p", "-T1", "-T2", "-T3", "-T4", "-T5",
        "--script", "--script-args"
      ],
      "forbidden_options": [
        "--privileged", "--unprivileged"
      ],
      "max_targets": 256,
      "timeout_limit": 3600
    },
    "nikto": {
      "path": "/usr/bin/nikto",
      "allowed_options": [
        "-h", "-p", "-ssl", "-Format", "-output",
        "-Tuning", "-timeout", "-useragent"
      ],
      "forbidden_options": [
        "-update"
      ],
      "max_targets": 1,
      "timeout_limit": 1800
    }
  }
}
```

#### 2.1.2 参数验证规则
```python
VALIDATION_RULES = {
    "ip_address": r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$",
    "domain_name": r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$",
    "port_range": r"^[1-9][0-9]{0,4}(-[1-9][0-9]{0,4})?$",
    "file_path": r"^[a-zA-Z0-9\/_\-\.]+$",
    "url": r"^https?:\/\/[^\s]+$"
}

DANGEROUS_PATTERNS = [
    r";\s*rm\s+-rf",           # 删除命令
    r";\s*dd\s+if=",           # 磁盘操作
    r">\s*\/dev\/",            # 设备文件写入
    r"\|\s*sh\s*",             # 管道到shell
    r"&&\s*rm\s+",             # 链式删除
    r"`.*`",                   # 命令替换
    r"\$\(.*\)",               # 命令替换
]
```

### 2.2 注入攻击防护

#### 2.2.1 输入清理
```python
def sanitize_input(user_input: str) -> str:
    """清理用户输入，防止注入攻击"""
    # 移除危险字符
    dangerous_chars = [';', '|', '&', '`', '$', '(', ')', '{', '}']
    for char in dangerous_chars:
        user_input = user_input.replace(char, '')
    
    # 限制长度
    if len(user_input) > MAX_INPUT_LENGTH:
        raise ValueError("Input too long")
    
    # 验证字符集
    if not re.match(r'^[a-zA-Z0-9\s\-\._:/]+$', user_input):
        raise ValueError("Invalid characters in input")
    
    return user_input.strip()
```

#### 2.2.2 参数化执行
```python
def execute_command_safely(tool: str, args: List[str]) -> subprocess.Popen:
    """安全的命令执行，使用参数化方式"""
    # 验证工具路径
    tool_path = get_validated_tool_path(tool)
    
    # 验证每个参数
    validated_args = []
    for arg in args:
        validated_arg = validate_argument(arg)
        validated_args.append(validated_arg)
    
    # 构建命令列表（不使用shell=True）
    cmd = [tool_path] + validated_args
    
    # 设置安全的执行环境
    env = get_secure_environment()
    
    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        shell=False,  # 关键：不使用shell
        cwd="/tmp",   # 安全的工作目录
        preexec_fn=drop_privileges  # 降低权限
    )
```

## 3. 访问控制

### 3.1 基于角色的访问控制 (RBAC)

#### 3.1.1 角色定义
```json
{
  "roles": {
    "admin": {
      "description": "系统管理员",
      "permissions": [
        "execute_any_command",
        "manage_users",
        "view_audit_logs",
        "modify_configuration"
      ],
      "command_limits": {
        "max_concurrent_tasks": 50,
        "max_execution_time": 7200
      }
    },
    "operator": {
      "description": "渗透测试操作员",
      "permissions": [
        "execute_scanning_commands",
        "execute_enumeration_commands",
        "view_own_tasks"
      ],
      "command_limits": {
        "max_concurrent_tasks": 10,
        "max_execution_time": 3600
      },
      "allowed_tools": ["nmap", "nikto", "dirb", "gobuster"]
    },
    "viewer": {
      "description": "只读用户",
      "permissions": [
        "view_task_status",
        "view_results"
      ],
      "command_limits": {
        "max_concurrent_tasks": 0,
        "max_execution_time": 0
      }
    }
  }
}
```

#### 3.1.2 权限检查
```python
def check_permission(user: User, action: str, resource: str) -> bool:
    """检查用户权限"""
    user_role = get_user_role(user)
    role_permissions = get_role_permissions(user_role)
    
    # 检查基本权限
    if action not in role_permissions:
        return False
    
    # 检查资源特定权限
    if not check_resource_permission(user, resource):
        return False
    
    # 检查速率限制
    if not check_rate_limit(user, action):
        return False
    
    return True
```

### 3.2 会话管理

#### 3.2.1 安全会话配置
```python
SESSION_CONFIG = {
    "session_timeout": 3600,        # 1小时超时
    "max_sessions_per_user": 3,     # 每用户最大会话数
    "session_renewal_threshold": 300, # 5分钟续期阈值
    "secure_cookies": True,         # 安全Cookie
    "httponly_cookies": True,       # HttpOnly Cookie
    "samesite_policy": "Strict"     # SameSite策略
}
```

#### 3.2.2 令牌管理
```python
def generate_secure_token() -> str:
    """生成安全令牌"""
    # 使用加密安全的随机数生成器
    token_bytes = secrets.token_bytes(32)
    
    # 添加时间戳和用户信息
    payload = {
        "token": token_bytes.hex(),
        "issued_at": time.time(),
        "expires_at": time.time() + SESSION_CONFIG["session_timeout"]
    }
    
    # 使用JWT签名
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")
```

## 4. 审计和监控

### 4.1 审计日志

#### 4.1.1 日志格式
```json
{
  "timestamp": "2025-01-01T00:00:00Z",
  "event_type": "command_execution",
  "severity": "info",
  "user_id": "user123",
  "session_id": "session456",
  "source_ip": "192.168.1.100",
  "command": "nmap -sS target.com",
  "result": "success",
  "execution_time": 120.5,
  "output_size": 2048,
  "security_score": 0.95
}
```

#### 4.1.2 关键事件记录
- 用户登录/登出
- 命令执行（成功/失败）
- 权限检查失败
- 安全策略违规
- 系统配置变更
- 异常错误事件

### 4.2 实时监控

#### 4.2.1 安全指标监控
```python
SECURITY_METRICS = {
    "failed_login_attempts": {
        "threshold": 5,
        "window": 300,  # 5分钟
        "action": "block_ip"
    },
    "command_injection_attempts": {
        "threshold": 1,
        "window": 60,
        "action": "alert_admin"
    },
    "privilege_escalation_attempts": {
        "threshold": 3,
        "window": 600,
        "action": "suspend_user"
    }
}
```

#### 4.2.2 异常检测
```python
def detect_anomalies(user_activity: List[Dict]) -> List[Dict]:
    """检测用户行为异常"""
    anomalies = []
    
    # 检测异常命令模式
    if detect_unusual_command_pattern(user_activity):
        anomalies.append({
            "type": "unusual_command_pattern",
            "severity": "medium",
            "description": "User executing unusual command combinations"
        })
    
    # 检测异常时间模式
    if detect_unusual_time_pattern(user_activity):
        anomalies.append({
            "type": "unusual_time_pattern", 
            "severity": "low",
            "description": "User active during unusual hours"
        })
    
    return anomalies
```

## 5. 网络安全

### 5.1 传输层安全

#### 5.1.1 TLS 配置
```python
TLS_CONFIG = {
    "min_version": "TLSv1.2",
    "ciphers": [
        "ECDHE-RSA-AES256-GCM-SHA384",
        "ECDHE-RSA-AES128-GCM-SHA256",
        "ECDHE-RSA-AES256-SHA384"
    ],
    "certificate_validation": True,
    "hsts_enabled": True,
    "hsts_max_age": 31536000
}
```

#### 5.1.2 API 安全
```python
API_SECURITY = {
    "rate_limiting": {
        "requests_per_minute": 60,
        "burst_limit": 10
    },
    "cors_policy": {
        "allowed_origins": ["https://trusted-domain.com"],
        "allowed_methods": ["GET", "POST"],
        "allowed_headers": ["Authorization", "Content-Type"]
    },
    "content_security_policy": {
        "default_src": "'self'",
        "script_src": "'self' 'unsafe-inline'",
        "style_src": "'self' 'unsafe-inline'"
    }
}
```

## 6. 部署安全

### 6.1 系统加固

#### 6.1.1 文件系统权限
```bash
# 设置正确的文件权限
chmod 750 /opt/kali_sse
chmod 640 /opt/kali_sse/config/*.json
chmod 600 /opt/kali_sse/secrets/*

# 设置正确的所有者
chown -R kali_sse:kali_sse /opt/kali_sse
```

#### 6.1.2 防火墙配置
```bash
# 只允许必要的端口
ufw allow 8000/tcp  # MCP API端口
ufw allow 8001/tcp  # SSE端口
ufw deny 22/tcp     # 禁用SSH（如果不需要）
ufw enable
```

### 6.2 容器安全

#### 6.2.1 Docker 安全配置
```dockerfile
# 使用非root用户
USER kali_sse

# 只读文件系统
RUN mount -o remount,ro /

# 限制能力
RUN setcap cap_net_raw+ep /usr/bin/nmap

# 安全扫描
RUN trivy filesystem --exit-code 1 .
```

## 7. 应急响应

### 7.1 安全事件响应

#### 7.1.1 事件分类
- **P0 - 严重**: 系统被完全妥协
- **P1 - 高危**: 权限提升或数据泄露
- **P2 - 中危**: 拒绝服务或异常行为
- **P3 - 低危**: 策略违规或可疑活动

#### 7.1.2 响应流程
1. **检测**: 自动监控系统检测异常
2. **分析**: 确定事件严重性和影响范围
3. **遏制**: 立即阻止攻击继续进行
4. **根除**: 清除攻击痕迹和后门
5. **恢复**: 恢复正常服务运行
6. **总结**: 分析事件原因并改进防护

### 7.2 备份和恢复

#### 7.2.1 数据备份策略
```python
BACKUP_CONFIG = {
    "frequency": "daily",
    "retention": 30,  # 保留30天
    "encryption": True,
    "compression": True,
    "verification": True,
    "offsite_backup": True
}
```

这个安全指南为系统的安全实施提供了全面的指导。
