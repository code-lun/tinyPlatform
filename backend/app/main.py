"""
FastAPI 应用入口
注册路由、配置中间件、管理生命周期
"""
import datetime
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# 显式加载 backend/.env（必须在其他 import 之前）
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import (
    PORT,
    LOG_LEVEL,
    ALLOWED_ORIGINS,
    SCRIPT_TIMEOUT,
    EXECUTOR_MAX_WORKERS,
    EXECUTOR_QUEUE_SIZE,
    EXECUTOR_QUEUE_WAIT_TIMEOUT,
    EXECUTOR_MAX_CONCURRENT_SCRIPTS,
    EXECUTOR_RESULT_TTL,
)
from app.routers import executor, tools
from app.utils.executor import ConcurrentScriptExecutor, ExecutorConfig
from app.utils.logger import logger


# ========== 生命周期管理 ==========
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动 → 运行 → 优雅关闭"""
    # ---- 启动阶段 ----
    # 从统一配置模块构建执行器配置（config.py 是环境变量的唯一入口）
    # 注意：config 中 EXECUTOR_MAX_CONCURRENT_SCRIPTS=0 表示不限制，
    #       而 ExecutorConfig 用 None 表示不限制，此处做语义转换
    executor = ConcurrentScriptExecutor(
        config=ExecutorConfig(
            max_workers=EXECUTOR_MAX_WORKERS,
            queue_size=EXECUTOR_QUEUE_SIZE,
            default_timeout=SCRIPT_TIMEOUT,
            queue_wait_timeout=EXECUTOR_QUEUE_WAIT_TIMEOUT,
            max_concurrent_scripts=(
                EXECUTOR_MAX_CONCURRENT_SCRIPTS
                if EXECUTOR_MAX_CONCURRENT_SCRIPTS > 0
                else None
            ),
            result_ttl=EXECUTOR_RESULT_TTL,
        ),
    )
    app.state.executor = executor
    logger.info("SERVER", f"服务启动于 http://0.0.0.0:{PORT}")

    yield  # ---- 运行阶段 ----

    # ---- 关闭阶段 ----
    logger.info("SERVER", "正在关闭服务，释放资源...")
    executor.shutdown(wait=True, timeout=30)


# 创建 FastAPI 应用实例
app = FastAPI(
    title="运维工具平台 API",
    description="统一运维工具调用接口，支持脚本执行和管理",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(tools.router, prefix="/api", tags=["工具管理"])
app.include_router(executor.router, prefix="/api", tags=["执行器"])


# ========== 健康检查端点 ==========
@app.get("/health", tags=["系统"])
async def health_check():
    """健康检查接口，返回服务运行状态和基本信息"""
    return {
        "status": "healthy",
        "service": "tinyPlatform-backend",
        "version": "1.0.0",
        "timestamp": datetime.datetime.now().isoformat(),
    }


# ========== 启动入口 ==========
if __name__ == "__main__":
    import uvicorn

    # uvicorn 内置信号处理已支持 SIGINT/SIGTERM 优雅退出，无需自定义 signal handler
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=PORT,
        reload=False,
        log_level=LOG_LEVEL,
    )