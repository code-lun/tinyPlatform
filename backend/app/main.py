"""
FastAPI 应用入口
注册路由、配置中间件
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import tools

# 创建 FastAPI 应用实例
app = FastAPI(
    title="运维工具平台 API",
    description="统一运维工具调用接口，支持脚本执行和管理",
    version="1.0.0",
    docs_url="/docs",           # Swagger UI
    redoc_url="/redoc",         # ReDoc
)

# CORS 配置（允许前端跨域请求）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(tools.router, prefix="/api", tags=["工具管理"])


# ========== 健康检查端点 ==========
@app.get("/health", tags=["系统"])
async def health_check():
    """
    健康检查接口
    返回服务运行状态和基本信息
    """
    return {
        "status": "healthy",
        "service": "ops-tool-platform",
        "version": "1.0.0",
        "timestamp": __import__("datetime").datetime.now().isoformat()
    }


# ========== 启动说明 ==========
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8180,
        reload=True,            # 开发模式热重载
    )