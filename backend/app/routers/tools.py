"""
工具管理路由
提供工具列表查询、工具执行等 API 端点
"""
from fastapi import APIRouter, HTTPException, Query
from app.models.tool_models import (
    ToolInfo, ToolListResponse, ToolExecuteResponse
)
from app.utils.executor import ScriptExecutor
from typing import Optional
from app.registry import tool_registry

router = APIRouter()

# 初始化脚本执行器
executor = ScriptExecutor(scripts_dir="../scripts", timeout=30)

# ========== API 端点 ==========

@router.get("/tools", response_model=ToolListResponse, summary="获取工具列表")
async def list_tools(
    category: Optional[str] = Query(None, description="按分类过滤工具")
):
    """
    获取所有可用工具的列表

    - **category**: 可选，按工具分类过滤（如"系统信息"、"资源巡检"）

    返回工具名称、描述、分类、参数定义等信息，不执行脚本
    """
    # 从注册中心获取所有已启用的工具
    all_tools = tool_registry.get_all()

    tool_list = []
    for tool in all_tools:
        # 按分类过滤
        if category and tool["category"] != category:
            continue

        tool_list.append(
            ToolInfo(
                name=tool["name"],
                description=tool["description"],
                category=tool["category"],
                params=tool["params"],
                endpoint=tool["endpoint"],
            )
        )

    return ToolListResponse(
        total=len(tool_list),
        tools=tool_list
    )


@router.get("/tools/{tool_name}", response_model=ToolExecuteResponse, summary="GET 执行工具")
async def execute_tool_get(tool_name: str):
    """
    通过 GET 请求执行指定工具（无需参数的工具）

    - **tool_name**: 工具名称，如 get_time、sys_check

    执行对应的 Shell 脚本并返回 JSON 格式结果
    """
    return await _execute_tool(tool_name, {})


@router.post("/tools/{tool_name}", response_model=ToolExecuteResponse, summary="POST 执行工具")
async def execute_tool_post(tool_name: str, params: dict = {}):
    """
    通过 POST 请求执行指定工具（支持传参）

    - **tool_name**: 工具名称，如 get_time、sys_check
    - **params**: 工具执行参数（JSON body）

    执行对应的 Shell 脚本并返回 JSON 格式结果
    """
    return await _execute_tool(tool_name, params)


# ========== 内部执行逻辑 ==========

async def _execute_tool(tool_name: str, params: dict) -> ToolExecuteResponse:
    """
    统一的工具执行内部函数

    1. 查找工具注册信息
    2. 调用脚本执行器
    3. 封装返回结果
    """
    # 1. 查找工具是否存在
    if not tool_registry.exists(tool_name):
        raise HTTPException(
            status_code=404,
            detail={
                "status": "error",
                "code": 404,
                "message": f"工具 '{tool_name}' 不存在",
                "data": None
            }
        )

    # 2. 获取脚本文件名并执行
    script_name = tool_registry.get_script_name(tool_name)
    # 使用工具级别的 timeout 配置，否则使用默认 30s
    tool_timeout = tool_registry.get_timeout(tool_name)
    if tool_timeout:
        executor.timeout = tool_timeout

    result = executor.execute(script_name, params)

    # 恢复默认超时
    executor.timeout = 30

    # 3. 返回结果
    return ToolExecuteResponse(
        tool_name=tool_name,
        status=result.get("status", "error"),
        code=result.get("code", -1),
        message=result.get("message", "执行异常"),
        data=result.get("data"),
        execution_time_ms=result.get("execution_time_ms", 0)
    )