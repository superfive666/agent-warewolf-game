"""复盘渲染：把上帝视角的事件流变成人类可读的战报。"""
from __future__ import annotations

from .events import Audience
from .roles import Faction, Role
from .state import GameState

_AUD_MARK = {
    Audience.PUBLIC: "  ",
    Audience.WOLVES: "🐺",
    Audience.PRIVATE: "🔒",
    Audience.GOD: "👁",
}


def render_replay(state: GameState, *, include_god: bool = True) -> str:
    lines = ["# 对局复盘", ""]
    lines += ["## 身份表", "", "| 座位 | 身份 | 阵营 | 结局 |", "|---|---|---|---|"]
    for s in state.seats:
        p = state.players[s]
        if p.alive:
            fate = "存活"
        else:
            when = {"night": f"第{p.died_day}夜", "vote": f"第{p.died_day}天被票",
                    "shot": f"第{p.died_day}天被枪杀"}.get(p.died_when, str(p.died_when))
            cause = {"killed": "被狼刀", "poisoned": "被毒", "exiled": "被放逐", "shot": "被枪杀"}
            fate = f"{when}（{cause.get(p.died_cause, p.died_cause)}）"
        lines.append(f"| {s} | {p.role.cn} | {p.faction.cn} | {fate} |")

    lines += ["", "## 结果", "",
              f"**{state.winner.cn if state.winner else '平局'}** —— {state.end_reason}",
              f"（共进行 {state.day} 天）", "", "## 全过程", ""]
    lines.append("> 图例：（空白）=全场公开　🐺=仅狼人可见　🔒=仅当事人可见　👁=上帝日志")
    lines.append("")

    current_day = None
    for e in state.event_log:
        if e.audience is Audience.GOD and not include_god:
            continue
        if e.day != current_day:
            current_day = e.day
            lines += ["", f"### 第 {current_day} 天" if current_day else "### 开局", ""]
        lines.append(f"`{_AUD_MARK[e.audience]}` **[{e.phase}]** {e.text}")
    return "\n".join(lines) + "\n"


def render_console(state: GameState, *, show_wolves: bool = False) -> str:
    """跑game时的实时输出用的精简版。"""
    out = []
    for e in state.event_log:
        if e.audience is Audience.PUBLIC:
            out.append(e.text)
        elif show_wolves and e.audience is Audience.WOLVES:
            out.append(f"🐺 {e.text}")
    return "\n".join(out)


def result_summary(state: GameState) -> dict:
    return {
        "winner": state.winner.value if state.winner else None,
        "winner_cn": state.winner.cn if state.winner else "平局",
        "reason": state.end_reason,
        "days": state.day,
        "roles": {str(s): state.players[s].role.value for s in state.seats},
        "alive": state.alive_seats(),
        "death_record": state.death_record,
        "sheriff": state.sheriff_seat,
        "sheriff_status": state.sheriff_status,
        "vote_history": state.vote_history,
        "seer_checks": state.seer_checks,
        "wolf_kill_history": state.wolf_kill_history,
        "witch_potion_log": state.witch_potion_log,
    }
