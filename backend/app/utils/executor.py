"""
并发脚本执行器
基于 ThreadPoolExecutor + Semaphore 实现，保持与原 ScriptExecutor 兼容的接口
"""
import json
import os
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

from app.utils.logger import logger


# ==================== 配置 ====================

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class TaskResult:
    task_id: str
    script_name: str
    status: TaskStatus
    result: Dict[str, Any]
    submitted_at: float
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


@dataclass
class ExecutorConfig:
    """
    并发执行器配置

    推荐配置：
        2核 Pod: max_workers=4, queue_size=50
        4核 Pod: max_workers=8, queue_size=100
    """
    max_workers: int = 4
    queue_size: int = 50
    default_timeout: int = 60
    max_concurrent_scripts: Optional[int] = None
    result_ttl: int = 300

    @classmethod
    def for_2core(cls) -> "ExecutorConfig":
        """2核 Pod 推荐配置"""
        return cls(max_workers=4, queue_size=50, default_timeout=60)

    @classmethod
    def for_4core(cls) -> "ExecutorConfig":
        """4核 Pod 推荐配置"""
        return cls(max_workers=8, queue_size=100, default_timeout=60)


# ==================== 自定义异常 ====================

class QueueFullError(Exception):
    """任务队列已满时抛出"""
    pass


# ==================== 核心执行器 ====================

class ConcurrentScriptExecutor:
    """
    并发脚本执行器

    提供两种调用模式：
    1. execute()  - 同步调用，阻塞等待结果（兼容原接口）
    2. submit()   - 异步调用，返回 task_id，通过 get_result() 查询

    特性：
    - 线程池复用，避免频繁创建线程
    - 有界队列，防止内存溢出
    - 每脚本并发限制，防止单个脚本占满线程池
    - 优雅关闭，等待正在执行的任务完成
    """

    def __init__(
        self,
        scripts_dir: Optional[str] = None,
        config: Optional[ExecutorConfig] = None,
    ):
        self.config = config or ExecutorConfig()
        self._scripts_dir = scripts_dir

        # ---- 线程池 ----
        self._pool = ThreadPoolExecutor(
            max_workers=self.config.max_workers,
            thread_name_prefix="script-worker",
        )

        # ---- 有界任务队列（用于背压控制）----
        self._semaphore = threading.BoundedSemaphore(
            self.config.queue_size + self.config.max_workers
        )

        # ---- 每脚本并发限制 ----
        self._script_semaphores: Dict[str, threading.BoundedSemaphore] = {}
        self._script_semaphores_lock = threading.Lock()

        # ---- 异步任务管理 ----
        self._tasks: Dict[str, Any] = {}
        self._results: Dict[str, TaskResult] = {}
        self._tasks_lock = threading.Lock()

        # ---- 清理线程停止标志 ----
        self._stop_event = threading.Event()

        # ---- 原始执行器（核心逻辑复用）----
        self._executor = _CoreExecutor(
            scripts_dir=scripts_dir,
            timeout=self.config.default_timeout,
        )

        # ---- 结果清理线程 ----
        self._cleanup_thread = threading.Thread(
            target=self._result_cleanup_loop,
            daemon=True,
            name="result-cleanup",
        )
        self._cleanup_thread.start()

        logger.info(
            "CONCURRENT_EXEC",
            f"并发执行器启动: workers={self.config.max_workers}, "
            f"queue_size={self.config.queue_size}",
        )

    # ==================== 同步接口（兼容原 API）====================

    def execute(
        self,
        script_name: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        同步执行（阻塞等待结果），与原始 ScriptExecutor.execute() 接口兼容。
        内部通过线程池执行，具有并发控制和队列管理。
        """
        if not self._semaphore.acquire(timeout=5):
            return self._executor._error_response(
                code=429,
                message="系统繁忙：任务队列已满，请稍后重试",
                elapsed=0,
            )

        try:
            future = self._pool.submit(
                self._run_with_script_semaphore,
                script_name, params, timeout,
            )
            # 阻塞等待，但加一个安全上限防止死锁
            effective_timeout = timeout or self.config.default_timeout
            result = future.result(timeout=effective_timeout + 10)
            return result
        except Exception as e:
            return self._executor._error_response(
                code=500,
                message=f"并发执行异常: {str(e)}",
                elapsed=0,
            )
        finally:
            self._semaphore.release()

    # ==================== 异步接口 ====================

    def submit(
        self,
        script_name: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> str:
        """
        异步提交任务，立即返回 task_id。
        通过 get_result(task_id) 查询结果。

        Raises:
            QueueFullError: 队列已满
        """
        task_id = str(uuid.uuid4())[:12]

        if not self._semaphore.acquire(blocking=False):
            raise QueueFullError("任务队列已满，请稍后重试")

        submitted_at = time.time()
        future = self._pool.submit(
            self._async_run,
            task_id, script_name, params, timeout,
        )

        with self._tasks_lock:
            self._tasks[task_id] = future
            self._results[task_id] = TaskResult(
                task_id=task_id,
                script_name=script_name,
                status=TaskStatus.PENDING,
                result={},
                submitted_at=submitted_at,
            )

        return task_id

    def get_result(
        self,
        task_id: str,
        block: bool = False,
        timeout: Optional[float] = None,
    ) -> Optional[TaskResult]:
        """
        查询异步任务结果

        Args:
            task_id: 任务ID
            block:   是否阻塞等待
            timeout: 阻塞超时（秒）

        Returns:
            TaskResult 或 None（任务不存在）
        """
        with self._tasks_lock:
            future = self._tasks.get(task_id)
            if future is None:
                return None

        if block:
            try:
                future.result(timeout=timeout)
            except Exception:
                pass

        with self._tasks_lock:
            return self._results.get(task_id)

    # ==================== 内部执行逻辑 ====================

    def _run_with_script_semaphore(
        self,
        script_name: str,
        params: Optional[Dict[str, Any]],
        timeout: Optional[int],
    ) -> Dict[str, Any]:
        """带每脚本并发限制的同步执行"""
        sem = self._get_script_semaphore(script_name)
        if sem is not None and not sem.acquire(timeout=5):
            return self._executor._error_response(
                code=429,
                message=f"脚本 {script_name} 并发数已达上限",
                elapsed=0,
            )
        try:
            return self._executor.execute(script_name, params, timeout)
        finally:
            if sem is not None:
                sem.release()

    def _async_run(
        self,
        task_id: str,
        script_name: str,
        params: Optional[Dict[str, Any]],
        timeout: Optional[int],
    ):
        """异步任务的实际执行体"""
        with self._tasks_lock:
            self._results[task_id].status = TaskStatus.RUNNING
            self._results[task_id].started_at = time.time()

        sem = self._get_script_semaphore(script_name)
        acquired = sem is not None and sem.acquire(timeout=5)

        try:
            if sem is not None and not acquired:
                result = self._executor._error_response(
                    code=429,
                    message=f"脚本 {script_name} 并发数已达上限",
                    elapsed=0,
                )
                status = TaskStatus.ERROR
            else:
                result = self._executor.execute(script_name, params, timeout)
                status = (
                    TaskStatus.SUCCESS
                    if result.get("status") == "success"
                    else TaskStatus.ERROR
                )

            with self._tasks_lock:
                self._results[task_id].status = status
                self._results[task_id].result = result
                self._results[task_id].completed_at = time.time()

        finally:
            if sem is not None and acquired:
                sem.release()
            self._semaphore.release()

    # ==================== 工具方法 ====================

    def _get_script_semaphore(
        self, script_name: str
    ) -> Optional[threading.BoundedSemaphore]:
        """
        获取每脚本并发限制信号量（懒创建）。
        若 max_concurrent_scripts 为 None，返回 None 表示不限制。
        """
        if self.config.max_concurrent_scripts is None:
            return None

        with self._script_semaphores_lock:
            if script_name not in self._script_semaphores:
                self._script_semaphores[script_name] = threading.BoundedSemaphore(
                    self.config.max_concurrent_scripts
                )
            return self._script_semaphores[script_name]

    def _result_cleanup_loop(self):
        """后台线程：定期清理过期的异步任务结果"""
        while not self._stop_event.is_set():
            # 使用 wait 替代 sleep，可被 stop_event 立即中断
            if self._stop_event.wait(timeout=30):
                break

            now = time.time()
            with self._tasks_lock:
                expired = [
                    tid for tid, tr in self._results.items()
                    if tr.completed_at and (now - tr.completed_at) > self.config.result_ttl
                ]
                for tid in expired:
                    self._tasks.pop(tid, None)
                    self._results.pop(tid, None)
                if expired:
                    logger.info("CLEANUP", f"清理了 {len(expired)} 个过期任务结果")

    # ==================== 状态查询 ====================

    def get_stats(self) -> Dict[str, Any]:
        """获取执行器运行状态"""
        with self._tasks_lock:
            pending = sum(
                1 for r in self._results.values()
                if r.status == TaskStatus.PENDING
            )
            running = sum(
                1 for r in self._results.values()
                if r.status == TaskStatus.RUNNING
            )
            completed = sum(
                1 for r in self._results.values()
                if r.status in (TaskStatus.SUCCESS, TaskStatus.ERROR)
            )

        # 安全访问工作队列大小（不同 Python 版本内部实现可能不同）
        try:
            queue_size = self._pool._work_queue.qsize()
        except AttributeError:
            queue_size = -1  # 不可用时标记为 -1

        return {
            "max_workers": self.config.max_workers,
            "queue_size": self.config.queue_size,
            "active_threads": queue_size,
            "pending_tasks": pending,
            "running_tasks": running,
            "completed_tasks": completed,
        }

    # ==================== 生命周期 ====================

    def shutdown(self, wait: bool = True, timeout: float = 30):
        """优雅关闭：停止清理线程 → 关闭线程池"""
        logger.info("CONCURRENT_EXEC", "正在关闭并发执行器...")
        # 1. 通知清理线程退出
        self._stop_event.set()
        # 2. 关闭线程池
        self._pool.shutdown(wait=wait)
        logger.info("CONCURRENT_EXEC", "并发执行器已关闭")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.shutdown()


# ==================== 原始执行器（提取为核心）====================

class _CoreExecutor:
    """
    核心执行逻辑（从原 ScriptExecutor 提取）
    保持不变，仅负责单次脚本执行
    """

    def __init__(
        self,
        scripts_dir: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        from app.core.config import SCRIPTS_DIR as DEFAULT_SCRIPTS_DIR, SCRIPT_TIMEOUT

        if scripts_dir is None:
            scripts_dir = str(DEFAULT_SCRIPTS_DIR)
        if timeout is None:
            timeout = SCRIPT_TIMEOUT

        scripts_path = Path(scripts_dir)
        if not scripts_path.is_absolute():
            backend_dir = Path(__file__).parent.parent.parent
            scripts_path = backend_dir / scripts_path
        self.scripts_dir = scripts_path.resolve()
        self.timeout = timeout

        if not self.scripts_dir.exists():
            raise FileNotFoundError(f"脚本目录不存在: {self.scripts_dir}")

    def execute(
        self,
        script_name: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """执行脚本（与原始逻辑完全一致）"""
        start_time = time.time()
        script_path = self.scripts_dir / script_name
        effective_timeout = timeout if timeout is not None else self.timeout

        if not script_path.exists():
            elapsed = (time.time() - start_time) * 1000
            return self._error_response(
                404, f"脚本文件不存在: {script_name}", elapsed=elapsed,
            )

        if not os.access(str(script_path), os.X_OK):
            elapsed = (time.time() - start_time) * 1000
            return self._error_response(
                403, f"脚本无执行权限: {script_name}", elapsed=elapsed,
            )

        try:
            env = os.environ.copy()
            if params:
                for key, value in params.items():
                    env[f"TOOL_PARAM_{key.upper()}"] = str(value)

            result = subprocess.run(
                ["bash", str(script_path)],
                capture_output=True,
                text=True,
                timeout=effective_timeout,
                env=env,
                cwd=str(script_path.parent),
            )

            elapsed = (time.time() - start_time) * 1000
            stdout = result.stdout.strip()

            if not stdout:
                stderr_msg = result.stderr.strip() or "脚本无输出"
                return self._error_response(
                    1, f"脚本执行无输出: {stderr_msg}", elapsed=elapsed,
                )

            try:
                output = json.loads(stdout)
            except json.JSONDecodeError as e:
                return self._error_response(
                    3,
                    f"脚本输出非标准 JSON 格式: {str(e)}",
                    data={"raw_output": stdout[:500]},
                    elapsed=elapsed,
                )

            output.setdefault("status", "success")
            output.setdefault("code", result.returncode)
            output["execution_time_ms"] = round(elapsed, 2)
            return output

        except subprocess.TimeoutExpired:
            elapsed = (time.time() - start_time) * 1000
            return self._error_response(
                408,
                f"脚本执行超时（超过 {effective_timeout} 秒）",
                elapsed=elapsed,
            )

        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            return self._error_response(
                500, f"脚本执行异常: {str(e)}", elapsed=elapsed,
            )

    def _error_response(
        self,
        code: int,
        message: str,
        data: Any = None,
        elapsed: float = 0,
    ) -> Dict[str, Any]:
        return {
            "status": "error",
            "code": code,
            "message": message,
            "data": data,
            "execution_time_ms": round(elapsed, 2),
        }