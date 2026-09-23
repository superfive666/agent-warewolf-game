"""信息隔离测试：对每局的全部 13 份视角做穷举断言。

对应 docs/04-视角与上下文.md §4。这是整个项目最重要的一组测试 ——
只要这里全绿，就没有任何 agent 能看到它不该看到的东西。
"""
from __future__ import annotations

import json
import unittest

from werewolf.agents.heuristic import HeuristicAgent
from werewolf.engine import Engine
from werewolf.events import Audience, visible_to_seat
from werewolf.roles import Role
from werewolf.state import GameConfig, new_game
from werewolf.views import build_player_view, build_wolf_team_view

N_GAMES = 40


def play(seed: int, **cfg):
    state = new_game(GameConfig(seed=seed, **cfg))
    agents = {s: HeuristicAgent(s, state.players[s].role, seed=seed) for s in state.seats}
    #: 逐帧记录每个决策点的视角
    snapshots = []
    engine = Engine(
        state, agents,
        view_recorder=lambda turn, seat, at, view: snapshots.append((seat, at, view)),
    )
    return engine.run(), snapshots


class TestVisibility(unittest.TestCase):
    """8 条断言 × N 局 × 每个决策点的视角快照。"""

    @classmethod
    def setUpClass(cls):
        cls.games = [play(seed) for seed in range(N_GAMES)]

    # 断言 1：非狼玩家的 timeline 里不含任何 WOLVES 事件
    def test_1_no_wolf_channel_leak(self):
        for state, snaps in self.games:
            wolves = set(state.wolf_seats())
            wolf_texts = {e.text for e in state.event_log if e.audience is Audience.WOLVES}
            for seat, _, view in snaps:
                if seat in wolves:
                    continue
                for entry in view.timeline:
                    self.assertNotIn(
                        entry["text"], wolf_texts,
                        f"{seat}号（好人）看到了狼人频道事件：{entry['text']}",
                    )

    # 断言 2：不含 visible_to 不包含自己的 PRIVATE 事件
    def test_2_no_private_leak(self):
        for state, snaps in self.games:
            by_text = {}
            for e in state.event_log:
                if e.audience is Audience.PRIVATE:
                    by_text.setdefault(e.text, set()).update(e.visible_to)
            for seat, _, view in snaps:
                for entry in view.timeline:
                    if entry["vis"] != "private":
                        continue
                    allowed = by_text.get(entry["text"])
                    self.assertIsNotNone(allowed, f"未知的 private 事件：{entry['text']}")
                    self.assertIn(seat, allowed, f"{seat}号看到了别人的私有事件：{entry['text']}")

    # 断言 3：视角里不含别人的真实身份（规则性公开除外）
    def test_3_no_role_leak(self):
        for state, snaps in self.games:
            # 规则允许公开身份的只有两种：白痴翻牌、狼人自爆。二者都有对应的公开事件。
            revealed_by_rule = {
                e.actor for e in state.event_log
                if e.type in ("idiot_reveal", "explode")
            }
            public_role_values = {
                state.players[s].role.value for s in revealed_by_rule
            }

            for seat, action_type, view in snaps:
                d = view.as_dict()
                # 剥掉三类"长得像身份表但其实不是"的东西：
                #   1. legal_actions —— 是动作 schema，里面的角色枚举是给所有人看的
                #   2. public_claims / public_check_claims —— 谁自称什么本来就是公开信息
                #   3. 事件 payload 里的 claim —— 同上
                #   4. rules_digest —— 板子构成（几狼几神几民）是全场公开的规则信息
                d.pop("legal_actions", None)
                d["public_state"].pop("public_claims", None)
                d["public_state"].pop("public_check_claims", None)
                d["public_state"].pop("rules_digest", None)
                if d["wolf_team"]:
                    d["wolf_team"]["intel"].pop("claimed_roles", None)
                for e in d["timeline"] + d["delta"]:
                    e.get("payload", {}).pop("claim", None)

                # 公开投影里根本不该有 role 字段
                for other, proj in d["public_state"]["players"].items():
                    self.assertNotIn("role", proj, f"公开玩家投影里出现了 role：{proj}")
                    if proj["revealed_role"] is not None:
                        self.assertIn(
                            int(other), revealed_by_rule,
                            f"{other}号的身份被标为公开，但没有对应的翻牌/自爆事件",
                        )

                dumped = json.dumps(d, ensure_ascii=False)
                allowed = {state.players[seat].role.value} | public_role_values
                if state.players[seat].is_wolf:
                    allowed.add(Role.WEREWOLF.value)  # 狼人本来就知道队友是狼
                for other in state.seats:
                    op = state.players[other]
                    if other == seat or op.role.value in allowed:
                        continue
                    if op.role.value in dumped:
                        self.fail(
                            f"{seat}号（{state.players[seat].role.cn}）在 {action_type} 决策点的视角里"
                            f"泄露了 {other}号 的真实身份 {op.role.cn}"
                        )
                # GOD 级事件绝不能出现在任何视角里
                for entry in view.timeline:
                    self.assertNotEqual(entry["vis"], "god")

    # 断言 4：好人的 wolf_team 恒为 None
    def test_4_goods_have_no_wolf_view(self):
        for state, snaps in self.games:
            wolves = set(state.wolf_seats())
            for seat, _, view in snaps:
                if seat in wolves:
                    self.assertIsNotNone(view.wolf_team, f"{seat}号是狼却没有狼队视角")
                else:
                    self.assertIsNone(view.wolf_team, f"{seat}号是好人却拿到了狼队视角")

    # 断言 5：狼队视角的 roster 只含 4 名狼人，不含任何好人身份
    def test_5_wolf_view_has_no_good_identities(self):
        for state, _ in self.games:
            wt = build_wolf_team_view(state)
            self.assertEqual([r["seat"] for r in wt.roster], state.wolf_seats())
            dumped = json.dumps(wt.as_dict(), ensure_ascii=False)
            for seat in state.seats:
                p = state.players[seat]
                if p.is_wolf or p.revealed_role:
                    continue
                self.assertNotIn(
                    p.role.value, dumped.split('"claimed_roles"')[0],
                    f"狼队视角里出现了好人 {seat}号 的真实身份 {p.role.cn}",
                )
            # 屠边进度这种上帝信息绝不能出现
            self.assertNotIn("remaining_gods", dumped)
            self.assertNotIn("remaining_villagers", dumped)

    # 断言 6：投票必须收齐后才公布 —— 同一轮里先投和后投的人看到的票型完全相同
    def test_6_votes_hidden_until_tallied(self):
        for game_no, (state, snaps) in enumerate(self.games):
            rounds: dict[tuple, list] = {}
            for seat, action_type, view in snaps:
                if action_type not in ("vote", "sheriff_vote"):
                    continue
                kind = "sheriff" if action_type == "sheriff_vote" else "exile"
                seen = tuple(sorted(
                    e["seq"] for e in view.timeline
                    if e["type"] in ("vote", "sheriff_vote")
                ))
                # 同一天、同一种投票、已公布轮次数相同的，就是同一轮
                key = (view.public_state["day"], kind, len(seen))
                rounds.setdefault(key, []).append((seat, seen, view))

            for key, entries in rounds.items():
                baseline = entries[0][1]
                for seat, seen, view in entries[1:]:
                    self.assertEqual(
                        seen, baseline,
                        f"第{game_no}局 {key}：{seat}号在投票时比同轮其他人多看到了票型，"
                        "说明引擎边收票边公布了",
                    )
                # 并且我的视角里不该出现任何"本轮"的票
                for seat, seen, view in entries:
                    my_votes = [
                        e for e in view.timeline
                        if e["type"] in ("vote", "sheriff_vote")
                    ]
                    for e in my_votes:
                        self.assertIn("计票", e["text"], "出现了未结算的投票事件")

    # 断言 7：预言家的验人结果只出现在预言家自己的视角里
    def test_7_seer_results_private(self):
        for state, snaps in self.games:
            seer = state.seat_of_role(Role.SEER)
            results = [
                e.text for e in state.event_log if e.type == "seer_result"
            ]
            for seat, _, view in snaps:
                if seat == seer:
                    continue
                texts = {e["text"] for e in view.timeline}
                for r in results:
                    self.assertNotIn(r, texts, f"{seat}号看到了预言家的验人结果")

    # 断言 8：女巫的刀口告知只出现在女巫自己的视角里
    def test_8_witch_info_private(self):
        for state, snaps in self.games:
            witch = state.seat_of_role(Role.WITCH)
            infos = [
                e.text for e in state.event_log
                if e.type in ("witch_info", "witch_heal", "witch_poison")
            ]
            for seat, _, view in snaps:
                if seat == witch:
                    continue
                texts = {e["text"] for e in view.timeline}
                for info in infos:
                    self.assertNotIn(info, texts, f"{seat}号看到了女巫的私有信息")


class TestViewShape(unittest.TestCase):
    def test_public_projection_has_no_role_attribute(self):
        """_PublicPlayer 在类型层面就不允许读别人的 role。"""
        from werewolf.views import _PublicPlayer

        state, _ = play(1)
        proj = _PublicPlayer(state.players[1])
        with self.assertRaises(AttributeError):
            _ = proj.role

    def test_exactly_13_contexts(self):
        state, _ = play(3)
        from werewolf.views import build_all_views

        views = build_all_views(state)
        self.assertEqual(len(views["players"]), 12)
        self.assertEqual(views["wolf_team"]["view_type"], "wolf_team")
        wolves = [
            s for s, v in views["players"].items() if v["wolf_team"] is not None
        ]
        self.assertEqual(len(wolves), 4, "狼队视角应该正好挂在 4 名狼人身上")
        # 4 名狼人共享的是同一份内容
        dumps = {json.dumps(views["players"][s]["wolf_team"], sort_keys=True) for s in wolves}
        self.assertEqual(len(dumps), 1, "4 名狼人拿到的狼队视角应该完全一致")

    def test_visibility_function_truth_table(self):
        from werewolf.events import Event

        cases = [
            (Audience.PUBLIC, [], True, True),
            (Audience.WOLVES, [], True, False),
            (Audience.PRIVATE, [5], False, False),
            (Audience.GOD, [5], False, False),
        ]
        for aud, vis_to, wolf_sees, good_sees in cases:
            e = Event(seq=1, day=1, phase="X", type="t", audience=aud, text="", visible_to=vis_to)
            self.assertEqual(visible_to_seat(e, 1, True), wolf_sees, f"{aud} 对狼人")
            self.assertEqual(visible_to_seat(e, 1, False), good_sees, f"{aud} 对好人")
        # PRIVATE 对 visible_to 里的人可见
        e = Event(seq=1, day=1, phase="X", type="t", audience=Audience.PRIVATE, text="", visible_to=[5])
        self.assertTrue(visible_to_seat(e, 5, False))


if __name__ == "__main__":
    unittest.main(verbosity=2)
