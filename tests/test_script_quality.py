"""剧本质量测试：警徽流、狼队分工、发言档案、上下文完整性。

这些是让对局读起来像真人局的机制。它们坏掉不会让程序崩溃，
只会让剧本变得很假 —— 所以必须有测试盯着。
"""
from __future__ import annotations

import unittest

from werewolf import prompts
from werewolf.actions import WOLF_POSITIONS
from werewolf.agents.heuristic import HeuristicAgent
from werewolf.engine import Engine
from werewolf.roles import Role
from werewolf.state import GameConfig, new_game
from werewolf.views import build_player_view


def play(seed=0, **cfg):
    st = new_game(GameConfig(seed=seed, **cfg))
    agents = {s: HeuristicAgent(s, st.players[s].role, seed=seed) for s in st.seats}
    return Engine(st, agents).run()


class TestBadgeFlow(unittest.TestCase):
    """警徽流是 12 人局最核心的机制 —— 预言家靠它在死后继续指挥好人。"""

    def test_real_seer_always_reports_a_badge_flow(self):
        for seed in range(30):
            st = play(seed)
            seer = st.seat_of_role(Role.SEER)
            spoke = any(sp["seat"] == seer for sp in st.speech_log)
            if not spoke:
                continue  # 首夜就被刀，还没来得及发言
            flows = [b for b in st.public_badge_flows if b["by"] == seer]
            self.assertTrue(flows, f"seed={seed} 预言家发了言却没报警徽流")

    def test_badge_flow_never_changes_once_announced(self):
        """警徽流是承诺，改口等于自证是狼。

        缩短是允许的 —— 目标死了或已经验过了，那是履约的进度，不是改口。
        不允许的是：一个还活着、还没验的目标被悄悄换掉。
        """
        for seed in range(40):
            st = play(seed)
            died_on = {d["seat"]: d["day"] for d in st.death_record}
            by_speaker: dict[int, list] = {}
            for b in st.public_badge_flows:
                prev = by_speaker.get(b["by"])
                if prev is not None:
                    checked_by_now = {
                        c["target"] for c in st.seer_checks if c["day"] <= b["day"]
                    }
                    for dropped in set(prev) - set(b["targets"]):
                        consumed = (
                            dropped in checked_by_now
                            or died_on.get(dropped, 99) <= b["day"]
                        )
                        self.assertTrue(
                            consumed,
                            f"seed={seed} 第{b['day']}天 {b['by']}号 把还活着也没验过的 "
                            f"{dropped}号 从警徽流里换掉了：{prev} → {b['targets']}",
                        )
                    # 老的警徽流全部履约完（验完或目标死了）之后，可以报一份新的；
                    # 但不能在老的还没走完时就往里塞新目标。
                    added = set(b["targets"]) - set(prev)
                    if added:
                        unconsumed = [
                            t for t in prev
                            if t not in checked_by_now and died_on.get(t, 99) > b["day"]
                        ]
                        self.assertFalse(
                            unconsumed,
                            f"seed={seed} 第{b['day']}天 {b['by']}号 在 {unconsumed} 还没验的情况下"
                            f"就往警徽流里加了 {sorted(added)}：{prev} → {b['targets']}",
                        )
                by_speaker[b["by"]] = b["targets"]

    def test_seer_actually_verifies_what_it_promised(self):
        """说到做到本身就是身份证明：活着的预言家要兑现自己报的警徽流。"""
        promised = fulfilled = 0
        for seed in range(40):
            st = play(seed)
            seer = st.seat_of_role(Role.SEER)
            flows = [b for b in st.public_badge_flows if b["by"] == seer]
            if not flows:
                continue
            checked = {c["target"] for c in st.seer_checks}
            # 只统计预言家报完警徽流之后还活着的晚上能验到的目标
            nights_left = len([c for c in st.seer_checks if c["day"] > flows[0]["day"]])
            for t in flows[0]["targets"][:nights_left]:
                promised += 1
                if t in checked:
                    fulfilled += 1
        self.assertGreater(promised, 0, "没有任何可统计的警徽流兑现机会")
        self.assertGreaterEqual(
            fulfilled / promised, 0.9,
            f"预言家只兑现了 {fulfilled}/{promised} 个警徽流目标",
        )

    def test_wolves_fake_a_badge_flow_when_hard_claiming(self):
        """悍跳狼不报警徽流的话一眼就假。"""
        found = False
        for seed in range(40):
            st = play(seed)
            for b in st.public_badge_flows:
                if st.is_wolf(b["by"]):
                    found = True
                    claim = st.public_claims.get(b["by"], {}).get("claim")
                    self.assertEqual(claim, "SEER", "报警徽流的狼应该是在悍跳预言家")
        self.assertTrue(found, "40 局里没有任何狼报过警徽流，悍跳逻辑可能没生效")


class TestWolfCoordination(unittest.TestCase):
    def test_wolves_assign_day_positions(self):
        for seed in range(20):
            st = play(seed)
            assign = st.wolf_strategy_board.get("assignments") or {}
            self.assertTrue(assign, f"seed={seed} 狼队完全没有分工")
            for seat, pos in assign.items():
                self.assertIn(pos, WOLF_POSITIONS)
                self.assertTrue(st.is_wolf(int(seat)), "分工只能派给狼队友")

    def test_at_most_one_hard_claim(self):
        """一队只出一个悍跳，两个狼同时跳预言家是送人头。"""
        for seed in range(30):
            st = play(seed)
            assign = st.wolf_strategy_board.get("assignments") or {}
            n = sum(1 for p in assign.values() if p == "HARD_CLAIM")
            self.assertLessEqual(n, 1, f"seed={seed} 出现了 {n} 个悍跳")

    def test_hard_claiming_wolf_never_reverts_to_villager(self):
        """悍跳之后改口说自己是平民 = 当场自曝，绝不能发生。"""
        for seed in range(40):
            st = play(seed)
            for seat in st.wolf_seats():
                claims = [sp["claim"] for sp in st.speech_log
                          if sp["seat"] == seat and sp["claim"]]
                if "SEER" in claims:
                    after = claims[claims.index("SEER"):]
                    self.assertTrue(
                        all(c == "SEER" for c in after),
                        f"seed={seed} {seat}号 悍跳预言家后又改口：{claims}",
                    )

    def test_nobody_ever_votes_for_themselves(self):
        for seed in range(40):
            st = play(seed)
            for v in st.vote_history:
                for voter, target in v["votes"].items():
                    self.assertNotEqual(
                        int(voter), target,
                        f"seed={seed} 第{v['day']}天 {voter}号投了自己",
                    )


class TestSpeechArchive(unittest.TestCase):
    """发言档案是 agent 能"盘逻辑"的前提。"""

    def test_archive_contains_every_public_speech(self):
        st = play(7)
        kinds = {"speech", "sheriff_speech", "sheriff_pk_speech", "pk_speech", "last_words"}
        spoken = [e for e in st.event_log if e.type in kinds]
        self.assertEqual(len(st.speech_log), len(spoken))

    def test_recent_days_keep_full_text_older_days_compressed(self):
        st = play(7)
        if st.day < 3:
            self.skipTest("这局太短，没有需要压缩的早期发言")
        view = build_player_view(st, st.alive_seats()[0])
        arch = view.public_state["speech_archive"]
        self.assertTrue(any(e["full"] for e in arch), "近两天应该有原文")
        self.assertTrue(any(not e["full"] for e in arch), "更早的应该被压缩")
        # 档案和原始 speech_log 是一一对应的，按顺序配对
        self.assertEqual(len(arch), len(st.speech_log))
        for e, sp in zip(arch, st.speech_log):
            self.assertEqual((e["day"], e["seat"]), (sp["day"], sp["seat"]))
            if e["full"]:
                self.assertEqual(e["text"], sp["text"], "近两天必须是发言原文")
            else:
                self.assertTrue(sp["text"].startswith(e["text"].rstrip("…")))

    def test_day_one_speeches_survive_into_late_game_prompts(self):
        """回归测试：早期这里有个 bug —— 发言只在事件增量里发一次，
        对话历史一裁剪就永久丢失，agent 根本没法盘第一天的逻辑。
        现在发言档案每回合重发，第一天的立场必须始终出现在 prompt 里。
        """
        st = play(7)
        if st.day < 3:
            self.skipTest("这局太短")
        day1 = [sp for sp in st.speech_log if sp["day"] == 1]
        self.assertTrue(day1)
        seat = st.alive_seats()[0]
        view = build_player_view(st, seat, action_type="speech")
        text = prompts.turn_prompt(view, full=False)  # 注意：增量模式
        self.assertIn("全场发言档案", text)
        for sp in day1[:3]:
            self.assertIn(f"{sp['seat']}号", text)
            head = sp["text"][:12]
            self.assertIn(head, text,
                          f"第1天 {sp['seat']}号 的发言没有出现在第{st.day}天的 prompt 里")

    def test_archive_is_public_so_everyone_sees_the_same_one(self):
        st = play(7)
        archives = [
            str(build_player_view(st, s).public_state["speech_archive"])
            for s in st.seats
        ]
        self.assertEqual(len(set(archives)), 1, "发言档案是公开信息，所有人看到的必须一致")


class TestPromptStructure(unittest.TestCase):
    def test_seer_prompt_teaches_the_three_part_speech(self):
        st = new_game(GameConfig(seed=1))
        st.day = 1
        view = build_player_view(st, st.seat_of_role(Role.SEER), action_type="speech")
        sp = prompts.system_prompt(view)
        for kw in ("报查验", "留警徽流", "心路历程", "撕掉警徽"):
            self.assertIn(kw, sp, f"预言家的 prompt 里缺少「{kw}」")

    def test_wolf_prompt_teaches_the_four_positions(self):
        st = new_game(GameConfig(seed=1))
        st.day = 1
        view = build_player_view(st, st.wolf_seats()[0], action_type="speech")
        sp = prompts.system_prompt(view)
        for kw in ("悍跳", "冲锋", "倒钩", "深水"):
            self.assertIn(kw, sp, f"狼人的 prompt 里缺少定位「{kw}」")

    def test_villager_prompt_teaches_declare_innocence_first(self):
        st = new_game(GameConfig(seed=1))
        st.day = 1
        villager = st.seat_of_role(Role.VILLAGER)
        view = build_player_view(st, villager, action_type="speech")
        self.assertIn("表水", prompts.system_prompt(view))

    def test_position_value_is_explained(self):
        st = new_game(GameConfig(seed=1))
        st.day = 1
        view = build_player_view(st, 1, action_type="speech")
        self.assertIn("后置位", prompts.system_prompt(view))

    def test_wolf_turn_prompt_shows_enemy_badge_flow_and_assignments(self):
        st = play(21)
        wolf = st.wolf_seats()[0]
        view = build_player_view(st, wolf, action_type="speech")
        text = prompts.turn_prompt(view, full=False)
        self.assertIn("狼队视角", text)
        if view.wolf_team.intel["enemy_badge_flows"]:
            self.assertIn("对方报的警徽流", text)
        if view.wolf_team.strategy_board.get("assignments"):
            self.assertIn("狼队白天分工", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
