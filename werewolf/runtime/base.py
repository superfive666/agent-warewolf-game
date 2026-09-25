"""座位运行时：引擎不再直接持有 agent 对象，而是持有一个"座位句柄"。

有了这层，同一个引擎可以把 agent 跑在三种地方：
  · LocalRuntime  —— 同进程（默认，最快，用于测试和单机跑批）
  · DockerRuntime —— 每个座位一个容器（单机部署）
  · K8sRuntime    —— 每个座位一个 Pod（集群部署）

生命周期的关键约束：**玩家离场就销毁容器，但会话必须先保存下来**。
所以 release() 的实现顺序永远是：先 snapshot_session() 写进存储，再拆容器。
"""
from __future__ import annotations

from typing import Protocol

from ..views import PlayerView


class RuntimeReleased(RuntimeError):
    """对一个已经销毁的座位继续索要动作。

    所有运行时都必须抛这个，不能只有容器版抛 —— 否则生命周期的 bug
    在同进程模式下被悄悄吞掉，只有上了容器才炸。
    """


class PlayerRuntime(Protocol):
    seat: int
    label: str

    def start(self) -> None:
        """准备好这个座位（起容器/Pod，等它就绪）。"""

    def act(self, view: PlayerView, error: str | None = None) -> dict:
        """把视角交给 agent，拿回一个动作。"""

    def snapshot_session(self) -> dict:
        """导出这个座位的完整会话，用于复盘。

        返回 {backend, model, role, system_prompt, messages, usage, memory_uri}。
        **必须在 release() 之前调用** —— 容器一拆就取不到了。
        """

    def release(self, reason: str) -> None:
        """该座位再也不会被 ask() 到了，可以销毁容器/Pod。幂等。"""

    @property
    def released(self) -> bool: ...


class LocalRuntime:
    """同进程运行时：直接调用一个 Agent 对象。"""

    def __init__(self, seat: int, agent, *, label: str = "") -> None:
        self.seat = seat
        self.agent = agent
        self.label = label or getattr(agent, "name", f"seat-{seat}")
        self._released = False
        self._release_reason: str | None = None

    def start(self) -> None:
        pass

    def act(self, view: PlayerView, error: str | None = None) -> dict:
        if self._released:
            raise RuntimeReleased(f"{self.label} 已经被销毁了，不该再被 ask")
        return self.agent.act(view, error=error)

    def snapshot_session(self) -> dict:
        a = self.agent
        return {
            # 用 agent 自己声明的 provider（claude / openai / heuristic），
            # 不要靠"有没有 model 属性"猜 —— 那会把所有 LLM 都标成 llm
            "backend": getattr(a, "provider", "heuristic"),
            "model": getattr(a, "model", None),
            "system_prompt": getattr(a, "_system", None),
            "messages": list(getattr(a, "_messages", []) or []),
            "usage": dict(getattr(a, "usage", {}) or {}),
            "memory_uri": None,  # 同进程没有独立 memory 卷
            "release_reason": self._release_reason,
        }

    def release(self, reason: str) -> None:
        self._released = True
        self._release_reason = reason

    @property
    def released(self) -> bool:
        return self._released


class RuntimePool:
    """管住全部座位的运行时，并保证"先存会话、再销毁"这个顺序。"""

    def __init__(self, runtimes: dict[int, PlayerRuntime], *, store=None,
                 game_id: str = "", roles: dict[int, str] | None = None) -> None:
        self.runtimes = runtimes
        self.store = store
        self.game_id = game_id
        self.roles = roles or {}

    def __getitem__(self, seat: int):
        return self.runtimes[seat]

    def __contains__(self, seat: int) -> bool:
        return seat in self.runtimes

    def start_all(self) -> None:
        for rt in self.runtimes.values():
            rt.start()

    def release(self, seat: int, reason: str) -> None:
        """玩家离场：先把会话落库，再销毁运行时。顺序不能反。"""
        rt = self.runtimes.get(seat)
        if rt is None or rt.released:
            return
        self._persist(seat, rt, reason)
        rt.release(reason)

    def release_all(self, reason: str = "game_over") -> None:
        for seat in sorted(self.runtimes):
            self.release(seat, reason)

    def _persist(self, seat: int, rt, reason: str) -> None:
        if self.store is None or not self.game_id:
            return
        try:
            session = rt.snapshot_session()
        except Exception as exc:  # 取不到也不能拖垮整局
            session = {"error": f"{type(exc).__name__}: {exc}"}
        session.setdefault("role", self.roles.get(seat))
        session["release_reason"] = reason
        self.store.save_agent_session(self.game_id, seat, session)
