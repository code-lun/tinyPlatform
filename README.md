# tinyPlatform

基于 FastAPI + MCP 的运维工具平台，Shell 脚本 → API → MCP 协议 → 大模型调用，全链路打通。

```
tinyPlatform/
├── README.md                        # 项目整体介绍、启动方式
├── .gitignore
├── docker-compose.yml               # 本地快速启动所有服务（可选）
│
├── scripts/                         # ① 运维脚本工具集合（纯脚本，无依赖）
│   ├── sys_check.sh                 # 系统资源巡检
│   ├── get_time.sh                  # 获取时间
│   └── ...                          # 按功能分类，可加子目录如 ./docker/, ./network/
│
├── backend/                         # ② FastAPI 后端服务（Python）
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI 入口，注册路由
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   └── tools.py             # 暴露 /api/tools/* 接口，调用 scripts/ 下脚本
│   │   ├── models/
│   │   │   └── tool_models.py       # Pydantic 请求/响应模型
│   │   ├── registry/
│   │   │   ├── __init__.py          # 全局 tool_registry 实例
│   │   │   ├── registry.py          # 注册中心核心逻辑
│   │   │   └── tools.yaml           # 工具定义（名称、脚本、分类、参数、超时）
│   │   ├── core/
│   │   │   └── config.py            # 统一配置模块，所有环境变量的唯一入口
│   │   └── utils/
│   │       ├── executor.py          # 封装 subprocess 执行脚本，解析 JSON
│   │       ├── auth.py              # Bearer Token 验证
│   │       └── logger.py            # 全局日志系统（stderr 彩色 + 文件按天轮转）
│   ├── requirements.txt             # fastapi, uvicorn, python-multipart 等
│   ├── Dockerfile
│   └── .env                         # 环境变量配置（API_TOKEN 等）
│
├── mcp/                             # ③ MCP 服务器（独立服务，可选）
│   ├── server.py                    # MCP 协议实现，调用 backend API
│   ├── requirements.txt             # mcp>=2.0, httpx, starlette, uvicorn
│   ├── Dockerfile
│   └── .env
| ── frontend/                        # ④ 前端（纯静态，解耦）
    ├── index.html                   # 主页面，调用 backend API
    ├── css/
    │   └── style.css
    ├── js/
    │   └── app.js                   # fetch 调用后端，渲染数据
    ├── nginx.conf                   # Nginx 配置（用于容器）
    └── Dockerfile                   # 基于 nginx:alpine 托管静态文件


```

---

## 项目简介与使用场景

### 项目定位

tinyPlatform 是一个面向运维与 AI Agent 场景的轻量级工具编排平台。其核心思路是：**将任意 Shell 脚本、命令行工具或外部 API 统一封装为标准化的 HTTP 接口与 MCP 工具**，从而实现"一次编写，多处调用"——既可通过 REST API 供前端或 CI/CD 流水线调用，也可通过 MCP 协议无缝接入大语言模型（LLM）Agent，使 AI 具备直接操作生产环境的能力。

### 典型使用场景

| 场景 | 说明 |
|------|------|
| **接入 Claude Code / Cursor 等 AI IDE** | 通过 MCP stdio 或 Streamable HTTP 传输模式，将运维工具注册为 AI 可调用的 function/tool。开发者在 IDE 中用自然语言描述需求，AI 自动选择并执行对应脚本，返回结构化结果。 |
| **接入任意 MCP 客户端** | 平台遵循 [Model Context Protocol](https://modelcontextprotocol.io/) 规范，任何支持 MCP 的客户端（如 Claude Desktop、自研 Agent 框架）均可即插即用。 |
| **脚本即 API** | 将已有的运维脚本（巡检、备份、部署等）放入 `scripts/` 并在 `tools.yaml` 注册，即可立即获得 REST 端点，无需额外编写后端代码。 |
| **外部 API 脚本化** | 对于需要调用的第三方 API（云厂商接口、监控系统等），可编写轻量 Shell/Python 包装脚本，统一纳入平台管理，实现调用入口收敛与权限控制。 |
| **可复用脚本资产沉淀** | 经过生产验证的脚本沉淀在平台中，配合参数化设计（`TOOL_PARAM_{KEY}`），团队成员或 AI Agent 可直接复用，避免重复造轮子。 |
| **AI 自定义工具链** | 针对特定系统环境调教（编写）的专用脚本，注册后可被 AI 按需选择调用，形成"AI + 运维知识库"的闭环。例如：AI 根据告警自动选择 `sys_check.sh` 进行诊断，再调用 `restart_service.sh` 执行修复。 |
| **CI/CD 与自动化流水线** | 平台暴露标准 REST API，可被 Jenkins、GitLab CI、GitHub Actions 等流水线工具直接调用，作为运维原子操作节点。 |

### 设计哲学

- **约定优于配置**：脚本遵循统一 JSON 输出规范，注册即用，无需修改框架代码。
- **最小侵入**：脚本层零依赖，纯 Bash 编写；平台层通过 subprocess 隔离执行，脚本故障不影响服务进程。
- **渐进式扩展**：从单脚本 → REST API → MCP 工具 → AI Agent 调用，逐层叠加，各层可独立使用。
- **安全可控**：Bearer Token 认证 + 工具白名单注册机制，未注册脚本不可被外部触达。

---

## 技术栈与关键技术介绍

本项目涉及的核心技术如下，按所属层次分类介绍。

### 2.1 后端框架：FastAPI

FastAPI 是一个基于 Python 类型提示的高性能异步 Web 框架，底层依赖 Starlette（ASGI 服务器接口）与 Pydantic（数据校验）[^1]。其原生支持 OpenAPI（Swagger）自动文档生成、依赖注入与异步 I/O，在 TechEmpower 基准测试中性能接近 Go 与 Node.js 框架[^2]。本项目利用 FastAPI 的路由注册与 Pydantic 模型实现工具接口的参数校验与响应序列化。

> [^1]: Ramírez, S. (2019–2026). *FastAPI Documentation*. https://fastapi.tiangolo.com/
> [^2]: TechEmpower Framework Benchmarks. https://www.techempower.com/benchmarks/

### 2.2 MCP（Model Context Protocol）

Model Context Protocol 是由 Anthropic 于 2024 年 11 月发布的开放协议，旨在为大语言模型提供与外部数据源、工具交互的标准化接口[^3]。其架构采用 Client–Server 模式，支持两种传输方式：

- **stdio**：适用于本地进程间通信（如 Claude Code、Claude Desktop）；
- **Streamable HTTP（SSE）**：适用于远程/容器化部署，支持多客户端并发。

协议核心原语包括 **Tools**（模型可调用的函数）、**Resources**（上下文数据）与 **Prompts**（提示模板）。本项目基于 `mcp` Python SDK（≥ 2.0）实现 MCP Server，将后端 REST 接口映射为 MCP Tool，使 LLM 可通过 JSON-RPC 2.0 消息完成工具发现（`tools/list`）与调用（`tools/call`）。

> [^3]: Anthropic. (2024). *Model Context Protocol Specification*. https://modelcontextprotocol.io/specification

### 2.3 数据校验：Pydantic

Pydantic 是 Python 生态中广泛使用的数据验证库，基于类型注解（type hints）在运行时进行数据解析与校验[^4]。本项目使用 Pydantic v2 定义工具请求/响应模型，确保外部输入的类型安全，并自动生成 OpenAPI Schema 供前端与文档消费。

> [^4]: Pydantic Documentation. https://docs.pydantic.dev/

### 2.4 进程管理：subprocess

Python 标准库 `subprocess` 模块提供对子进程的创建、I/O 管道与返回码管理能力[^5]。本项目通过 `subprocess.run()` 以同步方式执行 Shell 脚本，设置超时（timeout）防止阻塞，并通过环境变量 `TOOL_PARAM_{KEY}` 向脚本传递参数，避免命令行注入风险。

> [^5]: Python Software Foundation. *subprocess — Subprocess management*. https://docs.python.org/3/library/subprocess.html

### 2.5 配置管理：YAML + 环境变量

工具注册采用 YAML 声明式配置，便于人类可读与版本管理；运行时敏感配置（Token、路径等）通过 `.env` 文件注入环境变量，遵循 12-Factor App 的配置外置原则[^6]。

> [^6]: Wiggins, A. (2024). *The Twelve-Factor App*. https://12factor.net/

### 2.6 容器化：Docker & Docker Compose

Docker 通过操作系统级虚拟化（Linux namespace + cgroup）实现应用与环境的封装与隔离[^7]。本项目为 backend 与 mcp 各提供 Dockerfile，并通过 Docker Compose 编排多容器服务，支持卷挂载（脚本热更新）、健康检查（`/health`）与网络互通，实现一键部署。

> [^7]: Merkel, D. (2014). Docker: Lightweight Linux Containers for Consistent Development and Delivery. *Linux Journal*, 2014(239), 2.

### 2.7 日志

日志模块基于 Python `logging` 标准库实现，支持：
- **stderr 彩色输出**（开发环境）；
- **按天轮转文件日志**（`TimedRotatingFileHandler`，生产环境）；
- 日志级别通过环境变量 `LOG_LEVEL` 动态控制。

### 技术选型总览

| 层次 | 技术 | 版本要求 | 用途 |
|------|------|----------|------|
| API 层 | FastAPI + Uvicorn | ≥ 0.100 | HTTP 服务、路由、异步处理 |
| 数据校验 | Pydantic | ≥ 2.0 | 请求/响应模型、自动文档 |
| MCP 层 | mcp (Python SDK) | ≥ 2.0 | MCP 协议实现（stdio / Streamable HTTP） |
| HTTP 客户端 | httpx | ≥ 0.24 | MCP Server 调用 Backend API |
| 脚本执行 | subprocess (stdlib) | — | 子进程管理与超时控制 |
| 配置 | PyYAML + python-dotenv | — | 工具注册表 + 环境变量 |
| 容器化 | Docker + Compose | ≥ 24.0 | 打包、编排、部署 |
| 调试工具 | MCP Inspector / WebCurl | — | 开发调试与接口验证 |
## 快速上手

### 1. 克隆项目 & 安装依赖

```bash
# 克隆到本地
git pull  # 或 git clone <repo-url>
cd Tiny-Platform

# ---- 后端依赖 ----
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd ..

# ---- MCP 依赖 ----
cd mcp
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd ..
```

### 2. 配置环境变量

后端和 MCP 各自有一个 `.env` 文件，项目已包含默认值，直接可用。关键配置项：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `API_TOKEN` | `tinyPlatform-token-2024` | API 认证 Token |
| `SCRIPTS_DIR` | `../scripts` | 脚本目录路径 |
| `LOG_LEVEL` | `info` | 日志级别 |

### 3. 启动服务

```bash
# 启动后端（端口 8000）
cd backend && python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# 启动 MCP 服务（端口 8080，依赖后端已启动）
cd mcp && python3 server.py &
```

---

## 测试 & 使用

### WebCurl 测试后端 API

[WebCurl](https://github.com/o8oo8o/WebCurl) 是一个网页版 API 调试工具，启动后通过浏览器可视化调用后端接口。

**安装：**

```bash
# TODO: 填写 WebCurl 安装方式
```

**测试示例：**

```
Token:      tinyPlatform-token-2024
Header:     Authorization: Bearer tinyPlatform-token-2024
后端地址:   http://127.0.0.1:8000
```

| 接口 | 方法 | 是否需要 Token |
|------|------|---------------|
| `/health` | GET | 否 |
| `/api/tools` | GET | 是 |
| `/api/tools/{name}` | GET/POST | 是 |

```bash
# 健康检查（无需 Token）
curl http://127.0.0.1:8000/health

# 获取工具列表
curl -H "Authorization: Bearer tinyPlatform-token-2024" http://127.0.0.1:8000/api/tools

# 执行工具
curl -H "Authorization: Bearer tinyPlatform-token-2024" http://127.0.0.1:8000/api/tools/get_time

# 带参数执行
curl -H "Authorization: Bearer tinyPlatform-token-2024" \
     -X POST http://127.0.0.1:8000/api/tools/sys_check \
     -H "Content-Type: application/json" -d '{}'
```

### MCP Inspector 测试 MCP 功能

[MCP Inspector](https://github.com/modelcontextprotocol/inspector) 是 MCP 官方可视化测试工具，可连接 MCP 服务、浏览工具列表、调用工具并查看结果。

**安装（v1 版本）：**

直接执行，windows也是这个命令（cmd/powershell）
```bash
npm install -g @modelcontextprotocol/inspector@1
```

下载完成之后会自动跳转web，之后启用服务直接敲
```bash
mcp-inspector
```
**连接 MCP 服务：**

启动 Inspector 后，在连接界面填入 MCP 服务地址：

```
MCP 服务地址: http://localhost:8080/mcp/
```

> 将 `localhost` 替换为你的实际后端/MCP 服务器 IP。

**可用的 MCP 端点：**

| 端点 | 说明 |
|------|------|
| `/mcp/` | MCP Streamable HTTP 端点 |
| `/health` | MCP 健康检查 |

---

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

---

## Docker 部署

```bash
# 构建服务
backend&mcp路径下有Dockerfile，常规打包即可
也可以直接在项目根目录执行以下命令

```bash
docker build -t platform:v2.5 ./backend/ && docker build -t platform-mcp:v2.5 ./mcp/root@demo:/opt/Tiny-Platform
```

# 启动所有服务
docker compose up -d

# 查看日志
docker compose logs -f

# 验证
curl http://127.0.0.1:8000/health
curl -H "Authorization: Bearer tinyPlatform-token-2024" http://127.0.0.1:8000/api/tools
curl http://127.0.0.1:8080/health   # MCP 健康检查

# 停止
docker compose down
```

---

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

---

## 新增工具流程

1. 编写 Shell 脚本放入 `scripts/`，遵循 JSON 输出规范
2. 在 `backend/app/registry/tools.yaml` 添加工具定义
3. 热重载：`python3 -c "from app.registry import tool_registry; tool_registry.reload()"`（或重启后端）
