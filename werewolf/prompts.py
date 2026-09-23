"""把 PlayerView 渲染成给 LLM 的 prompt。对应 docs/04-视角与上下文.md §3。

三条原则：
  1. system 整局逐字不变 → 命中 prompt cache
  2. user 只发增量（自上次决策以来的新事件）
  3. 用 JSON Schema 硬约束输出，不靠"请输出 JSON"这种软约束
"""
from __future__ import annotations

from .roles import Role
from .views import PlayerView

RULES_DIGEST = """\
你正在参加一局【12 人标准狼人杀（屠边局）】。

板子：4 狼人 / 4 神（预言家·女巫·猎人·白痴）/ 4 平民，座位固定为 1~12 号。
胜负：
  · 好人胜 —— 4 名狼人全部出局
  · 狼人胜 —— 4 名神职全部出局（屠神）或 4 名平民全部出局（屠民），任一达成即可
技能：
  · 预言家：每晚查验一人，得知【狼人】或【好人】
  · 女巫：一瓶解药一瓶毒药，整局各一次，同夜只能用一瓶；首夜可自救
  · 猎人：被刀或被票出局时可开枪带走一人；被毒死时不能开枪
  · 白痴：被票出局时翻牌不死，但永久失去投票权，且当天不再有人出局
流程：每晚 狼人刀人 → 女巫用药 → 预言家验人；白天 公布死讯 → 发言 → 投票放逐。
第一天白天开始前有警长竞选，警长 1.5 票并决定发言顺序。
"""

ROLE_STRATEGY = {
    Role.WEREWOLF: """\
你是狼人。你的任务是活下来并把好人推出去。常用打法：
  · 悍跳：冒充预言家给好人发查杀，骗警徽、骗信任
  · 倒钩：假装相信真预言家，混进好人阵营
  · 抗推：牺牲一名队友换取其他队友的信任
  · 屠边：优先杀神（预言家、女巫、猎人）而不是平民，神死光就赢
你只知道 4 名狼队友是谁，其余 8 人对你也是黑的 —— 你并不知道谁是预言家。
夜里在狼人频道说的话好人永远看不到，白天要注意不要说漏嘴。""",
    Role.SEER: """\
你是预言家，是好人阵营最重要的信息源。常见打法：
  · 首日起跳报验人结果，争取警徽
  · 报"警徽流"（提前公布接下来几晚要验谁），这样你死了好人也知道该信谁
  · 你会被狼人悍跳对跳，要用发言逻辑说服好人相信你
  · 你大概率活不过第二晚，所以信息要尽早交出去""",
    Role.WITCH: """\
你是女巫。一瓶解药一瓶毒药，整局各一次。常见打法：
  · 首夜通常用解药（"首夜必救"），之后解药很难再用上
  · 毒药宁可不用也别毒错好人；最稳的是毒真预言家报出来的查杀
  · 你知道每晚谁被刀，这是除预言家外最硬的信息，但一旦公开你就会被狼人重点照顾""",
    Role.HUNTER: """\
你是猎人。你的枪是好人最后的威慑。常见打法：
  · 平时藏身份，被票出局或被刀时开枪带走最像狼的人
  · 被女巫毒死时开不了枪，所以要留意女巫的用药
  · 适时跳猎人可以吓退狼人的刀""",
    Role.IDIOT: """\
你是白痴。被票出局时会翻牌不死，但从此没有投票权。常见打法：
  · 你其实是一张"消耗好人一次投票"的牌，翻牌后可以继续用发言帮好人
  · 翻牌后你不再有票，狼人也没必要刀你，所以你可以放开了说""",
    Role.VILLAGER: """\
你是平民。你没有任何技能，只能靠听发言、看票型找狼。常见打法：
  · 认真分析谁在悍跳、谁在划水、谁的票投得反常
  · 投票时跟着你相信的预言家走
  · 不要随便跳神职，那会浪费狼人的一刀（也可能帮到好人，自行判断）""",
}

OUTPUT_RULE = """\
你必须只输出一个 JSON 对象，不要输出任何解释性文字、不要用 markdown 代码块包裹。
字段含义和取值范围会在每次请求里给出，超出范围的取值会被判为非法并要求你重来。
`private_thought` 字段是你的内心想法，任何其他玩家都看不到，请在里面写下你真实的推理。
发言字段（speech）要写得像真人在牌桌上说话：口语、有情绪、有针对性，2~5 句，不要写成报告。
"""


def system_prompt(view: PlayerView) -> str:
    """整局不变的角色卡。"""
    idt = view.identity
    parts = [
        RULES_DIGEST,
        "════════ 你的身份 ════════",
        f"你是 {idt['name']}（{idt['seat']} 号座位），身份是【{idt['role_cn']}】，"
        f"属于【{idt['faction_cn']}】。",
        f"技能：{idt['role_brief']}",
        f"胜利条件：{idt['win_condition']}",
    ]
    if view.is_wolf:
        mates = idt["role_knowledge"]["teammates"]
        parts.append(
            f"你的狼队友是：{'、'.join(f'{m}号' for m in mates)}。"
            "你们在夜里有一个好人完全看不到的狼人频道。"
        )
    parts += ["", "════════ 打法提示 ════════", ROLE_STRATEGY[view.role], "",
              "════════ 输出要求 ════════", OUTPUT_RULE]
    return "\n".join(parts)


def _fmt_public_state(view: PlayerView) -> str:
    ps = view.public_state
    lines = [
        f"第 {ps['day']} 天 / 阶段 {ps['phase']}",
        f"存活：{' '.join(str(s) + '号' for s in ps['alive_seats'])}",
    ]
    if ps["dead_seats"]:
        deaths = {d["seat"]: d for d in ps["death_record"]}
        lines.append(
            "出局：" + "　".join(
                f"{s}号(第{deaths[s]['day']}天{'夜里' if deaths[s]['when'] == 'night' else '被票' if deaths[s]['when'] == 'vote' else '被枪杀'})"
                for s in ps["dead_seats"] if s in deaths
            )
        )
    lines.append(
        "警长：" + (f"{ps['sheriff']}号" if ps["sheriff"] else {
            "none": "尚未竞选", "lost": "警徽流失", "destroyed": "警徽已撕毁"
        }.get(ps["sheriff_status"], "无"))
    )
    if ps["public_claims"]:
        lines.append("公开身份宣称（可能是假的）：" + "　".join(
            f"{s}号自称{Role(c['claim']).cn}" + (f"({c['detail']})" if c["detail"] else "")
            for s, c in ps["public_claims"].items() if c.get("claim")
        ))
    if ps["public_check_claims"]:
        lines.append("公开宣称的验人结果：" + "　".join(
            f"第{c['day']}天 {c['by']}号说 {c['target']}号是{'查杀' if c['result'] == 'WOLF' else '金水'}"
            for c in ps["public_check_claims"]
        ))
    if ps["revealed_roles"]:
        lines.append("已翻牌的身份：" + "　".join(f"{s}号={Role(r).cn}" for s, r in ps["revealed_roles"].items()))
    for v in ps["vote_history"][-2:]:
        kind = "警长票" if v["type"] == "sheriff" else "放逐票"
        desc = "、".join(f"{k}→{t}号" if t else f"{k}弃票" for k, t in v["votes"].items())
        lines.append(f"第{v['day']}天{kind}(第{v['round']}轮)：{desc}　出局={v['result'] or '平票'}")
    return "\n".join(lines)


def _fmt_role_knowledge(view: PlayerView) -> str:
    rk = view.identity["role_knowledge"]
    role = view.role
    if role is Role.SEER:
        if not rk["checks"]:
            return "你还没有查验过任何人。"
        return "你的验人记录：\n" + "\n".join(
            f"  第{c['day']}夜 验 {c['target']}号 → 【{'狼人(查杀)' if c['result'] == 'WOLF' else '好人(金水)'}】"
            for c in rk["checks"]
        ) + f"\n还没验过的存活玩家：{rk['unchecked_alive']}"
    if role is Role.WITCH:
        s = f"解药：{'还在' if rk['has_antidote'] else '已用完'}　毒药：{'还在' if rk['has_poison'] else '已用完'}"
        if rk["potion_log"]:
            s += "\n用药记录：" + "；".join(
                f"第{x['day']}夜{'解药救' if x['potion'] == 'antidote' else '毒杀'}{x['target']}号"
                for x in rk["potion_log"]
            )
        return s
    if role is Role.HUNTER:
        return f"你当前{'可以' if rk['can_shoot'] else '不能'}开枪。"
    if role is Role.IDIOT:
        return f"你{'已经' if rk['revealed'] else '还没'}翻牌，{'没有' if not rk['can_vote'] else '有'}投票权。"
    if role is Role.WEREWOLF:
        return f"狼队友：{rk['teammates']}　存活的队友：{rk['alive_teammates']}"
    return "你没有任何私有信息，只能靠公开信息推理。"


def _fmt_wolf_team(view: PlayerView) -> str:
    wt = view.wolf_team
    if wt is None:
        return ""
    roster = "、".join(
        "{}号{}".format(r["seat"], "" if r["alive"] else "(已出局)") for r in wt.roster
    )
    lines = ["════════ 狼队视角（好人永远看不到）════════", f"狼队：{roster}"]
    if wt.kill_history:
        outcome_cn = {"died": "成功", "saved_by_witch": "被女巫救了",
                      "empty_knife": "空刀", "pending": "待结算"}
        lines.append("刀人记录：" + "；".join(
            "第{}夜 刀{}号({})".format(k["day"], k["decided"], outcome_cn.get(k["outcome"], k["outcome"]))
            for k in wt.kill_history
        ))
    intel = wt.intel
    lines.append(
        f"情报：起跳预言家={intel['claimed_seers']}　我方悍跳={intel['our_claimed_gods']}　"
        f"我方被查杀={[c['target'] for c in intel['checks_on_us']]}"
    )
    used_cn = {True: "已用", False: "未用", None: "未知"}
    lines.append(
        "　　　女巫解药={}　女巫毒药={}　疑似神职={}".format(
            used_cn[intel["witch_antidote_used"]],
            used_cn[intel["witch_poison_used"]],
            intel["suspected_god_seats"],
        )
    )
    lines.append(f"　　　{intel['edge_hint']}")
    if wt.strategy_board.get("notes"):
        lines.append(f"狼队战术板：{wt.strategy_board['notes']}")
    recent = [c for c in wt.chat_log if c["day"] >= view.public_state["day"]]
    if recent:
        lines.append("今晚狼队频道：" + "　".join(
            "{}号「{}」{}".format(
                c["seat"], c["text"],
                "(建议刀{}号)".format(c["kill_suggestion"]) if c["kill_suggestion"] else "",
            )
            for c in recent
        ))
    return "\n".join(lines)


def _fmt_legal_action(view: PlayerView) -> str:
    la = view.legal_actions
    lines = ["════════ 轮到你了 ════════", la["description"], "",
             f"请输出一个 JSON 对象，动作类型 = {la['action_type']}，字段如下："]
    for field, spec in la["schema"].items():
        desc = spec.get("desc", "")
        opts = spec.get("options")
        line = f"  · {field} ({spec['type']})"
        if opts is not None:
            line += f" 可选值：{opts}"
        if desc:
            line += f" —— {desc}"
        lines.append(line)
    lines.append("  · private_thought (string) —— 你的内心推理，其他玩家看不到")
    return "\n".join(lines)


def turn_prompt(view: PlayerView, *, full: bool = False, error: str | None = None) -> str:
    """一次决策请求。full=True 时发完整 timeline（首次调用），否则只发增量。"""
    blocks = ["════════ 场上局势 ════════", _fmt_public_state(view),
              "", "════════ 你的私有信息 ════════", _fmt_role_knowledge(view)]
    wolf = _fmt_wolf_team(view)
    if wolf:
        blocks += ["", wolf]

    events = view.timeline if full else view.delta
    if events:
        title = "全部经过" if full else "自你上次行动以来的新进展"
        blocks += ["", f"════════ {title} ════════"]
        blocks += [
            ("  " if e["vis"] == "public" else "* ") + f"[第{e['day']}天 {e['phase']}] {e['text']}"
            for e in events
        ]
    blocks += ["", _fmt_legal_action(view)]
    if error:
        blocks += ["", f"⚠️ 你上一次的动作被判为非法：{error}\n请修正后重新输出。"]
    return "\n".join(blocks)


# --------------------------------------------------------------------------
# 输出的 JSON Schema（用于 output_config.format，硬约束返回结构）
# --------------------------------------------------------------------------

_INT_OR_NULL = {"type": ["integer", "null"]}
_STR = {"type": "string"}
_THOUGHT = {"private_thought": _STR}

_SPEECH_PROPS = {
    "speech": _STR,
    "claim": {"type": ["string", "null"], "enum": [r.value for r in Role] + [None]},
    "claim_detail": _STR,
    "claimed_check": {
        "type": ["object", "null"],
        "properties": {"target": {"type": "integer"}, "result": {"type": "string", "enum": ["WOLF", "GOOD"]}},
        "required": ["target", "result"],
        "additionalProperties": False,
    },
    "suspects": {"type": "array", "items": {"type": "integer"}},
    "trusts": {"type": "array", "items": {"type": "integer"}},
}

_SCHEMAS: dict[str, dict] = {
    "wolf_chat": {"speech": _STR, "kill_suggestion": _INT_OR_NULL, "strategy_note": _STR},
    "wolf_kill": {"target": _INT_OR_NULL},
    "witch_action": {"heal": {"type": "boolean"}, "poison": _INT_OR_NULL},
    "seer_check": {"target": {"type": "integer"}},
    "sheriff_signup": {"run": {"type": "boolean"}, "reason": _STR},
    "sheriff_speech": {**_SPEECH_PROPS, "quit": {"type": "boolean"}},
    "sheriff_vote": {"target": _INT_OR_NULL},
    "badge_transfer": {"target": _INT_OR_NULL, "reason": _STR},
    "speech": dict(_SPEECH_PROPS),
    "vote": {"target": _INT_OR_NULL, "reason": _STR},
    "last_words": {k: v for k, v in _SPEECH_PROPS.items() if k != "trusts"},
    "hunter_shoot": {"target": _INT_OR_NULL},
}


def output_schema(action_type: str) -> dict:
    props = {**_SCHEMAS[action_type], **_THOUGHT}
    return {
        "type": "json_schema",
        "schema": {
            "type": "object",
            "properties": props,
            "required": sorted(props),
            "additionalProperties": False,
        },
    }
