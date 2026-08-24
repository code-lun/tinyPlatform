"""
执行器状态路由
提供并发执行器（线程池）运行时状态查询，区别于 /api/tools 的工具执行
"""
from fastapi import APIRouter, Depends, Request

from app.utils.auth import verify_token

router = APIRouter(dependencies=[Depends(verify_token)])


@router.get("/executor/stats", summary="获取执行器运行状态")
async def executor_stats(request: Request):
    """
    获取并发执行器的运行时状态。

    返回字段：
    - max_workers:     线程池大小（并发 worker 数）
    - queue_capacity:  队列容量（配置值，背压控制上限）
    - active_tasks:    当前正在执行的脚本数
    - queued_tasks:    当前排队等待执行的任务数
    """
    return request.app.state.executor.get_stats()
