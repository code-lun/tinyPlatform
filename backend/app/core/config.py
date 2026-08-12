"""
全局配置模块 — 所有环境变量的唯一入口

优先级（由高到低）：
    1. Shell 环境变量（export / docker-compose environment）
    2. backend/.env 文件
    3. 本文件中的默认值

用法:
    from app.core.config import PORT, API_TOKEN, SCRIPTS_DIR, ...

新增配置项：在此文件添加一行 os.getenv("KEY", "default") 即可，
不需要在其他文件里重复调用 os.getenv()。
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# ============================================================
# 第一步：加载 .env 文件（只加载 backend 目录下的 .env）
# ============================================================

# 显式指定 .env 路径，不依赖工作目录
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_FILE)

# ============================================================
# 第二步：路径常量
# ============================================================

# 后端项目目录（config.py → core → app → backend）
BACKEND_DIR = _ENV_FILE.parent


def _resolve_scripts_dir(raw: str) -> Path:
    """将 SCRIPTS_DIR 配置项解析为绝对路径"""
    p = Path(raw)
    if p.is_absolute():
        return p.resolve()
    return (BACKEND_DIR / p).resolve()


# ============================================================
# 服务配置
# ============================================================

PORT = int(os.getenv("PORT", "8000"))

ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",")
]

# ============================================================
# 认证
# ============================================================

API_TOKEN = os.getenv("API_TOKEN", "tinyPlatform-token-2024")

# ============================================================
# 脚本执行
# ============================================================

SCRIPTS_DIR = _resolve_scripts_dir(os.getenv("SCRIPTS_DIR", "../scripts"))
SCRIPT_TIMEOUT = int(os.getenv("SCRIPT_TIMEOUT", "30"))

# ============================================================
# 日志
# ============================================================

LOG_LEVEL = os.getenv("LOG_LEVEL", "info")
LOG_DIR = os.getenv("LOG_DIR", "log_new/")
"""默认关闭日志写文件"""
LOG_FILE_ENABLED = os.getenv("LOG_FILE_ENABLED", "false").lower() == "true"
