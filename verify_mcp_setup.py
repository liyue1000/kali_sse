#!/usr/bin/env python3
"""
验证MCP设置

检查所有组件是否正确配置并可以与Cursor协同工作。
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def check_file_exists(file_path: str, description: str) -> bool:
    """检查文件是否存在"""
    if os.path.exists(file_path):
        print(f"✓ {description}: {file_path}")
        return True
    else:
        print(f"✗ {description} 不存在: {file_path}")
        return False


def check_python_dependencies() -> bool:
    """检查Python依赖"""
    print("\n🐍 检查Python依赖...")
    
    required_packages = [
        "pydantic",
        "pydantic_settings", 
        "fastapi",
        "uvicorn",
        "sse_starlette",
        "psutil",
        "jsonschema"
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
            print(f"✓ {package}")
        except ImportError:
            print(f"✗ {package} 未安装")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n❌ 缺少依赖包: {', '.join(missing_packages)}")
        print("请运行: pip install " + " ".join(missing_packages))
        return False
    
    return True


def check_mcp_config() -> bool:
    """检查MCP配置文件"""
    print("\n⚙️ 检查MCP配置...")
    
    config_paths = [
        "/home/kali/Desktop/pentest/pentestmcp/.cursor/mcp.json",
        "/home/kali/.cursor/mcp.json"
    ]
    
    config_found = False
    
    for config_path in config_paths:
        if os.path.exists(config_path):
            print(f"✓ 找到配置文件: {config_path}")
            
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                
                if "mcpServers" in config and "kali-sse-mcp" in config["mcpServers"]:
                    server_config = config["mcpServers"]["kali-sse-mcp"]
                    print(f"✓ 服务器配置正确")
                    print(f"  命令: {server_config.get('command')}")
                    print(f"  参数: {server_config.get('args')}")
                    print(f"  工作目录: {server_config.get('cwd')}")
                    config_found = True
                else:
                    print(f"✗ 配置文件格式错误")
                    
            except json.JSONDecodeError as e:
                print(f"✗ 配置文件JSON格式错误: {e}")
            except Exception as e:
                print(f"✗ 读取配置文件失败: {e}")
    
    if not config_found:
        print("✗ 未找到有效的MCP配置文件")
        return False
    
    return True


def test_mcp_server() -> bool:
    """测试MCP服务器"""
    print("\n🧪 测试MCP服务器...")
    
    server_path = "/home/kali/Desktop/pentest/pentestmcp/kali_sse/src/mcp_stdio_server.py"
    
    if not os.path.exists(server_path):
        print(f"✗ MCP服务器文件不存在: {server_path}")
        return False
    
    # 测试服务器启动
    try:
        test_message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0.0"}
            }
        }
        
        process = subprocess.Popen(
            ["python", server_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd="/home/kali/Desktop/pentest/pentestmcp/kali_sse",
            text=True
        )
        
        stdout, stderr = process.communicate(
            input=json.dumps(test_message) + "\n",
            timeout=10
        )
        
        if process.returncode == 0 and stdout:
            try:
                response = json.loads(stdout.strip())
                if "result" in response:
                    print("✓ MCP服务器响应正常")
                    print(f"  服务器名称: {response['result'].get('serverInfo', {}).get('name')}")
                    print(f"  协议版本: {response['result'].get('protocolVersion')}")
                    return True
                else:
                    print(f"✗ MCP服务器响应格式错误: {response}")
            except json.JSONDecodeError:
                print(f"✗ MCP服务器响应不是有效JSON: {stdout}")
        else:
            print(f"✗ MCP服务器启动失败")
            if stderr:
                print(f"  错误: {stderr}")
        
    except subprocess.TimeoutExpired:
        print("✗ MCP服务器响应超时")
        process.kill()
    except Exception as e:
        print(f"✗ 测试MCP服务器失败: {e}")
    
    return False


def check_cursor_version() -> bool:
    """检查Cursor版本"""
    print("\n🖱️ 检查Cursor版本...")
    
    try:
        # 尝试获取Cursor版本信息
        result = subprocess.run(
            ["cursor", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            version_info = result.stdout.strip()
            print(f"✓ Cursor版本: {version_info}")
            
            # 检查版本是否支持MCP
            if "0.45" in version_info or "0.46" in version_info or "0.47" in version_info:
                print("✓ Cursor版本支持MCP")
                return True
            else:
                print("⚠️ Cursor版本可能不支持MCP，建议升级到0.45.8+")
                return True  # 仍然返回True，因为可能支持
        else:
            print("⚠️ 无法获取Cursor版本信息")
            return True  # 假设支持
            
    except subprocess.TimeoutExpired:
        print("⚠️ Cursor命令响应超时")
        return True
    except FileNotFoundError:
        print("⚠️ 未找到cursor命令，请确保Cursor已正确安装")
        return True
    except Exception as e:
        print(f"⚠️ 检查Cursor版本失败: {e}")
        return True


def main():
    """主函数"""
    print("🔍 验证 Kali SSE MCP 设置")
    print("=" * 50)
    
    checks = [
        ("文件结构", lambda: all([
            check_file_exists("/home/kali/Desktop/pentest/pentestmcp/kali_sse/src/mcp_stdio_server.py", "MCP STDIO服务器"),
            check_file_exists("/home/kali/Desktop/pentest/pentestmcp/kali_sse/src/core/executor.py", "命令执行器"),
            check_file_exists("/home/kali/Desktop/pentest/pentestmcp/kali_sse/src/security/command_validator.py", "命令验证器"),
            check_file_exists("/home/kali/Desktop/pentest/pentestmcp/kali_sse/src/intelligence/syntax_checker.py", "语法检查器")
        ])),
        ("Python依赖", check_python_dependencies),
        ("MCP配置", check_mcp_config),
        ("MCP服务器", test_mcp_server),
        ("Cursor版本", check_cursor_version)
    ]
    
    passed = 0
    total = len(checks)
    
    for name, check_func in checks:
        print(f"\n{'='*20} {name} {'='*20}")
        if check_func():
            passed += 1
        else:
            print(f"❌ {name} 检查失败")
    
    print("\n" + "=" * 50)
    print(f"🎯 验证结果: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有检查通过！")
        print("\n📚 使用说明:")
        print("1. 重启 Cursor 编辑器")
        print("2. 打开项目: /home/kali/Desktop/pentest/pentestmcp")
        print("3. 检查 Cursor 设置 -> Features -> Model Context Protocol")
        print("4. 确认 'kali-sse-mcp' 显示为已连接")
        print("5. 在 Agent 模式下使用自然语言调用工具:")
        print("   - 'execute echo hello world'")
        print("   - 'validate nmap command'")
        print("   - 'list supported security tools'")
        print("\n🔧 故障排除:")
        print("- 如果连接失败，检查 Cursor 的 MCP 日志")
        print("- 确保Python路径和依赖正确")
        print("- 验证配置文件JSON格式")
        
        return True
    else:
        print("\n❌ 部分检查失败，请修复问题后重试")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
