#!/usr/bin/env python3
"""
Kali SSE MCP 快速启动示例

演示如何使用 Kali SSE MCP 命令执行器的基本功能。
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# 添加项目路径到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config_manager import ConfigManager
from src.core.executor import CommandExecutor
from src.security.command_validator import CommandValidator
from src.intelligence.syntax_checker import SyntaxChecker
from src.protocols.mcp_server import MCPServer

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_banner():
    """打印横幅"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                    Kali SSE MCP 命令执行器                    ║
║                     快速启动演示程序                          ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)


def demo_config_manager():
    """演示配置管理器"""
    print("\n🔧 配置管理器演示")
    print("=" * 50)
    
    try:
        # 创建配置管理器
        config_manager = ConfigManager()
        config = config_manager.get_config()
        
        print(f"✓ 服务器配置: {config.server.host}:{config.server.port}")
        print(f"✓ 调试模式: {config.server.debug}")
        print(f"✓ 安全验证: {config.security.command_validation_enabled}")
        print(f"✓ 智能化功能: {config.intelligence.enabled}")
        
        # 演示配置获取和设置
        original_host = config_manager.get("server.host")
        print(f"✓ 原始主机: {original_host}")
        
        config_manager.set("server.host", "127.0.0.1")
        new_host = config_manager.get("server.host")
        print(f"✓ 修改后主机: {new_host}")
        
        return config_manager
        
    except Exception as e:
        print(f"✗ 配置管理器演示失败: {e}")
        return None


def demo_command_validator(config_manager):
    """演示命令验证器"""
    print("\n🛡️ 命令验证器演示")
    print("=" * 50)
    
    try:
        validator = CommandValidator(config_manager)
        
        # 测试有效命令
        test_commands = [
            "nmap -sS 192.168.1.1",
            "nikto -h example.com",
            "echo 'Hello World'",
            "nmap -sS 192.168.1.1; rm -rf /",  # 危险命令
            "unknown_tool --help",  # 未知工具
        ]
        
        for command in test_commands:
            result = validator.validate_command(command)
            status = "✓" if result["valid"] else "✗"
            score = result["score"]
            
            print(f"{status} 命令: {command}")
            print(f"   有效性: {result['valid']}, 分数: {score:.2f}")
            
            if result["issues"]:
                print(f"   问题: {result['issues']}")
            
            print()
        
        # 显示支持的工具
        tools = validator.get_allowed_tools()
        print(f"✓ 支持的工具: {', '.join(tools)}")
        
        return validator
        
    except Exception as e:
        print(f"✗ 命令验证器演示失败: {e}")
        return None


def demo_syntax_checker(config_manager):
    """演示语法检查器"""
    print("\n🧠 语法检查器演示")
    print("=" * 50)
    
    try:
        syntax_checker = SyntaxChecker(config_manager)
        
        # 测试语法检查
        test_commands = [
            "nmap -sS 192.168.1.1",
            "nmap 192.168.1.1",  # 缺少扫描选项
            "nikto example.com",  # 缺少 -h 参数
            "namp -sS 192.168.1.1",  # 拼写错误
        ]
        
        for command in test_commands:
            result = syntax_checker.check_syntax(command)
            status = "✓" if result["valid"] else "⚠"
            score = result["score"]
            
            print(f"{status} 命令: {command}")
            print(f"   语法分数: {score:.2f}")
            
            if result["issues"]:
                print(f"   问题: {result['issues']}")
            
            if result["suggestions"]:
                print(f"   建议: {[s['message'] for s in result['suggestions']]}")
            
            if result["corrections"]:
                print(f"   纠正: {result['corrections']}")
            
            print()
        
        # 测试命令建议
        print("📝 命令建议演示:")
        suggestions = syntax_checker.get_suggestions("nma")
        for suggestion in suggestions[:3]:  # 只显示前3个
            print(f"   {suggestion['command']} - {suggestion['description']}")
        
        return syntax_checker
        
    except Exception as e:
        print(f"✗ 语法检查器演示失败: {e}")
        return None


def demo_command_executor(config_manager):
    """演示命令执行器"""
    print("\n⚡ 命令执行器演示")
    print("=" * 50)
    
    try:
        executor = CommandExecutor(config_manager)
        
        # 测试安全命令执行
        safe_commands = [
            "echo 'Hello from Kali SSE MCP'",
            "whoami",
            "pwd",
            "date",
        ]
        
        for command in safe_commands:
            print(f"🔄 执行: {command}")
            result = executor.execute(command, timeout=10)
            
            if result["success"]:
                print(f"✓ 成功 (返回码: {result['return_code']}, 耗时: {result['duration']:.2f}s)")
                if result["stdout"].strip():
                    print(f"   输出: {result['stdout'].strip()}")
            else:
                print(f"✗ 失败 (返回码: {result['return_code']})")
                if result["stderr"]:
                    print(f"   错误: {result['stderr']}")
            
            print()
        
        # 测试超时
        print("⏱️ 测试超时机制:")
        result = executor.execute("sleep 5", timeout=2)
        if not result["success"]:
            print("✓ 超时机制正常工作")
        
        # 显示系统统计
        stats = executor.get_system_stats()
        print(f"📊 系统统计: {stats}")
        
        return executor
        
    except Exception as e:
        print(f"✗ 命令执行器演示失败: {e}")
        return None


async def demo_mcp_server(config_manager):
    """演示MCP服务器"""
    print("\n🌐 MCP服务器演示")
    print("=" * 50)
    
    try:
        mcp_server = MCPServer(config_manager)
        
        # 测试工具列表
        tools_result = mcp_server._list_supported_tools()
        print(f"✓ 支持的工具数量: {tools_result['total_count']}")
        
        for tool in tools_result['tools'][:3]:  # 只显示前3个
            print(f"   - {tool['name']}: {tool['description']}")
        
        # 测试命令验证
        from src.protocols.mcp_server import CommandValidationRequest
        
        validation_request = CommandValidationRequest(
            command="nmap -sS 192.168.1.1",
            check_syntax=True,
            check_security=True
        )
        
        validation_result = mcp_server._validate_command(validation_request)
        print(f"✓ 命令验证: 有效={validation_result['valid']}, 安全分数={validation_result.get('security_score', 0):.2f}")
        
        # 测试命令建议
        from src.protocols.mcp_server import CommandSuggestionRequest
        
        suggestion_request = CommandSuggestionRequest(
            partial_command="nmap -s",
            context="network_scanning"
        )
        
        suggestion_result = mcp_server._get_command_suggestions(suggestion_request)
        if suggestion_result["success"]:
            print(f"✓ 命令建议数量: {len(suggestion_result['suggestions'])}")
        
        # 获取FastMCP应用
        app = mcp_server.get_mcp_app()
        print(f"✓ MCP应用已创建: {type(app).__name__}")
        
        return mcp_server
        
    except Exception as e:
        print(f"✗ MCP服务器演示失败: {e}")
        return None


async def demo_async_execution(config_manager):
    """演示异步执行"""
    print("\n🔄 异步执行演示")
    print("=" * 50)
    
    try:
        executor = CommandExecutor(config_manager)
        
        # 并发执行多个命令
        commands = [
            "echo 'Task 1'",
            "echo 'Task 2'", 
            "echo 'Task 3'",
        ]
        
        print("🚀 启动并发任务...")
        
        # 创建异步任务
        tasks = []
        for i, command in enumerate(commands):
            task = asyncio.create_task(
                executor.execute_async(command, task_id=f"async_task_{i}")
            )
            tasks.append(task)
        
        # 等待所有任务完成
        results = await asyncio.gather(*tasks)
        
        print("✓ 所有任务完成:")
        for i, result in enumerate(results):
            if result["success"]:
                print(f"   任务 {i+1}: {result['stdout'].strip()}")
            else:
                print(f"   任务 {i+1}: 失败")
        
    except Exception as e:
        print(f"✗ 异步执行演示失败: {e}")


def demo_integration_test():
    """演示集成测试"""
    print("\n🔗 集成测试演示")
    print("=" * 50)
    
    try:
        # 创建所有组件
        config_manager = ConfigManager()
        validator = CommandValidator(config_manager)
        syntax_checker = SyntaxChecker(config_manager)
        executor = CommandExecutor(config_manager)
        
        # 测试完整流程
        test_command = "echo 'Integration test successful'"
        
        print(f"🔍 测试命令: {test_command}")
        
        # 1. 安全验证
        security_result = validator.validate_command(test_command)
        print(f"1. 安全验证: {'✓' if security_result['valid'] else '✗'}")
        
        # 2. 语法检查
        syntax_result = syntax_checker.check_syntax(test_command)
        print(f"2. 语法检查: {'✓' if syntax_result['valid'] else '✗'}")
        
        # 3. 执行命令
        if security_result["valid"] and syntax_result["valid"]:
            exec_result = executor.execute(test_command)
            print(f"3. 命令执行: {'✓' if exec_result['success'] else '✗'}")
            
            if exec_result["success"]:
                print(f"   输出: {exec_result['stdout'].strip()}")
                print("🎉 集成测试通过!")
            else:
                print("❌ 命令执行失败")
        else:
            print("❌ 验证失败，跳过执行")
        
    except Exception as e:
        print(f"✗ 集成测试失败: {e}")


async def main():
    """主函数"""
    print_banner()
    
    print("🚀 开始 Kali SSE MCP 功能演示...")
    
    # 1. 配置管理器演示
    config_manager = demo_config_manager()
    if not config_manager:
        print("❌ 配置管理器初始化失败，退出演示")
        return
    
    # 2. 命令验证器演示
    validator = demo_command_validator(config_manager)
    
    # 3. 语法检查器演示
    syntax_checker = demo_syntax_checker(config_manager)
    
    # 4. 命令执行器演示
    executor = demo_command_executor(config_manager)
    
    # 5. MCP服务器演示
    mcp_server = await demo_mcp_server(config_manager)
    
    # 6. 异步执行演示
    await demo_async_execution(config_manager)
    
    # 7. 集成测试演示
    demo_integration_test()
    
    print("\n🎯 演示完成!")
    print("\n📚 下一步:")
    print("   1. 运行测试: python -m pytest tests/")
    print("   2. 启动服务器: python -m src serve")
    print("   3. 查看帮助: python -m src --help")
    print("   4. 阅读文档: docs/")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 演示被用户中断")
    except Exception as e:
        logger.error(f"演示程序异常: {e}")
        sys.exit(1)
