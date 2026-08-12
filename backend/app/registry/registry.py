"""
工具注册管理器（基于 YAML 配置文件）
提供工具加载、查询、过滤、热重载功能
"""
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.utils.logger import logger


class ToolRegistry:
    """
    工具注册管理器
    
    数据源：同目录下的 tools.yaml
    特性：
    - 启动时自动加载
    - 支持按名称、分类、标签查询
    - 支持 reload() 热重载（无需重启进程）
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化注册表
        
        Args:
            config_path: YAML 配置文件路径，默认使用同目录的 tools.yaml
        """
        if config_path is None:
            config_path = Path(__file__).parent / "tools.yaml"
        self._config_path = Path(config_path)
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self):
        """从 YAML 文件加载工具定义"""
        if not self._config_path.exists():
            raise FileNotFoundError(f"工具配置文件不存在: {self._config_path}")

        with open(self._config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        tools_raw = config.get("tools", [])
        self._tools.clear()

        for tool in tools_raw:
            if self._validate_tool(tool):
                self._tools[tool["name"]] = tool

        logger.info("REGISTRY", f"已从 {self._config_path.name} 加载 {len(self._tools)} 个工具")

    def _validate_tool(self, tool: Dict[str, Any]) -> bool:
        """验证工具定义完整性并设置默认值"""
        tool_name = tool.get("name", "?")
        required = ["name", "script", "category"]
        for field in required:
            if field not in tool or not tool[field]:
                logger.warning("REGISTRY", f"工具 '{tool_name}' 缺少必需字段 '{field}'，已跳过")
                return False

        tool.setdefault("display_name", tool["name"])
        tool.setdefault("description", "")
        tool.setdefault("params", [])
        tool.setdefault("timeout", None)
        tool.setdefault("enabled", True)
        tool.setdefault("tags", [])
        return True

    # ========== 查询接口 ==========

    def get_all(self, include_disabled: bool = False) -> List[Dict[str, Any]]:
        tools = []
        for tool in self._tools.values():
            if not include_disabled and not tool["enabled"]:
                continue
            tools.append(self._to_api_format(tool))
        return tools

    def get_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        tool = self._tools.get(name)
        if tool and tool["enabled"]:
            return self._to_api_format(tool)
        return None

    def get_by_category(self, category: str) -> List[Dict[str, Any]]:
        return [
            self._to_api_format(t) for t in self._tools.values()
            if t["enabled"] and t["category"] == category
        ]

    def get_by_tag(self, tag: str) -> List[Dict[str, Any]]:
        return [
            self._to_api_format(t) for t in self._tools.values()
            if t["enabled"] and tag in t.get("tags", [])
        ]

    def get_script_name(self, name: str) -> Optional[str]:
        tool = self._tools.get(name)
        if tool and tool["enabled"]:
            return tool["script"]
        return None

    def get_timeout(self, name: str) -> Optional[int]:
        tool = self._tools.get(name)
        if tool:
            return tool.get("timeout")
        return None

    def exists(self, name: str) -> bool:
        tool = self._tools.get(name)
        return tool is not None and tool["enabled"]

    def get_categories(self) -> List[str]:
        categories = {t["category"] for t in self._tools.values() if t["enabled"]}
        return sorted(categories)

    def get_tags(self) -> List[str]:
        tags = set()
        for t in self._tools.values():
            if t["enabled"]:
                tags.update(t.get("tags", []))
        return sorted(tags)

    def reload(self):
        """重新加载 YAML 配置文件（热更新）"""
        logger.info("REGISTRY", "收到热重载请求，开始重新加载工具配置...")
        self._load()
        logger.info("REGISTRY", f"热重载完成，当前 {self.count} 个启用的工具")

    @property
    def count(self) -> int:
        return len([t for t in self._tools.values() if t["enabled"]])

    # ========== 辅助方法 ==========

    def _to_api_format(self, tool: Dict[str, Any]) -> Dict[str, Any]:
        """转换为 API 对外格式"""
        return {
            "name": tool["name"],
            "display_name": tool["display_name"],
            "description": tool["description"],
            "category": tool["category"],
            "params": tool["params"],
            "timeout": tool["timeout"],
            "tags": tool["tags"],
            "endpoint": f"/api/tools/{tool['name']}",
        }