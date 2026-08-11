"""
运维工具平台 - MCP 服务器
基于 Model Context Protocol (MCP)，将后端 API 工具暴露给大模型

支持两种传输模式（通过 MCP_TRANSPORT 环境变量切换）：
  - stdio   — 标准输入输出（Claude Code 本地直接拉起进程）
  - http    — Streamable HTTP（容器化部署，Claude Code 通过 HTTP 连接）
"""
import asyncio
import json
import os
import sys
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

# ========== 配置 ==========
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "30.0"))
API_TOKEN = os.getenv("API_TOKEN", "")
MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "stdio")  # "stdio" | "http"
LOG_LEVEL = os.getenv("LOG_LEVEL", "info")

# 日志等级数值
_LOG_LEVELS = {"debug": 10, "info": 20, "warning": 30, "error": 40}
_LOG_THRESHOLD = _LOG_LEVELS.get(LOG_LEVEL.lower().strip(), 20)


def _auth_headers() -> dict:
    """构建带 token 的请求头"""
    if API_TOKEN:
        return {"Authorization": f"Bearer {API_TOKEN}"}
    return {}


# ========== 日志辅助（输出到 stderr，避免污染 stdio JSONRPC 通道） ==========
def log(level: str, tag: str, msg: str):
    """统一日志输出，带时间戳和等级"""
    if _LOG_LEVELS.get(level, 20) < _LOG_THRESHOLD:
        return
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level:<7s}] [{tag}] {msg}", file=sys.stderr, flush=True)


# ========== MCP 服务器实例 ==========
server = Server("ops-tool-platform")


# ========== 从后端获取工具列表 ==========
async def fetch_tools() -> list[Tool]:
    """调用后端 /api/tools 接口，转换为 MCP Tool 列表"""
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        try:
            resp = await client.get(
                f"{BACKEND_API_URL}/api/tools",
                headers=_auth_headers(),
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            log("error", "MCP", f"获取工具列表失败: {e}")
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
            param_schema = {
                "description": param.get("description", ""),
            }
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

    log("info", "MCP", f"已加载 {len(tools)} 个工具")
    return tools


# ========== MCP 工具列表处理器 ==========
async def handle_list_tools(ctx, params: PaginatedRequestParams) -> ListToolsResult:
    """当大模型请求工具列表时，返回从后端获取的工具"""
    tools = await fetch_tools()
    return ListToolsResult(tools=tools)


# ========== MCP 工具执行处理器 ==========
async def handle_call_tool(ctx, params: CallToolRequestParams) -> CallToolResult:
    """当大模型调用工具时，转发到后端执行并返回结果"""
    name = params.name
    arguments = params.arguments or {}

    # 调用后端 POST /api/tools/{name}
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        try:
            resp = await client.post(
                f"{BACKEND_API_URL}/api/tools/{name}",
                json=arguments,
                headers=_auth_headers(),
            )
            resp.raise_for_status()
            result = resp.json()
        except httpx.HTTPStatusError as e:
            error_detail = "未知错误"
            try:
                error_detail = e.response.json().get("message", str(e))
            except Exception:
                error_detail = str(e)
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=json.dumps({
                            "status": "error",
                            "message": f"后端调用失败: {error_detail}"
                        }, ensure_ascii=False),
                    )
                ]
            )
        except Exception as e:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=json.dumps({
                            "status": "error",
                            "message": f"请求后端异常: {str(e)}"
                        }, ensure_ascii=False),
                    )
                ]
            )

    # 将后端返回的结果包装为文本内容
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
async def run_stdio():
    """使用 stdio 传输启动 MCP 服务器"""
    log("info", "MCP", f"stdio 模式启动，后端地址: {BACKEND_API_URL}")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


# ========== HTTP 传输模式（容器化部署） ==========
async def run_http():
    """使用 Streamable HTTP 传输启动 MCP 服务器"""

    # 延迟导入，避免 stdio 模式下需要安装 starlette/uvicorn
    import anyio
    from starlette.applications import Starlette
    from starlette.routing import Route
    from mcp.server.streamable_http import StreamableHTTPServerTransport

    import uvicorn

    # 创建 HTTP 传输（mcp_session_id 作为路径标识）
    transport = StreamableHTTPServerTransport(
        mcp_session_id="ops-tools",
        is_json_response_enabled=True,
    )

    # ASGI 路由：将 /mcp 路径交给 transport 处理
    async def mcp_endpoint(scope, receive, send):
        await transport.handle_request(scope, receive, send)

    # 健康检查端点
    async def health(scope, receive, send):
        from starlette.responses import JSONResponse
        response = JSONResponse({
            "status": "healthy",
            "service": "ops-mcp-server",
            "transport": "streamable-http",
        })
        await response(scope, receive, send)

    @asynccontextmanager
    async def lifespan(app):
        """在应用生命周期内管理 MCP transport 连接"""
        async with transport.connect() as (read_stream, write_stream):
            # 在后台 task group 中运行 MCP server
            async with anyio.create_task_group() as tg:
                tg.start_soon(
                    server.run,
                    read_stream,
                    write_stream,
                    server.create_initialization_options(),
                )
                log("info", "MCP", f"HTTP 模式启动，后端地址: {BACKEND_API_URL}")
                yield
                # 关闭时取消后台任务
                tg.cancel_scope.cancel()

    app = Starlette(
        lifespan=lifespan,
        routes=[
            Route("/mcp", mcp_endpoint, methods=["GET", "POST", "DELETE"]),
            Route("/health", health, methods=["GET"]),
        ],
    )

    http_port = int(os.getenv("MCP_HTTP_PORT", "8080"))
    config = uvicorn.Config(app, host="0.0.0.0", port=http_port, log_level="info")
    uvicorn_server = uvicorn.Server(config)
    await uvicorn_server.serve()


# ========== 启动入口 ==========
if __name__ == "__main__":
    if MCP_TRANSPORT == "http":
        asyncio.run(run_http())
    else:
        asyncio.run(run_stdio())
