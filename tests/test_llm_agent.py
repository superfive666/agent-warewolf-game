"""LLM 后端测试：用假的 Anthropic client 跑通整条代码路径。

真正调用 Claude 需要 ANTHROPIC_API_KEY，CI 里跑不了，
所以这里用一个返回合法 JSON 的假 client，验证：
  · prompt 能正确渲染（system 稳定、user 增量）
  · 返回的 JSON 能被 actions.validate 接受
  · 非法动作时能带着错误信息重试
  · private_thought 被剥离，不会进入任何玩家视角
"""
from __future__ import annotations

import json
import unittest

from werewolf import prompts
from werewolf.agents.llm import LLMAgent
from werewolf.engine import Engine
from werewolf.events import Audience
from werewolf.roles import Role
from werewolf.state import GameConfig, new_game


class _Block:
    type = "text"

    def __init__(self, text):
        self.text = text


class _Response:
    def __init__(self, text):
        self.content = [_Block(text)]
        self.usage = type("U", (), {"input_tokens": 10, "output_tokens": 5,
                                    "cache_read_input_tokens": 0})()


class FakeMessages:
    """按 action_type 造一个合法动作，并记下收到的请求。"""

    def __init__(self, owner):
        self.owner = owner

    def create(self, **kw):
        self.owner.calls.append({"seat": self.owner.current_seat, **kw})
        schema = kw["output_config"]["format"]["schema"]
        fields = set(schema["properties"])
        la = self.owner.current_legal_actions
        at = la["action_type"]

        def first_option(field, fallback=None):
            opts = la["schema"].get(field, {}).get("options")
            if not opts:
                return fallback
            real = [o for o in opts if o is not None]
            return real[0] if real else None

        out = {"private_thought": f"我在想 {at} 该怎么做"}
        if "speech" in fields:
            out["speech"] = f"这是 {at} 的发言。"
        for f in ("claim", "claim_detail", "claimed_check"):
            if f in fields:
                out[f] = "" if f == "claim_detail" else None
        for f in ("suspects", "trusts"):
            if f in fields:
                out[f] = []
        if "target" in fields:
            out["target"] = first_option("target")
        if "kill_suggestion" in fields:
            out["kill_suggestion"] = first_option("kill_suggestion")
        if "strategy_note" in fields:
            out["strategy_note"] = ""
        if "heal" in fields:
            out["heal"] = False
        if "poison" in fields:
            out["poison"] = None
        if "run" in fields:
            out["run"] = False
        if "reason" in fields:
            out["reason"] = "因为我觉得是这样"
        if "quit" in fields:
            out["quit"] = False
        return _Response(json.dumps(out, ensure_ascii=False))


class FakeClient:
    def __init__(self):
        self.calls = []
        self.current_seat = None
        self.current_legal_actions = None
        self.messages = FakeMessages(self)


class _TrackingLLMAgent(LLMAgent):
    """把当前的 legal_actions 透给 FakeClient，好让它造出合法动作。"""

    def act(self, view, error=None):
        self._client.current_seat = self.seat
        self._client.current_legal_actions = view.legal_actions
        return super().act(view, error)


class TestLLMAgent(unittest.TestCase):
    def test_full_game_with_fake_llm(self):
        """12 个假 LLM agent 打完一整局，不出现任何回退。"""
        client = FakeClient()
        state = new_game(GameConfig(seed=5))
        agents = {
            s: _TrackingLLMAgent(s, state.players[s].role, client=client)
            for s in state.seats
        }
        state = Engine(state, agents).run()

        self.assertIsNotNone(state.winner)
        bad = [e for e in state.event_log if e.type in ("agent_error", "fallback_action")]
        self.assertEqual(bad, [], f"假 LLM 的动作应该全部合法，但出现了：{bad[:2]}")
        self.assertGreater(len(client.calls), 50, "应该发生了很多次模型调用")

    def test_system_prompt_is_byte_stable(self):
        """system 整局逐字不变，才能命中 prompt cache。"""
        client = FakeClient()
        state = new_game(GameConfig(seed=5))
        agents = {
            s: _TrackingLLMAgent(s, state.players[s].role, client=client)
            for s in state.seats
        }
        Engine(state, agents).run()
        by_seat = {}
        for call in client.calls:
            by_seat.setdefault(call["seat"], set()).add(call["system"][0]["text"])
        for seat, variants in by_seat.items():
            self.assertEqual(len(variants), 1, f"{seat}号的 system prompt 中途变了")
        for call in client.calls:
            self.assertEqual(call["system"][0]["cache_control"], {"type": "ephemeral"})

    def test_private_thought_never_reaches_any_view(self):
        client = FakeClient()
        state = new_game(GameConfig(seed=5))
        agents = {
            s: _TrackingLLMAgent(s, state.players[s].role, client=client)
            for s in state.seats
        }
        state = Engine(state, agents).run()
        self.assertTrue(any(a.thoughts for a in agents.values()), "应该记录了内心想法")
        dumped = json.dumps(
            [e.as_dict() for e in state.event_log], ensure_ascii=False
        )
        self.assertNotIn("我在想", dumped, "private_thought 漏进了事件日志")

    def test_retry_on_invalid_action(self):
        """动作非法时，错误信息要回灌给模型并重试。"""
        state = new_game(GameConfig(seed=5))
        seer = state.seat_of_role(Role.SEER)
        state.day = 1

        class BadThenGood:
            def __init__(self):
                self.errors = []
                self.n = 0

            def act(self, view, error=None):
                self.errors.append(error)
                self.n += 1
                if self.n == 1:
                    return {"target": view.seat}  # 非法：不能验自己
                return {"target": view.legal_actions["schema"]["target"]["options"][0]}

        agents = {s: BadThenGood() for s in state.seats}
        eng = Engine(state, agents)
        eng._setup()
        eng._night_seer()
        agent = agents[seer]
        self.assertEqual(agent.n, 2, "应该重试了一次")
        self.assertIsNone(agent.errors[0])
        self.assertIn("不是合法目标", agent.errors[1])
        self.assertEqual(len(state.seer_checks), 1)

    def test_output_schema_covers_every_action_type(self):
        from werewolf.actions import ACTION_TYPES

        for at in ACTION_TYPES:
            schema = prompts.output_schema(at)["schema"]
            self.assertFalse(schema["additionalProperties"])
            self.assertIn("private_thought", schema["properties"])
            self.assertEqual(set(schema["required"]), set(schema["properties"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
