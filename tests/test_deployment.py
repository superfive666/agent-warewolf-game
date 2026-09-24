"""部署与会话存储测试。

核心约束只有一条，但它很硬：
    **玩家离场就销毁运行时，但会话必须先存下来。**
所以这里反复验证的是"顺序"和"不丢"。
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from werewolf.lineup import Lineup
from werewolf.roles import Role
from werewolf.runtime import (
    DEPLOYMENTS, LocalRuntime, RuntimePool, RuntimeReleased, build_pool)
from werewolf.session import GameSession
from werewolf.state import GameConfig, new_game
from werewolf.store import FileStore, NullStore, SqliteStore, open_store
from werewolf.views import PlayerView, build_player_view


class TestStores(unittest.TestCase):
    """两种后端走同一个接口，行为必须一致。"""

    def _roundtrip(self, store):
        store.create_game("g1", config={"n_players": 12}, lineup=[{"seat": 1}],
                          deployment="docker")
        for i in range(1, 6):
            store.append_event("g1", {"seq": i, "day": 1, "phase": "P", "type": "t",
                                      "audience": "public", "text": f"e{i}", "actor": None})
        store.append_turn("g1", {"turn": 1, "seat": 3, "action_type": "speech",
                                 "accepted": True, "thought": "我在想", "action": {"a": 1}})
        store.save_agent_session("g1", 3, {"backend": "llm", "model": "claude-opus-5",
                                           "messages": [{"role": "user", "content": "x"}],
                                           "memory_uri": "vol://m", "release_reason": "exiled"})
        store.finish_game("g1", {"winner": "WOLF", "reason": "屠民", "days": 4})

        self.assertEqual(len(store.load_events("g1")), 5)
        self.assertEqual(len(store.load_events("g1", since=3)), 2)
        self.assertEqual(store.load_turns("g1")[0]["thought"], "我在想")
        sess = store.load_agent_sessions("g1")[0]
        self.assertEqual(sess["release_reason"], "exiled")
        self.assertEqual(sess["messages"], [{"role": "user", "content": "x"}])
        g = store.load_game("g1")
        self.assertEqual(g["winner"], "WOLF")
        self.assertEqual(len(store.list_games()), 1)

    def test_sqlite(self):
        with tempfile.TemporaryDirectory() as d:
            self._roundtrip(SqliteStore(Path(d) / "w.db"))

    def test_files(self):
        with tempfile.TemporaryDirectory() as d:
            self._roundtrip(FileStore(Path(d) / "runs"))

    def test_open_store_uris(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsInstance(open_store(f"sqlite:{d}/a.db"), SqliteStore)
            self.assertIsInstance(open_store(f"files:{d}/r"), FileStore)
            self.assertIsInstance(open_store("none:"), NullStore)
            with self.assertRaises(ValueError):
                open_store("mysql://nope")

    def test_events_are_written_while_the_game_runs_not_at_the_end(self):
        """崩在半路也要有东西可看，所以必须边跑边写。"""
        with tempfile.TemporaryDirectory() as d:
            store = SqliteStore(Path(d) / "w.db")
            seen = []

            class Spy(SqliteStore):
                pass

            s = GameSession(GameConfig(seed=5, n_players=9), Lineup.uniform(9),
                            store=store, game_id="mid")
            orig = store.append_event

            def spy(gid, e):
                seen.append(len(store.load_events("mid")))
                orig(gid, e)

            store.append_event = spy
            s.run()
            # 每写一条之前库里都应该已经有前面那些 —— 说明不是最后一次性 flush
            self.assertGreater(len(seen), 50)
            self.assertEqual(seen[10], 10)


class TestViewSerialization(unittest.TestCase):
    """容器化的前提：视角能无损地序列化再还原。"""

    def test_roundtrip_preserves_everything(self):
        st = new_game(GameConfig(seed=1))
        st.day = 1
        for seat in st.seats:
            v = build_player_view(st, seat, action_type="speech")
            self.assertEqual(PlayerView.from_dict(v.as_dict()).as_dict(), v.as_dict())

    def test_roundtrip_keeps_wolf_team_isolation(self):
        st = new_game(GameConfig(seed=1))
        st.day = 1
        wolf, good = st.wolf_seats()[0], next(s for s in st.seats if not st.is_wolf(s))
        self.assertIsNotNone(PlayerView.from_dict(
            build_player_view(st, wolf, action_type="speech").as_dict()).wolf_team)
        self.assertIsNone(PlayerView.from_dict(
            build_player_view(st, good, action_type="speech").as_dict()).wolf_team)


class TestReleaseLifecycle(unittest.TestCase):
    def _session(self, d, deployment="inprocess", seed=21, n=9):
        return GameSession(GameConfig(seed=seed, n_players=n), Lineup.uniform(n),
                           deployment=deployment, store_uri=f"sqlite:{d}/w.db",
                           memory_root=f"{d}/memory" if deployment == "subprocess" else None)

    def test_every_seat_is_released_exactly_once_with_a_reason(self):
        with tempfile.TemporaryDirectory() as d:
            s = self._session(d)
            st = s.run()
            for seat, rt in s.pool.runtimes.items():
                self.assertTrue(rt.released, f"{seat}号 的运行时没有被销毁")
            sessions = {x["seat"]: x for x in s.store.load_agent_sessions(s.id)}
            self.assertEqual(set(sessions), set(st.seats), "有座位的会话没存下来")
            for seat, sess in sessions.items():
                self.assertTrue(sess["release_reason"], f"{seat}号 没有释放原因")

    def test_release_reason_matches_how_the_player_left(self):
        with tempfile.TemporaryDirectory() as d:
            s = self._session(d)
            st = s.run()
            sessions = {x["seat"]: x for x in s.store.load_agent_sessions(s.id)}
            for seat in st.seats:
                p = st.players[seat]
                reason = sessions[seat]["release_reason"]
                if p.alive:
                    self.assertEqual(reason, "game_over", f"{seat}号 还活着却提前被销毁了")
                else:
                    self.assertEqual(reason, p.died_cause,
                                     f"{seat}号 的释放原因和死因对不上")

    def test_a_dying_player_is_not_released_before_its_last_words(self):
        """被票出的人还要留遗言、猎人还要开枪 —— 死了不等于能立刻拆。"""
        with tempfile.TemporaryDirectory() as d:
            s = self._session(d)
            released_at: dict[int, int] = {}
            pool = s.pool
            orig = pool.release

            def spy(seat, reason):
                released_at[seat] = len(s.state.event_log)
                orig(seat, reason)

            pool.release = spy
            st = s.run()

            kinds = ("last_words", "hunter_shot", "badge")
            for e in st.event_log:
                if e.type in kinds and e.actor in released_at:
                    self.assertLess(
                        e.seq, released_at[e.actor],
                        f"{e.actor}号 在 {e.type} 之前就被销毁了",
                    )

    def test_released_runtime_refuses_further_actions(self):
        with tempfile.TemporaryDirectory() as d:
            s = self._session(d)
            st = s.run()
            dead = next(x for x in st.seats if not st.players[x].alive)
            with self.assertRaises(RuntimeReleased):
                s.pool[dead].act(build_player_view(st, dead, action_type="speech"))

    def test_release_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            s = self._session(d)
            s.run()
            n_before = len(s.store.load_agent_sessions(s.id))
            s.pool.release_all("again")
            self.assertEqual(len(s.store.load_agent_sessions(s.id)), n_before)
            # 释放原因不应被第二次调用覆盖
            self.assertNotIn("again",
                             [x["release_reason"] for x in s.store.load_agent_sessions(s.id)])

    def test_session_is_saved_before_the_runtime_is_destroyed(self):
        """顺序错了就永远拿不回会话 —— 这条是整个设计的地基。"""
        order: list[str] = []

        class Recording(LocalRuntime):
            def snapshot_session(self):
                order.append(f"snapshot-{self.seat}")
                return super().snapshot_session()

            def release(self, reason):
                order.append(f"release-{self.seat}")
                super().release(reason)

        st = new_game(GameConfig(seed=1, n_players=9))
        from werewolf.agents.heuristic import HeuristicAgent

        rts = {s: Recording(s, HeuristicAgent(s, st.players[s].role, seed=1)) for s in st.seats}
        with tempfile.TemporaryDirectory() as d:
            store = SqliteStore(Path(d) / "w.db")
            pool = RuntimePool(rts, store=store, game_id="g")
            pool.release(3, "exiled")
            self.assertEqual(order, ["snapshot-3", "release-3"],
                             "必须先抓会话再销毁运行时")


class TestSubprocessDeployment(unittest.TestCase):
    """进程隔离：和 docker / k8s 走完全相同的 HTTP 契约，所以能在 CI 里验。"""

    def test_full_game_across_separate_processes(self):
        with tempfile.TemporaryDirectory() as d:
            s = GameSession(GameConfig(seed=21, n_players=9), Lineup.uniform(9),
                            deployment="subprocess", store_uri=f"sqlite:{d}/w.db",
                            memory_root=f"{d}/memory")
            st = s.run()
            self.assertIsNotNone(st.winner)
            # 每个 agent 都跑在自己的进程里，而且都已经退出
            for seat, rt in s.pool.runtimes.items():
                self.assertIsNotNone(rt.proc, f"{seat}号 没有起进程")
                self.assertIsNotNone(rt.proc.poll(), f"{seat}号 的进程没有退出（泄漏）")
            # 会话和 memory 卷都还在
            self.assertEqual(len(s.store.load_agent_sessions(s.id)), 9)
            self.assertTrue((Path(d) / "memory").exists(),
                            "进程销毁了，但 memory 卷必须保留")

    def test_agent_process_cannot_see_other_seats(self):
        """容器里只有自己那一个座位的视角，没有 GameState。"""
        with tempfile.TemporaryDirectory() as d:
            s = GameSession(GameConfig(seed=3, n_players=9), Lineup.uniform(9),
                            deployment="subprocess", store_uri=f"sqlite:{d}/w.db",
                            memory_root=f"{d}/memory")
            st = s.run()
            wolves = set(st.wolf_seats())
            for sess in s.store.load_agent_sessions(s.id):
                blob = json.dumps(sess, ensure_ascii=False)
                seat = sess["seat"]
                for other in st.seats:
                    if other == seat or other in wolves and seat in wolves:
                        continue
                    role = st.players[other].role
                    if role is Role.WEREWOLF and seat in wolves:
                        continue
                    self.assertNotIn(f'"{other}": "{role.value}"', blob)


class TestDeploymentWiring(unittest.TestCase):
    def test_all_deployments_are_buildable(self):
        st = new_game(GameConfig(seed=1, n_players=9))
        lineup = Lineup.uniform(9)
        pool = build_pool(st, lineup, deployment="inprocess", game_id="g")
        self.assertEqual(len(pool.runtimes), 9)
        with self.assertRaises(ValueError):
            build_pool(st, lineup, deployment="mainframe", game_id="g")

    def test_docker_and_k8s_modules_import_and_expose_the_protocol(self):
        """这台机器上不一定有 docker/k8s，但代码必须是可加载、签名正确的。"""
        from werewolf.runtime.docker import DockerRuntime
        from werewolf.runtime.k8s import K8sRuntime

        for cls in (DockerRuntime, K8sRuntime):
            for m in ("start", "act", "snapshot_session", "release"):
                self.assertTrue(callable(getattr(cls, m)), f"{cls.__name__} 缺少 {m}")

    def test_deployment_catalog_matches_what_the_frontend_offers(self):
        self.assertEqual(set(DEPLOYMENTS), {"inprocess", "subprocess", "docker", "k8s"})

    def test_k8s_rbac_cannot_delete_pvcs(self):
        """PVC 存的是 agent 的私有笔记，Pod 删了它必须还在 ——
        所以编排端根本不该有删 PVC 的权限。"""
        rbac = Path("deploy/k8s/00-namespace-rbac.yaml").read_text(encoding="utf-8")
        block = rbac.split("persistentvolumeclaims")[1].split("---")[0]
        self.assertIn("create", block)
        self.assertNotIn("delete", block)

    def test_dockerfile_declares_the_memory_volume(self):
        df = Path("deploy/docker/Dockerfile").read_text(encoding="utf-8")
        self.assertIn('VOLUME ["/memory"]', df)
        self.assertIn("werewolf.agent_server", df)


if __name__ == "__main__":
    unittest.main(verbosity=2)
