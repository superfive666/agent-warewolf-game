# 一个镜像同时充当 agent 容器和编排端。
#   agent 容器：  python3 -m werewolf.agent_server
#   编排端：      python3 run_server.py  /  python3 run_game.py
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    WEREWOLF_MEMORY_DIR=/memory

WORKDIR /app

# 只有 LLM 后端需要第三方依赖；规则 bot 是零依赖的
COPY requirements-llm.txt .
RUN pip install --no-cache-dir -r requirements-llm.txt

COPY werewolf/ ./werewolf/
COPY web/ ./web/
COPY run_server.py run_game.py ./

# agent 的私有 memory 挂载点。容器被销毁时这个卷要保留下来。
VOLUME ["/memory"]
RUN mkdir -p /memory

EXPOSE 8100 8000

# 默认以 agent 身份启动；编排端用 command 覆盖
CMD ["python3", "-m", "werewolf.agent_server"]
