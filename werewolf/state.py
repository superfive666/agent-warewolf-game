"""游戏状态（上帝视角）。只有引擎能直接访问，agent 永远拿不到这个对象。"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from .events import EventLog
from .roles import Faction, Role, board_for


@dataclass
class GameConfig:
    """对应 docs/01-游戏规则.md §8 的配置项总览。"""

    n_players: int = 12
    win_rule: str = "edge"  # edge(屠边) | city(屠城)
    sheriff: bool = True
    #: 狼人是否可以自爆
    wolf_explode: bool = True
    witch_self_rescue_first_night: bool = True
    witch_knows_victim: str = "always"  # always | first_night_only
    witch_same_night_both_potions: bool = False
    first_night_last_words: bool = True
    wolves_can_self_knife: bool = True
    wolf_chat_rounds: int = 1
    max_days: int = 20
    seed: int | None = None
    #: 发言字数上限。人类正常语速约 220 字/分钟，2 分钟 ≈ 450 字。
    max_speech_chars: int = 450
    #: 单个决策点最多向 agent 索要几次动作（含首次）。思考长度不限，但迭代次数有上限。
    max_iterations: int = 3

    def as_dict(self) -> dict:
        return dict(self.__dict__)


@dataclass
class Player:
    seat: int
    name: str
    role: Role
    alive: bool = True
    # 死亡信息
    died_day: int | None = None
    died_when: str | None = None  # night | vote | shot
    died_cause: str | None = None  # killed | poisoned | exiled | shot
    # 规则状态
    is_sheriff: bool = False
    can_vote: bool = True
    revealed_role: Role | None = None  # 被规则强制公开的身份（白痴翻牌）
    # 角色专属
    witch_has_antidote: bool = True
    witch_has_poison: bool = True
    idiot_revealed: bool = False
    exploded: bool = False  # 狼人是否自爆出局

    @property
    def faction(self) -> Faction:
        return self.role.faction

    @property
    def is_wolf(self) -> bool:
        return self.role is Role.WEREWOLF

    @property
    def is_god(self) -> bool:
        return self.role.is_god


@dataclass
class GameState:
    config: GameConfig
    players: dict[int, Player]
    rng: random.Random
    event_log: EventLog = field(default_factory=EventLog)

    day: int = 0
    phase: str = "SETUP"

    sheriff_seat: int | None = None
    sheriff_status: str = "none"  # none | elected | destroyed | lost
    speech_order: list[int] = field(default_factory=list)

    # 夜间暂存
    night_kill_target: int | None = None
    night_poison_target: int | None = None
    night_saved: bool = False

    # 记录
    seer_checks: list[dict] = field(default_factory=list)
    wolf_kill_history: list[dict] = field(default_factory=list)
    wolf_chat_log: list[dict] = field(default_factory=list)
    wolf_strategy_board: dict = field(
        default_factory=lambda: {
            "tonight_target": None,
            "protect": [],
            "push_target": None,
            #: 狼队白天分工 {座位: 悍跳/冲锋/倒钩/深水}
            "assignments": {},
            "notes": "",
        }
    )
    death_record: list[dict] = field(default_factory=list)
    vote_history: list[dict] = field(default_factory=list)
    public_claims: dict[int, dict] = field(default_factory=dict)
    #: 公开宣称的验人结果 [{day, by, target, result}]，只记录"谁说了什么"，不校验真假
    public_check_claims: list[dict] = field(default_factory=list)
    #: 公开报出的警徽流 [{day, by, targets:[座位]}]。真预言家和悍跳狼都会报，引擎不判真假
    public_badge_flows: list[dict] = field(default_factory=list)
    #: 全部公开发言的原文档案。真人靠"你第一天说过X"盘逻辑，agent 也必须拿得到原文
    speech_log: list[dict] = field(default_factory=list)
    witch_potion_log: list[dict] = field(default_factory=list)
    #: 心路历程：每个决策点 agent 的内心想法，只进复盘，绝不进任何玩家视角
    thought_log: list[dict] = field(default_factory=list)
    #: 自爆记录
    explode_log: list[dict] = field(default_factory=list)

    winner: Faction | None = None
    end_reason: str = ""

    # ---------- 查询 ----------
    @property
    def seats(self) -> list[int]:
        return sorted(self.players)

    def alive_seats(self) -> list[int]:
        return [s for s in self.seats if self.players[s].alive]

    def dead_seats(self) -> list[int]:
        return [s for s in self.seats if not self.players[s].alive]

    def wolf_seats(self) -> list[int]:
        return [s for s in self.seats if self.players[s].is_wolf]

    def alive_wolf_seats(self) -> list[int]:
        return [s for s in self.alive_seats() if self.players[s].is_wolf]

    def alive_god_seats(self) -> list[int]:
        return [s for s in self.alive_seats() if self.players[s].is_god]

    def alive_villager_seats(self) -> list[int]:
        return [s for s in self.alive_seats() if self.players[s].role is Role.VILLAGER]

    def seat_of_role(self, role: Role) -> int | None:
        for s in self.seats:
            if self.players[s].role is role:
                return s
        return None

    def is_wolf(self, seat: int) -> bool:
        return self.players[seat].is_wolf

    # ---------- 胜负 ----------
    def check_winner(self) -> Faction | None:
        if not self.alive_wolf_seats():
            self.winner = Faction.VILLAGE
            self.end_reason = "4 名狼人全部出局"
            return self.winner
        if self.config.win_rule == "city":
            if not [s for s in self.alive_seats() if not self.players[s].is_wolf]:
                self.winner = Faction.WOLF
                self.end_reason = "所有好人出局（屠城）"
                return self.winner
            return None
        if not self.alive_god_seats():
            self.winner = Faction.WOLF
            self.end_reason = "4 名神职全部出局（屠神）"
            return self.winner
        if not self.alive_villager_seats():
            self.winner = Faction.WOLF
            self.end_reason = "4 名平民全部出局（屠民）"
            return self.winner
        return None

    def vote_weight(self, seat: int) -> float:
        p = self.players[seat]
        if not p.can_vote:
            return 0.0
        return 1.5 if p.is_sheriff else 1.0


def new_game(config: GameConfig, names: list[str] | None = None) -> GameState:
    """发牌：随机把板子分配到 1~N 号座位。"""
    rng = random.Random(config.seed)
    roles = board_for(config.n_players)
    rng.shuffle(roles)
    names = names or [f"{i}号" for i in range(1, len(roles) + 1)]
    players = {
        seat: Player(seat=seat, name=names[seat - 1], role=roles[seat - 1])
        for seat in range(1, len(roles) + 1)
    }
    return GameState(config=config, players=players, rng=rng)
