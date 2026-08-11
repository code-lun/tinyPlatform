# ============================================================
# 运维工具平台 - MCP 服务器容器镜像
# 运行在 Streamable HTTP 模式，供 Claude Code 通过 HTTP 连接
# ============================================================

FROM python:3.11-alpine3.21

WORKDIR /app

# 安装依赖（利用层缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制 MCP 服务代码
COPY server.py .

EXPOSE 8080

# HTTP 传输模式 + 端口
ENV MCP_TRANSPORT=http
ENV MCP_HTTP_PORT=8080

CMD ["python3", "server.py"]
