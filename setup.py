#!/usr/bin/env python3
"""
Kali SSE MCP 命令执行器安装脚本
"""

from setuptools import setup, find_packages
import os
import sys

# 确保Python版本兼容性
if sys.version_info < (3, 8):
    raise RuntimeError("Kali SSE MCP requires Python 3.8 or higher")

# 读取README文件
def read_readme():
    """读取README文件内容"""
    readme_path = os.path.join(os.path.dirname(__file__), "README.md")
    if os.path.exists(readme_path):
        with open(readme_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""

# 读取requirements文件
def read_requirements():
    """读取requirements.txt文件"""
    requirements_path = os.path.join(os.path.dirname(__file__), "requirements.txt")
    requirements = []
    
    if os.path.exists(requirements_path):
        with open(requirements_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # 跳过注释和空行
                if line and not line.startswith("#"):
                    # 只保留第三方包，跳过标准库模块
                    if ">=" in line or "==" in line or "~=" in line:
                        requirements.append(line)
    
    return requirements

# 项目元数据
PACKAGE_NAME = "kali_sse_mcp"
VERSION = "1.0.0"
DESCRIPTION = "符合MCP规范的智能化Kali Linux命令执行器"
LONG_DESCRIPTION = read_readme()
AUTHOR = "Kali SSE MCP Team"
AUTHOR_EMAIL = "team@kali-sse-mcp.com"
URL = "https://github.com/kali-sse-mcp/kali-sse-mcp"
LICENSE = "MIT"

# 分类信息
CLASSIFIERS = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Information Technology",
    "Intended Audience :: System Administrators",
    "License :: OSI Approved :: MIT License",
    "Operating System :: POSIX :: Linux",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Security",
    "Topic :: System :: Systems Administration",
    "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
    "Topic :: Software Development :: Libraries :: Python Modules",
    "Environment :: Console",
    "Environment :: Web Environment",
]

# 关键词
KEYWORDS = [
    "mcp", "model-context-protocol", "kali-linux", "penetration-testing",
    "security-tools", "command-execution", "sse", "server-sent-events",
    "cybersecurity", "vulnerability-assessment", "network-scanning",
    "web-security", "automation", "intelligent-security"
]

# 项目URLs
PROJECT_URLS = {
    "Bug Reports": f"{URL}/issues",
    "Source": URL,
    "Documentation": f"{URL}/docs",
    "Changelog": f"{URL}/blob/main/CHANGELOG.md",
}

# 入口点
ENTRY_POINTS = {
    "console_scripts": [
        "kali-sse-mcp=kali_sse_mcp.cli:main",
        "kali-sse-server=kali_sse_mcp.server:main",
        "kali-sse-client=kali_sse_mcp.client:main",
    ],
    "mcp.servers": [
        "kali_sse=kali_sse_mcp.protocols.mcp_server:create_server",
    ],
}

# 额外的安装要求
EXTRAS_REQUIRE = {
    "dev": [
        "pytest>=7.4.3",
        "pytest-asyncio>=0.21.1",
        "pytest-cov>=4.1.0",
        "pytest-mock>=3.12.0",
        "black>=23.11.0",
        "isort>=5.12.0",
        "flake8>=6.1.0",
        "mypy>=1.7.0",
        "pre-commit>=3.6.0",
        "sphinx>=7.2.6",
        "sphinx-rtd-theme>=1.3.0",
    ],
    "monitoring": [
        "prometheus-client>=0.19.0",
        "grafana-api>=1.0.3",
        "elasticsearch>=8.11.0",
    ],
    "ml": [
        "tensorflow>=2.15.0",
        "torch>=2.1.0",
        "transformers>=4.36.0",
        "scikit-learn>=1.3.2",
    ],
    "geo": [
        "geoip2>=4.7.0",
        "maxminddb>=2.2.0",
        "folium>=0.15.0",
    ],
    "reporting": [
        "reportlab>=4.0.7",
        "weasyprint>=60.2",
        "jinja2>=3.1.2",
        "matplotlib>=3.8.2",
        "plotly>=5.17.0",
    ],
}

# 所有额外依赖
EXTRAS_REQUIRE["all"] = list(set(
    dep for deps in EXTRAS_REQUIRE.values() for dep in deps
))

# 包数据
PACKAGE_DATA = {
    "kali_sse_mcp": [
        "config/*.json",
        "config/*.yaml",
        "templates/*.html",
        "templates/*.jinja2",
        "static/css/*.css",
        "static/js/*.js",
        "static/images/*",
        "docs/*.md",
        "schemas/*.json",
    ]
}

# 数据文件
DATA_FILES = [
    ("etc/kali_sse_mcp", ["config/config.example.json"]),
    ("share/doc/kali_sse_mcp", ["README.md", "LICENSE"]),
    ("share/man/man1", ["docs/kali-sse-mcp.1"]),
]

# Python要求
PYTHON_REQUIRES = ">=3.8"

# 安装要求
INSTALL_REQUIRES = read_requirements()

# Zip安全
ZIP_SAFE = False

# 包含包数据
INCLUDE_PACKAGE_DATA = True

# 命名空间包
NAMESPACE_PACKAGES = []

# 测试套件
TEST_SUITE = "tests"

# 测试要求
TESTS_REQUIRE = [
    "pytest>=7.4.3",
    "pytest-asyncio>=0.21.1",
    "pytest-cov>=4.1.0",
    "pytest-mock>=3.12.0",
    "httpx>=0.25.2",
]

# 设置配置
setup(
    name=PACKAGE_NAME,
    version=VERSION,
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    author=AUTHOR,
    author_email=AUTHOR_EMAIL,
    url=URL,
    project_urls=PROJECT_URLS,
    license=LICENSE,
    classifiers=CLASSIFIERS,
    keywords=" ".join(KEYWORDS),
    
    # 包配置
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    package_data=PACKAGE_DATA,
    data_files=DATA_FILES,
    include_package_data=INCLUDE_PACKAGE_DATA,
    zip_safe=ZIP_SAFE,
    namespace_packages=NAMESPACE_PACKAGES,
    
    # 依赖配置
    python_requires=PYTHON_REQUIRES,
    install_requires=INSTALL_REQUIRES,
    extras_require=EXTRAS_REQUIRE,
    tests_require=TESTS_REQUIRE,
    test_suite=TEST_SUITE,
    
    # 入口点
    entry_points=ENTRY_POINTS,
    
    # 元数据
    platforms=["Linux"],
    maintainer=AUTHOR,
    maintainer_email=AUTHOR_EMAIL,
    download_url=f"{URL}/archive/v{VERSION}.tar.gz",
    
    # 构建配置
    cmdclass={},
    distclass=None,
    script_name=None,
    script_args=None,
    options={},
    
    # 其他配置
    obsoletes=[],
    provides=[PACKAGE_NAME],
    requires=[],
)

# 安装后检查
def post_install_check():
    """安装后检查"""
    try:
        import kali_sse_mcp
        print(f"✓ Kali SSE MCP {VERSION} 安装成功!")
        print(f"✓ 版本: {kali_sse_mcp.__version__}")
        print("✓ 使用 'kali-sse-mcp --help' 查看帮助信息")
    except ImportError as e:
        print(f"✗ 安装验证失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # 如果直接运行此脚本，执行安装后检查
    if len(sys.argv) > 1 and sys.argv[1] == "install":
        import atexit
        atexit.register(post_install_check)
