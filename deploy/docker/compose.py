#!/usr/bin/env python3
"""生成单机部署用的 docker-compose.yml：N 个 agent 容器 + 1 个编排端。

    python3 deploy/docker/compose.py -n 12 --backend llm --model claude-opus-5 > compose.yml
    docker compose -f compose.yml up

说明：正常玩的时候**不需要**这个文件 —— `--deployment docker` 会由编排端
用 docker CLI 按需起容器、并在玩家离场时立刻销毁。
这里生成的 compose 是给"想先手工把一桌拉起来看看"的场景用的。
"""
from __future__ import annotations

import argparse
import json
import sys


def render(n: int, backend: str, model: str, effort: str, image: str) -> str:
    lines = ["# 由 deploy/docker/compose.py 生成", "services:"]
    for seat in range(1, n + 1):
        lines += [
            f"  agent-{seat:02d}:",
            f"    image: {image}",
            f"    container_name: wolf-seat-{seat:02d}",
            "    command: [\"werewolf-agent\"]",
            "    environment:",
            f"      WEREWOLF_SEAT: \"{seat}\"",
            f"      WEREWOLF_BACKEND: \"{backend}\"",
            f"      WEREWOLF_MODEL: \"{model}\"",
            f"      WEREWOLF_EFFORT: \"{effort}\"",
            "      WEREWOLF_MEMORY_DIR: \"/memory\"",
            "      WEREWOLF_PORT: \"8100\"",
            "      ANTHROPIC_API_KEY: \"${ANTHROPIC_API_KEY:-}\"",
            "    volumes:",
            # 卷的生命周期长于容器：容器删了，agent 的笔记还在
            f"      - mem-{seat:02d}:/memory",
            "    networks: [wolf]",
            "    deploy:",
            "      resources:",
            "        limits: {cpus: '1.0', memory: 1g}",
            "    security_opt: [\"no-new-privileges:true\"]",
        ]
    lines += [
        "  orchestrator:",
        f"    image: {image}",
        "    command: [\"werewolf-server\", \"--host\", \"0.0.0.0\"]",
        "    environment:",
        "      WEREWOLF_STORE: \"sqlite:/data/werewolf.db\"",
        "      ANTHROPIC_API_KEY: \"${ANTHROPIC_API_KEY:-}\"",
        "    ports: [\"8000:8000\"]",
        "    volumes: [\"store:/data\"]",
        "    networks: [wolf]",
        f"    depends_on: [{', '.join(f'agent-{s:02d}' for s in range(1, n + 1))}]",
        "",
        "networks:",
        "  wolf: {driver: bridge}",
        "",
        "volumes:",
        "  store: {}",
    ]
    lines += [f"  mem-{s:02d}: {{}}" for s in range(1, n + 1)]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-n", "--n-players", type=int, default=12)
    ap.add_argument("--backend", default="heuristic", choices=["heuristic", "llm"])
    ap.add_argument("--model", default="claude-opus-5")
    ap.add_argument("--effort", default="medium")
    ap.add_argument("--image", default="werewolf-agent:latest")
    a = ap.parse_args()
    sys.stdout.write(render(a.n_players, a.backend, a.model, a.effort, a.image))
