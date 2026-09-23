"""规则测试：逐条验证 docs/01-游戏规则.md 里写的东西真的被实现了。"""
from __future__ import annotations

import unittest

from werewolf import actions as A
from werewolf.agents.heuristic import HeuristicAgent
from werewolf.engine import Engine
from werewolf.roles import SETUP_STANDARD_12, Faction, Role
from werewolf.state import GameConfig, Player, new_game


def make_state(roles_by_seat: dict[int, Role] | None = None, **cfg):
    """造一个可控牌型的局，用于定点测试规则。"""
    state = new_game(GameConfig(seed=0, **cfg))
    if roles_by_seat:
        for seat, role in roles_by_seat.items():
            state.players[seat] = Player(seat=seat, name=f"{seat}号", role=role)
    return state


class ScriptedAgent:
    """按 action_type 返回固定动作，缺省回退到规则 bot。"""

    def __init__(self, seat, role, script: dict, seed=0):
        self.seat, self.role, self.script = seat, role, script
        self._fallback = HeuristicAgent(seat, role, seed=seed)

    def act(self, view, error=None):
        at = view.legal_actions["action_type"]
        if at in self.script:
            val = self.script[at]
            return val(view) if callable(val) else dict(val)
        return self._fallback.act(view, error)


class TestSetup(unittest.TestCase):
    def test_standard_12_composition(self):
        """4 狼 + 4 神 + 4 民"""
        from collections import Counter

        c = Counter(SETUP_STANDARD_12)
        self.assertEqual(len(SETUP_STANDARD_12), 12)
        self.assertEqual(c[Role.WEREWOLF], 4)
        self.assertEqual(c[Role.VILLAGER], 4)
        self.assertEqual(
            sum(c[r] for r in (Role.SEER, Role.WITCH, Role.HUNTER, Role.IDIOT)), 4
        )

    def test_deal_is_reproducible(self):
        a = new_game(GameConfig(seed=99))
        b = new_game(GameConfig(seed=99))
        self.assertEqual(
            {s: a.players[s].role for s in a.seats},
            {s: b.players[s].role for s in b.seats},
        )


class TestWinConditions(unittest.TestCase):
    def test_wolves_all_dead_village_wins(self):
        st = new_game(GameConfig(seed=1))
        for s in st.wolf_seats():
            st.players[s].alive = False
        self.assertIs(st.check_winner(), Faction.VILLAGE)

    def test_all_gods_dead_wolves_win(self):
        """屠神：4 神全死，狼人立刻获胜（即使平民还都活着）"""
        st = new_game(GameConfig(seed=1))
        for s in st.seats:
            if st.players[s].is_god:
                st.players[s].alive = False
        self.assertEqual(len(st.alive_villager_seats()), 4, "平民应该还都活着")
        self.assertIs(st.check_winner(), Faction.WOLF)
        self.assertIn("屠神", st.end_reason)

    def test_all_villagers_dead_wolves_win(self):
        st = new_game(GameConfig(seed=1))
        for s in st.alive_villager_seats()[:]:
            st.players[s].alive = False
        self.assertEqual(len(st.alive_god_seats()), 4, "神应该还都活着")
        self.assertIs(st.check_winner(), Faction.WOLF)
        self.assertIn("屠民", st.end_reason)

    def test_city_rule_needs_all_goods_dead(self):
        """屠城局：只杀光神不够，必须杀光所有好人"""
        st = new_game(GameConfig(seed=1, win_rule="city"))
        for s in st.seats:
            if st.players[s].is_god:
                st.players[s].alive = False
        self.assertIsNone(st.check_winner())
        for s in st.alive_villager_seats()[:]:
            st.players[s].alive = False
        self.assertIs(st.check_winner(), Faction.WOLF)


class TestWitchRules(unittest.TestCase):
    def setUp(self):
        self.st = make_state()
        self.witch = self.st.seat_of_role(Role.WITCH)
        self.st.day = 1

    def test_cannot_use_both_potions_same_night(self):
        victim = next(s for s in self.st.alive_seats() if s != self.witch)
        other = next(s for s in self.st.alive_seats() if s not in (self.witch, victim))
        with self.assertRaises(A.InvalidAction) as cm:
            A.validate(self.st, self.witch, "witch_action",
                       {"heal": True, "poison": other}, {"victim": victim})
        self.assertIn("同一晚", str(cm.exception))

    def test_cannot_heal_when_nobody_killed(self):
        with self.assertRaises(A.InvalidAction):
            A.validate(self.st, self.witch, "witch_action", {"heal": True, "poison": None},
                       {"victim": None})

    def test_cannot_heal_twice(self):
        self.st.players[self.witch].witch_has_antidote = False
        victim = next(s for s in self.st.alive_seats() if s != self.witch)
        with self.assertRaises(A.InvalidAction):
            A.validate(self.st, self.witch, "witch_action", {"heal": True, "poison": None},
                       {"victim": victim})

    def test_cannot_poison_twice(self):
        self.st.players[self.witch].witch_has_poison = False
        other = next(s for s in self.st.alive_seats() if s != self.witch)
        with self.assertRaises(A.InvalidAction):
            A.validate(self.st, self.witch, "witch_action", {"heal": False, "poison": other},
                       {"victim": None})

    def test_self_rescue_only_on_first_night(self):
        self.st.day = 1
        ok = A.validate(self.st, self.witch, "witch_action", {"heal": True, "poison": None},
                        {"victim": self.witch})
        self.assertTrue(ok["heal"], "首夜应该允许自救")
        self.st.day = 2
        with self.assertRaises(A.InvalidAction) as cm:
            A.validate(self.st, self.witch, "witch_action", {"heal": True, "poison": None},
                       {"victim": self.witch})
        self.assertIn("自救", str(cm.exception))


class TestSeerRules(unittest.TestCase):
    def test_cannot_check_self_or_repeat(self):
        st = make_state()
        seer = st.seat_of_role(Role.SEER)
        st.day = 1
        with self.assertRaises(A.InvalidAction):
            A.validate(st, seer, "seer_check", {"target": seer})
        target = next(s for s in st.alive_seats() if s != seer)
        A.validate(st, seer, "seer_check", {"target": target})
        st.seer_checks.append({"day": 1, "target": target, "result": "GOOD"})
        with self.assertRaises(A.InvalidAction):
            A.validate(st, seer, "seer_check", {"target": target})

    def test_check_result_matches_truth(self):
        st = make_state()
        seer = st.seat_of_role(Role.SEER)
        agents = {s: HeuristicAgent(s, st.players[s].role, seed=0) for s in st.seats}
        eng = Engine(st, agents)
        eng._setup()
        st.day = 1
        eng._night_seer()
        self.assertEqual(len(st.seer_checks), 1)
        c = st.seer_checks[0]
        self.assertEqual(c["result"], "WOLF" if st.is_wolf(c["target"]) else "GOOD")


class TestIdiotRules(unittest.TestCase):
    def test_idiot_survives_exile_and_loses_vote(self):
        st = make_state()
        idiot = st.seat_of_role(Role.IDIOT)
        agents = {
            s: ScriptedAgent(s, st.players[s].role,
                             {"vote": {"target": idiot, "reason": "推白痴"},
                              "sheriff_signup": {"run": False, "reason": ""}})
            for s in st.seats
        }
        st.day = 1
        eng = Engine(st, agents)
        eng._setup()
        eng.run_day_vote()
        p = st.players[idiot]
        self.assertTrue(p.alive, "白痴被票出局后不应该死")
        self.assertTrue(p.idiot_revealed)
        self.assertFalse(p.can_vote, "白痴翻牌后应失去投票权")
        self.assertEqual(p.revealed_role, Role.IDIOT, "白痴身份应对全场公开")
        self.assertEqual(st.vote_weight(idiot), 0.0)

    def test_idiot_dies_normally_to_knife(self):
        st = make_state()
        idiot = st.seat_of_role(Role.IDIOT)
        agents = {s: HeuristicAgent(s, st.players[s].role, seed=0) for s in st.seats}
        eng = Engine(st, agents)
        st.day = 1
        eng.kill(idiot, when="night", cause="killed")
        self.assertFalse(st.players[idiot].alive, "白痴被刀应该正常死亡")


class TestHunterRules(unittest.TestCase):
    def _run_death(self, cause):
        st = make_state()
        hunter = st.seat_of_role(Role.HUNTER)
        victim = next(s for s in st.alive_seats() if s != hunter)
        agents = {
            s: ScriptedAgent(s, st.players[s].role, {"hunter_shoot": {"target": victim}})
            for s in st.seats
        }
        st.day = 1
        eng = Engine(st, agents)
        eng._setup()
        eng.kill(hunter, when="night", cause=cause)
        eng._after_death(hunter, allow_last_words=False, allow_hunter=True)
        return st, hunter, victim

    def test_hunter_can_shoot_when_knifed(self):
        st, hunter, victim = self._run_death("killed")
        self.assertFalse(st.players[victim].alive, "被刀的猎人应该能开枪")

    def test_hunter_cannot_shoot_when_poisoned(self):
        st, hunter, victim = self._run_death("poisoned")
        self.assertTrue(st.players[victim].alive, "被毒死的猎人不能开枪")

    def test_poison_beats_knife_for_shoot_eligibility(self):
        """同时被刀和被毒 → 按被毒处理，不能开枪"""
        st = make_state()
        hunter = st.seat_of_role(Role.HUNTER)
        agents = {s: HeuristicAgent(s, st.players[s].role, seed=0) for s in st.seats}
        eng = Engine(st, agents)
        eng._setup()
        st.day = 1
        st.night_kill_target = hunter
        st.night_poison_target = hunter
        eng.run_dawn()
        self.assertEqual(st.players[hunter].died_cause, "poisoned")


class TestSheriffRules(unittest.TestCase):
    def test_sheriff_has_1_5_votes(self):
        st = make_state()
        st.sheriff_seat = 1
        st.players[1].is_sheriff = True
        self.assertEqual(st.vote_weight(1), 1.5)
        self.assertEqual(st.vote_weight(2), 1.0)

    def test_badge_transfer(self):
        st = make_state()
        st.sheriff_seat = 1
        st.players[1].is_sheriff = True
        st.day = 1
        agents = {
            s: ScriptedAgent(s, st.players[s].role, {"badge_transfer": {"target": 5, "reason": ""}})
            for s in st.seats
        }
        eng = Engine(st, agents)
        eng.kill(1, when="vote", cause="exiled")
        eng._handle_badge(1)
        self.assertEqual(st.sheriff_seat, 5)
        self.assertTrue(st.players[5].is_sheriff)

    def test_badge_tear(self):
        st = make_state()
        st.sheriff_seat = 1
        st.players[1].is_sheriff = True
        st.day = 1
        agents = {
            s: ScriptedAgent(s, st.players[s].role, {"badge_transfer": {"target": None, "reason": ""}})
            for s in st.seats
        }
        eng = Engine(st, agents)
        eng.kill(1, when="vote", cause="exiled")
        eng._handle_badge(1)
        self.assertIsNone(st.sheriff_seat)
        self.assertEqual(st.sheriff_status, "destroyed")

    def test_no_sheriff_when_everyone_runs(self):
        st = make_state()
        st.day = 1
        agents = {
            s: ScriptedAgent(s, st.players[s].role, {"sheriff_signup": {"run": True, "reason": ""}})
            for s in st.seats
        }
        eng = Engine(st, agents)
        eng._setup()
        eng.run_sheriff_election()
        self.assertEqual(st.sheriff_status, "lost")
        self.assertIsNone(st.sheriff_seat)


class TestVoteRules(unittest.TestCase):
    def test_everyone_abstains_means_no_exile(self):
        st = make_state()
        st.day = 1
        agents = {
            s: ScriptedAgent(s, st.players[s].role, {"vote": {"target": None, "reason": ""}})
            for s in st.seats
        }
        eng = Engine(st, agents)
        eng._setup()
        eng.run_day_vote()
        self.assertEqual(len(st.alive_seats()), 12, "全员弃票不应该有人出局")

    def test_tie_goes_to_pk_then_peaceful_day(self):
        """平票 → PK 发言 → 再平票 → 平安日"""
        st = make_state()
        st.day = 1
        # 1~6 号投 7 号，7~12 号投 1 号，制造 6:6 平票
        def vote(view):
            target = 7 if view.seat <= 6 else 1
            opts = view.legal_actions["schema"]["target"]["options"]
            return {"target": target if target in opts else None, "reason": ""}

        agents = {s: ScriptedAgent(s, st.players[s].role, {"vote": vote}) for s in st.seats}
        eng = Engine(st, agents)
        eng._setup()
        eng.run_day_vote()
        rounds = [v for v in st.vote_history if v["type"] == "exile"]
        self.assertGreaterEqual(len(rounds), 2, "平票后应该有第二轮投票")
        self.assertEqual(len(st.alive_seats()), 12, "两轮都平票应该是平安日")


class TestSmoke(unittest.TestCase):
    def test_200_games_terminate_cleanly(self):
        """200 局随机对局：不崩、不死循环、一定有结局。"""
        from collections import Counter

        tally = Counter()
        for seed in range(200):
            st = new_game(GameConfig(seed=seed))
            agents = {s: HeuristicAgent(s, st.players[s].role, seed=seed) for s in st.seats}
            st = Engine(st, agents).run()
            self.assertIsNotNone(st.winner, f"seed={seed} 没有分出胜负")
            self.assertLess(st.day, st.config.max_days, f"seed={seed} 打满了最大天数")
            # 没有任何 agent 走到安全回退（说明规则 bot 始终给出合法动作）
            fallbacks = [e for e in st.event_log if e.type in ("fallback_action", "agent_error")]
            self.assertEqual(fallbacks, [], f"seed={seed} 出现了非法动作回退：{fallbacks[:1]}")
            tally[st.winner] += 1
        # 两边都得能赢，否则说明规则或 bot 有单边 bug
        self.assertGreater(tally[Faction.VILLAGE], 20, f"好人胜率过低：{tally}")
        self.assertGreater(tally[Faction.WOLF], 20, f"狼人胜率过低：{tally}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
