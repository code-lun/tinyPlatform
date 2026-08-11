# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# tinyPlatform — 运维工具平台

基于 FastAPI + MCP 的运维工具平台，Shell 脚本 → API → MCP 协议 → 大模型调用，全链路打通。

## 快速启动

### 本地开发

```bash
# 方式一（推荐，含优雅退出）：python -m app.main，Ctrl+C 自动释放端口
cd /opt/Tiny-Platform/backend && python3 -m app.main &

# 方式二（CLI）：uvicorn，前台运行时 Ctrl+C 可退出
cd /opt/Tiny-Platform/backend && python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
# 注：& 后台运行 + Ctrl+C 不会终止进程，需 kill 或 fg 后 Ctrl+C

# 验证后端（health 无需 token，API 需要 token）
curl http://127.0.0.1:8000/health
curl -H "Authorization: Bearer ops-token-2024" http://127.0.0.1:8000/api/tools | python3 -m json.tool

# 测试 MCP 全链路（需先启动后端）
python3 mcp/test_client.py
```

### Docker 部署

```bash
# 构建并启动所有服务
docker compose up -d

# 查看日志
docker compose logs -f

# 验证
curl http://127.0.0.1:8000/health
curl -H "Authorization: Bearer ops-token-2024" http://127.0.0.1:8000/api/tools
curl http://127.0.0.1:8080/health   # MCP 健康检查

# 停止
docker compose down
```

## 架构与调用链路

```
本地开发：  Claude Code ──(stdio/MCP)──▶ mcp/server.py ──(HTTP)──▶ FastAPI 后端 ──(subprocess)──▶ Shell 脚本
Docker 部署：Claude Code ──(HTTP/MCP)──▶ mcp:8080 ──(HTTP)──▶ backend:8000 ──(subprocess)──▶ Shell 脚本
```

| 层 | 目录 | 职责 |
|---|---|---|
| 脚本层 | `scripts/` | Shell 脚本，统一 JSON 输出，通过环境变量 `TOOL_PARAM_{KEY}` 接收参数 |
| API 层 | `backend/` | FastAPI，注册中心驱动工具发现，用 subprocess 执行脚本 |
| MCP 层 | `mcp/` | MCP SDK 2.0，支持 stdio（本地）和 Streamable HTTP（Docker）双传输模式 |
| 前端 | `frontend/` | 纯静态页面（未实现），Nginx 托管 |
| 容器化 | `Dockerfile*`, `docker-compose.yml` | Docker Compose 一键部署，健康检查，卷挂载 |

关键文件：
- `backend/app/registry/__init__.py` — 全局 `tool_registry` 实例，所有路由通过它查询/执行工具
- `backend/app/registry/tools.yaml` — 工具定义（名称、脚本、分类、参数、超时），修改后支持热重载
- `backend/app/utils/executor.py` — `ScriptExecutor` 封装 subprocess，以 `scripts/` 为基准目录
- `mcp/server.py` — MCP 服务端，`add_request_handler()` 注册模式（非 1.x 装饰器）
- `.claude/settings.json` — 注册了 `ops-tools` MCP 服务，Claude Code 可直接调用

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/api/tools` | GET | 工具列表，支持 `?category=` 过滤 |
| `/api/tools/{name}` | GET | 执行工具（无参） |
| `/api/tools/{name}` | POST | 执行工具（JSON body 传参） |

## 脚本规范

所有脚本输出统一 JSON：
```json
{
  "status": "success|error",
  "code": 0,
  "message": "描述信息",
  "data": { ... }
}
```
错误码：0=成功，1=通用错误，2=命令不可用，3=数据异常

## 新增工具流程

1. 编写 Shell 脚本放入 `scripts/`，遵循 JSON 输出规范
2. 在 `backend/app/registry/tools.yaml` 添加工具定义
3. 热重载：`python3 -c "from backend.app.registry.tools import reload_registry; reload_registry()"`（或重启后端）

## 关键技术细节

### 全局日志系统
- `backend/app/utils/logger.py` — 全局单例 `Logger` 类，统一输出到 stderr（兼容 MCP stdio）
- 日志等级：`debug | info | warning | error`，由 `LOG_LEVEL` 环境变量控制（默认 `info`）
- 输出格式：`[YYYY-MM-DD HH:MM:SS] [LEVEL   ] [TAG] message`
- 终端自动检测 TTY 以决定是否启用彩色输出
- 用法：`from app.utils.logger import logger` → `logger.info("TAG", "message")`
- 运行时切换等级：`logger.set_level("debug")`

### Token 认证
- `backend/.env` 中配置 `API_TOKEN=ops-token-2024`，所有 `/api/*` 请求必须携带 `Authorization: Bearer <token>` header
- `/health` 无需认证
- MCP 服务器通过环境变量 `API_TOKEN` 获取 token，自动附加到对后端的 HTTP 请求
- Claude Code 配置在 `.claude/settings.json` 的 `env` 块中设置 `API_TOKEN`
- 认证逻辑在 `backend/app/utils/auth.py`，通过 FastAPI `Depends` 挂载到 router

### MCP SDK 2.0 API（与 1.x 不兼容）
- 导入：`from mcp.server.lowlevel import Server`
- 注册：`server.add_request_handler("tools/list", PaginatedRequestParams, handler)`（非装饰器模式）
- Handler 签名：`async def handler(ctx, params)`（ctx 在前，两个参数）
- Tool 字段：`input_schema`（蛇形，非驼峰 `inputSchema`）
- **所有 `print()` 必须输出到 stderr**：`print(msg, file=sys.stderr, flush=True)`，stdout 专用于 JSONRPC

### 依赖版本
- MCP SDK 安装后 `starlette` 升到 1.x，需 `fastapi>=0.140` 配合
- `backend/requirements.txt` 写的 `fastapi==0.115.0` 已过时，重建环境时需更新

### Docker 配置细节
- **backend**: 暴露 8000，脚本目录通过 volume 挂载 `./scripts:/scripts:ro`，环境变量由 docker-compose 注入
- **mcp**: 暴露 8080，使用 `MCP_TRANSPORT=http` 启动 Streamable HTTP 模式，通过 `BACKEND_API_URL=http://backend:8000` 连接后端
- Claude Code 连接容器化 MCP 时，在 `.claude/settings.json` 中配置 HTTP 类型：
  ```json
  {
    "mcpServers": {
      "ops-tools": {
        "type": "http",
        "url": "http://127.0.0.1:8080/mcp"
      }
    }
  }
  ```
- 本地开发时保持原有 stdio 模式（`mcp/server.py` 默认 `MCP_TRANSPORT=stdio`）

### 测试命令备忘
```bash
# 后端测试（需带 token）
TOKEN="ops-token-2024"
curl http://127.0.0.1:8000/health
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/tools
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/tools/get_time
curl -H "Authorization: Bearer $TOKEN" -X POST http://127.0.0.1:8000/api/tools/sys_check -H 'Content-Type: application/json' -d '{}'
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/tools/nonexistent   # 应返回 404
curl http://127.0.0.1:8000/api/tools           # 无 token → 401

# MCP 测试
python3 mcp/test_client.py

# Docker 测试
curl http://127.0.0.1:8080/health              # MCP 健康检查
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/tools

# 热重载注册表（修改 tools.yaml 后）
python3 -c "from backend.app.registry.tools import reload_registry; reload_registry()"
```

## 当前状态

| 组件 | 状态 |
|------|------|
| 脚本层、后端 API、工具注册（YAML+热重载）、MCP 服务、Claude Code 集成 | ✅ 完成 |
| Token 认证（Bearer Token，env 配置，MCP 透传） | ✅ 完成 |
| 优雅退出（SIGINT/SIGTERM 信号处理） | ✅ 完成 |
| Docker 容器化（Dockerfile + docker-compose） | ✅ 完成 |
| 前端页面 | ⬜ 未开始 |
