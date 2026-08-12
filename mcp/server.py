"""
运维工具平台 - MCP 服务器
基于 Model Context Protocol (MCP)，将后端 API 工具暴露给大模型

支持两种传输模式（通过 MCP_TRANSPORT 环境变量切换）：
  - stdio   — 标准输入输出（Claude Code 本地直接拉起进程）
  - http    — Streamable HTTP（容器化部署，Claude Code 通过 HTTP 连接）
"""
import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime

import httpx
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    CallToolResult,
    ListToolsResult,
    CallToolRequestParams,
    PaginatedRequestParams,
)

from config import (
    BACKEND_API_URL,
    REQUEST_TIMEOUT,
    API_TOKEN,
    MCP_TRANSPORT,
    MCP_HTTP_PORT,
    LOG_LEVEL,
)
from logger import logger

# ========== 配置（统一入口: config.py） ==========

# ========== 共享 HTTP 客户端（复用连接池） ==========
_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    """获取共享的 httpx AsyncClient（懒初始化，连接复用）"""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(REQUEST_TIMEOUT),
        )
        logger.debug("MCP", "HTTP 客户端已创建（连接池复用）")
    return _http_client


async def _close_http_client():
    """关闭共享的 HTTP 客户端（释放连接池）"""
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None
        logger.debug("MCP", "HTTP 客户端已关闭")


def _auth_headers() -> dict:
    """构建带 token 的请求头"""
    if API_TOKEN:
        return {"Authorization": f"Bearer {API_TOKEN}"}
    return {}


# ========== MCP 服务器实例 ==========
server = Server("tinyPlatform-mcp")


# ========== 从后端获取工具列表 ==========
async def fetch_tools() -> list[Tool]:
    """调用后端 /api/tools 接口，转换为 MCP Tool 列表"""
    client = _get_http_client()
    try:
        resp = await client.get(
            f"{BACKEND_API_URL}/api/tools",
            headers=_auth_headers(),
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error("MCP", f"获取工具列表失败: {e}")
        return []

    tools = []
    for item in data.get("tools", []):
        # 构建 MCP Tool 的 inputSchema（JSON Schema）
        input_schema = {
            "type": "object",
            "properties": {},
            "required": [],
        }
        for param in item.get("params", []):
            param_schema: dict = {"description": param.get("description", "")}
            ptype = param.get("type", "string")
            if ptype == "number":
                param_schema["type"] = "number"
            elif ptype == "boolean":
                param_schema["type"] = "boolean"
            else:
                param_schema["type"] = "string"

            if "default" in param:
                param_schema["default"] = param["default"]

            input_schema["properties"][param["name"]] = param_schema
            if param.get("required"):
                input_schema["required"].append(param["name"])

        tools.append(
            Tool(
                name=item["name"],
                description=item.get("description", ""),
                input_schema=input_schema,
            )
        )

    logger.info("MCP", f"已加载 {len(tools)} 个工具")
    return tools


# ========== MCP 工具列表处理器 ==========
async def handle_list_tools(ctx, params: PaginatedRequestParams) -> ListToolsResult:
    """当大模型请求工具列表时，返回从后端获取的工具"""
    tools = await fetch_tools()
    return ListToolsResult(tools=tools)


# ========== MCP 工具执行处理器 ==========
def _build_error_result(message: str) -> CallToolResult:
    """构建 MCP 错误响应，统一错误输出格式"""
    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text=json.dumps({
                    "status": "error",
                    "message": message,
                }, ensure_ascii=False),
            )
        ]
    )


async def handle_call_tool(ctx, params: CallToolRequestParams) -> CallToolResult:
    """当大模型调用工具时，转发到后端执行并返回结果"""
    name = params.name
    arguments = params.arguments or {}

    client = _get_http_client()
    try:
        resp = await client.post(
            f"{BACKEND_API_URL}/api/tools/{name}",
            json=arguments,
            headers=_auth_headers(),
        )
        resp.raise_for_status()
        result = resp.json()
        logger.info("MCP", f"工具调用成功 tool={name}")
    except httpx.HTTPStatusError as e:
        error_detail = "未知错误"
        try:
            error_detail = e.response.json().get("message", str(e))
        except Exception:
            error_detail = str(e)
        logger.error("MCP", f"后端返回错误 tool={name} status={e.response.status_code}")
        return _build_error_result(f"后端调用失败: {error_detail}")
    except Exception as e:
        logger.error("MCP", f"请求后端异常 tool={name}: {e}")
        return _build_error_result(f"请求后端异常: {str(e)}")

    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text=json.dumps(result, ensure_ascii=False),
            )
        ]
    )


# 注册处理器
server.add_request_handler("tools/list", PaginatedRequestParams, handle_list_tools)
server.add_request_handler("tools/call", CallToolRequestParams, handle_call_tool)


# ========== stdio 传输模式（本地开发） ==========
# async def run_stdio() -> None:
#     """使用 stdio 传输启动 MCP 服务器"""
#     logger.info("MCP", f"stdio 模式启动，后端地址: {BACKEND_API_URL}")
#     try:
#         async with stdio_server() as (read_stream, write_stream):
#             await server.run(
#                 read_stream,
#                 write_stream,
#                 server.create_initialization_options(),
#             )
#     finally:
#         await _close_http_client()

# ========== stdio 传输模式（本地开发）优雅退出版本 ==========
async def run_stdio() -> None:
    """使用 stdio 传输启动 MCP 服务器"""
    logger.info("MCP", f"stdio 模式启动，后端地址: {BACKEND_API_URL}")
    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("MCP", "收到中断信号，正在优雅关闭...")
    finally:
        await _close_http_client()
        logger.info("MCP", "MCP 服务器已退出")

# ========== HTTP 传输模式（容器化部署） ==========
async def run_http() -> None:
    """使用 Streamable HTTP 传输启动 MCP 服务器"""

    # 延迟导入，避免 stdio 模式下需要安装 starlette/uvicorn
    import anyio
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from starlette.routing import Mount, Route
    from mcp.server.streamable_http import StreamableHTTPServerTransport

    import uvicorn

    # 创建 HTTP 传输（mcp_session_id 作为路径标识）
    transport = StreamableHTTPServerTransport(
        mcp_session_id="tinyPlatform-mcp",
        is_json_response_enabled=True,
    )

    # MCP 端点使用 Mount 挂载原始 ASGI handler
    # 健康检查端点（无需认证，标准 Starlette request → Response 模式）
    async def health(request: Request) -> JSONResponse:
        return JSONResponse({
            "status": "healthy",
            "service": "tinyPlatform-mcp",
            "transport": "streamable-http",
            "timestamp": datetime.now().isoformat(),
        })

    @asynccontextmanager
    async def lifespan(app):
        """在应用生命周期内管理 MCP transport 连接"""
        async with transport.connect() as (read_stream, write_stream):
            async with anyio.create_task_group() as tg:
                tg.start_soon(
                    server.run,
                    read_stream,
                    write_stream,
                    server.create_initialization_options(),
                )
                logger.info("MCP", f"HTTP 模式启动，后端地址: {BACKEND_API_URL}")
                yield
                tg.cancel_scope.cancel()
        await _close_http_client()

    app = Starlette(
        lifespan=lifespan,
        routes=[
            Mount("/mcp", app=transport.handle_request),
            Route("/health", health, methods=["GET"]),
        ],
    )

    config = uvicorn.Config(app, host="0.0.0.0", port=MCP_HTTP_PORT, log_level=LOG_LEVEL)
    uvicorn_server = uvicorn.Server(config)
    # await uvicorn_server.serve()
    """优雅退出"""
    try:
        await uvicorn_server.serve()
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("MCP", "收到中断信号，正在优雅关闭...")
    finally:
        await _close_http_client()
        logger.info("MCP", "MCP 服务器已退出")


# ========== 启动入口 ==========
if __name__ == "__main__":
    if MCP_TRANSPORT == "http":
        asyncio.run(run_http())
    else:
        asyncio.run(run_stdio())
