# ============================================================
# 运维工具平台 - 后端容器镜像
# ============================================================

FROM python:3.11-alpine3.21

WORKDIR /app

# 安装系统依赖（bash 用于执行 Shell 脚本）
RUN apk add --no-cache bash

# 安装 Python 依赖（利用 Docker 层缓存，先复制依赖文件）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app/ ./app/

# 脚本目录（运行时通过 volume 挂载或 COPY）
RUN mkdir -p /scripts

EXPOSE 8000

# 使用 python -m app.main 启动（支持 SIGTERM 优雅退出）
CMD ["python3", "-m", "app.main"]
