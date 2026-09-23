"""阵容配置：每个座位用哪个 agent 后端、哪个模型。

前端选择的东西最终都落到这里：人数 → 板子，每个座位 → 一份 SeatSpec。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .roles import Role

#: 前端可选的模型。键是模型 ID，值是展示名和简介。
AVAILABLE_MODELS = {
    "claude-opus-5": {"label": "Claude Opus 5", "note": "最强，推理和伪装都最好，也最贵"},
    "claude-sonnet-5": {"label": "Claude Sonnet 5", "note": "均衡，适合大部分座位"},
    "claude-haiku-4-5": {"label": "Claude Haiku 4.5", "note": "最快最便宜，适合平民位"},
}

AVAILABLE_BACKENDS = {
    "heuristic": {"label": "规则 bot", "note": "零依赖、毫秒级、不花钱，用来凑桌或做对照组"},
    "llm": {"label": "Claude", "note": "真正的 LLM agent，需要 ANTHROPIC_API_KEY"},
}

EFFORT_LEVELS = ["low", "medium", "high", "xhigh", "max"]


@dataclass
class SeatSpec:
    """一个座位的 agent 配置。"""

    seat: int
    backend: str = "heuristic"
    model: str = "claude-opus-5"
    effort: str = "medium"
    #: 思考长度不限，但单次决策的 token 预算要给足
    max_tokens: int = 16000
    label: str = ""

    def __post_init__(self) -> None:
        if self.backend not in AVAILABLE_BACKENDS:
            raise ValueError(f"未知后端 {self.backend}，可选 {sorted(AVAILABLE_BACKENDS)}")
        if self.backend == "llm" and self.model not in AVAILABLE_MODELS:
            raise ValueError(f"未知模型 {self.model}，可选 {sorted(AVAILABLE_MODELS)}")
        if self.effort not in EFFORT_LEVELS:
            raise ValueError(f"未知 effort {self.effort}，可选 {EFFORT_LEVELS}")
        if not self.label:
            self.label = (
                AVAILABLE_BACKENDS["heuristic"]["label"]
                if self.backend == "heuristic"
                else AVAILABLE_MODELS[self.model]["label"]
            )

    def as_dict(self) -> dict:
        return {
            "seat": self.seat, "backend": self.backend, "model": self.model,
            "effort": self.effort, "max_tokens": self.max_tokens, "label": self.label,
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
            specs[s] = SeatSpec(
                seat=s,
                backend=d.get("backend", "heuristic"),
                model=d.get("model", "claude-opus-5"),
                effort=d.get("effort", "medium"),
                max_tokens=int(d.get("max_tokens", 16000)),
            )
        return cls(specs)

    def uses_llm(self) -> bool:
        return any(sp.backend == "llm" for sp in self.specs.values())

    def as_list(self) -> list[dict]:
        return [self.specs[s].as_dict() for s in sorted(self.specs)]

    def build_agents(self, state, *, verbose: bool = False) -> dict:
        from .agents.heuristic import HeuristicAgent

        agents = {}
        for seat in state.seats:
            sp = self.specs[seat]
            role: Role = state.players[seat].role
            if sp.backend == "llm":
                from .agents.llm import LLMAgent

                agents[seat] = LLMAgent(
                    seat, role, model=sp.model, effort=sp.effort,
                    max_tokens=sp.max_tokens, verbose=verbose,
                )
            else:
                agents[seat] = HeuristicAgent(seat, role, seed=state.config.seed)
        return agents
