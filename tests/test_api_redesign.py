"""前端改版需要的新接口字段：结算身份表、统计、时间线、发言进度、耗时、历史对局回放。"""
from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

from werewolf import server
from werewolf.agents.heuristic import HeuristicAgent
from werewolf.engine import Engine
from werewolf.lineup import Lineup
from werewolf.replay import (build_timeline, fate_cn, players_from_events,
                             result_summary)
from werewolf.state import GameConfig, new_game
from werewolf.store import SqliteStore

from .test_i18n import leaks


def play(seed=5, **cfg):
    st = new_game(GameConfig(seed=seed, **cfg))
    return Engine(st, {s: HeuristicAgent(s, st.players[s].role, seed=seed)
                       for s in st.seats}).run()


class TestResultSummary(unittest.TestCase):
    def test_players_and_stats(self):
        st = play(seed=5)
        lineup = Lineup.uniform(12)
        r = result_summary(st, lineup)
        self.assertEqual([p["seat"] for p in r["players"]], st.seats)
        for p in r["players"]:
            self.assertIn(p["side"], ("wolf", "good"))
            self.assertTrue(p["role_cn"] and p["fate_cn"] and p["agent"])
            self.assertEqual(p["alive"], st.players[p["seat"]].alive)
            if p["alive"]:
                self.assertTrue(p["fate_cn"].startswith("存活"))
            else:
                self.assertRegex(p["fate_cn"], r"^第\d+[夜天] ")
            self.assertEqual(leaks(p["fate_cn"]), [])
        self.assertEqual(sum(p["side"] == "wolf" for p in r["players"]), 4)
        s = r["stats"]
        self.assertEqual(s["days"], st.day)
        self.assertEqual(s["n_players"], 12)
        self.assertEqual(s["n_alive"], len(st.alive_seats()))
        self.assertEqual(s["n_speeches"], len(st.speech_log))
        self.assertIsNone(result_summary(st)["players"][0]["agent"])

    def test_fate_labels(self):
        self.assertEqual(fate_cn(alive=True), "存活")
        self.assertEqual(fate_cn(alive=True, is_sheriff=True), "存活 · 警长")
        self.assertEqual(fate_cn(alive=True, idiot_revealed=True), "存活 · 已翻牌")
        self.assertEqual(fate_cn(alive=False, died_day=1, died_when="night",
                                 died_cause="killed"), "第1夜 被狼刀")
        self.assertEqual(fate_cn(alive=False, died_day=2, died_when="vote",
                                 died_cause="exiled"), "第2天 被放逐")
        self.assertEqual(fate_cn(alive=False, died_day=3, died_when="explode",
                                 died_cause="exploded"), "第3天 自爆")

    def test_players_from_events_matches_state(self):
        st = play(seed=5)
        evs = [e.as_dict() for e in st.event_log]
        rebuilt = players_from_events(evs)
        direct = result_summary(st)["players"]
        for a, b in zip(rebuilt, direct):
            for k in ("seat", "role", "side", "alive", "died_day", "died_cause", "fate_cn"):
                self.assertEqual(a[k], b[k], (k, a, b))


class TestTimeline(unittest.TestCase):
    def test_timeline_on_real_games(self):
        for n, seed in ((6, 3), (12, 5), (12, 11)):
            st = play(seed=seed, n_players=n)
            tl = build_timeline([e.as_dict() for e in st.event_log])
            with self.subTest(n=n, seed=seed):
                self.assertTrue(tl)
                self.assertEqual(tl[0]["kind"], "night")
                self.assertEqual(tl[0]["title"], "第 1 夜")
                for r in tl:
                    self.assertIn(r["kind"], ("night", "day"))
                    self.assertEqual(r["title"],
                                     f"第 {r['day']} {'夜' if r['kind'] == 'night' else '天'}")
                    self.assertTrue(r["items"])
                    for it in r["items"]:
                        self.assertFalse(it.startswith("上帝"), it)
                        self.assertEqual(leaks(it), [], it)
                # 夜晚和白天交替出现，不会同一个 (day, kind) 出现两次
                keys = [(r["day"], r["kind"]) for r in tl]
                self.assertEqual(len(keys), len(set(keys)))
                self.assertTrue(tl[-1]["items"][-1].startswith("游戏结束"))
                night_items = " ".join(i for r in tl if r["kind"] == "night" for i in r["items"])
                self.assertIn("狼人决定", night_items)

    def test_timeline_survives_json_roundtrip(self):
        st = play(seed=5)
        evs = json.loads(json.dumps([e.as_dict() for e in st.event_log], ensure_ascii=False))
        self.assertEqual(build_timeline(evs),
                         build_timeline([e.as_dict() for e in st.event_log]))


class TestSnapshot(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = SqliteStore(Path(self.tmp.name) / "t.db")
        self.patch = mock.patch.object(server, "STORE", self.store)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.store.close()
        self.tmp.cleanup()

    def test_speech_progress_and_duration(self):
        g = server.GameRunner(GameConfig(seed=5, n_players=12), Lineup.uniform(12))
        seen = []

        def on_event(e):
            g._on_event(e)
            if g.state.phase in ("DAY_SPEECH", "SHERIFF_SPEECH") and e.type in (
                    "speech", "sheriff_speech"):
                seen.append(g.snapshot()["speech_progress"])

        g.status = "running"
        g.session.run(on_event=on_event)
        g.status, g._t1 = "finished", g._t0 + 1.5
        self.assertTrue(seen)
        for sp in seen:
            self.assertEqual(set(sp), {"order", "done", "total"})
            self.assertEqual(sp["total"], len(sp["order"]))
            self.assertGreaterEqual(sp["done"], 1)
            self.assertLessEqual(sp["done"], sp["total"])
        # 白天发言的第一条就是 done=1
        self.assertIn(1, [sp["done"] for sp in seen])
        snap = g.snapshot()
        self.assertIsNone(snap["speech_progress"])
        self.assertEqual(snap["started_at"], snap["created_at"])
        self.assertIsNotNone(snap["finished_at"])
        self.assertEqual(snap["duration_s"], 1.5)
        self.assertFalse(snap["stored"])


class TestStoredGameFallback(unittest.TestCase):
    """服务重启后 GAMES 为空，只剩会话库 —— 历史对局照样能看。"""

    @classmethod
    def setUpClass(cls):
        from http.server import ThreadingHTTPServer

        cls.tmp = tempfile.TemporaryDirectory()
        cls.store = SqliteStore(Path(cls.tmp.name) / "t.db")
        cls.patch = mock.patch.object(server, "STORE", cls.store)
        cls.patch.start()
        g = server.GameRunner(GameConfig(seed=5, n_players=12), Lineup.uniform(12))
        g.start()
        g._thread.join(timeout=60)
        assert g.status == "finished", g.error
        cls.live = g
        cls.gid = g.id
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.t = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.t.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.t.join(timeout=5)
        server.GAMES.pop(cls.gid, None)
        cls.patch.stop()
        cls.store.close()
        cls.tmp.cleanup()

    def _get(self, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=30) as r:
            return json.loads(r.read())

    def test_live_replay_has_timeline(self):
        server.GAMES[self.gid] = self.live
        try:
            rep = self._get(f"/api/games/{self.gid}/replay")
            snap = self._get(f"/api/games/{self.gid}")
        finally:
            server.GAMES.pop(self.gid, None)
        self.assertTrue(rep["timeline"])
        self.assertIsInstance(rep["duration_s"], float)
        self.assertEqual(len(rep["result"]["players"]), 12)
        self.assertIn("n_speeches", rep["result"]["stats"])
        self.assertIsNone(snap["speech_progress"])
        self.assertFalse(snap["stored"])

    def test_stored_snapshot(self):
        server.GAMES.pop(self.gid, None)
        snap = self._get(f"/api/games/{self.gid}")
        self.assertTrue(snap["stored"])
        self.assertEqual(snap["status"], "finished")
        self.assertEqual(snap["winner"], self.live.state.winner.value)
        self.assertEqual(len(snap["players"]), 12)
        p = snap["players"][0]
        for k in ("seat", "role_cn", "fate_cn", "agent", "alive", "died_cause_cn", "claim_cn"):
            self.assertIn(k, p)
        self.assertTrue(p["agent"], "库里的结果要带上每个座位的 agent")
        self.assertEqual(snap["days"], self.live.state.day)
        self.assertIsNotNone(snap["finished_at"])
        self.assertGreaterEqual(snap["duration_s"], 0)

    def test_stored_events(self):
        pub = self._get(f"/api/games/{self.gid}/events?since=0&god=0")
        god = self._get(f"/api/games/{self.gid}/events?since=0&god=1")
        self.assertTrue(pub["events"])
        self.assertTrue(all(e["audience"] == "public" for e in pub["events"]))
        self.assertEqual(len(god["events"]), len(self.live.state.event_log))
        self.assertEqual(god["total"], len(self.live.state.event_log))
        tail = self._get(f"/api/games/{self.gid}/events?since=10&god=1")["events"]
        self.assertEqual(tail[0]["seq"], 11)
        self.assertTrue(pub["snapshot"]["stored"])

    def test_stored_replay(self):
        rep = self._get(f"/api/games/{self.gid}/replay")
        self.assertTrue(rep["stored"])
        self.assertIn("# 对局复盘", rep["markdown"])
        self.assertIn("## 心路历程", rep["markdown"])
        self.assertEqual(len(rep["thoughts"]), len(self.live.thoughts()))
        t = rep["thoughts"][0]
        for k in ("seat", "day", "phase_cn", "action_cn", "thought", "accepted", "role_cn"):
            self.assertIn(k, t)
        self.assertEqual(rep["timeline"],
                         build_timeline(self.live.all_events()))
        self.assertEqual(rep["result"]["winner"], self.live.state.winner.value)
        self.assertEqual(len(rep["sessions"]), 12)
        self.assertIsNotNone(rep["duration_s"])

    def test_stored_sessions(self):
        s = self._get(f"/api/games/{self.gid}/sessions")["sessions"]
        self.assertEqual(len(s), 12)
        self.assertIn("release_reason_cn", s[0])

    def test_history_list(self):
        lst = self._get("/api/games")
        past = [g for g in lst["past"] if g["id"] == self.gid]
        self.assertEqual(len(past), 1)
        e = past[0]
        for k in ("id", "created_at", "status", "winner", "winner_cn", "days",
                  "n_players", "deployment", "started_at", "ended_at", "duration_s"):
            self.assertIn(k, e)
        self.assertEqual(e["n_players"], 12)
        self.assertEqual(e["status"], "finished")

    def test_unknown_game_404(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self._get("/api/games/nope123/replay")
        self.assertEqual(cm.exception.code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
