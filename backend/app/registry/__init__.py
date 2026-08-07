"""
工具注册中心 - 统一入口
使用 YAML 配置文件驱动，所有工具定义在 tools.yaml 中
"""
from app.registry.registry import ToolRegistry

# 全局唯一注册实例
tool_registry = ToolRegistry()