"""
MCP 服务配置模块 — 所有环境变量的唯一入口

优先级（由高到低）：
    1. Shell 环境变量（export / docker-compose environment）
    2. mcp/.env 文件
    3. 本文件中的默认值

用法:
    from config import BACKEND_API_URL, API_TOKEN, MCP_TRANSPORT, ...

新增配置项：在此文件添加一行 os.getenv("KEY", "default") 即可，
不需要在其他文件里重复调用 os.getenv()。
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# ============================================================
# 第一步：加载 .env 文件（只加载 mcp 目录下的 .env）
# ============================================================

# 显式指定 .env 路径，不依赖工作目录
_ENV_FILE = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_ENV_FILE)

# ============================================================
# 第二步：路径常量
# ============================================================

# MCP 服务目录（config.py 所在的 mcp/ 目录）
MCP_DIR = Path(__file__).resolve().parent

# ============================================================
# 后端连接
# ============================================================

BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "30.0"))
API_TOKEN = os.getenv("API_TOKEN", "")

# ============================================================
# 传输模式
# ============================================================

MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "stdio")  # "stdio" | "http"
MCP_HTTP_PORT = int(os.getenv("MCP_HTTP_PORT", "8080"))

# ============================================================
# 日志
# ============================================================

LOG_LEVEL = os.getenv("LOG_LEVEL", "info")
LOG_DIR = os.getenv("LOG_DIR", "log_new/")
"""默认关闭日志写文件"""
LOG_FILE_ENABLED = os.getenv("LOG_FILE_ENABLED", "false").lower() == "true"