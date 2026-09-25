# 一个镜像同时充当 agent 容器和编排端。
#   agent 容器：  werewolf-agent   （= python3 -m werewolf.agent_server）
#   编排端：      werewolf-server  /  werewolf
#
# 编排端自带一份前端构建产物（web/dist），单镜像就能直接打开页面。
# 前端想单独部署（nginx 静态托管）时用 web/Dockerfile。

# ───────── 前端构建 ─────────
FROM node:22-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# ───────── 编排端 / agent ─────────
FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    WEREWOLF_MEMORY_DIR=/memory \
    WEREWOLF_WEB_DIR=/app/web/dist \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# 先只拷依赖清单，装依赖这一层就能被缓存住（README.md 是 pyproject 的 readme，构建元数据要用）
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-install-project --extra all

COPY werewolf/ ./werewolf/
COPY --from=web /web/dist ./web/dist/
RUN uv sync --locked --extra all

# agent 的私有 memory 挂载点。容器被销毁时这个卷要保留下来。
VOLUME ["/memory"]
RUN mkdir -p /memory

EXPOSE 8100 8000

# 默认以 agent 身份启动；编排端用 command 覆盖
CMD ["werewolf-agent"]
