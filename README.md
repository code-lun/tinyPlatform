# Tiny-Platform

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
