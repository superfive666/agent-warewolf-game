"""座位运行时：决定 agent 跑在哪里。"""
from __future__ import annotations

from .base import LocalRuntime, PlayerRuntime, RuntimePool, RuntimeReleased  # noqa: F401
from .local_proc import SubprocessRuntime  # noqa: F401

#: 支持的部署模式
DEPLOYMENTS = {
    "inprocess": "同进程 —— 最快，没有隔离，用于测试和跑批",
    "subprocess": "每座位一个进程 —— 进程隔离 + 独立 memory 目录，不需要 Docker",
    "docker": "每座位一个容器 —— 单机部署",
    "k8s": "每座位一个 Pod —— 集群部署",
}


def build_pool(state, lineup, *, deployment="inprocess", store=None, game_id="",
               image="werewolf-agent:latest", env=None, verbose=False, **kw):
    """按部署模式给每个座位建运行时，并装进 RuntimePool。"""
    roles = {s: state.players[s].role.value for s in state.seats}
    runtimes = {}

    if deployment == "inprocess":
        agents = lineup.build_agents(state, verbose=verbose)
        for seat in state.seats:
            runtimes[seat] = LocalRuntime(seat, agents[seat], label=lineup.specs[seat].label)
    elif deployment == "subprocess":
        for seat in state.seats:
            runtimes[seat] = SubprocessRuntime(
                seat, lineup.specs[seat], game_id=game_id,
                env={**(env or {}), "WEREWOLF_ROLE": roles[seat],
                     "WEREWOLF_SEED": str(state.config.seed or 0)}, **kw)
    elif deployment == "docker":
        from .docker import DockerRuntime

        for seat in state.seats:
            runtimes[seat] = DockerRuntime(
                seat, lineup.specs[seat], game_id=game_id, image=image,
                env={**(env or {}), "WEREWOLF_ROLE": roles[seat],
                     "WEREWOLF_SEED": str(state.config.seed or 0)}, **kw)
    elif deployment == "k8s":
        from .k8s import K8sRuntime

        for seat in state.seats:
            runtimes[seat] = K8sRuntime(
                seat, lineup.specs[seat], game_id=game_id, image=image,
                env={**(env or {}), "WEREWOLF_ROLE": roles[seat],
                     "WEREWOLF_SEED": str(state.config.seed or 0)}, **kw)
    else:
        raise ValueError(f"不认识的部署模式 {deployment!r}，可选：{sorted(DEPLOYMENTS)}")

    return RuntimePool(runtimes, store=store, game_id=game_id, roles=roles)


__all__ = ["PlayerRuntime", "LocalRuntime", "SubprocessRuntime", "RuntimePool",
           "RuntimeReleased",
           "DEPLOYMENTS", "build_pool"]
