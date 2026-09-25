# 一个镜像同时充当 agent 容器和编排端。
#   agent 容器：  werewolf-agent   （= python3 -m werewolf.agent_server）
#   编排端：      werewolf-server  /  werewolf
FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    WEREWOLF_MEMORY_DIR=/memory \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# 先只拷依赖清单，装依赖这一层就能被缓存住
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --extra all

COPY werewolf/ ./werewolf/
COPY web/ ./web/
RUN uv sync --locked --extra all

# agent 的私有 memory 挂载点。容器被销毁时这个卷要保留下来。
VOLUME ["/memory"]
RUN mkdir -p /memory

EXPOSE 8100 8000

# 默认以 agent 身份启动；编排端用 command 覆盖
CMD ["werewolf-agent"]
