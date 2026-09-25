"""中文显示层测试。

规矩：英文标识符只允许活在代码和数据库列里。**只要它出现在人眼前就是 bug。**
"""
from __future__ import annotations

import json
import re
import unittest

from werewolf import i18n, prompts
from werewolf.actions import ACTION_TYPES, WOLF_POSITIONS
from werewolf.agents.heuristic import HeuristicAgent
from werewolf.engine import Engine
from werewolf.events import Audience
from werewolf.replay import render_replay
from werewolf.roles import Role
from werewolf.state import GameConfig, new_game
from werewolf.views import build_player_view

#: 会被判为"系统英文标识符"的形状：全大写枚举、以及所有动作名/死因名
_LEAK = re.compile(
    r"\b[A-Z][A-Z_]{2,}\b"
    r"|\b(?:speech|vote|wolf_chat|wolf_kill|seer_check|witch_action|last_words"
    r"|hunter_shoot|badge_transfer|sheriff_signup|sheriff_speech|sheriff_vote"
    r"|killed|exiled|poisoned|exploded|game_over|heuristic)\b"
)

#: 允许出现的英文：模型名、URL、以及产品名
_ALLOWED = re.compile(r"claude-[\w.-]+|gpt-[\w.-]+|o\d-mini|https?://\S+|Claude|OpenAI|JSON|API")


def leaks(text: str) -> list[str]:
    return sorted(set(_LEAK.findall(_ALLOWED.sub(" ", text))))


def play(seed=21, **cfg):
    st = new_game(GameConfig(seed=seed, **cfg))
    return Engine(st, {s: HeuristicAgent(s, st.players[s].role, seed=seed)
                       for s in st.seats}).run()


class TestTablesAreComplete(unittest.TestCase):
    def test_every_action_type_has_a_chinese_name(self):
        for at in ACTION_TYPES:
            self.assertIn(at, i18n.ACTION_CN, f"动作 {at} 没有中文名")
            self.assertTrue(i18n.action_cn(at).strip())

    def test_every_phase_reached_in_play_has_a_chinese_name(self):
        st = play()
        for e in st.event_log:
            self.assertIn(e.phase, i18n.PHASE_CN, f"阶段 {e.phase} 没有中文名")

    def test_every_role_faction_and_position_has_a_chinese_name(self):
        for r in Role:
            self.assertTrue(i18n.role_cn(r.value).strip())
        for p in WOLF_POSITIONS:
            self.assertIn(p, i18n.POSITION_CN, f"狼队定位 {p} 没有中文名")
        for a in Audience:
            self.assertTrue(i18n.audience_cn_of(a.value).strip())

    def test_unknown_key_degrades_instead_of_crashing(self):
        self.assertEqual(i18n.phase_cn("NOT_A_PHASE"), "NOT_A_PHASE")
        self.assertEqual(i18n.phase_cn(None), "")
        self.assertEqual(i18n.role_cn(None), "")


class TestNoEnglishInPlayerFacingText(unittest.TestCase):
    def test_replay_has_no_system_identifiers(self):
        for seed in (3, 21, 42):
            found = leaks(render_replay(play(seed)))
            self.assertEqual(found, [], f"seed={seed} 战报里漏了英文标识符：{found}")

    def test_public_event_text_has_no_system_identifiers(self):
        st = play()
        for e in st.event_log:
            if e.audience is Audience.GOD:
                continue
            found = leaks(e.text)
            self.assertEqual(found, [], f"事件正文漏了英文：{e.text[:70]} → {found}")

    def test_god_log_is_chinese_too(self):
        """上帝日志也是给人看的（复盘要读），不能留英文死因。"""
        st = play()
        for e in st.event_log:
            if e.audience is not Audience.GOD or e.type in ("setup", "thought"):
                continue
            found = leaks(e.text)
            self.assertEqual(found, [], f"上帝日志漏了英文：{e.text[:70]} → {found}")

    def test_turn_prompt_has_no_system_identifiers(self):
        st = play()
        seat = st.alive_seats()[0]
        view = build_player_view(st, seat, action_type="speech")
        text = prompts.turn_prompt(view, full=True)
        # prompt 里的字段名（schema）是给模型看的，只查局势和档案那几段
        head = text.split("════════ 轮到你了")[0]
        found = leaks(head)
        self.assertEqual(found, [], f"prompt 局势部分漏了英文：{found}")

    def test_thought_log_entries_carry_chinese(self):
        st = play()
        for t in st.thought_log:
            self.assertTrue(t.get("phase_cn"), "心路历程缺 phase_cn")
            self.assertTrue(t.get("action_cn"), "心路历程缺 action_cn")
            if t["accepted"] and t["action"]:
                self.assertTrue(t.get("action_desc") is not None)
                self.assertEqual(leaks(t["action_desc"]), [],
                                 f"动作描述漏了英文：{t['action_desc']}")


class TestApiCarriesChinese(unittest.TestCase):
    """网页端不自己维护一份翻译表 —— 中文由服务端给。"""

    def test_events_carry_phase_cn(self):
        st = play()
        for e in st.event_log:
            d = e.as_dict()
            self.assertIn("phase_cn", d)
            self.assertIn("audience_cn", d)
            self.assertNotIn("_", d["phase_cn"], "phase_cn 看着还是英文标识符")

    def test_view_timeline_carries_phase_cn(self):
        st = play()
        view = build_player_view(st, st.alive_seats()[0])
        for e in view.timeline:
            self.assertTrue(e.get("phase_cn"))

    def test_snapshot_carries_chinese_for_everything_rendered(self):
        from werewolf.lineup import Lineup
        from werewolf.server import GameRunner

        g = GameRunner(GameConfig(seed=3, n_players=9), Lineup.uniform(9))
        g.session.run()
        snap = g.snapshot()
        self.assertTrue(snap["phase_cn"])
        self.assertIn("sheriff_status_cn", snap)
        for p in snap["players"]:
            self.assertIn("claim_cn", p)
            self.assertIn("died_cause_cn", p)
            if p["claim"]:
                self.assertNotEqual(p["claim_cn"], p["claim"], "自称身份没翻译")
            if p["died_cause"]:
                self.assertNotEqual(p["died_cause_cn"], p["died_cause"])
        for s in g.agent_sessions():
            self.assertIn("release_reason_cn", s)
            self.assertIn("backend_cn", s)

    def test_frontend_uses_the_chinese_fields(self):
        """前端必须读 _cn 字段，而不是自己拼英文。"""
        from pathlib import Path

        js = Path("web/app.js").read_text(encoding="utf-8")
        for expected in ("phase_cn", "claim_cn", "action_cn", "action_desc",
                         "release_reason_cn", "died_cause_cn"):
            self.assertIn(expected, js, f"前端没用 {expected}")


class TestDescribeAction(unittest.TestCase):
    def test_covers_every_action_type(self):
        samples = {
            "wolf_chat": {"my_position": "HARD_CLAIM", "kill_suggestion": 3},
            "wolf_kill": {"target": 3},
            "seer_check": {"target": 7},
            "witch_action": {"heal": True, "poison": None},
            "sheriff_signup": {"run": True},
            "sheriff_speech": {"claim": "SEER", "quit": False},
            "sheriff_vote": {"target": 2},
            "badge_transfer": {"target": 5},
            "speech": {"claim": "VILLAGER", "suspects": [7]},
            "vote": {"target": None},
            "last_words": {"claim": "WITCH"},
            "hunter_shoot": {"target": 9},
        }
        for at in ACTION_TYPES:
            desc = i18n.describe_action(at, samples[at])
            self.assertTrue(desc, f"{at} 没有生成描述")
            self.assertEqual(leaks(desc), [], f"{at} 的描述里有英文：{desc}")

    def test_explode_is_described(self):
        self.assertEqual(i18n.describe_action("speech", {"explode": True}), "自爆")

    def test_empty_action_is_safe(self):
        self.assertEqual(i18n.describe_action("speech", None), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
