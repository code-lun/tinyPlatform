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


def _int_env(key: str, default: int) -> int:
    """安全读取整型环境变量，非法值或空值回退默认"""
    raw = os.getenv(key, "")
    if raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


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
# 并发执行器配置
# ============================================================

# 线程池大小，默认使用 Python 3.8+ ThreadPoolExecutor 官方公式：
# min(32, cpu_count + 4)，适合 I/O 密集型任务且避免高核机器线程过多
EXECUTOR_MAX_WORKERS: int = _int_env(
    "EXECUTOR_MAX_WORKERS",
    min(32, (os.cpu_count() or 1) + 4),
)

# 等待队列容量（背压控制）
EXECUTOR_QUEUE_SIZE: int = _int_env("EXECUTOR_QUEUE_SIZE", 50)

# 脚本默认执行超时复用 SCRIPT_TIMEOUT（见上方「脚本执行」段），不再单独配置

# 队列/信号量等待超时（秒），获取不到槽位时多久后返回 429
EXECUTOR_QUEUE_WAIT_TIMEOUT: int = _int_env("EXECUTOR_QUEUE_WAIT_TIMEOUT", 5)

# 每脚本最大并发数，0 表示不限制
EXECUTOR_MAX_CONCURRENT_SCRIPTS: int = _int_env("EXECUTOR_MAX_CONCURRENT_SCRIPTS", 0)

# 异步任务结果保留时间（秒），超过后由后台清理线程回收
EXECUTOR_RESULT_TTL: int = _int_env("EXECUTOR_RESULT_TTL", 300)

# ============================================================
# 日志
# ============================================================

LOG_LEVEL = os.getenv("LOG_LEVEL", "info")
LOG_DIR = os.getenv("LOG_DIR", "log_new/")
"""默认关闭日志写文件"""
LOG_FILE_ENABLED = os.getenv("LOG_FILE_ENABLED", "false").lower() == "true"