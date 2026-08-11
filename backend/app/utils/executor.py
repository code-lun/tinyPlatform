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
    - 超时控制
    - JSON 输出解析
    - 异常兜底
    - 执行耗时统计
    - 日志记录
    """
    
    def __init__(self, scripts_dir: str, timeout: int = 30):
        """
        初始化执行器
        
        Args:
            scripts_dir: 脚本存放目录（相对于 backend 目录或绝对路径）
            timeout: 脚本执行超时时间（秒）
        """
        # 获取脚本目录的绝对路径
        backend_dir = Path(__file__).parent.parent.parent  # executor.py -> utils -> app -> backend
        self.scripts_dir = (backend_dir / scripts_dir).resolve()
        self.timeout = timeout
        
        # 确保脚本目录存在
        if not self.scripts_dir.exists():
            raise FileNotFoundError(f"脚本目录不存在: {self.scripts_dir}")
    
    def execute(self, script_name: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        执行指定的 Shell 脚本
        
        Args:
            script_name: 脚本文件名（如 get_time.sh）
            params: 传递给脚本的参数（暂未实现，预留接口）
        
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
        
        # ========== 前置检查 ==========
        
        # 1. 检查脚本文件是否存在
        if not script_path.exists():
            elapsed = (time.time() - start_time) * 1000
            return self._error_response(
                code=404,
                message=f"脚本文件不存在: {script_name}",
                elapsed=elapsed
            )
        
        # 2. 检查脚本是否可执行
        if not os.access(str(script_path), os.X_OK):
            elapsed = (time.time() - start_time) * 1000
            return self._error_response(
                code=403,
                message=f"脚本无执行权限: {script_name}",
                elapsed=elapsed
            )
        
        # ========== 执行脚本 ==========
        
        try:
            # 设置环境变量（如果需要传参）
            env = os.environ.copy()
            if params:
                for key, value in params.items():
                    env[f"TOOL_PARAM_{key.upper()}"] = str(value)
            
            # 执行脚本
            result = subprocess.run(
                ["bash", str(script_path)],      # 使用 bash 执行脚本
                capture_output=True,             # 捕获标准输出和错误输出
                text=True,                       # 以文本模式处理
                timeout=self.timeout,            # 超时控制
                env=env,                         # 传递环境变量
                cwd=str(script_path.parent),     # 在脚本所在目录执行
            )
            
            elapsed = (time.time() - start_time) * 1000
            
            # 获取标准输出
            stdout = result.stdout.strip()
            
            # 如果标准输出为空，返回错误
            if not stdout:
                stderr_msg = result.stderr.strip() or "脚本无输出"
                return self._error_response(
                    code=1,
                    message=f"脚本执行无输出: {stderr_msg}",
                    elapsed=elapsed
                )
            
            # ========== 解析 JSON 输出 ==========
            
            try:
                output = json.loads(stdout)
            except json.JSONDecodeError as e:
                # JSON 解析失败，返回原始输出
                return self._error_response(
                    code=3,
                    message=f"脚本输出非标准 JSON 格式: {str(e)}",
                    data={"raw_output": stdout[:500]},  # 截取前500字符
                    elapsed=elapsed
                )
            
            # 确保必要字段存在
            if "status" not in output:
                output["status"] = "success"
            if "code" not in output:
                output["code"] = result.returncode
            
            # 添加执行耗时
            output["execution_time_ms"] = round(elapsed, 2)
            
            # ========== 日志记录（打印到控制台） ==========
            self._log_execution(
                script_name=script_name,
                status=output.get("status"),
                code=output.get("code"),
                elapsed=elapsed
            )
            
            return output
        
        except subprocess.TimeoutExpired:
            elapsed = (time.time() - start_time) * 1000
            return self._error_response(
                code=408,
                message=f"脚本执行超时（超过 {self.timeout} 秒）: {script_name}",
                elapsed=elapsed
            )
        
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            return self._error_response(
                code=500,
                message=f"脚本执行异常: {str(e)}",
                elapsed=elapsed
            )
    
    # ========== 私有方法 ==========
    
    def _error_response(self, code: int, message: str, data: Any = None, elapsed: float = 0) -> Dict[str, Any]:
        """生成标准错误响应"""
        return {
            "status": "error",
            "code": code,
            "message": message,
            "data": data,
            "execution_time_ms": round(elapsed, 2)
        }
    
    def _log_execution(self, script_name: str, status: str, code: int, elapsed: float):
        """记录执行日志"""
        logger.info("EXEC", f"脚本: {script_name} | 状态: {status} | 码: {code} | 耗时: {elapsed:.2f}ms")