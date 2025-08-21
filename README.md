# Kali SSE MCP 命令执行器

## 项目概述

Kali SSE MCP 命令执行器是一个符合 Model Context Protocol (MCP) 规范的智能化 Kali Linux 命令执行系统。该系统通过 Server-Sent Events (SSE) 提供实时命令执行能力，具备完整的安全机制和智能化功能。

## 核心特性

### 🔒 安全性
- **命令验证机制**：严格的命令白名单/黑名单过滤
- **权限控制**：基于角色的访问控制 (RBAC)
- **注入防护**：防止命令注入攻击
- **审计日志**：完整的命令执行审计跟踪

### 🧠 智能化
- **语法验证**：自动命令语法检查和纠错
- **错误学习**：从执行失败中学习，避免重复错误
- **策略优化**：基于优先级树的智能决策
- **任务链**：触发器驱动的自动化任务执行

### ⚡ 性能
- **异步执行**：支持长时间运行的渗透测试命令
- **实时监控**：通过 SSE 提供实时执行状态
- **队列管理**：智能的命令队列和资源管理
- **结果缓存**：优化重复命令的执行效率

### 🔌 兼容性
- **MCP 标准**：严格遵循 MCP 协议规范
- **RESTful API**：标准的 HTTP API 接口
- **SSE 支持**：实时事件流通信
- **多客户端**：支持多个客户端同时连接

## 项目结构

```
kali_sse/
├── docs/                    # 开发文档
│   ├── architecture.md     # 架构设计文档
│   ├── api_reference.md    # API 参考文档
│   ├── security_guide.md   # 安全指南
│   └── deployment.md       # 部署指南
├── src/                     # 源代码
│   ├── core/               # 核心模块
│   ├── security/           # 安全模块
│   ├── intelligence/       # 智能化模块
│   ├── protocols/          # MCP协议实现
│   └── utils/              # 工具模块
├── tests/                  # 测试代码
├── config/                 # 配置文件
├── examples/               # 使用示例
├── requirements.txt        # 依赖包
├── setup.py               # 安装脚本
└── README.md              # 项目说明
```

## 快速开始

### 环境要求
- Python 3.8+
- Kali Linux 或兼容的 Linux 发行版
- 必要的渗透测试工具 (nmap, nikto, dirb, etc.)

### 安装
```bash
# 克隆项目
cd /home/kali/Desktop/pentest/pentestmcp/kali_sse

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 安装项目
pip install -e .
```

### 配置
```bash
# 复制配置模板
cp config/config.example.json config/config.json

# 编辑配置文件
nano config/config.json
```

### 启动服务
```bash
# 启动 MCP 服务器
python -m kali_sse.server

# 或使用配置文件启动
python -m kali_sse.server --config config/config.json
```

## 开发状态

- [x] 项目架构设计
- [ ] MCP 协议核心模块
- [ ] 命令执行引擎
- [ ] 安全验证系统
- [ ] 智能化功能
- [ ] 测试套件
- [ ] 性能优化

## 贡献指南

请参阅 [CONTRIBUTING.md](docs/CONTRIBUTING.md) 了解如何为项目做出贡献。

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

## 联系方式

如有问题或建议，请通过以下方式联系：
- 创建 Issue
- 提交 Pull Request
- 发送邮件至项目维护者

---

**注意**: 本工具仅用于授权的渗透测试和安全研究。使用者需要确保遵守相关法律法规。
