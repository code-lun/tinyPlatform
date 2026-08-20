"""
工具管理路由
提供工具列表查询、工具执行等 API 端点
"""
import asyncio
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

from app.models.tool_models import (
    ToolExecuteResponse,
    ToolInfo,
    ToolListResponse,
)
from app.registry import tool_registry
from app.utils.auth import verify_token
from app.utils.executor import ConcurrentScriptExecutor
from app.utils.logger import logger

router = APIRouter(dependencies=[Depends(verify_token)])


# ========== 依赖注入 ==========
def get_executor(request: Request) -> ConcurrentScriptExecutor:
    """从 app.state 获取 executor 实例（由 lifespan 管理生命周期）"""
    return request.app.state.executor


# ========== API 端点 ==========

@router.get("/tools", response_model=ToolListResponse, summary="获取工具列表")
async def list_tools(
    category: Optional[str] = Query(None, description="按分类过滤工具"),
):
    """
    获取所有可用工具的列表

    - **category**: 可选，按工具分类过滤（如"系统信息"、"资源巡检"）

    返回工具名称、描述、分类、参数定义等信息，不执行脚本
    """
    all_tools = tool_registry.get_all()

    tool_list = [
        ToolInfo(
            name=tool["name"],
            description=tool["description"],
            category=tool["category"],
            params=tool["params"],
            endpoint=tool["endpoint"],
        )
        for tool in all_tools
        if not category or tool["category"] == category
    ]

    logger.info("API", f"工具列表查询 category={category or '全部'} total={len(tool_list)}")
    return ToolListResponse(
        total=len(tool_list),
        tools=tool_list,
    )


@router.get(
    "/tools/{tool_name}",
    response_model=ToolExecuteResponse,
    summary="GET 执行工具",
)
async def execute_tool_get(
    tool_name: str,
    executor: ConcurrentScriptExecutor = Depends(get_executor),
):
    """
    通过 GET 请求执行指定工具（无需参数的工具）

    - **tool_name**: 工具名称，如 get_time、sys_check

    执行对应的 Shell 脚本并返回 JSON 格式结果
    """
    return await _execute_tool(tool_name, {}, executor)


@router.post(
    "/tools/{tool_name}",
    response_model=ToolExecuteResponse,
    summary="POST 执行工具",
)
async def execute_tool_post(
    tool_name: str,
    params: Optional[dict] = Body(None, description="工具执行参数"),
    executor: ConcurrentScriptExecutor = Depends(get_executor),
):
    """
    通过 POST 请求执行指定工具（支持传参）

    - **tool_name**: 工具名称，如 get_time、sys_check
    - **params**: 工具执行参数（JSON body）

    执行对应的 Shell 脚本并返回 JSON 格式结果
    """
    return await _execute_tool(tool_name, params or {}, executor)


# ========== 内部执行逻辑 ==========

async def _execute_tool(
    tool_name: str,
    params: dict,
    executor: ConcurrentScriptExecutor,
) -> ToolExecuteResponse:
    """
    统一的工具执行内部函数

    1. 查找工具注册信息
    2. 在线程池中调用脚本执行器（避免阻塞事件循环）
    3. 封装返回结果
    """
    logger.info("API", f"请求执行工具 tool={tool_name}")

    # 1. 查找工具是否存在
    if not tool_registry.exists(tool_name):
        logger.warning("API", f"工具不存在 tool={tool_name}")
        raise HTTPException(
            status_code=404,
            detail={
                "status": "error",
                "code": 404,
                "message": f"工具 '{tool_name}' 不存在",
                "data": None,
            },
        )

    # 2. 获取脚本文件名，在线程池中执行（避免阻塞事件循环）
    script_name = tool_registry.get_script_name(tool_name)
    tool_timeout = tool_registry.get_timeout(tool_name)

    result = await asyncio.to_thread(
        executor.execute, script_name, params, tool_timeout,
    )

    # 3. 返回结果
    elapsed = result.get("execution_time_ms", 0)
    logger.info(
        "API",
        f"工具执行完成 tool={tool_name} "
        f"status={result.get('status')} "
        f"code={result.get('code')} "
        f"elapsed={elapsed:.0f}ms",
    )

    return ToolExecuteResponse(
        tool_name=tool_name,
        status=result.get("status", "error"),
        code=result.get("code", -1),
        message=result.get("message", "执行异常"),
        data=result.get("data"),
        execution_time_ms=elapsed,
    )