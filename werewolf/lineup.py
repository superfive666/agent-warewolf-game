"""阵容配置：每个座位用哪个 agent 后端、哪个模型。

前端选择的东西最终都落到这里：人数 → 板子，每个座位 → 一份 SeatSpec。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

#: 环境变量名的合法形状
_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

from .roles import Role

#: Claude 后端的可选模型
CLAUDE_MODELS = {
    "claude-opus-5": {"label": "Claude Opus 5", "note": "最强，推理和伪装都最好，也最贵"},
    "claude-sonnet-5": {"label": "Claude Sonnet 5", "note": "均衡，适合大部分座位"},
    "claude-haiku-4-5": {"label": "Claude Haiku 4.5", "note": "最快最便宜，适合平民位"},
}

#: OpenAI 后端的建议模型。**这只是建议** —— 自建网关可以服务任意模型名，
#: 所以 openai 后端的 model 字段不做白名单校验。
OPENAI_MODELS = {
    "gpt-5": {"label": "GPT-5", "note": "默认"},
    "gpt-5-mini": {"label": "GPT-5 mini", "note": "便宜，适合平民位"},
    "o4-mini": {"label": "o4-mini", "note": "推理模型"},
}

#: 向后兼容：老的 "llm" 就是 Claude
AVAILABLE_MODELS = CLAUDE_MODELS

AVAILABLE_BACKENDS = {
    "heuristic": {"label": "规则 bot", "note": "零依赖、毫秒级、不花钱，用来凑桌或做对照组",
                  "models": {}, "needs_key": None},
    "human": {"label": "真人玩家", "note": "留给你自己坐。一桌最多 1 个；有真人时对局中不能开上帝视角",
              "models": {}, "needs_key": None},
    "claude": {"label": "Claude", "note": "需要 ANTHROPIC_API_KEY",
               "models": CLAUDE_MODELS, "needs_key": "ANTHROPIC_API_KEY",
               "custom_model": False},
    "openai": {"label": "OpenAI / 兼容网关",
               "note": "需要 OPENAI_API_KEY；自建网关另设 OPENAI_BASE_URL。模型名可以随便填",
               "models": OPENAI_MODELS, "needs_key": "OPENAI_API_KEY",
               "custom_model": True},
}

#: "llm" 是 "claude" 的旧名字，继续接受
BACKEND_ALIASES = {"llm": "claude"}

EFFORT_LEVELS = ["low", "medium", "high", "xhigh", "max"]

#: 一桌最多几个真人座位
MAX_HUMAN_SEATS = 1

#: 不调用模型的后端（不需要密钥，也不算 LLM 座位）
NON_LLM_BACKENDS = {"heuristic", "human"}


@dataclass
class SeatSpec:
    """一个座位的 agent 配置。

    挂自己的 provider 只需要三个参数：``base_url`` + ``model`` + ``api_key``。

    密钥有两种给法，任选：
      · ``api_key``     —— 直接给密钥本身
      · ``api_key_env`` —— 给一个环境变量名，运行时去那里取（默认按后端取）

    **``as_dict()`` 会把密钥脱敏。** 阵容要写进会话库、还要回传给前端展示，
    密钥不能跟着走。内存里该用的时候照常用（``resolve_api_key()``），
    但任何持久化和对外输出里只会看到 ``api_key_set: true/false``。
    """

    seat: int
    backend: str = "heuristic"
    model: str = "claude-opus-5"
    effort: str = "medium"
    #: 思考长度不限，但单次决策的 token 预算要给足
    max_tokens: int = 16000
    #: 自定义 provider 的地址。留空则读环境变量（OPENAI_BASE_URL）
    base_url: str = ""
    #: 密钥本身。只活在内存里，绝不进 as_dict()
    api_key: str = field(default="", repr=False)
    #: 或者：去哪个环境变量取密钥（存的是变量名，不是密钥）
    api_key_env: str = ""
    label: str = ""

    def __post_init__(self) -> None:
        self.backend = BACKEND_ALIASES.get(self.backend, self.backend)
        if self.backend not in AVAILABLE_BACKENDS:
            raise ValueError(f"未知后端 {self.backend}，可选 {sorted(AVAILABLE_BACKENDS)}")
        info = AVAILABLE_BACKENDS[self.backend]

        if self.backend == "claude" and self.model not in CLAUDE_MODELS:
            raise ValueError(f"未知 Claude 模型 {self.model}，可选 {sorted(CLAUDE_MODELS)}")
        if self.backend == "openai":
            # 自建网关可以服务任意模型名，所以不做白名单，只要求非空
            if not str(self.model).strip():
                raise ValueError("openai 后端必须指定模型名")
            if self.model in CLAUDE_MODELS:  # 一眼就是选错了后端
                raise ValueError(f"{self.model} 是 Claude 模型，请把后端改成 claude")
        if self.effort not in EFFORT_LEVELS:
            raise ValueError(f"未知 effort {self.effort}，可选 {EFFORT_LEVELS}")
        self.api_key = (self.api_key or "").strip()
        if self.api_key_env and not _ENV_NAME.match(self.api_key_env):
            # 最常见的手滑：把密钥本身粘到了变量名那一栏。直接帮他挪过去。
            if not self.api_key and len(self.api_key_env) > 20 and " " not in self.api_key_env:
                self.api_key, self.api_key_env = self.api_key_env, ""
            else:
                raise ValueError(
                    f"api_key_env 要填【环境变量名】（比如 MY_GATEWAY_KEY），"
                    f"密钥本身请填 api_key。收到 {self.api_key_env!r}"
                )
        if not self.api_key_env and info.get("needs_key"):
            self.api_key_env = info["needs_key"]
        if self.base_url and not self.base_url.startswith(("http://", "https://")):
            raise ValueError(f"base_url 必须以 http(s):// 开头，收到 {self.base_url!r}")

        if not self.label:
            self.label = (
                info["label"] if self.backend in NON_LLM_BACKENDS
                else info["models"].get(self.model, {}).get("label") or self.model
            )

    def resolve_api_key(self) -> str:
        """取真正要用的密钥：显式给的优先，否则读环境变量。"""
        import os

        return self.api_key or os.environ.get(self.api_key_env or "", "") or ""

    def has_api_key(self) -> bool:
        return bool(self.resolve_api_key())

    def as_dict(self) -> dict:
        """对外形态。**密钥在这里被脱敏** —— 这是入库和回传前端用的。"""
        return {
            "seat": self.seat, "backend": self.backend, "model": self.model,
            "effort": self.effort, "max_tokens": self.max_tokens,
            "base_url": self.base_url, "api_key_env": self.api_key_env,
            # 只说"有没有配"，不说是什么
            "api_key_set": bool(self.api_key),
            "label": self.label,
        }


@dataclass
class Lineup:
    specs: dict[int, SeatSpec] = field(default_factory=dict)

    @classmethod
    def uniform(cls, n_players: int, backend: str = "heuristic", **kw) -> "Lineup":
        return cls({s: SeatSpec(seat=s, backend=backend, **kw) for s in range(1, n_players + 1)})

    @classmethod
    def from_payload(cls, n_players: int, seats: list[dict] | None) -> "Lineup":
        """从前端传来的 JSON 构造。缺省的座位用规则 bot 补齐。"""
        by_seat = {int(d["seat"]): d for d in (seats or []) if d.get("seat")}
        specs = {}
        for s in range(1, n_players + 1):
            d = by_seat.get(s, {})
            backend = BACKEND_ALIASES.get(d.get("backend", "heuristic"),
                                          d.get("backend", "heuristic"))
            default_model = "gpt-5" if backend == "openai" else "claude-opus-5"
            # 密钥可以直接传（挂自建 provider 用），但它只活在内存里：
            # SeatSpec.as_dict() 会脱敏，所以入库和回传前端的都看不到它。
            specs[s] = SeatSpec(
                seat=s,
                backend=backend,
                model=(d.get("model") or default_model),
                effort=d.get("effort", "medium"),
                max_tokens=int(d.get("max_tokens", 16000)),
                base_url=(d.get("base_url") or "").strip(),
                api_key=(d.get("api_key") or "").strip(),
                api_key_env=(d.get("api_key_env") or "").strip(),
            )
        humans = [s for s, sp in specs.items() if sp.backend == "human"]
        if len(humans) > MAX_HUMAN_SEATS:
            raise ValueError(f"一桌最多 {MAX_HUMAN_SEATS} 个真人座位，现在选了 {humans}")
        return cls(specs)

    def missing_keys(self) -> list[int]:
        """哪些座位配了 LLM 但拿不到密钥 —— 开局前就该提示，而不是打到一半才报错。"""
        return [
            sp.seat for sp in self.specs.values()
            if sp.backend not in NON_LLM_BACKENDS and not sp.has_api_key()
        ]

    def uses_llm(self) -> bool:
        return any(sp.backend not in NON_LLM_BACKENDS for sp in self.specs.values())

    def human_seats(self) -> list[int]:
        return sorted(s for s, sp in self.specs.items() if sp.backend == "human")

    def as_list(self) -> list[dict]:
        return [self.specs[s].as_dict() for s in sorted(self.specs)]

    def build_agents(self, state, *, verbose: bool = False) -> dict:
        from .agents.heuristic import HeuristicAgent

        agents = {}
        for seat in state.seats:
            sp = self.specs[seat]
            role: Role = state.players[seat].role
            if sp.backend == "human":
                from .agents.human import HumanAgent

                agents[seat] = HumanAgent(seat, role)
            elif sp.backend == "claude":
                from .agents.llm import LLMAgent

                agents[seat] = LLMAgent(
                    seat, role, model=sp.model, effort=sp.effort,
                    max_tokens=sp.max_tokens, verbose=verbose,
                    api_key=sp.api_key or None,
                    api_key_env=sp.api_key_env or "ANTHROPIC_API_KEY",
                )
            elif sp.backend == "openai":
                from .agents.openai_agent import OpenAIAgent

                agents[seat] = OpenAIAgent(
                    seat, role, model=sp.model, max_tokens=sp.max_tokens,
                    base_url=sp.base_url or None, verbose=verbose,
                    api_key=sp.api_key or None,
                    api_key_env=sp.api_key_env or "OPENAI_API_KEY",
                    effort=sp.effort if sp.effort in ("low", "medium", "high") else None,
                )
            else:
                agents[seat] = HeuristicAgent(seat, role, seed=state.config.seed)
        return agents
