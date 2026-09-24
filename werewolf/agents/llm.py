"""Claude API 后端：真正让 LLM 来扮演一个座位。

每个座位持有**自己独立的对话历史**，座位之间没有任何共享对象 ——
狼人之间的"串供"只能通过引擎写进狼队视角的那条通道进行，
这在架构上杜绝了"LLM 无意中共享上下文"的泄密。

需要 `pip install anthropic`，并设置 ANTHROPIC_API_KEY（或 `ant auth login`）。
"""
from __future__ import annotations

import json

from ..prompts import output_schema, system_prompt, turn_prompt
from ..roles import Role
from ..views import PlayerView

DEFAULT_MODEL = "claude-opus-5"


class LLMAgent:
    """一个座位 = 一个独立的 Claude 会话。"""

    def __init__(
        self,
        seat: int,
        role: Role,
        *,
        model: str = DEFAULT_MODEL,
        effort: str = "medium",
        max_tokens: int = 16000,
        client=None,
        verbose: bool = False,
    ) -> None:
        self.seat = seat
        self.role = role
        self.name = f"llm-{seat}-{model}"
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens
        self.verbose = verbose
        self._client = client
        self._system: str | None = None
        self._messages: list[dict] = []
        #: 每次决策的内心想法，只进复盘，不进任何玩家视角
        self.thoughts: list[dict] = []
        self.usage = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0}

    # ------------------------------------------------------------------
    @property
    def client(self):
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError(
                    "LLM 后端需要 anthropic SDK：pip install anthropic"
                ) from exc
            self._client = anthropic.Anthropic()
        return self._client

    # ------------------------------------------------------------------
    def act(self, view: PlayerView, error: str | None = None) -> dict:
        first = self._system is None
        if first:
            # system 整局逐字不变 → 命中 prompt cache
            self._system = system_prompt(view)

        user = turn_prompt(view, full=first, error=error)
        self._messages.append({"role": "user", "content": user})

        action_type = view.legal_actions["action_type"]
        response = self._call(action_type)
        self._track_usage(response)

        text = next((b.text for b in response.content if b.type == "text"), "")
        self._messages.append({"role": "assistant", "content": text})
        # 只回灌结构化动作，思考块不回灌（省 token，也避免自我强化）
        self._trim_history()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"模型返回的不是合法 JSON：{text[:200]!r}") from exc

        # private_thought 由引擎统一摘走并记进上帝日志，这里只做本地留档和打印
        thought = data.get("private_thought", "")
        self.thoughts.append(
            {"seq": view.generated_at_seq, "day": view.public_state["day"],
             "action_type": action_type, "thought": thought}
        )
        if self.verbose and thought:
            print(f"  [{self.seat}号 {self.role.cn} · {action_type}] 💭 {thought}")
        return data

    def _call(self, action_type: str):
        """思考长度不设上限，所以 max_tokens 给得大；超过 16K 时走流式避免 HTTP 超时。"""
        kw = dict(
            model=self.model,
            max_tokens=self.max_tokens,
            system=[{"type": "text", "text": self._system,
                     "cache_control": {"type": "ephemeral"}}],
            messages=self._messages,
            thinking={"type": "adaptive"},
            output_config={"effort": self.effort, "format": output_schema(action_type)},
        )
        if self.max_tokens > 16000:
            with self.client.messages.stream(**kw) as stream:
                return stream.get_final_message()
        return self.client.messages.create(**kw)

    # ------------------------------------------------------------------
    def _track_usage(self, response) -> None:
        u = getattr(response, "usage", None)
        if not u:
            return
        for k in self.usage:
            self.usage[k] += getattr(u, k, 0) or 0

    def _trim_history(self, keep_turns: int = 24) -> None:
        """只保留最近 N 轮对话。

        这样做是安全的，因为**每回合的 user 消息里都会重发一份完整的发言档案**
        （见 prompts._fmt_speech_archive）和全部票型——也就是说，盘逻辑需要的原始材料
        不依赖对话历史，裁掉的只是 agent 自己早期的措辞。

        （早期版本这里的注释声称"摘要里已经重新给过了"，但当时的摘要只有身份宣称和
        最近两轮票型，没有任何发言原文，导致 agent 在第 24 轮之后永久丢失第一天的发言。
        这是让对局读起来不像真人的主要原因之一。）
        """
        if len(self._messages) > keep_turns * 2:
            self._messages = self._messages[-keep_turns * 2:]
            # 历史必须以 user 开头
            while self._messages and self._messages[0]["role"] != "user":
                self._messages.pop(0)


def make_agent_factory(
    llm_seats: set[int] | None = None,
    *,
    model: str = DEFAULT_MODEL,
    effort: str = "medium",
    verbose: bool = False,
    heuristic_seed: int | None = None,
):
    """生成 agent 工厂：llm_seats 里的座位用 LLM，其余用规则 bot。

    llm_seats=None 表示全部座位都用 LLM。更细粒度的按座位配模型见 werewolf.lineup。
    """
    from .heuristic import HeuristicAgent

    def factory(seat: int, role: Role):
        if llm_seats is None or seat in llm_seats:
            return LLMAgent(seat, role, model=model, effort=effort, verbose=verbose)
        return HeuristicAgent(seat, role, seed=heuristic_seed)

    return factory
