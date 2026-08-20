"""
全局日志模块（并发安全版）
提供统一的日志记录功能，支持多等级、彩色输出、时间戳、文件写入

用法:
    from app.utils.logger import logger

    logger.debug("TAG", "调试信息")
    logger.info("TAG", "常规信息")
    logger.warning("TAG", "警告信息")
    logger.error("TAG", "错误信息")

日志等级（由 LOG_LEVEL 环境变量控制，默认 info）：
    debug   — 开发调试，输出所有日志
    info    — 常规运行信息（默认）
    warning — 仅输出警告和错误
    error   — 仅输出错误

环境变量：
    LOG_LEVEL         — 日志等级: debug | info | warning | error（默认 info）
    LOG_DIR           — 日志文件目录（默认项目根目录下的 logs/）
    LOG_FILE_ENABLED  — 是否启用文件日志，设为 "false" 关闭（默认启用）
"""
import os
import sys
import threading
from datetime import datetime
from enum import IntEnum
from pathlib import Path


class LogLevel(IntEnum):
    """日志等级，数值越小越详细"""
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40


class Logger:
    """
    全局日志类（单例模式，线程安全）

    输出目标：
    - stderr 控制台（带颜色，实时刷出）
    - 日志文件（无颜色，按天轮转）

    特性：
    - 自动从 LOG_LEVEL 环境变量读取日志等级
    - 终端彩色输出（非 TTY 环境自动关闭）
    - 统一输出到 stderr（兼容 MCP stdio 协议）
    - 日志文件按天自动轮转（文件名含日期）
    - 日志目录自动创建
    - 时间戳精确到秒
    - 全链路并发安全（控制台输出原子化 + 文件操作全程持锁）
    """

    _instance = None
    _init_lock = threading.Lock()

    # ANSI 终端颜色码
    _COLORS = {
        LogLevel.DEBUG:   "\033[36m",   # 青色
        LogLevel.INFO:    "\033[32m",   # 绿色
        LogLevel.WARNING: "\033[33m",   # 黄色
        LogLevel.ERROR:   "\033[31m",   # 红色
    }
    _RESET = "\033[0m"

    _LEVEL_MAP = {
        "debug":    LogLevel.DEBUG,
        "info":     LogLevel.INFO,
        "warning":  LogLevel.WARNING,
        "error":    LogLevel.ERROR,
        # 兼容 uvicorn 风格的等级名称
        "trace":    LogLevel.DEBUG,
        "critical": LogLevel.ERROR,
    }

    # ---- 项目根目录（logger.py → utils → app → backend → 项目根） ----
    _PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

    def __new__(cls):
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # 使用独立锁保护初始化过程，防止多线程重复初始化
        with self._init_lock:
            if self._initialized:
                return

            self._level = self._parse_level(os.getenv("LOG_LEVEL", "info"))
            self._use_color = sys.stderr.isatty()

            # ---- 文件日志初始化 ----
            self._file_enabled = os.getenv("LOG_FILE_ENABLED", "false").lower() == "true"
            self._log_dir: Path | None = None
            self._current_date: str = ""
            self._file_handle = None
            # 文件操作专用锁：保护 _file_handle / _current_date / _open_log_file 的全链路
            self._file_lock = threading.Lock()

            if self._file_enabled:
                self._init_file_logging()

            self._initialized = True

    # ========== 公共接口 ==========

    def debug(self, tag: str, message: str):
        """调试日志 — 开发阶段使用，生产环境通常关闭"""
        self._log(LogLevel.DEBUG, tag, message)

    def info(self, tag: str, message: str):
        """信息日志 — 常规运行状态"""
        self._log(LogLevel.INFO, tag, message)

    def warning(self, tag: str, message: str):
        """警告日志 — 非致命问题，需关注"""
        self._log(LogLevel.WARNING, tag, message)

    def error(self, tag: str, message: str):
        """错误日志 — 需处理的错误情况"""
        self._log(LogLevel.ERROR, tag, message)

    # ========== 等级管理 ==========

    @property
    def level(self) -> LogLevel:
        return self._level

    def set_level(self, level_str: str):
        """运行时切换日志等级（支持热更新）"""
        self._level = self._parse_level(level_str)
        self.info("LOGGER", f"日志等级已切换为 {self._level.name}")

    # ========== 文件日志状态 ==========

    @property
    def file_enabled(self) -> bool:
        """文件日志是否已启用"""
        return self._file_enabled and self._file_handle is not None

    @property
    def log_file_path(self) -> str | None:
        """当前日志文件路径（未启用时返回 None）"""
        with self._file_lock:
            if self._file_handle:
                return self._file_handle.name
            return None

    # ========== 内部实现 ==========

    def _parse_level(self, level_str: str) -> LogLevel:
        """将字符串转换为 LogLevel，无法识别时默认 INFO"""
        return self._LEVEL_MAP.get(level_str.lower().strip(), LogLevel.INFO)

    def _init_file_logging(self):
        """初始化文件日志：确定目录并打开当天的日志文件"""
        log_dir_env = os.getenv("LOG_DIR", "")
        if log_dir_env:
            log_dir = Path(log_dir_env)
            if not log_dir.is_absolute():
                log_dir = self._PROJECT_ROOT / log_dir_env
        else:
            """兜底默认日志路径"""
            log_dir = self._PROJECT_ROOT / "logs"

        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            self._log_dir = log_dir
            self._open_log_file()
        except OSError as e:
            self._file_enabled = False
            self._log_dir = None
            # 文件日志初始化失败时，通过 stderr 报告（绕过 _log 避免递归）
            print(
                f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                f"[WARNING] [LOGGER] 日志目录创建失败 ({log_dir}): {e}，文件日志已禁用",
                file=sys.stderr, flush=True,
            )

    def _open_log_file(self):
        """
        打开当天日期的日志文件（如已打开且日期未变则跳过）
        ⚠️ 调用方必须已持有 self._file_lock
        """
        today = datetime.now().strftime("%Y-%m-%d")
        if self._file_handle and today == self._current_date:
            return  # 同一天，复用当前文件句柄

        # 关闭旧文件
        if self._file_handle:
            try:
                self._file_handle.close()
            except OSError:
                pass

        # 打开新文件，日志前缀名位置 "platform-"
        log_path = self._log_dir / f"platform-{today}.log"
        try:
            self._file_handle = open(str(log_path), "a", encoding="utf-8")
            self._current_date = today
        except OSError as e:
            self._file_enabled = False
            self._file_handle = None
            print(
                f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                f"[WARNING] [LOGGER] 日志文件打开失败 ({log_path}): {e}，文件日志已禁用",
                file=sys.stderr, flush=True,
            )

    def _log(self, level: LogLevel, tag: str, message: str):
        """核心输出方法：同时写入 stderr 和日志文件（并发安全）"""
        if level < self._level:
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        level_name = level.name

        # ---- stderr 控制台输出（原子写入，避免多线程行内交错） ----
        if self._use_color:
            color = self._COLORS.get(level, "")
            console_line = (
                f"{color}[{timestamp}] [{level_name:<7s}] [{tag}] "
                f"{message}{self._RESET}\n"
            )
        else:
            console_line = f"[{timestamp}] [{level_name:<7s}] [{tag}] {message}\n"

        # 单次 write + flush 保证整条日志不被其他线程打断
        try:
            sys.stderr.write(console_line)
            sys.stderr.flush()
        except OSError:
            pass  # stderr 不可写时静默降级

        # ---- 文件输出（无颜色，全链路持锁） ----
        if self._file_enabled:
            file_line = f"[{timestamp}] [{level_name:<7s}] [{tag}] {message}\n"
            with self._file_lock:
                if not self._file_enabled or self._file_handle is None:
                    return  # 可能在等待锁期间被其他线程降级
                try:
                    self._open_log_file()          # 跨天自动轮转（已在锁内）
                    self._file_handle.write(file_line)
                    self._file_handle.flush()
                except OSError:
                    # 写入失败时静默降级，不阻塞业务
                    pass


# ========== 全局单例 ==========
logger = Logger()