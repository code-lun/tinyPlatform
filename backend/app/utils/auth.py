"""
Token 验证依赖
所有 /api/* 路由强制执行 Bearer Token 验证
"""
import os
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.utils.logger import logger

# HTTPBearer 自动从 Authorization header 提取 Bearer token
_bearer = HTTPBearer(auto_error=True)


def _get_expected_token() -> str:
    """从环境变量读取期望的 token，未配置则返回空字符串"""
    return os.getenv("API_TOKEN", "")


async def verify_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
):
    """
    验证请求中的 Bearer token 是否与 API_TOKEN 环境变量一致。

    用法：挂载到 APIRouter 或 include_router 的 dependencies 中。
    所有 /api/* 请求强制验证，/health 等无需验证的路由不受影响。
    """
    expected = _get_expected_token()

    if not expected:
        # 未配置 token，拒绝所有请求（安全优先）
        logger.error("AUTH", "API_TOKEN 未配置，拒绝请求")
        raise HTTPException(
            status_code=500,
            detail="服务端未配置 API_TOKEN，请联系管理员",
        )

    if credentials.credentials != expected:
        logger.warning("AUTH", f"token 验证失败 path={request.url.path}")
        raise HTTPException(
            status_code=401,
            detail="Token 验证失败，请检查 Authorization header",
        )
