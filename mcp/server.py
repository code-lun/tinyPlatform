"""
运维工具平台 - MCP 服务器
基于 Model Context Protocol (MCP)，将后端 API 工具暴露给大模型
"""
import asyncio
import json
import os
import sys

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


# ========== 辅助：向 stderr 输出日志（避免污染 stdio JSONRPC 通道） ==========
def log(msg: str):
    print(msg, file=sys.stderr, flush=True)


# ========== MCP 服务器实例 ==========
server = Server("ops-tool-platform")


# ========== 从后端获取工具列表 ==========
async def fetch_tools() -> list[Tool]:
    """调用后端 /api/tools 接口，转换为 MCP Tool 列表"""
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        try:
            resp = await client.get(f"{BACKEND_API_URL}/api/tools")
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            log(f"[MCP] 获取工具列表失败: {e}")
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

    log(f"[MCP] 已加载 {len(tools)} 个工具")
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


# ========== 启动入口 ==========
async def main():
    """启动 MCP 服务器（使用 stdio 传输）"""
    log(f"[MCP] 服务器启动，后端地址: {BACKEND_API_URL}")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
