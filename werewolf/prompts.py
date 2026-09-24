"""把 PlayerView 渲染成给 LLM 的 prompt。对应 docs/04-视角与上下文.md §3。

三条原则：
  1. system 整局逐字不变 → 命中 prompt cache
  2. user 只发增量（自上次决策以来的新事件）
  3. 用 JSON Schema 硬约束输出，不靠"请输出 JSON"这种软约束
"""
from __future__ import annotations

from .roles import Role
from .views import PlayerView

def rules_digest(view: PlayerView) -> str:
    """规则摘要。随板子人数变化，所以按局生成。"""
    rd = view.public_state["rules_digest"]
    n = rd["n_players"]
    skills = {
        "SEER": "  · 预言家：每晚查验一人，得知【狼人】或【好人】",
        "WITCH": "  · 女巫：一瓶解药一瓶毒药，整局各一次，同夜只能用一瓶；首夜可自救",
        "HUNTER": "  · 猎人：被刀或被票出局时可开枪带走一人；被毒死时不能开枪",
        "IDIOT": "  · 白痴：被票出局时翻牌不死，但永久失去投票权，且当天不再有人出局",
    }
    lines = [
        f"你正在参加一局【{rd['board_name']}】。",
        "",
        f"座位固定为 1~{n} 号。",
        "胜负（屠边）：",
        f"  · 好人胜 —— {rd['wolves']} 名狼人全部出局",
        f"  · 狼人胜 —— {rd['gods']} 名神职全部出局（屠神）"
        f"或 {rd['villagers']} 名平民全部出局（屠民），任一达成即可",
        "技能：",
    ]
    lines += [skills[r] for r in ("SEER", "WITCH", "HUNTER", "IDIOT") if r in rd["roles"]]
    lines += [
        "  · 狼人：每晚共同刀一人（可空刀）；白天可以【自爆】",
        "",
        "流程：每晚 狼人商议刀人 → 女巫用药 → 预言家验人；"
        "白天 公布死讯 → 依次发言 → 投票放逐 → 遗言。",
    ]
    if rd["sheriff"]:
        lines.append("第一天白天开始前有警长竞选，警长 1.5 票并决定发言顺序。")
    lines.append(
        "【自爆】狼人在白天发言阶段可以自爆：当场亮明狼人身份立刻出局，"
        "白天立即结束（后续发言取消、今天不投票），直接进入黑夜。"
        "自爆没有遗言，若自爆者是警长则警徽销毁。"
    )
    lines.append(
        f"【发言长度】每次发言最多 {rd['max_speech_chars']} 字，"
        "大约等于真人在牌桌上讲 2 分钟。超长会被打回重说。"
    )
    return "\n".join(lines)

#: 各角色的发言结构。取自真人牌桌上通行的发言套路，而不是泛泛的"要动脑子"。
ROLE_STRATEGY = {
    Role.WEREWOLF: """\
你是狼人。白天你要扮成好人，所以**你的发言必须长得像一个好人的发言**。

狼队的四种白天定位（第一夜在狼人频道里分工，一队通常只出一个悍跳）：
  · 悍跳：冒充预言家，给一个好人发查杀，跟真预言家对跳抢警徽。
    你必须把预言家那套发言结构完整模仿出来——报查验、留警徽流、讲验人心路历程。
    只报查杀不留警徽流，是最容易被好人识破的破绽。
  · 冲锋：扮平民，但强势站边自家悍跳、打真预言家、帮着归票。
    风险是太急会暴露，所以要给出"我为什么信他"的具体理由，不能只喊口号。
  · 倒钩：扮平民，反过来站边【真】预言家，骗到好人信任，后期再反水。
    倒钩最怕被自家队友误伤，所以夜里要让队友知道你在倒钩。
  · 深水：扮平民，少说少错，把发言权和火力让给队友，保存到后期。

其他要点：
  · 屠边：优先杀神（预言家、女巫、猎人）而不是平民，神死光就赢
  · 自爆：局势极差时用你这条命换掉好人一整个白天。队友还活着才值得
  · 你只知道狼队友是谁，其余人对你也是黑的——你并不知道谁是预言家
  · 夜里在狼人频道说的话好人永远看不到，白天要注意不要说漏嘴""",

    Role.SEER: """\
你是预言家，好人阵营唯一的硬信息源，而且你大概率活不过第二晚。
所以**你的任务不是活着，是在死之前把信息和指挥权交出去**。

真人预言家的警上发言是固定的三部曲，你要照着打：
  1. **报查验**：我是场上唯一的预言家，X 号是我的查杀 / 金水。
  2. **留警徽流**：今明晚连验 A 和 B。
     AB 都是狼 → 警徽飞外置位；AB 都是好人 → 撕掉警徽；一好一狼 → 警徽飞好人。
     这一步最关键——你死了以后，好人靠警徽流才知道该信谁、警徽该给谁。
     不留警徽流的"预言家"在真人局里会被直接当成狼。
  3. **聊心路历程**：我昨晚为什么验 X，警徽流为什么选 A 和 B。
     给出理由才有说服力，光报结果跟悍跳狼没有区别。

其他要点：
  · 你几乎必须上警——只有拿到警徽，警徽流、归票权、1.5 票和发言顺序才生效
  · 会有狼人跟你对跳，好人要在你们两个里二选一。
    赢下这个对跳靠的是逻辑细节和警徽流质量，不是嗓门
  · 后续每晚的验人**尽量兑现你报出去的警徽流**，说到做到本身就是身份证明""",

    Role.WITCH: """\
你是女巫。你知道每晚谁被刀，这是场上第二硬的信息。

  · 首夜通常用解药（"首夜必救"），之后解药很难再用上
  · 毒药宁可不用也别毒错好人；最稳的是毒真预言家报出来的查杀
  · **你跳身份的时候，第一件事是给好人复盘夜间的刀口**：
    哪天谁倒了、我救了谁、我毒了谁。这些信息只有真女巫拿得到，是你的身份证明
  · 但一旦公开，你就会被狼人重点照顾，所以要挑值得的时机跳""",

    Role.HUNTER: """\
你是猎人。你的枪是好人最后的威慑。

  · 平时**按平民的方式发言**，低调藏身份，不要主动跳
  · 一旦起跳就要强势带队——你带着枪，狼人不敢轻易推你
  · 被女巫毒死时开不了枪，所以要留意女巫的用药
  · 什么时候跳：好人要被推错人、或者你觉得自己马上会被刀的时候""",

    Role.IDIOT: """\
你是白痴。被票出局时会翻牌不死，但从此没有投票权。

  · 你其实是一张"消耗好人一次投票"的牌，翻牌后可以继续用发言帮好人
  · 翻牌后你不再有票，狼人也没必要刀你，所以那之后你可以放开了说
  · 翻牌前按平民打，不要暴露""",

    Role.VILLAGER: """\
你是平民。你没有技能，你的价值全在发言质量和投票上。

真人平民的发言顺序是**先表水、再找狼**：
  1. **表水**：先让别人相信你是好人——讲清楚你的判断依据、你听谁的、为什么。
     在别人还怀疑你的时候急着指认别人，是最危险的操作。
  2. **找狼**：表完水再站边和归票。

其他要点：
  · 认真盘前面每个人说过什么：谁在悍跳、谁在划水、谁的票投得反常、谁前后矛盾
  · 投票跟着你相信的预言家走，别自己乱开车
  · "我是好人，我怀疑 X 号"这种没有依据的发言在真人局里会被当成划水狼打""",
}

#: 发言位次的价值。真人局里后置位明显优于前置位，这是警长权力的全部意义。
POSITION_NOTE = """\
发言位次是有价值的：**后置位比前置位有利**。
前面发言的人说完，后面的人可以针对性地反驳、补刀、归票，而前面的人已经没有机会再解释；
而且发言一多，最早说的话很容易被大家忘掉。
所以警长决定从哪边开始发言，本质上是在决定谁被架在火上烤。
你如果在前置位，就要把话说得足够扎实、留下能被后面引用的判断；
你如果在后置位，就要真的去盘前面每一个人说了什么，而不是重复一遍你的立场。"""

OUTPUT_RULE = """\
你必须只输出一个 JSON 对象，不要输出任何解释性文字、不要用 markdown 代码块包裹。
字段含义和取值范围会在每次请求里给出，超出范围的取值会被判为非法并要求你重来。
`private_thought` 字段是你的内心想法，任何其他玩家都看不到，请在里面写下你真实的推理：
你怎么读的场上局势、你在骗谁、你为什么这么选。这部分不限长度，写透。
发言字段（speech）不一样——那是要念出来给全场听的，要写得像真人在牌桌上说话：
口语、有情绪、有针对性，并且**必须控制在字数上限内**（大约真人讲 2 分钟的量）。
"""


def system_prompt(view: PlayerView) -> str:
    """整局不变的角色卡。"""
    idt = view.identity
    parts = [
        rules_digest(view),
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
    parts += ["", "════════ 打法提示 ════════", ROLE_STRATEGY[view.role],
              "", POSITION_NOTE, "",
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
    if ps["public_badge_flows"]:
        lines.append("公开报出的警徽流：" + "　".join(
            "第{}天 {}号报「{}」".format(
                b["day"], b["by"], "、".join(f"{t}号" for t in b["targets"]))
            for b in ps["public_badge_flows"]
        ))
    # 票型全给，不截断 —— 票型是抓狼最硬的证据之一
    for v in ps["vote_history"]:
        kind = "警长票" if v["type"] == "sheriff" else "放逐票"
        desc = "、".join(f"{k}→{t}号" if t else f"{k}弃票" for k, t in v["votes"].items())
        lines.append(f"第{v['day']}天{kind}(第{v['round']}轮)：{desc}　出局={v['result'] or '平票'}")
    return "\n".join(lines)


def _fmt_speech_archive(view: PlayerView) -> str:
    """全场发言档案。这是 agent 能"盘逻辑"的前提 —— 没有原文就只能靠标签推理。"""
    arch = view.public_state["speech_archive"]
    if not arch:
        return ""
    lines = ["════════ 全场发言档案（这是你盘逻辑的原始材料）════════",
             "近两天给发言原文，更早的压成一行立场摘要。注意找前后矛盾、注意谁在划水。"]
    day = None
    for e in arch:
        if e["day"] != day:
            day = e["day"]
            lines.append(f"\n── 第 {day} 天 ──")
        tags = []
        if e["claim"]:
            tags.append(f"跳{Role(e['claim']).cn}")
        if e["claimed_check"]:
            c = e["claimed_check"]
            tags.append(f"报{c['target']}号={'查杀' if c['result'] == 'WOLF' else '金水'}")
        if e["badge_flow"]:
            tags.append("警徽流" + "".join(f"{t}号" for t in e["badge_flow"]))
        if e["suspects"]:
            tags.append("怀疑" + "".join(f"{t}号" for t in e["suspects"]))
        if e["trusts"]:
            tags.append("信任" + "".join(f"{t}号" for t in e["trusts"]))
        tag = ("［" + "／".join(tags) + "］") if tags else ""
        me = "（你自己）" if e["seat"] == view.seat else ""
        lines.append(f"  {e['seat']}号{me}{tag}：{e['text']}")
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
    if intel["enemy_badge_flows"]:
        lines.append("　　　对方报的警徽流（他接下来要验谁，这决定我们今晚刀谁）：" + "　".join(
            "{}号→{}".format(b["by"], "、".join(f"{t}号" for t in b["targets"]))
            for b in intel["enemy_badge_flows"]
        ))
    if intel["our_badge_flows"]:
        lines.append("　　　我方报的假警徽流（必须记住，明天要圆回来）：" + "　".join(
            "{}号→{}".format(b["by"], "、".join(f"{t}号" for t in b["targets"]))
            for b in intel["our_badge_flows"]
        ))
    used_cn = {True: "已用", False: "未用", None: "未知"}
    lines.append(
        "　　　女巫解药={}　女巫毒药={}　疑似神职={}".format(
            used_cn[intel["witch_antidote_used"]],
            used_cn[intel["witch_poison_used"]],
            intel["suspected_god_seats"],
        )
    )
    lines.append(f"　　　{intel['edge_hint']}")
    assign = wt.strategy_board.get("assignments") or {}
    if assign:
        from .actions import WOLF_POSITIONS
        lines.append("狼队白天分工：" + "　".join(
            "{}号={}".format(k, WOLF_POSITIONS[v].split(" ")[0]) for k, v in sorted(assign.items())
        ))
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
    if la.get("_memory"):
        lines.append(
            "  · notes_update (string) —— 更新你的私人笔记本。留空表示不改。"
            "笔记本会一直跟着你（连容器重启也在），用来记你的推理链、"
            "对每个人的判断、以及你打算怎么骗人。其他人永远看不到。"
        )
    return "\n".join(lines)


def turn_prompt(view: PlayerView, *, full: bool = False, error: str | None = None,
                notes: str = "") -> str:
    """一次决策请求。full=True 时发完整 timeline（首次调用），否则只发增量。

    notes 是这个 agent 自己的私人笔记本（跨回合、跨容器重启保留），
    只有它自己看得到，任何其他玩家和其他 agent 都拿不到。
    """
    blocks = ["════════ 场上局势 ════════", _fmt_public_state(view),
              "", "════════ 你的私有信息 ════════", _fmt_role_knowledge(view)]
    if notes:
        blocks += ["", "════════ 你的私人笔记本（只有你自己看得到）════════", notes]
    # 发言档案每回合都重发（不依赖对话历史），否则早期发言会随历史裁剪永久丢失
    archive = _fmt_speech_archive(view)
    if archive:
        blocks += ["", archive]
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
    "badge_flow": {"type": "array", "items": {"type": "integer"}},
    "suspects": {"type": "array", "items": {"type": "integer"}},
    "trusts": {"type": "array", "items": {"type": "integer"}},
}

_SCHEMAS: dict[str, dict] = {
    "wolf_chat": {
        "speech": _STR, "kill_suggestion": _INT_OR_NULL, "strategy_note": _STR,
        "my_position": {"type": ["string", "null"],
                        "enum": ["HARD_CLAIM", "CHARGE", "BACKHOOK", "DEEP", None]},
        "position_plan": {"type": "object", "additionalProperties": {"type": "string"}},
    },
    "wolf_kill": {"target": _INT_OR_NULL},
    "witch_action": {"heal": {"type": "boolean"}, "poison": _INT_OR_NULL},
    "seer_check": {"target": {"type": "integer"}},
    "sheriff_signup": {"run": {"type": "boolean"}, "reason": _STR},
    "sheriff_speech": {**_SPEECH_PROPS, "quit": {"type": "boolean"}, "explode": {"type": "boolean"}},
    "sheriff_vote": {"target": _INT_OR_NULL},
    "badge_transfer": {"target": _INT_OR_NULL, "reason": _STR},
    "speech": {**_SPEECH_PROPS, "explode": {"type": "boolean"}},
    "vote": {"target": _INT_OR_NULL, "reason": _STR},
    "last_words": {k: v for k, v in _SPEECH_PROPS.items() if k != "trusts"},
    "hunter_shoot": {"target": _INT_OR_NULL},
}


def output_schema(action_type: str, *, memory: bool = False) -> dict:
    props = {**_SCHEMAS[action_type], **_THOUGHT}
    if memory:
        props["notes_update"] = _STR
    return {
        "type": "json_schema",
        "schema": {
            "type": "object",
            "properties": props,
            "required": sorted(props),
            "additionalProperties": False,
        },
    }
