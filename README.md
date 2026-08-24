# tinyPlatform

> **Shell 脚本 → REST API → MCP 协议 → LLM Agent**
> 一个轻量级运维工具编排平台，让存量脚本秒变 AI 可调用能力。

## 1. 项目简介

tinyPlatform 解决的核心问题是：**如何让现有的运维脚本同时服务于人和 AI**。

它不需要你重写业务逻辑，只需将 Shell/Python 脚本放入指定目录并简单注册，即可自动获得：
-   **标准化 REST API**：供前端、CI/CD 流水线或 curl 直接调用。
-   **MCP Tool**：供 Claude Code、Cursor、自研 Agent 等通过自然语言驱动。

### 适用场景

| 场景 | 价值 |
| :--- | :--- |
| **AI IDE 集成** | 在 Cursor/Claude Code 中用自然语言执行巡检、重启、查日志等操作，无需离开编辑器。 |
| **存量脚本 API 化** | 老脚本不用改代码，注册即暴露 HTTP 接口，统一鉴权与日志。 |
| **Agent 工具链** | AI 根据告警自动选择诊断脚本，再调用修复脚本，形成闭环。 |
| **CI/CD 原子操作** | Jenkins/GitLab CI 通过标准 API 调用运维动作，告别 `ssh + shell` 硬编码。 |
| **第三方 API 封装** | 将云厂商 SDK 或复杂 curl 命令包装成简单脚本，收敛调用入口。 |

### 设计原则

-   **脚本零侵入**：纯 Bash/Python 编写，不依赖平台框架，单独也能跑。
-   **约定大于配置**：输出符合 JSON 规范即可被识别，无需额外适配层。
-   **安全隔离**：subprocess 独立进程执行 + Bearer Token 鉴权 + 白名单机制。
-   **渐进式接入**：可以只用 API 层，也可以叠加 MCP 层，按需启用。

---

## 2. 技术栈速览

| 组件 | 选型 | 说明 |
| :--- | :--- | :--- |
| **API 框架** | FastAPI + Uvicorn | 异步高性能，自带 OpenAPI 文档，Pydantic 校验参数 |
| **MCP 实现** | mcp (Python SDK ≥2.0) | 支持 stdio（本地调试）和 Streamable HTTP（远程部署） |
| **脚本执行** | subprocess | 标准库，超时控制，环境变量传参防注入 |
| **配置管理** | YAML + .env | 工具定义走 YAML，敏感信息走环境变量 |
| **容器化** | Docker Compose | 一键拉起 backend + mcp，支持健康检查与卷挂载 |
| **日志** | logging | stderr 彩色输出（开发）+ 按天轮转文件（生产） |

---

## 3. 快速上手

### 3.1 克隆 & 安装

```bash
# 克隆项目
cd /opt && git clone https://github.com/code-lun/tinyPlatform.git && cd tinyPlatform

# 后端依赖
cd backend
python3 -m venv venv && ./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

# MCP 依赖
cd ../mcp
python3 -m venv venv && ./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
```

### 3.2 配置

后端和 MCP 各自有 `.env` 文件，默认值可直接使用。关键项：

| 变量                     | 默认值                       | 说明                             |
| :--------------------- | :------------------------ | :----------------------------- |
| `API_TOKEN`            | `tinyPlatform-token-2024` | Bearer Token，生产环境务必修改          |
| `SCRIPTS_DIR`          | `../scripts`              | 脚本目录相对路径                       |
| `LOG_LEVEL`            | `info`                    | 日志级别（debug/info/warning/error） |
| `EXECUTOR_MAX_WORKERS` | `cpu_count + 4`           | 线程池大小（两核则为2+4）                 |
> ⚠️ **注意**：MCP 默认使用 stdio 模式，如需 HTTP 模式请在 `mcp/.env` 中调整传输配置。
#### 环境变量优先级说明
优先级（由高到低）：
    1. Shell 环境变量（export / docker-compose environment）
    2. backend/.env 文件
    3. 本文件中的默认值
敏感环境变量，一律使用env的方式，其他方式会被提交到仓库，可能造成泄露

### 3.3 启动服务

```bash
# 启动后端（端口 8000）
cd backend && source venv/bin/activate
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# 启动 MCP（端口 8080，需后端已就绪）
cd ../mcp && source venv/bin/activate
python3 server.py &
```

---

## 4. 测试验证

### 4.1 后端 API 测试

推荐使用 [WebCurl](https://github.com/o8oo8o/WebCurl)（网页版 Postman）或命令行 curl。

```bash
# 健康检查（无需 Token）
curl http://127.0.0.1:8000/health

# 获取工具列表
curl -H "Authorization: Bearer tinyPlatform-token-2024" \
     http://127.0.0.1:8000/api/tools

# 执行工具（GET）
curl -H "Authorization: Bearer tinyPlatform-token-2024" \
     http://127.0.0.1:8000/api/tools/get_time

# 执行工具（POST 带参数）
curl -H "Authorization: Bearer tinyPlatform-token-2024" \
     -X POST http://127.0.0.1:8000/api/tools/sys_check \
     -H "Content-Type: application/json" -d '{}'
```

### 4.2 MCP 功能测试

使用官方 [MCP Inspector](https://github.com/modelcontextprotocol/inspector)：

```bash
# 安装（v1 版本，仅支持本地图形环境）
npm install -g @modelcontextprotocol/inspector@1

# 启动后浏览器自动打开
mcp-inspector
```

连接地址填写：`http://localhost:8080/mcp/`

可在界面中浏览工具列表、填写参数、查看返回结果，是

### 4.3 功能截图
#### cli获取工具清单
![alt text](png/image.png)

#### mcp api调用测试成功（cc调用）stdio模式
![alt text](png/image-1.png)

#### mcp调用测试（使用inspector1.0）
![alt text](png/image-2.png)

#### 调用日志
![alt text](png/image-3.png)

---

## 5. 架构与调用链路

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────┐
│ Claude Code │────▶│  MCP Server  │────▶│ FastAPI     │────▶│ Shell    │
│ Cursor      │stdio│  (8080)      │HTTP │ Backend     │sub  │ Scripts  │
│ Agent       │/HTTP│              │     │ (8000)      │proc │          │
└─────────────┘     └──────────────┘     └─────────────┘     └──────────┘
```

| 层 | 目录 | 职责 |
| :--- | :--- | :--- |
| 脚本层 | `scripts/` | 业务逻辑，JSON 输出，通过 `TOOL_PARAM_{KEY}` 接收参数 |
| API 层 | `backend/` | 路由注册、鉴权、subprocess 执行、日志记录 |
| MCP 层 | `mcp/` | 协议转换，将 REST 接口映射为 MCP Tool |
| 容器层 | `docker-compose.yml` | 编排部署、健康检查、脚本卷挂载热更新 |

---

## 6. Docker 部署
```bash
# 构建镜像（在项目根目录执行）
docker build -t platform:v2.5 ./backend/
docker build -t platform-mcp:v2.5 ./mcp/

# 启动
docker compose up -d

# 查看日志
docker compose logs -f

# 验证
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8080/health

# 停止
docker compose down
```

> 💡 **提示**：`scripts/` 目录通过 volume 挂载，修改脚本后无需重建镜像，重启后端或触发热重载即可生效。

---

## 7. 脚本编写规范

所有脚本**必须**输出以下 JSON 格式，否则平台无法正确解析：

```json
{
  "status": "success",
  "code": 0,
  "message": "系统资源正常",
  "data": {
    "cpu_usage": "12%",
    "mem_usage": "45%"
  }
}
```

**错误码约定：**

| code | 含义 |
| :--- | :--- |
| 0 | 成功 |
| 1 | 通用错误 |
| 2 | 命令/依赖不可用 |
| 3 | 数据异常/参数非法 |

**参数接收方式：**
通过环境变量 `TOOL_PARAM_{KEY}` 读取，**不要**从命令行 `$1 $2` 读取，避免注入风险。

```bash
# 示例：读取 tools.yaml 中定义的 host 参数
HOST="${TOOL_PARAM_HOST:-localhost}"
```

---

## 8. 新增工具三步走

1.  **写脚本**：放入 `scripts/`，遵循上述 JSON 输出规范
2.  **注册**：在 `backend/app/registry/tools.yaml` 添加定义（名称、路径、参数、超时等）
3.  **生效**：重启后端，或执行热重载命令：(目前建议重启后端)
    ```bash
    python3 -c "from app.registry import tool_registry; tool_registry.reload()"
    ```

> ✅ 注册后即可通过 `/api/tools/{name}` 调用，MCP 端也会自动发现新工具，无需额外配置。

## 9.PR
可以提PR到develop分支，我审核后，没有问题就会通过