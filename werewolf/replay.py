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


#: 算作"一次公开发言"的事件类型
SPEECH_EVENT_TYPES = ("speech", "sheriff_speech", "sheriff_pk_speech", "pk_speech", "last_words")


def fate_cn(*, alive: bool, died_day=None, died_when=None, died_cause=None,
            is_sheriff: bool = False, idiot_revealed: bool = False) -> str:
    """一句话结局：'存活 · 警长'、'第1夜 被狼刀'、'第2天 被放逐'、'第3天 自爆'。"""
    if alive:
        tags = ["存活"]
        if is_sheriff:
            tags.append("警长")
        if idiot_revealed:
            tags.append("已翻牌")
        return " · ".join(tags)
    when = "夜" if died_when == "night" else "天"
    day = f"第{died_day}{when}" if died_day is not None else ""
    return f"{day} {i18n.cause_cn(died_cause) or '出局'}".strip()


def _agent_label(lineup, seat: int):
    if lineup and seat in getattr(lineup, "specs", {}):
        return lineup.specs[seat].label
    return None


def players_summary(state: GameState, lineup=None) -> list[dict]:
    """按座位排好的身份 + 结局表，给结算页/历史对局用。"""
    out = []
    for s in state.seats:
        p = state.players[s]
        is_sheriff = state.sheriff_seat == s and p.alive
        out.append({
            "seat": s,
            "role": p.role.value,
            "role_cn": p.role.cn,
            "side": "wolf" if p.faction is Faction.WOLF else "good",
            "agent": _agent_label(lineup, s),
            "alive": p.alive,
            "is_sheriff": is_sheriff,
            "died_day": p.died_day,
            "died_when": p.died_when,
            "died_cause": p.died_cause,
            "died_cause_cn": i18n.cause_cn(p.died_cause),
            "fate_cn": fate_cn(alive=p.alive, died_day=p.died_day, died_when=p.died_when,
                               died_cause=p.died_cause, is_sheriff=is_sheriff,
                               idiot_revealed=p.idiot_revealed),
        })
    return out


def count_speeches(events) -> int:
    """公开发言条数。接受 Event 对象或 as_dict() 形态的字典。"""
    n = 0
    for e in events:
        typ = e["type"] if isinstance(e, dict) else e.type
        aud = e["audience"] if isinstance(e, dict) else e.audience.value
        if typ in SPEECH_EVENT_TYPES and aud == Audience.PUBLIC.value:
            n += 1
    return n


def result_summary(state: GameState, lineup=None) -> dict:
    return {
        "players": players_summary(state, lineup),
        "stats": {
            "days": state.day,
            "n_speeches": count_speeches(state.event_log),
            "n_alive": len(state.alive_seats()),
            "n_players": len(state.seats),
        },
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


# ---------------------------------------------------------------------------
# 结构化时间线：给前端的"关键节点"时间轴。只依赖事件字典，所以历史对局也能用。
# ---------------------------------------------------------------------------

def _strip_god(text: str) -> str:
    text = (text or "").strip()
    for prefix in ("上帝：", "上帝:"):
        if text.startswith(prefix):
            text = text[len(prefix):]
    return text.strip()


def _first(seq):
    return seq[0] if seq else None


def _fmt_votes(v) -> str:
    v = float(v)
    return str(int(v)) if v.is_integer() else f"{v:.1f}"


def _timeline_item(e: dict) -> str | None:
    typ, payload = e.get("type"), e.get("payload") or {}
    targets = e.get("targets") or []
    actor = e.get("actor")
    if typ == "wolf_kill":
        t = payload.get("target", _first(targets))
        return f"狼人决定刀 {t}号" if t else "狼人决定空刀"
    if typ == "witch_heal":
        t = _first(targets)
        return f"女巫用解药救了 {t}号" if t else "女巫使用了解药"
    if typ == "witch_poison":
        return f"女巫毒了 {_first(targets)}号"
    if typ == "seer_result":
        t = payload.get("target", _first(targets))
        return f"预言家查验 {t}号：{'狼人' if payload.get('result') == 'WOLF' else '好人'}"
    if typ == "sheriff_result":
        if targets:
            return f"{targets[0]}号当选警长"
        return _strip_god(e.get("text"))
    if typ == "vote":
        tally = payload.get("tally") or {}
        rnd = payload.get("round", 1)
        if not tally:
            return f"放逐投票（第{rnd}轮）：全部弃票"
        ranked = sorted(tally.items(), key=lambda kv: -float(kv[1]))
        desc = "、".join(f"{k}号 {_fmt_votes(v)}票" for k, v in ranked)
        res = payload.get("result")
        return f"放逐投票（第{rnd}轮）：{desc}" + ("" if res else "，平票")
    if typ == "exile":
        if targets:
            return f"{targets[0]}号被投票放逐出局"
        return _strip_god(e.get("text"))
    if typ == "idiot_reveal":
        return f"{actor}号翻牌亮出白痴身份，免于出局但失去投票权"
    if typ == "explode":
        seat = payload.get("seat", actor)
        return f"{seat}号自爆，亮明狼人身份出局，当天发言与投票中止"
    if typ in ("dawn", "hunter_shot", "badge", "game_over"):
        return _strip_god(e.get("text"))
    return None


def build_timeline(events: list[dict]) -> list[dict]:
    """[{day, kind: night|day, title: '第 1 夜', items: [str, ...]}]

    输入是上帝视角的完整事件流（``Event.as_dict()`` 形态）。NIGHT_* 阶段算夜里，
    其余都算白天。只收关键节点：刀人、用药、验人、警长、死讯、放逐、翻牌、开枪、
    自爆、警徽、结局。
    """
    rounds: list[dict] = []
    for e in events:
        day = e.get("day") or 0
        if day <= 0:
            continue
        text = _timeline_item(e)
        if not text:
            continue
        kind = "night" if str(e.get("phase", "")).startswith("NIGHT") else "day"
        if not rounds or rounds[-1]["day"] != day or rounds[-1]["kind"] != kind:
            rounds.append({"day": day, "kind": kind,
                           "title": f"第 {day} {'夜' if kind == 'night' else '天'}",
                           "items": []})
        rounds[-1]["items"].append(text)
    return rounds


def thoughts_from_events(events: list[dict]) -> list[dict]:
    """从上帝日志里的 thought 事件还原心路历程（payload 就是 thought_log 条目）。"""
    return [e["payload"] for e in events
            if e.get("type") == "thought" and (e.get("payload") or {}).get("thought")]


def thoughts_from_turns(turns: list[dict]) -> list[dict]:
    """存储层的决策记录 → thought_log 形态（事件里没有 thought 时的兜底）。"""
    out = []
    for t in turns:
        if not t.get("thought"):
            continue
        out.append({
            "turn": t.get("turn"), "seq": t.get("seq"), "day": t.get("day"),
            "phase": t.get("phase"), "phase_cn": i18n.phase_cn(t.get("phase")),
            "seat": t.get("seat"), "role": t.get("role"), "role_cn": i18n.role_cn(t.get("role")),
            "action_type": t.get("action_type"), "action_cn": i18n.action_cn(t.get("action_type")),
            "attempt": t.get("attempt", 1), "thought": t["thought"], "action": t.get("action"),
            "action_desc": i18n.describe_action(t.get("action_type"), t.get("action")),
            "accepted": bool(t.get("accepted")), "error": t.get("error"),
        })
    return out


def render_stored_replay(game: dict, events: list[dict], thoughts: list[dict]) -> str:
    """历史对局（服务重启后只剩库里的数据）的文字战报。"""
    result = game.get("result") or {}
    config = game.get("config") or {}
    n = config.get("n_players") or len(result.get("players") or [])
    try:
        board_name = board_summary(n)["name"]
    except (ValueError, KeyError, TypeError):
        board_name = f"{n}人局"
    L = ["# 对局复盘", "", f"**{board_name}** · "
         f"胜负规则：{'屠城' if config.get('win_rule') == 'city' else '屠边'}"
         f" · 随机种子：`{config.get('seed')}`", ""]
    winner = result.get("winner")
    L += ["## 结果", "",
          f"### {'🟢 好人阵营胜利' if winner == 'VILLAGE' else '🔴 狼人阵营胜利' if winner == 'WOLF' else '⚪ 平局 / 未完成'}",
          "", f"{result.get('reason') or game.get('end_reason') or '对局未正常结束'}"
          f"　·　共进行 {result.get('days') or game.get('days') or 0} 天", ""]
    players = result.get("players") or []
    if players:
        L += ["## 身份表", "", "| 座位 | 身份 | 阵营 | agent | 结局 |", "|---|---|---|---|---|"]
        for p in players:
            badge = " 👑" if p.get("is_sheriff") else ""
            L.append(f"| {p['seat']}号{badge} | {p.get('role_cn', '')} | "
                     f"{'狼人阵营' if p.get('side') == 'wolf' else '好人阵营'} | "
                     f"{p.get('agent') or ''} | {p.get('fate_cn', '')} |")
        L.append("")
    timeline = build_timeline(events)
    if timeline:
        L += ["## 关键节点", ""]
        for r in timeline:
            L.append(f"**{r['title']}**")
            L += [f"- {x}" for x in r["items"]]
            L.append("")
    L += ["## 全过程", "",
          "> 图例：（空白）=全场公开　🐺=仅狼人可见　🔒=仅当事人可见　👁=上帝日志", ""]
    current_day = None
    for e in events:
        if e.get("type") == "thought":
            continue
        if e.get("day") != current_day:
            current_day = e.get("day")
            L += ["", f"### 第 {current_day} 天" if current_day else "### 开局", ""]
        try:
            mark = _AUD_MARK[Audience(e.get("audience"))]
        except ValueError:
            mark = "　　"
        L.append(f"`{mark}` **[{e.get('phase_cn') or i18n.phase_cn(e.get('phase'))}]** {e.get('text', '')}")
    L.append("")
    L += ["## 心路历程", "",
          "每个 agent 在每个决策点的内心想法。**这些内容从未进入过任何其他玩家的视角。**", ""]
    by_seat: dict[int, list[dict]] = defaultdict(list)
    for t in thoughts:
        by_seat[t["seat"]].append(t)
    for seat in sorted(by_seat):
        entries = by_seat[seat]
        L += ["", f"### {seat}号 · {entries[0].get('role_cn') or i18n.role_cn(entries[0].get('role'))}", ""]
        for t in entries:
            tag = "" if t.get("accepted") else f"（第{t.get('attempt')}次尝试，被判非法：{t.get('error')}）"
            L.append(f"- **第{t.get('day')}天 · {t.get('phase_cn') or i18n.phase_cn(t.get('phase'))}"
                     f" · {t.get('action_cn') or i18n.action_cn(t.get('action_type'))}**{tag}")
            L.append(f"  > {t['thought']}")
            if t.get("accepted") and t.get("action_desc"):
                L.append(f"  - → 实际动作：{t['action_desc']}")
    L.append("")
    return "\n".join(L) + "\n"


_CAUSE_WHEN = {"killed": "night", "poisoned": "night", "exiled": "vote",
               "shot": "shot", "exploded": "explode"}


def players_from_events(events: list[dict], lineup: list[dict] | None = None) -> list[dict]:
    """只有事件流时（旧库、或中途断掉的对局）还原 players_summary 形态的身份表。"""
    roles: dict[int, str] = {}
    for e in events:
        if e.get("type") == "setup":
            roles = {int(k): v for k, v in ((e.get("payload") or {}).get("roles") or {}).items()}
            break
    labels = {x.get("seat"): x.get("label") for x in (lineup or [])}
    deaths: dict[int, dict] = {}
    idiots: set[int] = set()
    sheriff = None
    for e in events:
        typ, payload, targets = e.get("type"), e.get("payload") or {}, e.get("targets") or []
        if typ == "death" and payload.get("seat") is not None:
            cause = payload.get("cause")
            deaths[int(payload["seat"])] = {"day": e.get("day"), "cause": cause,
                                            "when": _CAUSE_WHEN.get(cause)}
        elif typ == "idiot_reveal":
            idiots.add(e.get("actor"))
            if sheriff == e.get("actor"):
                sheriff = None
        elif typ == "sheriff_result" and targets:
            sheriff = targets[0]
        elif typ == "badge":
            sheriff = targets[0] if targets else None
        elif typ == "explode" and sheriff == e.get("actor"):
            sheriff = None
    out = []
    for s in sorted(roles or labels):
        role = roles.get(s)
        d = deaths.get(s)
        alive = d is None
        is_sheriff = alive and sheriff == s
        try:
            wolf = Role(role).faction is Faction.WOLF
        except ValueError:
            wolf = False
        out.append({
            "seat": s, "role": role, "role_cn": i18n.role_cn(role),
            "side": "wolf" if wolf else "good", "agent": labels.get(s),
            "alive": alive, "is_sheriff": is_sheriff,
            "died_day": d and d["day"], "died_when": d and d["when"],
            "died_cause": d and d["cause"], "died_cause_cn": i18n.cause_cn(d and d["cause"]),
            "fate_cn": fate_cn(alive=alive, died_day=d and d["day"], died_when=d and d["when"],
                               died_cause=d and d["cause"], is_sheriff=is_sheriff,
                               idiot_revealed=s in idiots),
        })
    return out
