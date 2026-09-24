"""一局对局的完整装配：存储 + 座位运行时 + 引擎。

这是唯一需要知道"部署模式"的地方。引擎本身对容器一无所知 ——
它只认识 `runtime.act(view)`，所以同一套规则在同进程/进程/容器/Pod 里跑出来完全一样。
"""
from __future__ import annotations

import uuid

from .engine import Engine
from .lineup import Lineup
from .replay import result_summary
from .runtime import build_pool
from .state import GameConfig, new_game
from .store import open_store


class GameSession:
    def __init__(self, config: GameConfig, lineup: Lineup, *,
                 deployment: str = "inprocess",
                 store_uri: str = "sqlite:runs/werewolf.db",
                 game_id: str | None = None,
                 image: str = "werewolf-agent:latest",
                 env: dict | None = None,
                 verbose: bool = False,
                 store=None,
                 **runtime_kw) -> None:
        self.id = game_id or uuid.uuid4().hex[:12]
        self.config = config
        self.lineup = lineup
        self.deployment = deployment
        self.store = store if store is not None else open_store(store_uri)
        self.state = new_game(config)
        self.pool = build_pool(
            self.state, lineup, deployment=deployment, store=self.store,
            game_id=self.id, image=image, env=env, verbose=verbose, **runtime_kw,
        )
        self.engine: Engine | None = None

    # ------------------------------------------------------------------
    def run(self, *, on_event=None, view_recorder=None):
        self.store.create_game(
            self.id, config=self.config.as_dict(),
            lineup=self.lineup.as_list(), deployment=self.deployment,
        )
        try:
            self.pool.start_all()
            self.engine = Engine(
                self.state, self.pool.runtimes,
                on_event=on_event, view_recorder=view_recorder,
                store=self.store, game_id=self.id, pool=self.pool,
            )
            return self.engine.run()
        except BaseException as exc:
            # 崩了也要把已经拿到的会话存下来，再把容器收干净
            self.pool.release_all("aborted")
            self.store.finish_game(self.id, {
                **result_summary(self.state, self.lineup),
                "status": "failed", "error": f"{type(exc).__name__}: {exc}",
            })
            raise
        finally:
            # release_all 是幂等的：正常结束时引擎已经放过了，这里只兜底漏网的
            self.pool.release_all("game_over")

    def result(self) -> dict:
        return result_summary(self.state, self.lineup)


def run_game(config: GameConfig, lineup: Lineup, **kw) -> GameSession:
    s = GameSession(config, lineup, **kw)
    s.run()
    return s
