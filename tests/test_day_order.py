"""第一天白天的环节顺序。

标准规则：**首次天亮时不宣布死讯，先竞选警长，发完警徽才公布昨晚的情况。**
这样竞选时全场（包括昨晚被刀的人自己）都不知道谁死了，这是该环节博弈的前提。
"""
from __future__ import annotations

import unittest

from werewolf.agents.heuristic import HeuristicAgent
from werewolf.engine import Engine
from werewolf.events import Audience
from werewolf.state import GameConfig, new_game


def play(seed=0, agent_cls=HeuristicAgent, recorder=None, **cfg):
    st = new_game(GameConfig(seed=seed, **cfg))
    agents = {s: agent_cls(s, st.players[s].role, seed=seed) for s in st.seats}
    return Engine(st, agents, view_recorder=recorder).run()


def _first(st, *types, day=None):
    for e in st.event_log:
        if e.type in types and (day is None or e.day == day):
            return e
    return None


class NoHeal(HeuristicAgent):
    """女巫不救 —— 否则首夜几乎不会有人死，这条路径根本跑不到。"""

    def act(self, view, error=None):
        if view.legal_actions["action_type"] == "witch_action":
            return {"heal": False, "poison": None}
        return super().act(view, error)


class TestFirstDayOrder(unittest.TestCase):
    def test_election_finishes_before_deaths_are_announced(self):
        for seed in range(30):
            st = play(seed, NoHeal)
            elect = _first(st, "sheriff_result", day=1)
            dawn = _first(st, "dawn", day=1)
            self.assertIsNotNone(dawn, f"seed={seed} 第1天没有公布死讯")
            if elect is None:
                continue  # 无人上警 / 全员上警，警徽流失也会发 sheriff_result
            self.assertLess(
                elect.seq, dawn.seq,
                f"seed={seed} 警徽还没发完就公布了死讯（{elect.seq} vs {dawn.seq}）",
            )

    def test_daybreak_comes_before_the_election(self):
        st = play(1, NoHeal)
        day_break = _first(st, "daybreak", day=1)
        signup = _first(st, "sheriff_signup", day=1)
        self.assertIsNotNone(day_break)
        self.assertLess(day_break.seq, signup.seq)
        self.assertNotIn("倒牌", day_break.text, "天亮那句话不能带死讯")
        self.assertNotIn("平安夜", day_break.text)

    def test_no_public_event_leaks_the_death_before_the_badge_is_issued(self):
        """竞选期间，任何公开事件都不能透露昨晚谁死了。"""
        for seed in range(30):
            st = play(seed, NoHeal)
            elect = _first(st, "sheriff_result", day=1)
            if elect is None:
                continue
            night_dead = [d["seat"] for d in st.death_record
                          if d["day"] == 1 and d["when"] == "night"]
            if not night_dead:
                continue
            for e in st.event_log:
                if e.seq > elect.seq or e.audience is not Audience.PUBLIC:
                    continue
                self.assertNotIn(
                    e.type, ("dawn", "death"),
                    f"seed={seed} 竞选结束前就公布了死亡信息",
                )

    def test_from_day_two_on_there_is_no_election(self):
        st = play(3, NoHeal)
        if st.day < 2:
            self.skipTest("这局只打了一天")
        for e in st.event_log:
            if e.type in ("sheriff_signup", "sheriff_vote") and e.day >= 2:
                self.fail(f"第{e.day}天不该再有警长竞选：{e.text[:50]}")


class TestNightVictimStillPlaysTheElection(unittest.TestCase):
    """昨晚被刀的人，在竞选时连他自己都还不知道自己死了。"""

    def _run_capturing_signup_views(self, seed):
        seen = {}

        def rec(turn, seat, action_type, view):
            if action_type == "sheriff_signup":
                seen.setdefault(seat, view)

        st = play(seed, NoHeal, recorder=rec)
        night_dead = [d["seat"] for d in st.death_record
                      if d["day"] == 1 and d["when"] == "night"]
        return st, seen, night_dead

    def test_victim_sees_itself_as_alive_during_the_election(self):
        found = False
        for seed in range(30):
            st, seen, dead = self._run_capturing_signup_views(seed)
            for seat in dead:
                if seat not in seen:
                    continue
                found = True
                self.assertTrue(
                    seen[seat].identity["alive"],
                    f"seed={seed} {seat}号 在竞选时就知道自己死了",
                )
                self.assertIn(seat, seen[seat].public_state["alive_seats"])
        self.assertTrue(found, "30 局里没有出现首夜死亡，这条路径没被覆盖")

    def test_victim_is_offered_the_signup_action_at_all(self):
        for seed in range(30):
            st, seen, dead = self._run_capturing_signup_views(seed)
            for seat in dead:
                self.assertIn(seat, seen,
                              f"seed={seed} {seat}号 昨晚死了就没让他上警 —— 顺序反了")


class TestDeadSheriffHandsOffTheBadge(unittest.TestCase):
    """死者当选警长之后，公布死讯 → 遗言 → 移交警徽。"""

    def _rigged(self, seed=4):
        # 先探出第1夜的刀口
        probe = new_game(GameConfig(seed=seed))
        eng = Engine(probe, {s: NoHeal(s, probe.players[s].role, seed=seed)
                             for s in probe.seats})
        eng._setup()
        probe.day = 1
        eng.run_night()
        victim = probe.night_kill_target

        class Rig(NoHeal):
            def act(self, view, error=None):
                at = view.legal_actions["action_type"]
                if at == "sheriff_signup":
                    return {"run": view.seat == victim, "reason": ""}
                if at == "sheriff_vote":
                    opts = view.legal_actions["schema"]["target"]["options"]
                    return {"target": victim if victim in opts else None}
                return super().act(view, error)

        st = new_game(GameConfig(seed=seed))
        st = Engine(st, {s: Rig(s, st.players[s].role, seed=seed) for s in st.seats}).run()
        return st, victim

    def test_a_secretly_dead_player_can_win_the_election(self):
        st, victim = self._rigged()
        elect = _first(st, "sheriff_result", day=1)
        self.assertEqual(elect.targets, [victim], "刀口没能当选，用例没构造成功")
        self.assertFalse(st.players[victim].alive, "他本来就该是死的")

    def test_badge_is_passed_on_after_the_death_is_announced(self):
        st, victim = self._rigged()
        elect = _first(st, "sheriff_result", day=1)
        dawn = _first(st, "dawn", day=1)
        badge = _first(st, "badge", day=1)
        self.assertLess(elect.seq, dawn.seq, "应该先发警徽再公布死讯")
        self.assertIsNotNone(badge, "死掉的警长没有移交/撕毁警徽")
        self.assertLess(dawn.seq, badge.seq, "移交警徽要发生在公布死讯之后")
        self.assertEqual(badge.actor, victim)
        # 警徽要么传给了活人，要么被撕掉
        if st.sheriff_seat is not None:
            self.assertTrue(st.players[st.sheriff_seat].alive)
            self.assertNotEqual(st.sheriff_seat, victim)
        else:
            self.assertEqual(st.sheriff_status, "destroyed")


class TestExplodeDuringTheElection(unittest.TestCase):
    """警上自爆：竞选作废，但昨晚的死亡是既成事实，仍然要结算公布。"""

    def _boom(self, seed=42):
        class Boom(NoHeal):
            def act(self, view, error=None):
                out = super().act(view, error)
                if view.legal_actions["action_type"] == "sheriff_speech" and view.is_wolf:
                    out["explode"] = True
                return out

        return play(seed, Boom)

    def test_election_is_aborted_and_badge_is_lost(self):
        st = self._boom()
        self.assertTrue(st.explode_log)
        self.assertIsNone(st.sheriff_seat)
        self.assertIn(st.sheriff_status, ("lost", "destroyed"))

    def test_deaths_are_still_announced(self):
        """自爆不能把昨晚的死亡吞掉 —— 否则场上状态直接对不上。"""
        st = self._boom()
        dawn = _first(st, "dawn", day=1)
        self.assertIsNotNone(dawn, "警上自爆之后没有公布昨晚的死讯")
        boom = _first(st, "explode", day=1)
        self.assertLess(boom.seq, dawn.seq)

    def test_no_speeches_or_votes_after_the_explosion(self):
        st = self._boom()
        boom = _first(st, "explode", day=1)
        for e in st.event_log:
            if e.day != 1 or e.seq <= boom.seq:
                continue
            self.assertNotIn(e.type, ("vote", "speech", "sheriff_speech", "last_words"),
                             f"自爆之后不该还有 {e.type}：{e.text[:50]}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
