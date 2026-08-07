		# Skill: 运维工具平台开发（tinyPlatform）

## 技能元信息
- **名称**：tinyPlatform
- **版本**：1.1
- **适用场景**：从零搭建运维工具平台，支持 Web UI 和 AI Agent 调用
- **最后更新**：2026-08-06

---

## 一、项目目标

构建一个**解耦的运维工具平台**，实现以下核心能力：
1. **脚本工具集**：标准化 Shell 脚本，统一输出 JSON 格式
2. **API 服务层**：FastAPI 封装脚本调用，提供 RESTful API
3. **前端展示层**：独立容器部署，调用 API 展示结果
4. **AI 接入层**：MCP 协议支持大模型（LLM）调用工具

---

## 二、整体架构

| 层级    | 组件          | 职责                       | 部署方式        |
| ----- | ----------- | ------------------------ | ----------- |
| 工具层   | `scripts/`  | 运维 Shell 脚本集合，统一 JSON 输出 | 挂载到后端容器     |
| API 层 | `backend/`  | FastAPI 服务，执行脚本并返回结果     | 后端容器        |
| 展示层   | `frontend/` | 静态 Web 页面，调用后端 API       | 独立容器（Nginx） |
| 接入层   | `mcp/`      | MCP 协议服务器，供大模型调用         | 后端容器        |

### 架构图
```
前端容器 ──▶ 后端容器 ──▶ 脚本目录（挂载）
                │
                ▼
           MCP 容器 ──▶ 大模型（Claude/GPT）
```

---

## 三、目录结构规划

```
tinyPlatform/
├── README.md                 # 项目说明、快速启动指南
├── .gitignore
├── docker-compose.yml        # 编排所有容器服务
│
├── scripts/                  # ① 工具脚本层（纯 Shell）
│   ├── sys_check.sh          # 系统资源巡检
│   ├── get_time.sh           # 获取当前时间
│   └── ...                   # 后续新增脚本按功能分类
│
├── backend/                  # ② API 服务层（FastAPI + Python）
│   ├── app/
│   │   ├── main.py           # FastAPI 应用入口，注册路由
│   │   ├── routers/          # 路由层（API 端点）
│   │   │   └── tools.py      # 工具相关路由（列表/执行）
│   │   ├── models/           # Pydantic 数据模型
│   │   │   └── tool_models.py
│   │   └── utils/            # 工具函数
│   │       └── executor.py   # 脚本执行器（subprocess 封装）
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example          # 环境变量模板
│
├── mcp/                      # ③ MCP 服务层（可选）
│   ├── server.py             # MCP 协议实现
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/                 # ④ 前端展示层（静态页面）
│   ├── index.html            # 主页面
│   ├── css/
│   │   └── style.css         # 样式
│   ├── js/
│   │   └── app.js            # 调用后端 API
│   ├── nginx.conf            # Nginx 配置
│   └── Dockerfile            # 基于 Nginx Alpine
│
└── .github/
    └── workflows/
        └── build.yml         # CI/CD 自动构建镜像（可选）
```

---

## 四、核心设计原则

### 4.1 脚本规范
- **统一输出格式**：所有脚本输出标准 JSON 结构
  ```json
  {
    "status": "success|error",
    "code": 0,
    "message": "描述信息",
    "data": { ... }
  }
  ```
- **错误码约定**：0=成功，1=通用错误，2=命令不可用，3=数据异常
- **容错处理**：每个命令须有 `2>/dev/null` 和空值兜底

### 4.2 后端设计
- **脚本执行器**：封装 `subprocess`，统一处理超时、异常、JSON 解析
- **工具注册表**：集中管理所有工具（名称、描述、对应脚本、参数定义）（表通过目录挂载）
- **动态扩展**：新增脚本只需修改注册表（或配置文件/数据库），无需改代码（脚本目录挂载宿主机）
- **CORS 配置**：允许前端跨域请求

### 4.3 前端设计
- **纯静态页面**：无后端渲染，完全通过 AJAX 调用 API
- **组件解耦**：前端通过环境变量配置 API 地址，与后端部署位置无关
- **容器化部署**：使用 Nginx 托管静态文件

### 4.4 MCP 设计
- **独立服务**：MCP 服务器作为独立容器运行，不依赖前端
- **调用后端**：MCP 通过 HTTP 调用 Backend API，复用工具注册逻辑
- **工具暴露**：将注册表中的工具自动转换为 MCP 协议格式
- **传输方式**：使用 stdio 传输（JSONRPC over stdin/stdout），供 Claude Code 等 MCP 客户端直接拉起子进程
- **SDK 版本**：当前使用 MCP Python SDK 2.0，底层 API 采用 `add_request_handler()` 注册模式（非 1.x 装饰器）
- **日志隔离**：所有日志输出到 stderr，stdout 专用于 JSONRPC 协议消息

---

## 五、开发阶段规划

| 阶段 | 内容 | 状态 | 产出 | 验证方式 |
|------|------|------|------|----------|
| **阶段一** | 编写标准脚本 | ✅ 完成 | `scripts/get_time.sh`, `scripts/sys_check.sh` | 手动执行脚本，JSON 格式正确 |
| **阶段二** | 搭建 FastAPI 后端 | ✅ 完成 | `/api/tools`, `/api/tools/{name}`, `/health` | `curl` 测试全部通过 |
| **阶段三** | 搭建前端页面 | ⬜ 未开始 | `frontend/` 目录已建，文件为空 | — |
| **阶段四** | 实现 MCP 服务 | ✅ 完成 | `mcp/server.py` (MCP 2.0 API)，含测试客户端 | `mcp/test_client.py` 测试通过 |
| **阶段五** | Docker Compose 集成 | ⬜ 未开始 | `docker-compose.yml` 为空 | — |
| **阶段六** | 动态工具注册 | ✅ 完成 | YAML 注册表 + ToolRegistry，支持热重载 | 修改 `tools.yaml` 后工具列表即时更新 |

---

## 六、技术选型

| 组件 | 技术 | 理由 |
|------|------|------|
| 脚本 | Bash/Shell | 运维通用，依赖少，执行效率高 |
| 后端框架 | FastAPI (Python) | 自动生成 API 文档，天然支持 OpenAPI，适合大模型对接 |
| 前端 | 原生 HTML/CSS/JS | 轻量，无需构建工具，容器体积小 |
| 前端容器 | Nginx Alpine | 极简静态文件服务器 |
| MCP SDK | mcp (Python) | 官方协议实现，与 FastAPI 技术栈统一 |
| 容器编排 | Docker Compose | 简单易用，适合小型项目 |
| 配置管理 | YAML/JSON 文件 | 无需数据库，降低初始复杂度 |

---

## 七、关键接口契约

### Backend API（供前端和 MCP 调用）

| 端点 | 方法 | 功能 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/api/tools` | GET | 获取所有工具列表（含名称、描述、参数） |
| `/api/tools/{tool_name}` | GET | 执行指定工具，返回 JSON 结果 |
| `/api/tools/{tool_name}` | POST | 执行指定工具（支持传参） |

### MCP 协议（供大模型调用）

- MCP 服务器内部调用 Backend API，将工具包装为 MCP Tool
- 大模型通过 MCP 协议发现工具并执行

---

## 八、快速启动流程

### 开发模式
1. 编写脚本 → 手动测试 JSON 输出
2. 启动 FastAPI 后端（uvicorn）
3. 用 curl/浏览器测试 API
4. 前端静态页面连接本地后端测试

### 生产模式
1. `docker-compose up -d` 启动所有服务
2. 访问 `http://localhost` 使用前端页面
3. MCP 客户端连接 `http://localhost:8080`

---

## 九、扩展方向（后续迭代）

| 功能 | 方案 |
|------|------|
| 脚本参数支持 | 工具注册表增加 `params` 字段，前端动态渲染输入表单 |
| 用户认证 | FastAPI 集成 JWT/OAuth2 |
| 执行历史 | 增加 SQLite 存储，记录谁在何时执行了什么工具 |
| 权限控制 | 基于 RBAC 限制用户可用的工具列表 |
| 定时任务 | 集成 Celery 或 APScheduler，定期执行巡检脚本 |
| 监控告警 | 接入 Prometheus，暴露 Metrics 端点 |
| 配置热加载 | 工具注册表改为 YAML 文件，修改后无需重启服务 |

---

## 十、注意事项

| 事项 | 建议 |
|------|------|
| 脚本安全 | 绝不允许前端直接传参执行任意命令，必须白名单注册 |
| 超时控制 | 所有脚本执行设置超时（默认 30s），防止僵尸进程 |
| 日志审计 | 后端记录所有调用日志（工具名、参数、结果、耗时） |
| 容器挂载 | 脚本目录通过 Volume 挂载，方便热更新无需重建镜像 |
| 环境隔离 | 各服务通过环境变量配置（数据库连接、API 地址等） |
| 错误处理 | 脚本必须兜底所有异常，保证始终输出合法 JSON |

---

## 十一、相关资源

- FastAPI 官方文档：https://fastapi.tiangolo.com
- MCP 协议规范：https://modelcontextprotocol.io
- Docker Compose 文档：https://docs.docker.com/compose

---

> **版本**: 1.1 | **更新日期**: 2026-08-06 | **维护人**: Ignilibera
>
> ### 当前实现状态 (2026-08-06)
>
> **已实现并验证：**
> - 后端 API：`GET /health`, `GET /api/tools`, `GET/POST /api/tools/{tool_name}` 全部可用
> - 脚本执行器：`ScriptExecutor` 封装 subprocess，支持超时、JSON 解析、环境变量传参
> - 工具注册表：基于 `tools.yaml` 的动态注册，`ToolRegistry` 支持热重载 (`reload()`)
> - MCP 服务器：基于 MCP SDK 2.0，stdio 传输，已验证 `list_tools` / `call_tool` 全链路
> - Claude Code 集成：`.claude/settings.json` 已配置，新开会话即可调用工具
>
> **已知注意事项：**
> - MCP SDK 锁定 2.0 API（`add_request_handler` 模式），与 1.x 装饰器模式不兼容
> - 安装 MCP 依赖后 `starlette` 升级到 1.x，需要 `fastapi>=0.140` 配套
> - MCP 服务器 `print()` 必须走 stderr，stdout 留给 JSONRPC（已在 `server.py` 中封装 `log()` 函数）
> - 测试客户端位于 `mcp/test_client.py`，需先启动后端再运行