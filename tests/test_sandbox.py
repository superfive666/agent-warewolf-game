"""沙箱新增能力的测试：自爆、可变人数、发言字数、迭代上限、心路历程、Web 服务。"""
from __future__ import annotations

import json
import threading
import unittest
import urllib.request
from collections import Counter

from werewolf import actions as A
from werewolf.agents.heuristic import HeuristicAgent
from werewolf.engine import DayInterrupted, Engine
from werewolf.events import Audience
from werewolf.lineup import Lineup, SeatSpec
from werewolf.roles import BOARDS, Faction, Role, board_summary
from werewolf.state import GameConfig, new_game


def play(seed=0, **cfg):
    st = new_game(GameConfig(seed=seed, **cfg))
    agents = {s: HeuristicAgent(s, st.players[s].role, seed=seed) for s in st.seats}
    return Engine(st, agents).run()


class TestBoards(unittest.TestCase):
    def test_every_board_is_playable(self):
        for n in sorted(BOARDS):
            with self.subTest(n=n):
                b = board_summary(n)
                self.assertEqual(b["wolves"] + b["gods"] + b["villagers"], n)
                st = play(seed=7, n_players=n)
                self.assertEqual(len(st.seats), n)
                self.assertIsNotNone(st.winner, f"{n}人局没有分出胜负")

    def test_both_sides_can_win_on_every_board(self):
        for n in sorted(BOARDS):
            tally = Counter(play(seed=s, n_players=n).winner for s in range(30))
            with self.subTest(n=n):
                self.assertGreater(tally[Faction.VILLAGE], 0, f"{n}人局好人从没赢过：{tally}")
                self.assertGreater(tally[Faction.WOLF], 0, f"{n}人局狼人从没赢过：{tally}")

    def test_unknown_board_rejected(self):
        with self.assertRaises(ValueError):
            new_game(GameConfig(n_players=7))


class TestExplode(unittest.TestCase):
    def _forced_explode_game(self, **cfg):
        st = new_game(GameConfig(seed=42, **cfg))

        class Boom(HeuristicAgent):
            def act(self, view, error=None):
                out = super().act(view, error)
                if view.legal_actions["action_type"] == "speech" and view.is_wolf:
                    out["explode"] = True
                return out

        agents = {s: Boom(s, st.players[s].role, seed=1) for s in st.seats}
        eng = Engine(st, agents)
        eng._setup()
        st.day = 1
        return st, eng

    def test_explode_ends_the_day_with_no_vote(self):
        st, eng = self._forced_explode_game()
        with self.assertRaises(DayInterrupted):
            eng.run_day_speeches()
            eng.run_day_vote()
        self.assertEqual(len(st.explode_log), 1)
        boomer = st.explode_log[0]["seat"]
        self.assertTrue(st.players[boomer].exploded)
        self.assertFalse(st.players[boomer].alive)
        self.assertEqual(st.players[boomer].revealed_role, Role.WEREWOLF, "自爆必须亮明狼人身份")
        self.assertEqual([e for e in st.event_log if e.type == "vote"], [], "自爆后不该有投票")
        self.assertEqual([e for e in st.event_log if e.type == "last_words"], [], "自爆没有遗言")

    def test_explode_destroys_the_badge(self):
        st, eng = self._forced_explode_game()
        wolf = st.wolf_seats()[0]
        st.sheriff_seat = wolf
        st.sheriff_status = "elected"
        st.players[wolf].is_sheriff = True
        with self.assertRaises(DayInterrupted):
            eng.run_day_speeches()
        if st.explode_log[0]["seat"] == wolf:
            self.assertIsNone(st.sheriff_seat)
            self.assertEqual(st.sheriff_status, "destroyed")

    def test_good_players_cannot_explode(self):
        st = new_game(GameConfig(seed=42))
        st.day = 1
        good = next(s for s in st.seats if not st.is_wolf(s))
        self.assertNotIn("explode", A.legal_actions(st, good, "speech")["schema"])
        out = A.validate(st, good, "speech", {"speech": "我要自爆", "explode": True})
        self.assertFalse(out["explode"], "好人的 explode 必须被强制为 False")

    def test_explode_can_be_disabled(self):
        st = new_game(GameConfig(seed=42, wolf_explode=False))
        st.day = 1
        wolf = st.wolf_seats()[0]
        self.assertNotIn("explode", A.legal_actions(st, wolf, "speech")["schema"])
        for seed in range(20):
            self.assertEqual(play(seed=seed, wolf_explode=False).explode_log, [])

    def test_explode_happens_in_normal_play(self):
        """规则 bot 在正常对局里确实会自爆，不是死代码。"""
        total = sum(len(play(seed=s).explode_log) for s in range(60))
        self.assertGreater(total, 0, "60 局里一次自爆都没有，自爆逻辑可能没被触发")


class TestSpeechLimit(unittest.TestCase):
    def test_overlong_speech_rejected(self):
        st = new_game(GameConfig(seed=1, max_speech_chars=100))
        st.day = 1
        with self.assertRaises(A.InvalidAction) as cm:
            A.validate(st, 1, "speech", {"speech": "啊" * 101})
        self.assertIn("100", str(cm.exception))
        A.validate(st, 1, "speech", {"speech": "啊" * 100})

    def test_limit_is_announced_to_the_agent(self):
        st = new_game(GameConfig(seed=1, max_speech_chars=280))
        st.day = 1
        spec = A.legal_actions(st, 1, "speech")
        self.assertIn("280", spec["schema"]["speech"]["desc"])

    def test_no_speech_in_a_real_game_exceeds_the_limit(self):
        for seed in range(20):
            st = play(seed=seed)
            limit = st.config.max_speech_chars
            for e in st.event_log:
                if e.type in ("speech", "sheriff_speech", "last_words", "pk_speech"):
                    body = e.text.split("：", 1)[-1].split("　【")[0]
                    self.assertLessEqual(len(body), limit + 10, f"发言超长：{e.text[:60]}")


class TestIterationCap(unittest.TestCase):
    def test_agent_is_asked_at_most_max_iterations_times(self):
        st = new_game(GameConfig(seed=1, max_iterations=2))
        st.day = 1

        class AlwaysBad:
            def __init__(self):
                self.calls = 0

            def act(self, view, error=None):
                self.calls += 1
                return {"target": 999}  # 永远非法

        agents = {s: AlwaysBad() for s in st.seats}
        eng = Engine(st, agents)
        eng._setup()
        seer = st.seat_of_role(Role.SEER)
        eng._night_seer()
        self.assertEqual(agents[seer].calls, 2, "应该正好问了 max_iterations=2 次")
        # 用尽后走安全回退，流程没有卡死
        self.assertEqual(len(st.seer_checks), 1)
        self.assertTrue(any(e.type == "fallback_action" for e in st.event_log))


class TestThoughts(unittest.TestCase):
    def test_thoughts_are_recorded(self):
        st = play(seed=5)
        self.assertGreater(len(st.thought_log), 50)
        self.assertTrue(all(t["thought"] for t in st.thought_log if t["accepted"]))

    def test_thoughts_never_enter_any_player_view(self):
        """心路历程是 GOD 级信息，任何玩家视角里都不能出现。"""
        from werewolf.views import build_player_view

        st = new_game(GameConfig(seed=5))
        snaps = []
        agents = {s: HeuristicAgent(s, st.players[s].role, seed=5) for s in st.seats}
        Engine(st, agents,
               view_recorder=lambda t, se, at, v: snaps.append((se, v))).run()

        thoughts = {t["thought"] for t in st.thought_log if t["thought"]}
        self.assertTrue(thoughts)
        for seat, view in snaps:
            dumped = json.dumps(view.as_dict(), ensure_ascii=False)
            for th in thoughts:
                self.assertNotIn(th, dumped, f"{seat}号的视角里出现了心路历程")
        # thought 事件必须全是 GOD 级
        for e in st.event_log:
            if e.type == "thought":
                self.assertIs(e.audience, Audience.GOD)


class TestLineup(unittest.TestCase):
    def test_per_seat_model_selection(self):
        lu = Lineup.from_payload(9, [
            {"seat": 1, "backend": "llm", "model": "claude-opus-5", "effort": "high"},
            {"seat": 2, "backend": "llm", "model": "claude-haiku-4-5"},
        ])
        self.assertEqual(lu.specs[1].model, "claude-opus-5")
        self.assertEqual(lu.specs[1].effort, "high")
        self.assertEqual(lu.specs[2].label, "Claude Haiku 4.5")
        self.assertEqual(lu.specs[3].backend, "heuristic", "没配的座位应该补成规则 bot")
        self.assertTrue(lu.uses_llm())

    def test_bad_model_rejected(self):
        with self.assertRaises(ValueError):
            SeatSpec(seat=1, backend="llm", model="gpt-4")
        with self.assertRaises(ValueError):
            SeatSpec(seat=1, backend="telepathy")

    def test_heuristic_lineup_builds_agents(self):
        st = new_game(GameConfig(seed=1, n_players=9))
        agents = Lineup.uniform(9).build_agents(st)
        self.assertEqual(len(agents), 9)
        self.assertTrue(all(hasattr(a, "act") for a in agents.values()))


class TestServer(unittest.TestCase):
    """起一个真的 HTTP 服务，跑完一局，验证前端要用的每个接口。"""

    @classmethod
    def setUpClass(cls):
        from http.server import ThreadingHTTPServer

        from werewolf.server import Handler

        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.port = cls.httpd.server_address[1]
        cls.t = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.t.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()   # 不关的话监听 socket 会一直留着
        cls.t.join(timeout=5)

    def _get(self, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=30) as r:
            return json.loads(r.read())

    def _post(self, path, body):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())

    def test_options_endpoint(self):
        o = self._get("/api/options")
        self.assertEqual(sorted(int(k) for k in o["boards"]), sorted(BOARDS))
        self.assertIn("claude-opus-5", o["models"])
        self.assertIn("heuristic", o["backends"])

    def test_full_game_through_the_api(self):
        import time

        created = self._post("/api/games", {"n_players": 9, "seed": 3, "seats": []})
        gid = created["id"]
        for _ in range(200):
            snap = self._get(f"/api/games/{gid}")
            if snap["status"] in ("finished", "failed", "stopped"):
                break
            time.sleep(0.05)
        self.assertEqual(snap["status"], "finished", snap.get("error"))
        self.assertIn(snap["winner"], ("VILLAGE", "WOLF"))

        # 观众视角只拿得到公开事件
        pub = self._get(f"/api/games/{gid}/events?since=0&god=0")["events"]
        self.assertTrue(pub)
        self.assertTrue(all(e["audience"] == "public" for e in pub),
                        "观众视角混进了非公开事件")
        god = self._get(f"/api/games/{gid}/events?since=0&god=1")["events"]
        self.assertGreater(len(god), len(pub))
        self.assertTrue(any(e["audience"] == "wolves" for e in god))

        # 复盘含心路历程
        rep = self._get(f"/api/games/{gid}/replay")
        self.assertIn("## 心路历程", rep["markdown"])
        self.assertGreater(len(rep["thoughts"]), 0)

        # 13 份上下文（9 人局是 9+1）
        views = self._get(f"/api/games/{gid}/views")
        self.assertEqual(len(views["players"]), 9)
        self.assertIsNotNone(views["wolf_team"])

    def test_bad_config_rejected(self):
        import urllib.error

        with self.assertRaises(urllib.error.HTTPError) as cm:
            self._post("/api/games", {"n_players": 7, "seats": []})
        self.assertEqual(cm.exception.code, 400)


if __name__ == "__main__":
    unittest.main(verbosity=2)
