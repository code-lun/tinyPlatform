# tinyPlatform — 运维工具平台

基于 FastAPI + MCP 的运维工具平台，Shell 脚本 → API → MCP 协议 → 大模型调用，全链路打通。

## 快速启动

```bash
# 1. 启动后端
cd /opt/Tiny-Platform/backend && python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# 2. 验证后端
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/tools | python3 -m json.tool

# 3. 测试 MCP（需先启动后端）
cd /opt/tinyPlatform && python3 mcp/test_client.py
```

## 项目结构

```
tinyPlatform/
├── scripts/                  # ① Shell 脚本（统一 JSON 输出格式）
│   ├── get_time.sh           #   获取系统时间
│   └── sys_check.sh          #   系统资源巡检（CPU/内存/磁盘）
│
├── backend/                  # ② FastAPI 后端
│   └── app/
│       ├── main.py           #   应用入口，CORS，路由注册
│       ├── routers/tools.py  #   /api/tools, /api/tools/{name} (GET/POST)
│       ├── models/tool_models.py  # Pydantic 请求/响应模型
│       ├── registry/         #   工具注册中心
│       │   ├── tools.yaml    #   工具定义（名称、脚本、参数、超时）
│       │   ├── registry.py   #   ToolRegistry 类（加载、查询、热重载）
│       │   └── tools.py      #   函数式封装接口
│       └── utils/executor.py #   ScriptExecutor（subprocess 封装）
│
├── mcp/                      # ③ MCP 服务器（供 Claude Code 调用）
│   ├── server.py             #   MCP 2.0 协议实现，stdio 传输
│   ├── test_client.py        #   测试客户端
│   └── requirements.txt      #   mcp>=1.0.0, httpx>=0.27.0
│
├── frontend/                 # ④ 前端（文件框架已建，内容为空）
│   ├── index.html            #   ⬜ 待实现
│   ├── css/style.css         #   ⬜ 待实现
│   ├── js/app.js             #   ⬜ 待实现
│   └── nginx.conf            #   ⬜ 待实现
│
├── .claude/settings.json     # Claude Code MCP 配置
├── docker-compose.yml        # ⬜ 待编写
├── skills.md                 # 完整设计文档
└── README.md                 # 项目介绍
```

## 当前状态

| 组件 | 状态 | 说明 |
|------|------|------|
| 脚本层 | ✅ 完成 | get_time.sh, sys_check.sh，统一 JSON 输出 |
| 后端 API | ✅ 完成 | 全部端点可用，curl 测试通过 |
| 工具注册 | ✅ 完成 | YAML 驱动，支持热重载，/api/tools?category= 过滤 |
| MCP 服务 | ✅ 完成 | MCP SDK 2.0，测试客户端验证全链路 |
| Claude Code 集成 | ✅ 已配置 | .claude/settings.json 注册了 ops-tools |
| 前端页面 | ⬜ 未开始 | 目录和空文件已建 |
| Docker 化 | ⬜ 未开始 | docker-compose.yml 为空 |

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/api/tools` | GET | 工具列表，支持 `?category=` 过滤 |
| `/api/tools/{name}` | GET | 执行工具（无参） |
| `/api/tools/{name}` | POST | 执行工具（JSON body 传参） |

## 架构：调用链路

```
Claude Code ──(stdio/MCP)──▶ mcp/server.py ──(HTTP)──▶ FastAPI 后端 ──(subprocess)──▶ Shell 脚本
```

- MCP 服务器从后端 `/api/tools` 拉取工具列表，转换为 MCP Tool 格式
- 大模型调用工具时，MCP 转发到后端 `/api/tools/{name}`，后端执行脚本并返回 JSON
- 脚本通过环境变量 `TOOL_PARAM_{KEY}` 接收参数

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
3. 可选：调用 `backend/app/registry/tools.reload_registry()` 热重载，或重启后端

## 关键技术细节

### 依赖版本注意事项
- MCP SDK 安装后 `starlette` 会升到 1.x，需 `fastapi>=0.140` 配合
- 当前 `backend/requirements.txt` 写的是旧版本号（`fastapi==0.115.0`），实际环境已升级，下次重建环境时需更新

### MCP SDK 2.0 API（与 1.x 不兼容）
- 导入：`from mcp.server.lowlevel import Server`（不是 `from mcp.server`）
- 注册：`server.add_request_handler("tools/list", PaginatedRequestParams, handler)`（不是装饰器）
- Handler 签名：`async def handler(ctx, params)`（两个参数，ctx 在前）
- Tool 字段：`input_schema`（蛇形，不是驼峰 `inputSchema`）
- **所有 `print()` 必须输出到 stderr**：`print(msg, file=sys.stderr, flush=True)`

### 测试命令备忘
```bash
# 后端测试
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/tools
curl http://127.0.0.1:8000/api/tools/get_time
curl -X POST http://127.0.0.1:8000/api/tools/sys_check -H 'Content-Type: application/json' -d '{}'
curl http://127.0.0.1:8000/api/tools/nonexistent   # 应返回 404

# MCP 测试
python3 mcp/test_client.py

# 热重载注册表
python3 -c "from backend.app.registry.tools import reload_registry; reload_registry()"
```
