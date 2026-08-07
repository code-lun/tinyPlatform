"""
工具访问接口（封装 tool_registry）
为保持向后兼容，提供函数式调用风格
内部使用全局 tool_registry 实例
"""
from typing import List, Dict, Any, Optional
from app.registry import tool_registry


def get_all_tools(include_disabled: bool = False) -> List[Dict[str, Any]]:
    """获取所有已启用的工具"""
    return tool_registry.get_all(include_disabled)


def get_tool_by_name(name: str) -> Optional[Dict[str, Any]]:
    """根据名称获取单个工具"""
    return tool_registry.get_by_name(name)


def get_tools_by_category(category: str) -> List[Dict[str, Any]]:
    """按分类过滤工具"""
    return tool_registry.get_by_category(category)


def get_tools_by_tag(tag: str) -> List[Dict[str, Any]]:
    """按标签过滤工具"""
    return tool_registry.get_by_tag(tag)


def get_categories() -> List[str]:
    """获取所有分类"""
    return tool_registry.get_categories()


def get_tags() -> List[str]:
    """获取所有标签"""
    return tool_registry.get_tags()


def reload_registry():
    """热重载工具注册表"""
    tool_registry.reload()