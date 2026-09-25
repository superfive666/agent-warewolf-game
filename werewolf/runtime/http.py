"""通过 HTTP 驱动一个跑在容器里的 agent。Docker 和 k8s 运行时都基于它。"""
from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

from ..views import PlayerView
from .base import RuntimeReleased


class AgentUnreachable(RuntimeError):
    pass


class HttpRuntime:
    """把视角发给容器，拿回动作。容器的地址由子类负责提供。"""

    def __init__(self, seat: int, base_url: str, *, label: str = "",
                 timeout: float = 600.0, ready_timeout: float = 120.0) -> None:
        self.seat = seat
        self.base_url = base_url.rstrip("/")
        self.label = label or f"http-seat-{seat}"
        self.timeout = timeout
        self.ready_timeout = ready_timeout
        self._released = False
        self._last_session: dict | None = None

    # ---------- HTTP ----------
    def _request(self, path: str, body: dict | None = None, timeout: float | None = None) -> dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"} if data else {},
            method="POST" if data is not None else "GET",
        )
        with urllib.request.urlopen(req, timeout=timeout or self.timeout) as r:
            return json.loads(r.read() or b"{}")

    def _port_open(self) -> bool:
        """先用裸 socket 探端口，再发 HTTP。

        直接对没起来的端口发 urllib 请求会在连接被拒的路径上漏 socket
        （测试里表现为 ResourceWarning），而容器启动期间这种失败会有几十次。
        """
        u = urllib.parse.urlparse(self.base_url)
        try:
            with socket.create_connection((u.hostname, u.port or 80), timeout=1):
                return True
        except OSError:
            return False

    def wait_ready(self) -> None:
        deadline = time.time() + self.ready_timeout
        last = None
        while time.time() < deadline:
            if self._port_open():
                try:
                    self._request("/healthz", timeout=5)
                    return
                except Exception as exc:
                    last = exc
            time.sleep(0.3)
        raise AgentUnreachable(f"{self.label} 在 {self.ready_timeout}s 内没有就绪：{last}")

    # ---------- PlayerRuntime ----------
    def start(self) -> None:
        self.wait_ready()

    def act(self, view: PlayerView, error: str | None = None) -> dict:
        if self._released:
            raise RuntimeReleased(f"{self.label} 已经被销毁了，不该再被 ask")
        out = self._request("/act", {"view": view.as_dict(), "error": error})
        if "error" in out:
            raise RuntimeError(out["error"])
        return out["action"]

    def snapshot_session(self) -> dict:
        """容器还活着的时候把会话抓出来。抓失败就退回上一次的快照。"""
        try:
            self._last_session = self._request("/session", timeout=30)
        except Exception as exc:
            if self._last_session is None:
                return {"error": f"取会话失败：{type(exc).__name__}: {exc}"}
        return dict(self._last_session or {})

    def release(self, reason: str) -> None:
        self._released = True

    @property
    def released(self) -> bool:
        return self._released
