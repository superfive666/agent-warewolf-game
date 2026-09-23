"""★ 视角生成：12 份个人视角 + 1 份狼队视角。对应 docs/04-视角与上下文.md。

不变式（由 _PublicPlayer 在类型层面强制）：
    build_player_view(state, seat) 只能读
      1. state.players[seat]         —— 自己那一格
      2. 公开派生量（经 _PublicPlayer 投影，**没有 role 属性**）
      3. state.event_log.visible(seat, ...)  —— 我有权看到的事件
    任何试图读别人 .role 的代码都会 AttributeError 而不是静默泄密。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import actions as actions_mod
from .events import Audience
from .roles import ROLE_BRIEF_CN, WIN_CONDITION_CN, Faction, Role
from .state import GameState


class _PublicPlayer:
    """玩家的公开投影。刻意不暴露 ``role``——写错就报错，不会静默泄密。"""

    __slots__ = ("seat", "name", "alive", "is_sheriff", "can_vote", "revealed_role")

    def __init__(self, p) -> None:
        self.seat = p.seat
        self.name = p.name
        self.alive = p.alive
        self.is_sheriff = p.is_sheriff
        self.can_vote = p.can_vote
        # 只有被规则强制公开的身份才出现（目前只有白痴翻牌）
        self.revealed_role = p.revealed_role.value if p.revealed_role else None

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__slots__}


def public_players(state: GameState) -> dict[int, _PublicPlayer]:
    return {s: _PublicPlayer(state.players[s]) for s in state.seats}


# --------------------------------------------------------------------------
# 狼队视角（1 份，4 名狼人共享）
# --------------------------------------------------------------------------

@dataclass
class WolfTeamView:
    generated_at_seq: int
    roster: list[dict]
    alive_wolves: list[int]
    dead_wolves: list[int]
    chat_log: list[dict]
    kill_history: list[dict]
    intel: dict
    strategy_board: dict

    def as_dict(self) -> dict:
        return {
            "view_type": "wolf_team",
            "generated_at_seq": self.generated_at_seq,
            "roster": self.roster,
            "alive_wolves": self.alive_wolves,
            "dead_wolves": self.dead_wolves,
            "chat_log": self.chat_log,
            "kill_history": self.kill_history,
            "intel": self.intel,
            "strategy_board": self.strategy_board,
        }


def _wolf_intel(state: GameState) -> dict:
    """狼队情报。**每一条都只来自狼人真实可观测的事实**，注释标明来源。"""
    wolves = set(state.wolf_seats())
    pub = public_players(state)

    # 来源：公开发言（所有人都听得到）
    claimed = {
        seat: info["claim"]
        for seat, info in state.public_claims.items()
        if info.get("claim")
    }
    claimed_seers = sorted(s for s, c in claimed.items() if c == Role.SEER.value)
    god_claims = {Role.SEER.value, Role.WITCH.value, Role.HUNTER.value, Role.IDIOT.value}
    # 只算"悍跳了神职"的队友；跳平民不算悍跳
    our_claimed_gods = sorted(
        s for s, c in claimed.items() if s in wolves and c in god_claims
    )

    # 来源：公开发言里宣称的验人结果（同一条被重复公布只记一次）
    checks_on_us = []
    for c in state.public_check_claims:
        if c["target"] in wolves and c not in checks_on_us:
            checks_on_us.append(c)
    golden_waters: dict[int, list[int]] = {}
    for c in state.public_check_claims:
        if c["result"] == "GOOD":
            golden_waters.setdefault(c["target"], []).append(c["by"])

    # 来源：我们刀了谁 vs 天亮谁死了 —— 狼人自己就能对账
    antidote_used = None
    poison_used = None
    for rec in state.wolf_kill_history:
        if rec.get("outcome") == "saved_by_witch":
            antidote_used = True
        if rec.get("extra_deaths"):
            poison_used = True
    if antidote_used is None and state.wolf_kill_history:
        antidote_used = False
    if poison_used is None and state.wolf_kill_history:
        poison_used = False

    # 来源：公开的存活名单 + 我们知道自己人是谁
    alive = state.alive_seats()
    alive_wolves = [s for s in alive if s in wolves]
    alive_goods = [s for s in alive if s not in wolves]

    # 屠边优先级：只根据「公开起跳 / 已翻牌」推断谁像神，不含任何上帝信息
    def god_likelihood(seat: int) -> int:
        rr = pub[seat].revealed_role
        if rr in god_claims:
            return 3
        if claimed.get(seat) in god_claims:
            return 2
        if seat in golden_waters:
            return 1
        return 0

    suspected_gods = sorted(
        (s for s in alive_goods if god_likelihood(s) > 0),
        key=lambda s: (-god_likelihood(s), s),
    )

    return {
        "_source_note": "本区块所有字段都由狼人可观测的公开信息或己方行动结果推导，不含上帝信息。",
        "claimed_roles": {str(k): v for k, v in sorted(claimed.items())},
        "claimed_seers": claimed_seers,
        "our_claimed_gods": our_claimed_gods,
        "golden_waters": {str(k): v for k, v in sorted(golden_waters.items())},
        "checks_on_us": checks_on_us,
        "witch_antidote_used": antidote_used,
        "witch_poison_used": poison_used,
        "alive_wolf_count": len(alive_wolves),
        "alive_good_count": len(alive_goods),
        "suspected_god_seats": suspected_gods,
        "edge_hint": (
            f"好人还剩 {len(alive_goods)} 人，其中 {len(suspected_gods)} 人公开表现得像神。"
            "屠边只需杀光 4 神或 4 民其中一边。"
        ),
    }


def build_wolf_team_view(state: GameState) -> WolfTeamView:
    wolves = state.wolf_seats()
    roster = []
    for s in wolves:
        p = state.players[s]
        entry = {"seat": s, "name": p.name, "alive": p.alive}
        if not p.alive:
            entry.update(died_day=p.died_day, died_by=p.died_cause)
        roster.append(entry)
    return WolfTeamView(
        generated_at_seq=len(state.event_log),
        roster=roster,
        alive_wolves=state.alive_wolf_seats(),
        dead_wolves=[s for s in wolves if not state.players[s].alive],
        chat_log=list(state.wolf_chat_log),
        kill_history=list(state.wolf_kill_history),
        intel=_wolf_intel(state),
        strategy_board=dict(state.wolf_strategy_board),
    )


# --------------------------------------------------------------------------
# 个人视角（12 份）
# --------------------------------------------------------------------------

@dataclass
class PlayerView:
    identity: dict
    public_state: dict
    timeline: list[dict]
    wolf_team: WolfTeamView | None
    legal_actions: dict | None
    generated_at_seq: int
    #: 自上次决策以来的新事件，LLM 后端只发这一段（省 token、命中 cache）
    delta: list[dict] = field(default_factory=list)

    @property
    def seat(self) -> int:
        return self.identity["seat"]

    @property
    def role(self) -> Role:
        return Role(self.identity["role"])

    @property
    def is_wolf(self) -> bool:
        return self.role is Role.WEREWOLF

    def as_dict(self) -> dict:
        return {
            "view_type": "player",
            "generated_at_seq": self.generated_at_seq,
            "identity": self.identity,
            "public_state": self.public_state,
            "timeline": self.timeline,
            "delta": self.delta,
            "wolf_team": self.wolf_team.as_dict() if self.wolf_team else None,
            "legal_actions": self.legal_actions,
        }


def _role_knowledge(state: GameState, seat: int) -> dict:
    """角色专属私有知识 —— 12 份视角真正不同的地方。"""
    p = state.players[seat]
    role = p.role

    if role is Role.SEER:
        checked = {c["target"] for c in state.seer_checks}
        return {
            "checks": [dict(c) for c in state.seer_checks],
            "unchecked_alive": [s for s in state.alive_seats() if s != seat and s not in checked],
        }
    if role is Role.WITCH:
        return {
            "has_antidote": p.witch_has_antidote,
            "has_poison": p.witch_has_poison,
            "potion_log": [dict(x) for x in state.witch_potion_log],
        }
    if role is Role.HUNTER:
        return {"can_shoot": p.alive or p.died_cause != "poisoned"}
    if role is Role.IDIOT:
        return {"revealed": p.idiot_revealed, "can_vote": p.can_vote}
    if role is Role.WEREWOLF:
        mates = [s for s in state.wolf_seats() if s != seat]
        return {
            "teammates": mates,
            "alive_teammates": [s for s in mates if state.players[s].alive],
        }
    return {}  # 平民没有任何私有信息


def _public_state(state: GameState) -> dict:
    pub = public_players(state)
    return {
        "day": state.day,
        "phase": state.phase,
        "alive_seats": state.alive_seats(),
        "dead_seats": state.dead_seats(),
        "players": {str(s): pub[s].as_dict() for s in state.seats},
        "sheriff": state.sheriff_seat,
        "sheriff_status": state.sheriff_status,
        "speech_order": list(state.speech_order),
        "death_record": [dict(d) for d in state.death_record],
        "public_claims": {str(k): dict(v) for k, v in sorted(state.public_claims.items())},
        "public_check_claims": [dict(c) for c in state.public_check_claims],
        "revealed_roles": {
            str(s): pub[s].revealed_role for s in state.seats if pub[s].revealed_role
        },
        "vote_history": [dict(v) for v in state.vote_history],
        "rules_digest": {
            "setup": "12人局：4狼人 / 4神(预言家·女巫·猎人·白痴) / 4平民",
            "win_rule": state.config.win_rule,
            "sheriff": state.config.sheriff,
        },
    }


def build_player_view(
    state: GameState,
    seat: int,
    *,
    action_type: str | None = None,
    action_ctx: dict | None = None,
    since_seq: int = 0,
) -> PlayerView:
    """构造某个座位的个人视角。狼人会额外挂上共享的狼队视角。"""
    me = state.players[seat]
    is_wolf = me.is_wolf

    identity = {
        "seat": seat,
        "name": me.name,
        "role": me.role.value,
        "role_cn": me.role.cn,
        "role_brief": ROLE_BRIEF_CN[me.role],
        "faction": me.faction.value,
        "faction_cn": me.faction.cn,
        "is_god": me.is_god,
        "alive": me.alive,
        "is_sheriff": me.is_sheriff,
        "can_vote": me.can_vote,
        "win_condition": WIN_CONDITION_CN[me.faction],
        "role_knowledge": _role_knowledge(state, seat),
    }

    visible = state.event_log.visible(seat, is_wolf)
    timeline = [e.as_view_entry() for e in visible]
    delta = [e.as_view_entry() for e in visible if e.seq > since_seq]

    legal = None
    if action_type:
        legal = actions_mod.legal_actions(state, seat, action_type, action_ctx or {})

    return PlayerView(
        identity=identity,
        public_state=_public_state(state),
        timeline=timeline,
        delta=delta,
        wolf_team=build_wolf_team_view(state) if is_wolf else None,
        legal_actions=legal,
        generated_at_seq=len(state.event_log),
    )


def build_all_views(state: GameState) -> dict:
    """一次性导出全部 13 份上下文，用于 --dump-views 和信息隔离测试。"""
    return {
        "players": {
            str(s): build_player_view(state, s).as_dict() for s in state.seats
        },
        "wolf_team": build_wolf_team_view(state).as_dict(),
    }
