# Kali SSE MCP 部署指南

## 1. 系统要求

### 1.1 硬件要求
- **CPU**: 2核心以上
- **内存**: 4GB RAM 最小，8GB 推荐
- **存储**: 10GB 可用空间
- **网络**: 稳定的网络连接

### 1.2 软件要求
- **操作系统**: Kali Linux 2024.1+ 或兼容的 Linux 发行版
- **Python**: 3.8 或更高版本
- **安全工具**: nmap, nikto, dirb, gobuster 等

## 2. 安装步骤

### 2.1 环境准备
```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装必要的系统包
sudo apt install -y python3 python3-pip python3-venv git

# 安装安全工具（如果未安装）
sudo apt install -y nmap nikto dirb gobuster sqlmap
```

### 2.2 项目安装
```bash
# 进入项目目录
cd /home/kali/Desktop/pentest/pentestmcp/kali_sse

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 升级pip
pip install --upgrade pip

# 安装依赖
pip install -r requirements.txt

# 安装项目
pip install -e .
```

### 2.3 配置设置
```bash
# 复制配置模板
cp config/config.example.json config/config.json

# 编辑配置文件
nano config/config.json
```

### 2.4 权限设置
```bash
# 创建必要的目录
sudo mkdir -p /var/log/kali_sse
sudo mkdir -p /var/lib/kali_sse
sudo mkdir -p /etc/kali_sse

# 设置权限
sudo chown -R $USER:$USER /var/log/kali_sse
sudo chown -R $USER:$USER /var/lib/kali_sse
sudo chmod 755 /var/log/kali_sse
sudo chmod 755 /var/lib/kali_sse

# 复制配置到系统目录
sudo cp config/config.json /etc/kali_sse/
```

## 3. 配置详解

### 3.1 基础配置
```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 8000,
    "debug": false,
    "workers": 1
  },
  "security": {
    "authentication": {
      "enabled": true,
      "secret_key": "your-secret-key-here"
    }
  }
}
```

### 3.2 安全配置
```json
{
  "security": {
    "command_validation": {
      "enabled": true,
      "whitelist_mode": true,
      "allowed_tools": {
        "nmap": {
          "path": "/usr/bin/nmap",
          "timeout_limit": 3600
        }
      }
    }
  }
}
```

### 3.3 执行配置
```json
{
  "execution": {
    "default_timeout": 300,
    "max_concurrent_tasks": 20,
    "working_directory": "/tmp/kali_sse"
  }
}
```

## 4. 启动服务

### 4.1 开发模式启动
```bash
# 激活虚拟环境
source venv/bin/activate

# 启动服务器
python -m src serve --debug

# 或使用配置文件
python -m src serve --config config/config.json
```

### 4.2 生产模式启动
```bash
# 使用 systemd 服务
sudo cp scripts/kali-sse-mcp.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable kali-sse-mcp
sudo systemctl start kali-sse-mcp
```

### 4.3 Docker 部署
```bash
# 构建镜像
docker build -t kali-sse-mcp .

# 运行容器
docker run -d \
  --name kali-sse-mcp \
  -p 8000:8000 \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/logs:/var/log/kali_sse \
  kali-sse-mcp
```

## 5. 验证部署

### 5.1 健康检查
```bash
# 检查服务状态
curl http://localhost:8000/health

# 检查配置
python -m src config-check

# 运行测试
python -m pytest tests/
```

### 5.2 功能测试
```bash
# 测试命令验证
python -m src validate "nmap -sS 192.168.1.1"

# 测试命令执行
python -m src execute "echo 'Hello World'"

# 运行演示程序
python examples/quick_start.py
```

## 6. 监控和日志

### 6.1 日志配置
```json
{
  "monitoring": {
    "logging": {
      "level": "INFO",
      "file": "/var/log/kali_sse/app.log",
      "max_file_size": 104857600,
      "backup_count": 5
    }
  }
}
```

### 6.2 监控指标
```bash
# 查看指标
curl http://localhost:8000/metrics

# 查看系统状态
curl http://localhost:8000/health
```

### 6.3 日志查看
```bash
# 查看应用日志
tail -f /var/log/kali_sse/app.log

# 查看审计日志
tail -f /var/log/kali_sse/audit.log

# 查看系统服务日志
sudo journalctl -u kali-sse-mcp -f
```

## 7. 安全加固

### 7.1 网络安全
```bash
# 配置防火墙
sudo ufw allow 8000/tcp
sudo ufw enable

# 配置 SSL/TLS
sudo apt install nginx
sudo certbot --nginx -d your-domain.com
```

### 7.2 访问控制
```json
{
  "security": {
    "rate_limiting": {
      "enabled": true,
      "requests_per_minute": 60
    },
    "cors": {
      "allowed_origins": ["https://trusted-domain.com"]
    }
  }
}
```

### 7.3 审计配置
```json
{
  "security": {
    "audit": {
      "enabled": true,
      "log_file": "/var/log/kali_sse/audit.log",
      "events": ["authentication", "command_execution"]
    }
  }
}
```

## 8. 性能优化

### 8.1 系统优化
```bash
# 调整文件描述符限制
echo "* soft nofile 65536" | sudo tee -a /etc/security/limits.conf
echo "* hard nofile 65536" | sudo tee -a /etc/security/limits.conf

# 优化内核参数
echo "net.core.somaxconn = 65536" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

### 8.2 应用优化
```json
{
  "server": {
    "workers": 4,
    "max_connections": 1000,
    "keepalive_timeout": 30
  },
  "execution": {
    "max_concurrent_tasks": 50
  }
}
```

## 9. 备份和恢复

### 9.1 备份策略
```bash
#!/bin/bash
# backup.sh
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backup/kali_sse_$DATE"

mkdir -p $BACKUP_DIR

# 备份配置
cp -r /etc/kali_sse $BACKUP_DIR/

# 备份数据
cp -r /var/lib/kali_sse $BACKUP_DIR/

# 备份日志
cp -r /var/log/kali_sse $BACKUP_DIR/

# 压缩备份
tar -czf $BACKUP_DIR.tar.gz $BACKUP_DIR
rm -rf $BACKUP_DIR
```

### 9.2 恢复过程
```bash
# 停止服务
sudo systemctl stop kali-sse-mcp

# 恢复配置
sudo tar -xzf backup.tar.gz
sudo cp -r backup/etc/kali_sse /etc/
sudo cp -r backup/var/lib/kali_sse /var/lib/
sudo cp -r backup/var/log/kali_sse /var/log/

# 重启服务
sudo systemctl start kali-sse-mcp
```

## 10. 故障排除

### 10.1 常见问题

#### 服务无法启动
```bash
# 检查端口占用
sudo netstat -tlnp | grep 8000

# 检查权限
ls -la /var/log/kali_sse
ls -la /var/lib/kali_sse

# 检查配置
python -m src config-check
```

#### 命令执行失败
```bash
# 检查工具路径
which nmap
which nikto

# 检查权限
ls -la /usr/bin/nmap

# 检查配置
cat /etc/kali_sse/config.json | jq .security.command_validation
```

#### 性能问题
```bash
# 检查系统资源
top
free -h
df -h

# 检查日志
tail -f /var/log/kali_sse/app.log | grep ERROR
```

### 10.2 调试模式
```bash
# 启用调试模式
python -m src serve --debug

# 查看详细日志
export KALI_SSE_LOG_LEVEL=DEBUG
python -m src serve
```

## 11. 升级指南

### 11.1 升级步骤
```bash
# 备份当前版本
./scripts/backup.sh

# 停止服务
sudo systemctl stop kali-sse-mcp

# 更新代码
git pull origin main

# 更新依赖
pip install -r requirements.txt

# 运行迁移（如果需要）
python scripts/migrate.py

# 重启服务
sudo systemctl start kali-sse-mcp

# 验证升级
python -m src version
curl http://localhost:8000/health
```

### 11.2 回滚步骤
```bash
# 停止服务
sudo systemctl stop kali-sse-mcp

# 恢复备份
./scripts/restore.sh backup_20240101_120000.tar.gz

# 重启服务
sudo systemctl start kali-sse-mcp
```

## 12. 维护任务

### 12.1 定期维护
```bash
# 清理日志
find /var/log/kali_sse -name "*.log" -mtime +30 -delete

# 清理临时文件
find /tmp/kali_sse -mtime +1 -delete

# 更新安全工具
sudo apt update && sudo apt upgrade nmap nikto dirb gobuster
```

### 12.2 监控脚本
```bash
#!/bin/bash
# monitor.sh
if ! curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "Service is down, restarting..."
    sudo systemctl restart kali-sse-mcp
fi
```

这个部署指南提供了完整的部署、配置、监控和维护流程。
