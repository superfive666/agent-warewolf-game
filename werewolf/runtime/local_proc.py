"""进程隔离运行时：每个座位一个独立的 OS 进程（不需要 Docker）。

用途有两个：
  1. 没装 Docker 的机器上也能拿到真正的进程级隔离和独立 memory 目录
  2. 它和 Docker / k8s 走**完全相同的 HTTP 契约**，所以能在 CI 里验证
     那两条路径的全部逻辑（起→就绪→act→抓会话→销毁），不需要真的有集群
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path

from .http import HttpRuntime


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class SubprocessRuntime(HttpRuntime):
    def __init__(self, seat: int, spec, *, game_id: str, memory_root: str | Path = "runs/memory",
                 env: dict | None = None, label: str = "", **kw) -> None:
        self.seat = seat
        self.spec = spec
        self.game_id = game_id
        #: memory 目录独立于进程，进程被杀掉笔记还在
        self.memory_root = Path(memory_root) / game_id
        self.env = dict(env or {})
        self.port = _free_port()
        self.proc: subprocess.Popen | None = None
        super().__init__(seat, f"http://127.0.0.1:{self.port}",
                         label=label or f"proc:{spec.label}", **kw)

    def start(self) -> None:
        self.memory_root.mkdir(parents=True, exist_ok=True)
        env = {
            **os.environ,
            "WEREWOLF_SEAT": str(self.seat),
            "WEREWOLF_BACKEND": self.spec.backend,
            "WEREWOLF_MODEL": self.spec.model,
            "WEREWOLF_EFFORT": self.spec.effort,
            "WEREWOLF_BASE_URL": self.spec.base_url,
            "WEREWOLF_API_KEY_ENV": self.spec.api_key_env,
            # 显式给了密钥就注进去；没给就靠容器自己的环境变量
            **({self.spec.api_key_env: self.spec.api_key} if self.spec.api_key else {}),
            "WEREWOLF_MAX_TOKENS": str(self.spec.max_tokens),
            "WEREWOLF_MEMORY_DIR": str(self.memory_root),
            "WEREWOLF_PORT": str(self.port),
            **{k: str(v) for k, v in self.env.items()},
        }
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "werewolf.agent_server"],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            cwd=Path(__file__).resolve().parent.parent.parent,
        )
        self.wait_ready()

    def release(self, reason: str) -> None:
        """杀进程。**memory 目录保留** —— 会话和笔记要留下来复盘。"""
        if self._released:
            return
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        super().release(reason)

    def logs(self, tail: int = 50) -> str:
        if not self.proc or not self.proc.stdout:
            return ""
        try:
            return self.proc.stdout.read().decode(errors="replace")[-4000:]
        except Exception:
            return ""
