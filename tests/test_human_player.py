"""真人玩家座位：11 个 agent + 1 个人。

守护的规则（docs/03-技术设计.md「真人玩家座位」）：
  · 真人座位就是一个会阻塞等待的 agent：待办里给合法动作，提交后交引擎照常校验
  · 一桌最多 1 个真人；真人座位不需要密钥，不管哪种部署模式都跑在编排端进程里
  · 读自己视角、提交动作都要座位凭证；凭证只在开局返回里给一次
  · 有真人的对局在进行中锁死上帝视角：god=1 被忽略，/views、/sessions 返回 403；结束后解锁
  · 中止对局能把阻塞在真人座位上的引擎线程叫醒
"""
from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

from werewolf import server
from werewolf import i18n
from werewolf.actions import ACTION_TYPES
from werewolf.agents.heuristic import HeuristicAgent
from werewolf.agents.human import (HUMAN_MAX_ITERATIONS, HumanAgent, HumanCancelled,
                                   HumanNotWaiting)
from werewolf.lineup import Lineup
from werewolf.roles import Role
from werewolf.runtime import LocalRuntime, build_pool
from werewolf.state import GameConfig, new_game
from werewolf.store import SqliteStore
from werewolf.views import PlayerView, build_player_view

from .test_i18n import leaks

HUMAN_SEAT = 3


def seats_with_human(n: int, seat: int = HUMAN_SEAT) -> list[dict]:
    return [{"seat": s, "backend": "human" if s == seat else "heuristic"}
            for s in range(1, n + 1)]


def wait_until(pred, timeout: float = 10.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        v = pred()
        if v:
            return v
        time.sleep(0.005)
    raise AssertionError("等待超时")


class TestHumanAgent(unittest.TestCase):
    def setUp(self):
        self.st = new_game(GameConfig(seed=1, n_players=9))
        self.seat = self.st.seats[0]
        self.agent = HumanAgent(self.seat, self.st.players[self.seat].role)
        self.view = build_player_view(self.st, self.seat, action_type="sheriff_signup")

    def _act_in_thread(self, error=None):
        box = {}

        def run():
            try:
                box["out"] = self.agent.act(self.view, error=error)
            except BaseException as exc:  # noqa: BLE001 —— 测试要看到 HumanCancelled
                box["exc"] = exc

        t = threading.Thread(target=run, daemon=True)
        t.start()
        return t, box

    def test_pending_then_submit(self):
        self.assertIsNone(self.agent.pending())
        t, box = self._act_in_thread(error="上次填错了")
        p = wait_until(self.agent.pending)
        self.assertEqual(p["action_type"], "sheriff_signup")
        self.assertEqual(p["error"], "上次填错了")
        self.assertIn("run", p["legal_actions"]["schema"])
        self.agent.submit(p["request_id"], {"run": True, "private_thought": "偷偷写的"})
        t.join(timeout=5)
        # 真人动作里的 private_thought 被丢掉，不会混进上帝日志
        self.assertEqual(box["out"], {"run": True})
        self.assertIsNone(self.agent.pending())

    def test_submit_when_not_waiting(self):
        with self.assertRaises(HumanNotWaiting):
            self.agent.submit(1, {"run": True})
        t, _ = self._act_in_thread()
        p = wait_until(self.agent.pending)
        with self.assertRaises(HumanNotWaiting):
            self.agent.submit(p["request_id"] + 1, {"run": True})
        with self.assertRaises(ValueError):
            self.agent.submit(p["request_id"], "不是对象")
        self.agent.submit(p["request_id"], {"run": False})
        t.join(timeout=5)

    def test_cancel_wakes_engine_thread(self):
        t, box = self._act_in_thread()
        wait_until(self.agent.pending)
        self.agent.cancel()
        t.join(timeout=5)
        self.assertFalse(t.is_alive())
        self.assertIsInstance(box["exc"], HumanCancelled)
        # HumanCancelled 不能被引擎的 `except Exception` 吞掉
        self.assertNotIsInstance(box["exc"], Exception)


class TestLineupAndPool(unittest.TestCase):
    def test_at_most_one_human(self):
        Lineup.from_payload(12, seats_with_human(12))
        two = seats_with_human(12)
        two[5]["backend"] = "human"
        with self.assertRaises(ValueError):
            Lineup.from_payload(12, two)

    def test_human_needs_no_key(self):
        lu = Lineup.from_payload(12, seats_with_human(12))
        self.assertEqual(lu.missing_keys(), [])
        self.assertFalse(lu.uses_llm())
        self.assertEqual(lu.human_seats(), [HUMAN_SEAT])
        self.assertEqual(lu.specs[HUMAN_SEAT].label, "真人玩家")
        self.assertEqual(lu.specs[HUMAN_SEAT].as_dict()["backend"], "human")

    def test_human_seat_stays_in_process_for_every_deployment(self):
        # 只构造运行时，不 start —— 不会真的起进程
        st = new_game(GameConfig(seed=2, n_players=12))
        lu = Lineup.from_payload(12, seats_with_human(12))
        for dep in ("inprocess", "subprocess"):
            with self.subTest(deployment=dep):
                pool = build_pool(st, lu, deployment=dep, game_id="t")
                rt = pool.runtimes[HUMAN_SEAT]
                self.assertIsInstance(rt, LocalRuntime)
                self.assertIsInstance(rt.agent, HumanAgent)
                self.assertEqual(rt.max_iterations, HUMAN_MAX_ITERATIONS)
                self.assertEqual(sorted(pool.runtimes), st.seats)
                others = [pool.runtimes[s] for s in st.seats if s != HUMAN_SEAT]
                self.assertFalse(any(isinstance(getattr(r, "agent", None), HumanAgent)
                                     for r in others))


class TestHumanForm(unittest.TestCase):
    """合法动作翻成的表单：浏览器直接渲染，所以里面不能有任何英文标识符。"""

    CTX = {"victim": 3, "candidates": [1, 2], "can_explode": True}

    def test_every_action_for_every_role_is_chinese(self):
        st = new_game(GameConfig(seed=5, n_players=12))
        for seat in st.seats:
            for at in ACTION_TYPES:
                view = build_player_view(st, seat, action_type=at, action_ctx=self.CTX)
                form = i18n.human_form(view.legal_actions, alive=st.alive_seats(), me=seat)
                texts = [form["action_cn"], form["description"]]
                for f in form["fields"]:
                    texts += [f["label"], f["desc"]]
                    texts += [o["label"] for o in f.get("options", []) + f.get("results", [])]
                    self.assertIn(f["kind"], ("choice", "multi", "text", "textarea", "check"))
                for t in texts:
                    with self.subTest(seat=seat, action=at, text=t):
                        self.assertEqual(leaks(t), [])
                        self.assertNotRegex(t, r"\b(null|None|True|False)\b")

    def test_option_values_round_trip_through_validate(self):
        """表单里的每个 value 原样交回去都能过引擎校验。"""
        from werewolf.actions import validate

        st = new_game(GameConfig(seed=5, n_players=12))
        seer = next(s for s in st.seats if st.players[s].role is Role.SEER)
        for at, field in (("seer_check", "target"), ("vote", "target"),
                          ("sheriff_signup", "run")):
            view = build_player_view(st, seer, action_type=at, action_ctx=self.CTX)
            form = i18n.human_form(view.legal_actions, alive=st.alive_seats(), me=seer)
            f = next(x for x in form["fields"] if x["name"] == field)
            for o in f["options"]:
                with self.subTest(action=at, value=o["value"]):
                    validate(st, seer, at, {field: o["value"]}, self.CTX)

    def test_knowledge_lines(self):
        st = new_game(GameConfig(seed=5, n_players=12))
        for seat in st.seats:
            lines = i18n.knowledge_cn(build_player_view(st, seat).identity)
            for t in lines:
                self.assertEqual(leaks(t), [])
            if st.players[seat].role is Role.WEREWOLF:
                self.assertTrue(lines[0].startswith("狼队友："))
            if st.players[seat].role is Role.VILLAGER:
                self.assertEqual(lines, [])


class _ServerCase(unittest.TestCase):
    def setUp(self):
        from http.server import ThreadingHTTPServer

        self.tmp = tempfile.TemporaryDirectory()
        self.store = SqliteStore(Path(self.tmp.name) / "t.db")
        self.patch = mock.patch.object(server, "STORE", self.store)
        self.patch.start()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.port = self.httpd.server_address[1]
        self.t = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.t.start()
        self.gids: list[str] = []

    def tearDown(self):
        for gid in self.gids:
            g = server.GAMES.pop(gid, None)
            if g is not None:
                g.stop()
                if g._thread:
                    g._thread.join(timeout=10)
        self.httpd.shutdown()
        self.httpd.server_close()
        self.t.join(timeout=5)
        self.patch.stop()
        self.store.close()
        self.tmp.cleanup()

    def req(self, path, body=None):
        """返回 (状态码, JSON)。"""
        data = None if body is None else json.dumps(body).encode()
        r = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data,
                                   headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(r, timeout=30) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def create(self, n=12, seed=4, seat=HUMAN_SEAT):
        code, snap = self.req("/api/games", {"n_players": n, "seed": seed,
                                              "seats": seats_with_human(n, seat)})
        self.assertEqual(code, 201, snap)
        self.gids.append(snap["id"])
        return snap


class TestHumanOverHttp(_ServerCase):
    def test_full_game_with_human_seat(self):
        """真人用浏览器那套接口打完一整局（背后让规则 bot 替他出主意）。"""
        snap = self.create()
        gid, human = snap["id"], snap["human"]
        self.assertEqual(human["seat"], HUMAN_SEAT)
        self.assertTrue(human["token"])
        self.assertTrue(snap["has_human"] and snap["god_locked"])
        self.assertEqual(snap["human_seat"], HUMAN_SEAT)
        g = server.GAMES[gid]
        true_role = g.state.players[HUMAN_SEAT].role
        seat_url = f"/api/games/{gid}/seat?token={human['token']}"

        # 凭证：不带 / 带错都只能旁观
        self.assertEqual(self.req(f"/api/games/{gid}/seat")[0], 403)
        self.assertEqual(self.req(f"/api/games/{gid}/seat?token=nope")[0], 403)
        self.assertEqual(self.req(f"/api/games/{gid}/act",
                                  {"token": "nope", "request_id": 1, "action": {}})[0], 403)

        brain = HeuristicAgent(HUMAN_SEAT, true_role, seed=4)
        n_acts = 0
        sent_bad = False
        checked_lock = False
        while True:
            code, sv = self.req(seat_url)
            self.assertEqual(code, 200, sv)
            if sv["status"] not in ("pending", "running"):
                break
            view = sv["view"]
            # 真人拿到的就是自己的个人视角：有自己的身份，看不到别人的
            self.assertEqual(view["identity"]["seat"], HUMAN_SEAT)
            self.assertEqual(view["identity"]["role"], true_role.value)
            for p in view["public_state"]["players"].values():
                self.assertNotIn("role", p)
            if true_role is not Role.WEREWOLF:
                self.assertIsNone(view["wolf_team"])
            pending = sv["pending"]
            if not pending:
                if not checked_lock:
                    self._assert_god_locked(gid)
                    checked_lock = True
                time.sleep(0.002)
                continue
            self.assertTrue(pending["action_cn"])
            self.assertEqual(pending["form"]["action_type"], pending["action_type"])
            self.assertIsInstance(sv["knowledge_cn"], list)
            if not sent_bad and pending["action_type"] in ("vote", "sheriff_vote", "speech"):
                # 故意交一个非法动作：引擎打回来，待办里带上错误，再交一次
                sent_bad = True
                bad = ({"target": 99} if "vote" in pending["action_type"]
                       else {"speech": "啊" * 5000})  # 超过字数上限
                self.assertEqual(self.req(f"/api/games/{gid}/act", {
                    "token": human["token"], "request_id": pending["request_id"],
                    "action": bad})[0], 200)
                again = wait_until(lambda: (self.req(seat_url)[1].get("pending") or {})
                                   .get("error"))
                self.assertTrue(again)
                continue
            pv = PlayerView.from_dict({**view, "legal_actions": pending["legal_actions"]})
            action = brain.act(pv, error=pending.get("error"))
            code, res = self.req(f"/api/games/{gid}/act", {
                "token": human["token"], "request_id": pending["request_id"],
                "action": action})
            self.assertEqual(code, 200, res)
            # 同一条待办重复提交 → 409
            self.assertEqual(self.req(f"/api/games/{gid}/act", {
                "token": human["token"], "request_id": pending["request_id"],
                "action": action})[0], 409)
            n_acts += 1

        g._thread.join(timeout=30)
        self.assertEqual(g.status, "finished", g.error)
        self.assertGreater(n_acts, 0)
        self.assertTrue(sent_bad)
        self.assertTrue(checked_lock)
        # 真人的动作照样进了公开记录，而且不带心路历程
        self.assertFalse([t for t in g.state.thought_log
                          if t["seat"] == HUMAN_SEAT and t["thought"]])
        # 结束后解锁：上帝视角、会话、复盘都能看
        snap = self.req(f"/api/games/{gid}?god=1")[1]
        self.assertFalse(snap["god_locked"])
        self.assertTrue(all(p["role"] for p in snap["players"]))
        god_events = self.req(f"/api/games/{gid}/events?since=0&god=1")[1]["events"]
        self.assertTrue(any(e["audience"] != "public" for e in god_events))
        code, sess = self.req(f"/api/games/{gid}/sessions")
        self.assertEqual(code, 200)
        me = [x for x in sess["sessions"] if x["seat"] == HUMAN_SEAT][0]
        self.assertEqual(me["backend"], "human")
        self.assertEqual(me["backend_cn"], "真人玩家")
        self.assertEqual(self.req(f"/api/games/{gid}/replay")[0], 200)
        # 历史对局（只剩库）也认得出真人座位
        server.GAMES.pop(gid)
        stored = self.req(f"/api/games/{gid}")[1]
        self.assertTrue(stored["stored"] and stored["has_human"])
        self.assertEqual(stored["human_seat"], HUMAN_SEAT)
        self.assertFalse(stored["god_locked"])

    def _assert_god_locked(self, gid):
        snap = self.req(f"/api/games/{gid}?god=1")[1]
        self.assertTrue(snap["god_locked"])
        others = [p for p in snap["players"] if p["seat"] != HUMAN_SEAT]
        self.assertTrue(all(p["role"] is None for p in others))
        self.assertIsNone([p for p in snap["players"] if p["seat"] == HUMAN_SEAT][0]["role"])
        evs = self.req(f"/api/games/{gid}/events?since=0&god=1")[1]["events"]
        self.assertTrue(all(e["audience"] == "public" for e in evs))
        self.assertEqual(self.req(f"/api/games/{gid}/views")[0], 403)
        self.assertEqual(self.req(f"/api/games/{gid}/sessions")[0], 403)

    def test_stop_while_waiting_for_human(self):
        snap = self.create(n=9, seed=7, seat=1)
        gid, token = snap["id"], snap["human"]["token"]
        wait_until(lambda: self.req(f"/api/games/{gid}/seat?token={token}")[1]["pending"])
        self.assertEqual(self.req(f"/api/games/{gid}/stop", {})[0], 200)
        g = server.GAMES[gid]
        g._thread.join(timeout=10)
        self.assertFalse(g._thread.is_alive())
        self.assertEqual(g.status, "stopped")
        self.assertEqual(self.store.load_game(gid)["status"], "failed")
        # 停了之后再交动作 → 409
        self.assertEqual(self.req(f"/api/games/{gid}/act",
                                  {"token": token, "request_id": 1, "action": {}})[0], 409)

    def test_no_human_game_is_unchanged(self):
        code, snap = self.req("/api/games", {"n_players": 6, "seed": 1})
        self.assertEqual(code, 201)
        self.gids.append(snap["id"])
        self.assertNotIn("human", snap)
        self.assertFalse(snap["has_human"])
        self.assertFalse(snap["god_locked"])
        self.assertEqual(self.req(f"/api/games/{snap['id']}/seat?token=x")[0], 404)

    def test_two_humans_rejected(self):
        seats = seats_with_human(12)
        seats[0]["backend"] = "human"
        code, res = self.req("/api/games", {"n_players": 12, "seats": seats})
        self.assertEqual(code, 400)
        self.assertIn("真人", res["error"])


if __name__ == "__main__":
    unittest.main()
