"""
Kali SSE MCP 主入口点

提供命令行接口启动 MCP 服务器。
"""

import asyncio
import logging
import sys
import signal
from pathlib import Path
import uvicorn
import click

from .core.config_manager import ConfigManager
from .protocols.mcp_server import MCPServer

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class KaliSSEServer:
    """Kali SSE MCP 服务器"""
    
    def __init__(self, config_path: str = None):
        """
        初始化服务器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_manager = ConfigManager(config_path)
        self.mcp_server = MCPServer(self.config_manager)
        self.running = False
    
    async def start(self):
        """启动服务器"""
        try:
            logger.info("正在启动 Kali SSE MCP 服务器...")
            
            # 获取配置
            server_config = self.config_manager.get_server_config()
            
            # 创建 FastAPI 应用
            app = self.mcp_server.get_app()
            
            # 配置 uvicorn
            config = uvicorn.Config(
                app,
                host=server_config.host,
                port=server_config.port,
                log_level="info" if not server_config.debug else "debug",
                reload=server_config.reload,
                workers=1,  # MCP 服务器通常使用单进程
            )
            
            # 启动服务器
            server = uvicorn.Server(config)
            
            # 设置信号处理
            self._setup_signal_handlers(server)
            
            self.running = True
            logger.info(f"服务器已启动: http://{server_config.host}:{server_config.port}")
            
            await server.serve()
            
        except Exception as e:
            logger.error(f"服务器启动失败: {e}")
            raise
    
    def _setup_signal_handlers(self, server):
        """设置信号处理器"""
        def signal_handler(signum, frame):
            logger.info(f"收到信号 {signum}，正在关闭服务器...")
            self.running = False
            asyncio.create_task(server.shutdown())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def stop(self):
        """停止服务器"""
        logger.info("正在停止服务器...")
        self.running = False


@click.group()
@click.option('--config', '-c', help='配置文件路径')
@click.option('--debug', '-d', is_flag=True, help='启用调试模式')
@click.pass_context
def cli(ctx, config, debug):
    """Kali SSE MCP 命令行工具"""
    ctx.ensure_object(dict)
    ctx.obj['config'] = config
    ctx.obj['debug'] = debug
    
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
@click.option('--host', '-h', default='0.0.0.0', help='服务器主机地址')
@click.option('--port', '-p', default=8000, help='服务器端口')
@click.option('--reload', is_flag=True, help='启用自动重载')
@click.pass_context
def serve(ctx, host, port, reload):
    """启动 MCP 服务器"""
    config_path = ctx.obj.get('config')
    
    try:
        # 创建服务器实例
        server = KaliSSEServer(config_path)
        
        # 如果指定了命令行参数，覆盖配置
        if host != '0.0.0.0':
            server.config_manager.set('server.host', host)
        if port != 8000:
            server.config_manager.set('server.port', port)
        if reload:
            server.config_manager.set('server.reload', True)
        
        # 启动服务器
        asyncio.run(server.start())
        
    except KeyboardInterrupt:
        logger.info("服务器已停止")
    except Exception as e:
        logger.error(f"服务器运行失败: {e}")
        sys.exit(1)


@cli.command()
@click.argument('command')
@click.option('--timeout', '-t', default=300, help='超时时间（秒）')
@click.option('--async', 'async_exec', is_flag=True, help='异步执行')
@click.pass_context
def execute(ctx, command, timeout, async_exec):
    """执行单个命令（用于测试）"""
    config_path = ctx.obj.get('config')
    
    try:
        # 创建配置管理器和执行器
        config_manager = ConfigManager(config_path)
        from .core.executor import CommandExecutor
        from .security.command_validator import CommandValidator
        
        executor = CommandExecutor(config_manager)
        validator = CommandValidator(config_manager)
        
        # 验证命令
        validation_result = validator.validate_command(command)
        if not validation_result["valid"]:
            click.echo(f"命令验证失败: {validation_result['issues']}")
            sys.exit(1)
        
        # 执行命令
        click.echo(f"执行命令: {command}")
        
        if async_exec:
            result = asyncio.run(executor.execute_async(command, timeout=timeout))
        else:
            result = executor.execute(command, timeout=timeout)
        
        # 显示结果
        click.echo(f"执行结果:")
        click.echo(f"  成功: {result['success']}")
        click.echo(f"  返回码: {result['return_code']}")
        click.echo(f"  执行时间: {result['duration']:.2f}秒")
        
        if result['stdout']:
            click.echo(f"标准输出:\n{result['stdout']}")
        
        if result['stderr']:
            click.echo(f"标准错误:\n{result['stderr']}")
        
    except Exception as e:
        logger.error(f"命令执行失败: {e}")
        sys.exit(1)


@cli.command()
@click.argument('command')
@click.pass_context
def validate(ctx, command):
    """验证命令语法和安全性"""
    config_path = ctx.obj.get('config')
    
    try:
        # 创建验证器
        config_manager = ConfigManager(config_path)
        from .security.command_validator import CommandValidator
        from .intelligence.syntax_checker import SyntaxChecker
        
        validator = CommandValidator(config_manager)
        syntax_checker = SyntaxChecker(config_manager)
        
        # 安全验证
        security_result = validator.validate_command(command)
        click.echo(f"安全验证:")
        click.echo(f"  有效: {security_result['valid']}")
        click.echo(f"  分数: {security_result['score']:.2f}")
        
        if security_result['issues']:
            click.echo(f"  问题: {security_result['issues']}")
        
        # 语法检查
        syntax_result = syntax_checker.check_syntax(command)
        click.echo(f"语法检查:")
        click.echo(f"  有效: {syntax_result['valid']}")
        click.echo(f"  分数: {syntax_result['score']:.2f}")
        
        if syntax_result['issues']:
            click.echo(f"  问题: {syntax_result['issues']}")
        
        if syntax_result['suggestions']:
            click.echo(f"  建议: {syntax_result['suggestions']}")
        
    except Exception as e:
        logger.error(f"验证失败: {e}")
        sys.exit(1)


@cli.command()
@click.pass_context
def config_check(ctx):
    """检查配置文件"""
    config_path = ctx.obj.get('config')
    
    try:
        config_manager = ConfigManager(config_path)
        config = config_manager.get_config()
        
        click.echo("配置检查:")
        click.echo(f"  服务器: {config.server.host}:{config.server.port}")
        click.echo(f"  调试模式: {config.server.debug}")
        click.echo(f"  安全验证: {config.security.command_validation_enabled}")
        click.echo(f"  智能化功能: {config.intelligence.enabled}")
        
        # 验证工具配置
        validator = CommandValidator(config_manager)
        tools = validator.get_allowed_tools()
        click.echo(f"  支持的工具: {', '.join(tools)}")
        
        click.echo("配置有效 ✓")
        
    except Exception as e:
        logger.error(f"配置检查失败: {e}")
        sys.exit(1)


@cli.command()
def version():
    """显示版本信息"""
    from . import __version__, __author__, __description__
    
    click.echo(f"Kali SSE MCP v{__version__}")
    click.echo(f"作者: {__author__}")
    click.echo(f"描述: {__description__}")


def main():
    """主入口点"""
    try:
        cli()
    except Exception as e:
        logger.error(f"程序异常: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
