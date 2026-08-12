"""
脚本执行器
封装 subprocess 调用，统一处理超时、异常、JSON 解析
"""
import subprocess
import json
import time
import os
from typing import Dict, Any
from pathlib import Path
from app.utils.logger import logger


class ScriptExecutor:
    """
    脚本执行器类

    功能：
    - 执行 Shell 脚本
    - 超时控制（支持全局默认 + 单次覆盖，线程安全）
    - JSON 输出解析
    - 异常兜底
    - 执行耗时统计
    - 日志记录
    """

    def __init__(self, scripts_dir: str | None = None, timeout: int | None = None):
        """
        初始化执行器

        Args:
            scripts_dir: 脚本存放目录（绝对路径或相对于 backend 目录），
                         默认从 SCRIPTS_DIR 环境变量读取
            timeout:     全局默认超时时间（秒），默认从 SCRIPT_TIMEOUT 环境变量读取
        """
        from app.core.config import SCRIPTS_DIR as DEFAULT_SCRIPTS_DIR, SCRIPT_TIMEOUT

        if scripts_dir is None:
            scripts_dir = str(DEFAULT_SCRIPTS_DIR)
        if timeout is None:
            timeout = SCRIPT_TIMEOUT

        scripts_path = Path(scripts_dir)
        if not scripts_path.is_absolute():
            backend_dir = Path(__file__).parent.parent.parent
            scripts_path = (backend_dir / scripts_path)
        self.scripts_dir = scripts_path.resolve()
        self.timeout = timeout

        if not self.scripts_dir.exists():
            raise FileNotFoundError(f"脚本目录不存在: {self.scripts_dir}")

    def execute(
        self,
        script_name: str,
        params: Dict[str, Any] | None = None,
        timeout: int | None = None,
    ) -> Dict[str, Any]:
        """
        执行指定的 Shell 脚本

        Args:
            script_name: 脚本文件名（如 get_time.sh）
            params:      传递给脚本的参数（通过环境变量 TOOL_PARAM_{KEY} 注入）
            timeout:     单次执行超时（秒），不传则使用实例默认值，线程安全

        Returns:
            标准 JSON 结果字典
            {
                "status": "success|error",
                "code": 0,
                "message": "描述",
                "data": {...},
                "execution_time_ms": 123
            }
        """
        start_time = time.time()
        script_path = self.scripts_dir / script_name
        effective_timeout = timeout if timeout is not None else self.timeout

        # ========== 前置检查 ==========

        if not script_path.exists():
            elapsed = (time.time() - start_time) * 1000
            logger.warning("EXEC", f"脚本不存在: {script_name}")
            return self._error_response(
                code=404,
                message=f"脚本文件不存在: {script_name}",
                elapsed=elapsed,
            )

        if not os.access(str(script_path), os.X_OK):
            elapsed = (time.time() - start_time) * 1000
            logger.warning("EXEC", f"脚本无执行权限: {script_name}")
            return self._error_response(
                code=403,
                message=f"脚本无执行权限: {script_name}",
                elapsed=elapsed,
            )

        # ========== 执行脚本 ==========

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
                logger.warning("EXEC", f"脚本无输出: {script_name} | stderr={stderr_msg[:200]}")
                return self._error_response(
                    code=1,
                    message=f"脚本执行无输出: {stderr_msg}",
                    elapsed=elapsed,
                )

            # ========== 解析 JSON 输出 ==========

            try:
                output = json.loads(stdout)
            except json.JSONDecodeError as e:
                logger.warning("EXEC", f"JSON 解析失败: {script_name} | {e}")
                return self._error_response(
                    code=3,
                    message=f"脚本输出非标准 JSON 格式: {str(e)}",
                    data={"raw_output": stdout[:500]},
                    elapsed=elapsed,
                )

            output.setdefault("status", "success")
            output.setdefault("code", result.returncode)
            output["execution_time_ms"] = round(elapsed, 2)

            self._log_execution(
                script_name=script_name,
                status=output.get("status"),
                code=output.get("code"),
                elapsed=elapsed,
            )

            return output

        except subprocess.TimeoutExpired:
            elapsed = (time.time() - start_time) * 1000
            logger.error("EXEC", f"脚本执行超时: {script_name} (>{effective_timeout}s)")
            return self._error_response(
                code=408,
                message=f"脚本执行超时（超过 {effective_timeout} 秒）: {script_name}",
                elapsed=elapsed,
            )

        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            logger.error("EXEC", f"脚本执行异常: {script_name} | {e}")
            return self._error_response(
                code=500,
                message=f"脚本执行异常: {str(e)}",
                elapsed=elapsed,
            )

    # ========== 私有方法 ==========

    def _error_response(
        self, code: int, message: str,
        data: Any = None, elapsed: float = 0,
    ) -> Dict[str, Any]:
        """生成标准错误响应"""
        return {
            "status": "error",
            "code": code,
            "message": message,
            "data": data,
            "execution_time_ms": round(elapsed, 2),
        }

    def _log_execution(
        self, script_name: str, status: str, code: int, elapsed: float,
    ):
        """记录执行日志"""
        logger.info(
            "EXEC",
            f"脚本: {script_name} | 状态: {status} | 码: {code} | 耗时: {elapsed:.2f}ms",
        )