# Tiny-Platform
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
│   │   └── utils/
│   │       └── executor.py          # 封装 subprocess 执行脚本，解析 JSON
│   ├── requirements.txt             # fastapi, uvicorn, python-multipart 等
│   ├── Dockerfile
│   └── .env.example                 # 环境变量示例（如脚本路径、日志级别）
│
├── mcp/                             # ③ MCP 服务器（独立服务，可选）
│   ├── server.py                    # MCP 协议实现，调用 backend API 或直接调用脚本
│   ├── requirements.txt             # mcp-sdk, httpx 等
│   ├── Dockerfile
│   └── .env.example
│
├── frontend/                        # ④ 前端（纯静态，解耦）
│   ├── index.html                   # 主页面，调用 backend API
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   └── app.js                   # fetch 调用后端，渲染数据
│   ├── nginx.conf                   # Nginx 配置（用于容器）
│   └── Dockerfile                   # 基于 nginx:alpine 托管静态文件
│
└── .github/                         # (可选) CI/CD 自动构建镜像
    └── workflows/
        └── build.yml