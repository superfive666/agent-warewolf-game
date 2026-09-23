"""角色、阵营与板子配置。对应 docs/01-游戏规则.md §1、§3。"""
from __future__ import annotations

from enum import Enum


class Faction(str, Enum):
    VILLAGE = "VILLAGE"
    WOLF = "WOLF"

    @property
    def cn(self) -> str:
        return "好人阵营" if self is Faction.VILLAGE else "狼人阵营"


class Role(str, Enum):
    WEREWOLF = "WEREWOLF"
    SEER = "SEER"
    WITCH = "WITCH"
    HUNTER = "HUNTER"
    IDIOT = "IDIOT"
    VILLAGER = "VILLAGER"

    @property
    def cn(self) -> str:
        return ROLE_CN[self]

    @property
    def faction(self) -> Faction:
        return Faction.WOLF if self is Role.WEREWOLF else Faction.VILLAGE

    @property
    def is_god(self) -> bool:
        return self in GOD_ROLES


ROLE_CN = {
    Role.WEREWOLF: "狼人",
    Role.SEER: "预言家",
    Role.WITCH: "女巫",
    Role.HUNTER: "猎人",
    Role.IDIOT: "白痴",
    Role.VILLAGER: "平民",
}

GOD_ROLES = frozenset({Role.SEER, Role.WITCH, Role.HUNTER, Role.IDIOT})

#: 标准 12 人屠边局：4 狼 + 4 神 + 4 民
SETUP_STANDARD_12 = (
    [Role.WEREWOLF] * 4
    + [Role.SEER, Role.WITCH, Role.HUNTER, Role.IDIOT]
    + [Role.VILLAGER] * 4
)

#: 每个角色的胜利条件描述，直接进 agent 的身份卡
WIN_CONDITION_CN = {
    Faction.VILLAGE: "把 4 名狼人全部票出局（放逐或猎人开枪均可）。",
    Faction.WOLF: "杀光 4 名神职（屠神）或杀光 4 名平民（屠民），任一达成即获胜。",
}

ROLE_BRIEF_CN = {
    Role.WEREWOLF: (
        "你每晚和狼队友一起商量刀一个人（也可以空刀）。白天你要伪装成好人，"
        "误导投票、保护队友、把好人推出去。你不知道好人的具体身份。"
    ),
    Role.SEER: "你每晚可以查验一名存活玩家，得知他是【狼人】还是【好人】。",
    Role.WITCH: (
        "你有一瓶解药和一瓶毒药，整局各只能用一次，同一晚只能用一瓶。"
        "上帝每晚会告诉你今晚谁被狼人刀了。"
    ),
    Role.HUNTER: "你被狼刀或被投票出局时可以开枪带走一名玩家；被女巫毒死时不能开枪。",
    Role.IDIOT: (
        "你被投票出局时会翻牌，不死，但此后永久失去投票权，且当天不再有人出局。"
        "被刀、被毒、被枪杀时正常死亡。"
    ),
    Role.VILLAGER: "你没有任何技能，只能靠发言和投票找出狼人。",
}
