"""OpenAI（及兼容网关）后端测试。

真调 API 需要 key，CI 里跑不了，所以用假 client 覆盖三件事：
  1. 整条代码路径（prompt 组装 → 调用 → 解析 → 交给引擎校验）
  2. **能力降级**：自建网关不支持 json_schema / max_completion_tokens 时能退让
  3. **密钥安全**：密钥永远不进阵容、不进会话库
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from werewolf.agents.chat_base import extract_json
from werewolf.agents.openai_agent import OpenAIAgent, _is_capability_error
from werewolf.engine import Engine
from werewolf.lineup import AVAILABLE_BACKENDS, Lineup, SeatSpec
from werewolf.roles import Role
from werewolf.state import GameConfig, new_game
from werewolf.views import build_player_view


class FakeErr(Exception):
    def __init__(self, msg, status=400):
        super().__init__(msg)
        self.status_code = status


class FakeCompletions:
    """可配置的假端点：声明自己支持哪些能力，不支持的就报错。"""

    def __init__(self, owner):
        self.owner = owner

    def create(self, **kw):
        o = self.owner
        o.calls.append(kw)
        rf = kw.get("response_format")
        if rf and rf["type"] == "json_schema" and "json_schema" not in o.supports:
            raise FakeErr("Unsupported parameter: response_format.json_schema")
        if rf and rf["type"] == "json_schema" and rf["json_schema"].get("strict") \
                and "strict" not in o.supports:
            raise FakeErr("response_format.json_schema.strict is not supported")
        if rf and rf["type"] == "json_object" and "json_object" not in o.supports:
            raise FakeErr("Unsupported parameter: response_format")
        if "max_completion_tokens" in kw and "max_completion_tokens" not in o.supports:
            raise FakeErr("Unrecognized request argument: max_completion_tokens")
        if "max_tokens" in kw and "max_tokens" not in o.supports:
            raise FakeErr("Unrecognized request argument: max_tokens")
        if "reasoning_effort" in kw and "reasoning_effort" not in o.supports:
            raise FakeErr("Unsupported parameter: reasoning_effort")
        return o.make_response(kw)


class FakeChat:
    def __init__(self, owner):
        self.completions = FakeCompletions(owner)


class FakeOpenAI:
    def __init__(self, supports=("json_schema", "strict", "max_completion_tokens"),
                 wrap=None):
        self.supports = set(supports)
        self.calls = []
        self.wrap = wrap  # 用来模拟"模型不老实，裹了 markdown"
        #: 由 _Tracking agent 填进来，好让假模型挑合法目标（真模型是从 prompt 里读的）
        self.legal = None
        self.chat = FakeChat(self)

    def _pick(self, field, nullable):
        opts = ((self.legal or {}).get("schema", {}).get(field, {}) or {}).get("options")
        real = [o for o in (opts or []) if o is not None]
        if real:
            return real[0]
        return None if nullable else 1

    def make_response(self, kw):
        schema = None
        rf = kw.get("response_format")
        if rf and rf["type"] == "json_schema":
            schema = rf["json_schema"]["schema"]
        else:
            # 降级模式下 schema 是写在 prompt 里的，模拟"老实照着 schema 输出"的模型
            for m in reversed(kw["messages"]):
                if m["role"] == "system" and "JSON Schema" in m["content"]:
                    schema = json.loads(m["content"].split("\n", 1)[1])
                    break
        out = {"private_thought": "我在想这一手"}
        for field, spec in (schema or {}).get("properties", {}).items():
            if field in out:
                continue
            t = spec.get("type")
            types = t if isinstance(t, list) else [t]
            if "string" in types:
                out[field] = "说点什么"
            elif "integer" in types:
                out[field] = self._pick(field, "null" in types)
            elif "boolean" in types:
                out[field] = False
            elif "array" in types:
                out[field] = []
            elif "object" in types:
                out[field] = None if "null" in types else {}
        text = json.dumps(out, ensure_ascii=False)
        if self.wrap:
            text = self.wrap(text)
        return _Resp(text)


class _Msg:
    def __init__(self, c): self.content = c


class _Choice:
    def __init__(self, c):
        self.message = _Msg(c)
        self.finish_reason = "stop"


class _Usage:
    prompt_tokens, completion_tokens, prompt_tokens_details = 100, 20, None


class _Resp:
    def __init__(self, text):
        self.choices = [_Choice(text)]
        self.usage = _Usage()


def _view(action_type="speech", seat=None):
    st = new_game(GameConfig(seed=1))
    st.day = 1
    seat = seat or st.seat_of_role(Role.SEER)
    return build_player_view(st, seat, action_type=action_type)


class TestJsonExtraction(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(extract_json('{"a": 1}'), {"a": 1})

    def test_markdown_fence(self):
        self.assertEqual(extract_json('好的：\n```json\n{"a": 2}\n```'), {"a": 2})

    def test_leading_prose_and_braces_in_strings(self):
        self.assertEqual(
            extract_json('我想了想 {"a": 3, "s": "里面有}花括号"} 就这样'),
            {"a": 3, "s": "里面有}花括号"},
        )

    def test_rejects_garbage(self):
        for bad in ("", "   ", "完全不是 json"):
            with self.assertRaises(ValueError):
                extract_json(bad)


class TestCapabilityDegradation(unittest.TestCase):
    """自建网关能力参差不齐，必须能自己退到能用的那一档。"""

    def _act(self, supports):
        client = FakeOpenAI(supports=supports)
        a = OpenAIAgent(3, Role.SEER, model="my-model", client=client)
        out = a.act(_view())
        return a, client, out

    def test_best_case_uses_strict_json_schema(self):
        a, client, _ = self._act(("json_schema", "strict", "max_completion_tokens"))
        self.assertEqual(a._mode, "json_schema_strict")
        self.assertEqual(a._token_param, "max_completion_tokens")
        self.assertEqual(len(client.calls), 1, "一次就该成功，不该多试")

    def test_falls_back_to_non_strict_schema(self):
        a, _, _ = self._act(("json_schema", "max_completion_tokens"))
        self.assertEqual(a._mode, "json_schema")

    def test_falls_back_to_json_object(self):
        a, _, _ = self._act(("json_object", "max_completion_tokens"))
        self.assertEqual(a._mode, "json_object")

    def test_falls_back_to_plain_text(self):
        a, _, out = self._act(("max_tokens",))
        self.assertEqual(a._mode, "text")
        self.assertEqual(a._token_param, "max_tokens")
        self.assertIn("speech", out)

    def test_falls_back_to_max_tokens(self):
        a, _, _ = self._act(("json_schema", "strict", "max_tokens"))
        self.assertEqual(a._token_param, "max_tokens")

    def test_working_mode_is_remembered(self):
        client = FakeOpenAI(supports=("json_object", "max_tokens"))
        a = OpenAIAgent(3, Role.SEER, model="m", client=client)
        a.act(_view())
        n_first = len(client.calls)
        client.calls.clear()
        a.act(_view())
        self.assertEqual(len(client.calls), 1,
                         f"第一次试探用了 {n_first} 次，之后应该直接命中")

    def test_auth_errors_are_not_retried(self):
        """认证/额度问题降级一百次也没用，必须直接抛。"""
        class Dead(FakeOpenAI):
            def make_response(self, kw):
                raise FakeErr("Incorrect API key provided", 401)

        a = OpenAIAgent(3, Role.SEER, model="m", client=Dead())
        with self.assertRaises(FakeErr):
            a.act(_view())

    def test_capability_error_classification(self):
        self.assertTrue(_is_capability_error(FakeErr("Unsupported parameter: x")))
        self.assertTrue(_is_capability_error(TypeError("unexpected keyword")))
        self.assertFalse(_is_capability_error(FakeErr("rate limit", 429)))
        self.assertFalse(_is_capability_error(FakeErr("boom", 500)))
        self.assertFalse(_is_capability_error(FakeErr("insufficient quota", 400)))

    def test_untidy_model_output_still_parses(self):
        client = FakeOpenAI(wrap=lambda t: f"当然可以！\n```json\n{t}\n```")
        a = OpenAIAgent(3, Role.SEER, model="m", client=client)
        self.assertIn("speech", a.act(_view()))


class TestFullGame(unittest.TestCase):
    def test_twelve_openai_agents_play_a_whole_game(self):
        client = FakeOpenAI()
        st = new_game(GameConfig(seed=5))

        class Tracking(OpenAIAgent):
            def act(self, view, error=None):
                self._client.legal = view.legal_actions
                return super().act(view, error)

        agents = {s: Tracking(s, st.players[s].role, model="gw/qwen-max", client=client)
                  for s in st.seats}
        st = Engine(st, agents).run()
        self.assertIsNotNone(st.winner)
        bad = [e for e in st.event_log if e.type in ("agent_error", "fallback_action")]
        self.assertEqual(bad, [], f"假端点的动作应该全部合法，但出现了：{bad[:2]}")

    def test_base_url_is_passed_through(self):
        a = OpenAIAgent(1, Role.SEER, model="m", base_url="https://gw.example/v1",
                        client=FakeOpenAI())
        self.assertEqual(a.base_url, "https://gw.example/v1")

    def test_memory_notes_survive_and_reach_the_prompt(self):
        with tempfile.TemporaryDirectory() as d:
            client = FakeOpenAI()
            a = OpenAIAgent(1, Role.SEER, model="m", client=client, memory_dir=Path(d) / "s1")
            a.write_notes("我怀疑 7 号")
            a.act(_view(seat=1))
            sent = client.calls[0]["messages"][-1]["content"]
            self.assertIn("私人笔记本", sent)
            self.assertIn("我怀疑 7 号", sent)


class TestCredentialSafety(unittest.TestCase):
    """密钥绝不能进阵容 —— 阵容会原样写进会话库。"""

    def test_lineup_never_carries_a_key(self):
        lu = Lineup.from_payload(3, [
            {"seat": 1, "backend": "openai", "model": "m",
             "base_url": "https://gw/v1", "api_key_env": "MY_KEY",
             # 就算前端硬塞，也不该被接受
             "api_key": "sk-should-never-appear", "openai_api_key": "sk-nope"},
        ])
        blob = json.dumps(lu.as_list(), ensure_ascii=False)
        self.assertNotIn("sk-should-never-appear", blob)
        self.assertNotIn("sk-nope", blob)
        self.assertNotIn("api_key\"", blob.replace("api_key_env", ""))
        self.assertEqual(lu.specs[1].api_key_env, "MY_KEY")

    def test_a_real_key_pasted_into_api_key_env_is_rejected(self):
        with self.assertRaises(ValueError):
            SeatSpec(seat=1, backend="openai", model="m", api_key_env="sk-abc123")

    def test_base_url_must_be_http(self):
        with self.assertRaises(ValueError):
            SeatSpec(seat=1, backend="openai", model="m", base_url="my-gateway/v1")

    def test_openai_model_is_free_text_but_not_empty(self):
        SeatSpec(seat=1, backend="openai", model="anything/at-all:v3")
        with self.assertRaises(ValueError):
            SeatSpec(seat=1, backend="openai", model="  ")

    def test_claude_model_is_still_validated(self):
        with self.assertRaises(ValueError):
            SeatSpec(seat=1, backend="claude", model="gpt-5")

    def test_llm_alias_still_means_claude(self):
        self.assertEqual(SeatSpec(seat=1, backend="llm").backend, "claude")
        self.assertEqual(Lineup.from_payload(2, [{"seat": 1, "backend": "llm"}])
                         .specs[1].backend, "claude")

    def test_backend_catalog_declares_its_key_env(self):
        self.assertEqual(AVAILABLE_BACKENDS["openai"]["needs_key"], "OPENAI_API_KEY")
        self.assertEqual(AVAILABLE_BACKENDS["claude"]["needs_key"], "ANTHROPIC_API_KEY")
        self.assertTrue(AVAILABLE_BACKENDS["openai"]["custom_model"])


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestProviderLabelling(unittest.TestCase):
    """会话存档要如实记录是哪家的模型，不能所有 LLM 都标成 llm。"""

    def test_snapshot_reports_the_real_provider(self):
        from werewolf.agents.heuristic import HeuristicAgent
        from werewolf.agents.llm import LLMAgent
        from werewolf.runtime import LocalRuntime

        cases = [
            (HeuristicAgent(1, Role.SEER), "heuristic"),
            (OpenAIAgent(1, Role.SEER, model="gw/x", client=FakeOpenAI()), "openai"),
            (LLMAgent(1, Role.SEER, model="claude-opus-5", client=object()), "claude"),
        ]
        for agent, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(
                    LocalRuntime(1, agent).snapshot_session()["backend"], expected)

    def test_both_llm_backends_share_one_base(self):
        """共用逻辑放在 chat_base 里，避免两边行为漂移。"""
        from werewolf.agents.chat_base import ChatAgent
        from werewolf.agents.llm import LLMAgent

        for cls in (LLMAgent, OpenAIAgent):
            self.assertTrue(issubclass(cls, ChatAgent))
            # 只有"怎么调 API"是各自实现的
            self.assertIn("_complete", cls.__dict__)
            self.assertNotIn("act", cls.__dict__)
