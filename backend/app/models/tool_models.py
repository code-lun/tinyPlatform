"""
Pydantic 数据模型定义
用于 API 请求/响应的数据验证和文档生成
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Any


# ========== 工具信息模型 ==========

class ToolParamInfo(BaseModel):
    """工具参数定义"""
    name: str = Field(..., description="参数名称")
    type: str = Field(..., description="参数类型（string/number/boolean）")
    required: bool = Field(False, description="是否必填")
    default: Optional[Any] = Field(None, description="默认值")
    description: str = Field("", description="参数说明")


class ToolInfo(BaseModel):
    """单个工具的详细信息"""
    name: str = Field(..., description="工具名称（唯一标识）")
    description: str = Field(..., description="工具功能描述")
    category: str = Field(..., description="工具分类")
    params: List[ToolParamInfo] = Field([], description="工具参数列表")
    endpoint: str = Field(..., description="工具调用端点")


class ToolListResponse(BaseModel):
    """工具列表响应"""
    total: int = Field(..., description="工具总数")
    tools: List[ToolInfo] = Field(..., description="工具列表")


# ========== 工具执行模型 ==========

class ToolExecuteResponse(BaseModel):
    """工具执行响应"""
    tool_name: str = Field(..., description="执行的工具名称")
    status: str = Field(..., description="执行状态（success/error）")
    code: int = Field(..., description="执行状态码（0=成功）")
    message: str = Field(..., description="执行结果描述")
    data: Optional[Any] = Field(None, description="返回数据")
    execution_time_ms: float = Field(0, description="执行耗时（毫秒）")