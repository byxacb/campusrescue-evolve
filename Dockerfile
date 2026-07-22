# BYO-MCP servers — 统一 Dockerfile（适用于 5 个 server）
FROM python:3.12-slim

WORKDIR /app

# 安装依赖
RUN pip install --no-cache-dir fastmcp==3.4.4 uvicorn==0.51.0 httpx==0.28.1 google-api-python-client>=2.179.0 google-auth-httplib2>=0.2.0

# 复制 server 代码（构建参数 SERVER_NAME 决定）
ENV SERVER_NAME=audit_report
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

# 复制整个 mcp_servers 目录（让 server 间可共享 evaluator 代码）
COPY . /app/

EXPOSE 8080

# 启动命令
CMD python mcp_servers/${SERVER_NAME}/server.py
