"""
FastAPI 应用入口
注册路由、配置中间件
"""
import datetime
import signal
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# 显式加载 backend/.env（必须在其他 import 之前）
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import PORT, LOG_LEVEL, ALLOWED_ORIGINS
from app.routers import tools
from app.utils.logger import logger


# ========== 生命周期管理 ==========
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动 → 运行 → 优雅关闭"""
    yield
    logger.info("SERVER", "正在关闭服务，释放资源...")


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


# ========== 启动入口（含优雅退出） ==========
if __name__ == "__main__":
    import uvicorn

    server = None
    shutdown_flag = False

    def _signal_handler(sig, frame):
        global shutdown_flag
        if not shutdown_flag:
            shutdown_flag = True
            logger.info("SERVER", "收到中断信号，正在优雅退出...")
            if server is not None:
                server.should_exit = True

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    config = uvicorn.Config(
        "app.main:app",
        host="0.0.0.0",
        port=PORT,
        reload=False,
        log_level=LOG_LEVEL,
    )
    server = uvicorn.Server(config)

    logger.info("SERVER", f"服务启动于 http://0.0.0.0:{PORT}")
    try:
        server.run()
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("SERVER", "服务已停止，端口已释放")