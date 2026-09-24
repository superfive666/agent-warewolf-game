"""单机部署：每个座位一个 Docker 容器。

用 docker CLI 而不是 SDK，这样编排端零依赖。

生命周期：
  start()   docker volume create（memory 卷）→ docker run -d → 等 /healthz
  release() 先把会话抓出来（由 RuntimePool 负责）→ docker rm -f 容器
            **卷不删** —— agent 的私有笔记本要活得比容器长
"""
from __future__ import annotations

import shutil
import socket
import subprocess

from .http import HttpRuntime


def docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        subprocess.run(["docker", "info"], capture_output=True, timeout=10, check=True)
        return True
    except Exception:
        return False


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class DockerRuntime(HttpRuntime):
    def __init__(self, seat: int, spec, *, game_id: str, image: str,
                 memory_root: str = "", env: dict | None = None,
                 cpus: str = "1", memory_limit: str = "1g",
                 network: str | None = None, label: str = "", **kw) -> None:
        self.game_id = game_id
        self.image = image
        self.spec = spec
        self.env = dict(env or {})
        self.cpus = cpus
        self.memory_limit = memory_limit
        self.network = network
        self.container = f"wolf-{game_id}-seat-{seat:02d}"
        #: 卷的生命周期长于容器，销毁容器不会丢掉 agent 的笔记
        self.volume = memory_root or f"wolf-{game_id}-mem-{seat:02d}"
        self.host_port = _free_port()
        super().__init__(seat, f"http://127.0.0.1:{self.host_port}",
                         label=label or f"docker:{spec.label}", **kw)

    # ------------------------------------------------------------------
    def _run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(["docker", *args], capture_output=True, text=True,
                              check=check, timeout=120)

    def start(self) -> None:
        self._run("volume", "create", self.volume)
        self._run("rm", "-f", self.container, check=False)

        env = {
            "WEREWOLF_SEAT": str(self.seat),
            "WEREWOLF_BACKEND": self.spec.backend,
            "WEREWOLF_MODEL": self.spec.model,
            "WEREWOLF_EFFORT": self.spec.effort,
            "WEREWOLF_MAX_TOKENS": str(self.spec.max_tokens),
            "WEREWOLF_MEMORY_DIR": "/memory",
            "WEREWOLF_PORT": "8100",
            **self.env,
        }
        cmd = ["run", "-d", "--name", self.container,
               "--cpus", self.cpus, "--memory", self.memory_limit,
               # agent 不需要对外发起任何连接（除了调模型 API），也不需要特权
               "--security-opt", "no-new-privileges",
               "-v", f"{self.volume}:/memory",
               "-p", f"127.0.0.1:{self.host_port}:8100"]
        if self.network:
            cmd += ["--network", self.network]
        for k, v in env.items():
            cmd += ["-e", f"{k}={v}"]
        cmd += [self.image]
        self._run(*cmd)
        self.wait_ready()

    def release(self, reason: str) -> None:
        """销毁容器。**不删卷** —— 会话和笔记要留下来复盘。"""
        if self._released:
            return
        self._run("rm", "-f", self.container, check=False)
        super().release(reason)

    def logs(self, tail: int = 50) -> str:
        r = self._run("logs", "--tail", str(tail), self.container, check=False)
        return (r.stdout or "") + (r.stderr or "")
