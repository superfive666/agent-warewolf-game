"""复盘渲染：把上帝视角的事件流变成一份详细战报，含每个 agent 的心路历程。"""
from __future__ import annotations

from collections import Counter, defaultdict

from . import i18n
from .events import Audience
from .roles import Faction, Role, board_summary
from .state import GameState

_AUD_MARK = {
    Audience.PUBLIC: "　　",
    Audience.WOLVES: "🐺",
    Audience.PRIVATE: "🔒",
    Audience.GOD: "👁",
}

_WHEN_CN, _CAUSE_CN = i18n.WHEN_CN, i18n.CAUSE_CN


def _fate(p) -> str:
    if p.alive:
        return "存活到最后"
    return f"第{p.died_day}天{_WHEN_CN.get(p.died_when, p.died_when)}（{_CAUSE_CN.get(p.died_cause, p.died_cause)}）"


def render_replay(state: GameState, *, include_god: bool = True, lineup=None) -> str:
    """完整战报：身份表 → 结果 → 关键节点 → 全过程 → 每人心路历程 → 统计。"""
    b = board_summary(state.config.n_players)
    L = ["# 对局复盘", "", f"**{b['name']}** · "
         f"胜负规则：{'屠边' if state.config.win_rule == 'edge' else '屠城'}"
         f" · 随机种子：`{state.config.seed}`", ""]

    # ---------- 结果 ----------
    L += ["## 结果", "",
          f"### {'🟢 好人阵营胜利' if state.winner is Faction.VILLAGE else '🔴 狼人阵营胜利' if state.winner is Faction.WOLF else '⚪ 平局'}",
          "", f"{state.end_reason}　·　共进行 {state.day} 天", ""]

    # ---------- 身份表 ----------
    L += ["## 身份表", "", "| 座位 | 身份 | 阵营 | agent | 结局 |", "|---|---|---|---|---|"]
    for s in state.seats:
        p = state.players[s]
        agent_label = ""
        if lineup and s in getattr(lineup, "specs", {}):
            sp = lineup.specs[s]
            agent_label = sp.label + (f" ({sp.effort})" if sp.backend == "llm" else "")
        badge = " 👑" if state.sheriff_seat == s else ""
        L.append(f"| {s}号{badge} | {p.role.cn} | {p.faction.cn} | {agent_label} | {_fate(p)} |")
    L.append("")

    # ---------- 关键节点 ----------
    L += ["## 关键节点", ""]
    exploded_seats = {e["seat"] for e in state.explode_log}
    for d in state.death_record:
        pl = state.players[d["seat"]]
        if d["seat"] in exploded_seats:
            e = next(x for x in state.explode_log if x["seat"] == d["seat"])
            L.append(f"- **第{d['day']}天** 💥 {d['seat']}号（狼人）在「"
                     f"{e.get('phase_cn') or i18n.phase_cn(e['phase'])}」阶段自爆，"
                     "当天发言和投票全部中止")
        else:
            L.append(f"- **第{d['day']}天** {d['seat']}号（{pl.role.cn}）"
                     f"{_CAUSE_CN.get(d['cause'], d['cause'])}出局")
    if state.sheriff_status == "elected" and state.sheriff_seat:
        L.append(f"- 警长：{state.sheriff_seat}号（{state.players[state.sheriff_seat].role.cn}）")
    elif state.sheriff_status in ("lost", "destroyed"):
        L.append(f"- {i18n.SHERIFF_STATUS_CN[state.sheriff_status]}，本局无警长")
    L.append("")

    # ---------- 神职操作 ----------
    L += ["## 神职与狼队的每一手", ""]
    if state.seer_checks:
        L.append("**预言家验人**")
        for c in state.seer_checks:
            L.append(f"- 第{c['day']}夜 验 {c['target']}号 → "
                     f"{'🔴' if c['result'] == 'WOLF' else '🟢'} {i18n.check_cn(c['result'])}"
                     f"（实际是{state.players[c['target']].role.cn}）")
        L.append("")
    if state.witch_potion_log:
        L.append("**女巫用药**")
        for x in state.witch_potion_log:
            L.append(f"- 第{x['day']}夜 {'解药救' if x['potion'] == 'antidote' else '毒杀'} "
                     f"{x['target']}号（{state.players[x['target']].role.cn}）")
        L.append("")
    assign = state.wolf_strategy_board.get("assignments") or {}
    if assign:
        L.append("**狼队白天分工**")
        L.append("- " + "　".join(
            f"{k}号={i18n.position_cn(v)}" for k, v in sorted(assign.items())))
        L.append("")
    if state.wolf_kill_history:
        L.append("**狼队刀人**")
        outcome = {"died": "得手", "saved_by_witch": "被女巫解药救了",
                   "empty_knife": "空刀", "pending": "—"}
        for k in state.wolf_kill_history:
            tgt = f"{k['decided']}号（{state.players[k['decided']].role.cn}）" if k["decided"] else "空刀"
            votes = "、".join(f"{v}号投{t}号" if t else f"{v}号空刀"
                              for v, t in k["votes"].items())
            L.append(f"- 第{k['day']}夜 刀 {tgt} → {outcome.get(k['outcome'], k['outcome'])}"
                     f"　（狼队内部：{votes}）")
        L.append("")

    # ---------- 投票 ----------
    if state.vote_history:
        L += ["## 投票记录", ""]
        for v in state.vote_history:
            kind = "警长竞选" if v["type"] == "sheriff" else "放逐投票"
            desc = "、".join(
                f"{k}号→{t}号" if t else f"{k}号弃票" for k, t in v["votes"].items()
            ) or "无人投票"
            if v["result"] is None:
                res = "平票"
            elif v["type"] == "sheriff":
                res = f"{v['result']}号当选警长"
            else:
                res = f"{v['result']}号被放逐"
            L.append(f"- **第{v['day']}天 {kind}（第{v['round']}轮）**：{desc}")
            L.append(f"  - 计票 {({k: round(x, 1) for k, x in v['tally'].items()})} → {res}")
        L.append("")

    # ---------- 全过程 ----------
    L += ["## 全过程", "",
          "> 图例：（空白）=全场公开　🐺=仅狼人可见　🔒=仅当事人可见　👁=上帝日志（含心路历程）", ""]
    current_day = None
    for e in state.event_log:
        if e.audience is Audience.GOD and not include_god:
            continue
        if e.type == "thought":
            continue  # 心路历程单独成章，这里不重复
        if e.day != current_day:
            current_day = e.day
            L += ["", f"### 第 {current_day} 天" if current_day else "### 开局", ""]
        L.append(f"`{_AUD_MARK[e.audience]}` **[{i18n.phase_cn(e.phase)}]** {e.text}")
    L.append("")

    # ---------- 心路历程 ----------
    L += ["## 心路历程", "",
          "每个 agent 在每个决策点的内心想法。**这些内容从未进入过任何其他玩家的视角。**", ""]
    by_seat: dict[int, list[dict]] = defaultdict(list)
    for t in state.thought_log:
        if t["thought"]:
            by_seat[t["seat"]].append(t)
    for seat in state.seats:
        p = state.players[seat]
        entries = by_seat.get(seat, [])
        L += ["", f"### {seat}号 · {p.role.cn}（{p.faction.cn}）· {_fate(p)}", ""]
        if not entries:
            L.append("_（该 agent 没有产出内心想法）_")
            continue
        for t in entries:
            tag = "" if t["accepted"] else f"（第{t['attempt']}次尝试，被判非法：{t['error']}）"
            phase = t.get("phase_cn") or i18n.phase_cn(t["phase"])
            act = t.get("action_cn") or i18n.action_cn(t["action_type"])
            L.append(f"- **第{t['day']}天 · {phase} · {act}**{tag}")
            L.append(f"  > {t['thought']}")
            desc = t.get("action_desc") or i18n.describe_action(t["action_type"], t.get("action"))
            if t["accepted"] and desc:
                L.append(f"  - → 实际动作：{desc}")
    L.append("")

    # ---------- 统计 ----------
    L += ["", "## 统计", ""]
    votes_cast = Counter()
    for v in state.vote_history:
        for voter, target in v["votes"].items():
            if target is not None:
                votes_cast[int(voter)] += 1
    retries = [t for t in state.thought_log if not t["accepted"]]
    L += [
        f"- 事件总数：{len(state.event_log)}",
        f"- 决策次数：{len({(t['turn']) for t in state.thought_log})}",
        f"- 心路历程条数：{sum(len(v) for v in by_seat.values())}",
        f"- 非法动作重试：{len(retries)} 次",
        f"- 自爆：{len(state.explode_log)} 次",
    ]
    return "\n".join(L) + "\n"


def render_console(state: GameState, *, show_wolves: bool = False) -> str:
    out = []
    for e in state.event_log:
        if e.audience is Audience.PUBLIC:
            out.append(e.text)
        elif show_wolves and e.audience is Audience.WOLVES:
            out.append(f"🐺 {e.text}")
    return "\n".join(out)


def result_summary(state: GameState, lineup=None) -> dict:
    return {
        "winner": state.winner.value if state.winner else None,
        "winner_cn": state.winner.cn if state.winner else "平局",
        "reason": state.end_reason,
        "days": state.day,
        "board": board_summary(state.config.n_players),
        "config": state.config.as_dict(),
        "lineup": lineup.as_list() if lineup else None,
        "roles": {str(s): state.players[s].role.value for s in state.seats},
        "roles_cn": {str(s): state.players[s].role.cn for s in state.seats},
        "alive": state.alive_seats(),
        "death_record": state.death_record,
        "sheriff": state.sheriff_seat,
        "sheriff_status": state.sheriff_status,
        "vote_history": state.vote_history,
        "seer_checks": state.seer_checks,
        "wolf_kill_history": state.wolf_kill_history,
        "witch_potion_log": state.witch_potion_log,
        "explode_log": state.explode_log,
        "n_thoughts": len([t for t in state.thought_log if t["thought"]]),
    }
