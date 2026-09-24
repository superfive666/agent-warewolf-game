"""Claude（Anthropic）后端。

每个座位持有**自己独立的对话历史**，座位之间没有任何共享对象 ——
狼人之间的"串供"只能通过引擎写进狼队视角的那条通道进行，
这在架构上杜绝了"LLM 无意中共享上下文"的泄密。

需要 `pip install -r requirements-llm.txt`，并设置 ANTHROPIC_API_KEY（或 `ant auth login`）。
"""
from __future__ import annotations

import os

from ..prompts import output_schema
from ..roles import Role
from .chat_base import ChatAgent

DEFAULT_MODEL = "claude-opus-5"


class LLMAgent(ChatAgent):
    """一个座位 = 一个独立的 Claude 会话。"""

    provider = "claude"

    def __init__(self, seat: int, role: Role | None, *,
                 model: str = DEFAULT_MODEL,
                 effort: str = "medium",
                 max_tokens: int = 16000,
                 api_key_env: str = "ANTHROPIC_API_KEY",
                 client=None, verbose: bool = False, memory_dir=None) -> None:
        super().__init__(seat, role, model=model, max_tokens=max_tokens,
                         verbose=verbose, memory_dir=memory_dir)
        self.effort = effort
        self.api_key_env = api_key_env
        self._client = client

    @property
    def client(self):
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError(
                    "Claude 后端需要 SDK：pip install -r requirements-llm.txt"
                ) from exc
            key = os.environ.get(self.api_key_env)
            # 没显式给 key 时交给 SDK 自己解析（环境变量 / ant auth login 的 profile）
            self._client = anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()
        return self._client

    # ------------------------------------------------------------------
    def _complete(self, action_type: str) -> str:
        """思考长度不设限，所以 max_tokens 给得大；超过 16K 时走流式避免 HTTP 超时。"""
        kw = dict(
            model=self.model,
            max_tokens=self.max_tokens,
            system=[{"type": "text", "text": self._system,
                     "cache_control": {"type": "ephemeral"}}],
            messages=self._messages,
            thinking={"type": "adaptive"},
            output_config={"effort": self.effort,
                           "format": output_schema(action_type, memory=bool(self.memory_dir))},
        )
        if self.max_tokens > 16000:
            with self.client.messages.stream(**kw) as stream:
                resp = stream.get_final_message()
        else:
            resp = self.client.messages.create(**kw)
        self._track(resp)
        return next((b.text for b in resp.content if b.type == "text"), "")

    def _track(self, resp) -> None:
        u = getattr(resp, "usage", None)
        if not u:
            return
        self._add_usage(
            input_tokens=getattr(u, "input_tokens", 0) or 0,
            output_tokens=getattr(u, "output_tokens", 0) or 0,
            cache_read_input_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
        )


def make_agent_factory(llm_seats: set[int] | None = None, *, model: str = DEFAULT_MODEL,
                       effort: str = "medium", verbose: bool = False,
                       heuristic_seed: int | None = None):
    """生成 agent 工厂：llm_seats 里的座位用 Claude，其余用规则 bot。

    llm_seats=None 表示全部座位都用 Claude。更细粒度的按座位配模型见 werewolf.lineup。
    """
    from .heuristic import HeuristicAgent

    def factory(seat: int, role: Role):
        if llm_seats is None or seat in llm_seats:
            return LLMAgent(seat, role, model=model, effort=effort, verbose=verbose)
        return HeuristicAgent(seat, role, seed=heuristic_seed)

    return factory
