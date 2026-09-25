"""中文显示层。

内部数据模型一律用英文标识符（代码好读、DB 好查、schema 稳定），
但**凡是会被人看到的地方都必须翻成中文** —— 战报、心路历程、prompt、网页。

所以英文标识符只允许出现在两个地方：代码里，和数据库的列里。
只要它出现在玩家或复盘读者眼前，就是 bug（tests/test_i18n.py 会扫）。
"""
from __future__ import annotations

import re

from .roles import Role

#: 流程阶段
PHASE_CN = {
    "SETUP": "发牌",
    "NIGHT": "黑夜",
    "NIGHT_WOLF_CHAT": "狼人夜谈",
    "NIGHT_WOLF_KILL": "狼人刀人",
    "NIGHT_WITCH": "女巫用药",
    "NIGHT_SEER": "预言家验人",
    "NIGHT_HUNTER": "猎人确认",
    "DAWN": "天亮",
    "DAYBREAK": "天亮",
    "LAST_WORDS": "遗言",
    "SHERIFF_SIGNUP": "上警",
    "SHERIFF_SPEECH": "警上发言",
    "SHERIFF_VOTE": "警长投票",
    "SHERIFF_PK": "警长PK",
    "BADGE_TRANSFER": "警徽移交",
    "DAY_SPEECH": "白天发言",
    "DAY_VOTE": "投票放逐",
    "DAY_VOTE_PK": "放逐PK",
    "HUNTER_SHOT": "猎人开枪",
    "IDIOT_REVEAL": "白痴翻牌",
    "GAME_OVER": "游戏结束",
}

#: 动作类型
ACTION_CN = {
    "wolf_chat": "狼人夜谈",
    "wolf_kill": "决定刀人",
    "witch_action": "女巫用药",
    "seer_check": "预言家验人",
    "sheriff_signup": "是否上警",
    "sheriff_speech": "警上发言",
    "sheriff_vote": "投警长票",
    "badge_transfer": "移交警徽",
    "speech": "发言",
    "vote": "投票",
    "last_words": "遗言",
    "hunter_shoot": "猎人开枪",
}

#: 死因
CAUSE_CN = {
    "killed": "被狼刀", "poisoned": "被女巫毒", "exiled": "被放逐",
    "shot": "被猎人枪杀", "exploded": "自爆",
}

#: 死亡时机
WHEN_CN = {"night": "夜里", "vote": "被投票", "shot": "被枪杀", "explode": "自爆"}

#: 座位运行时的释放原因
RELEASE_CN = {**CAUSE_CN, "game_over": "游戏结束", "aborted": "中途终止", "dead": "出局"}

#: 验人结果
CHECK_CN = {"WOLF": "查杀", "GOOD": "金水"}

#: 狼队白天定位
POSITION_CN = {"HARD_CLAIM": "悍跳", "CHARGE": "冲锋", "BACKHOOK": "倒钩", "DEEP": "深水"}

#: 可见性
AUDIENCE_CN = {"public": "全场公开", "wolves": "仅狼人可见",
               "private": "仅当事人可见", "god": "上帝日志"}

#: agent 后端
BACKEND_CN = {"heuristic": "规则bot", "human": "真人玩家", "claude": "Claude", "openai": "OpenAI",
              "llm": "Claude"}

#: 警徽状态
SHERIFF_STATUS_CN = {"none": "尚未竞选", "elected": "已产生",
                     "lost": "警徽流失", "destroyed": "警徽已销毁"}


def _get(table: dict, key, default=None) -> str:
    if key is None:
        return default or ""
    return table.get(key, default if default is not None else str(key))


def audience_cn_of(audience) -> str:
    return _get(AUDIENCE_CN, audience)


def phase_cn(phase) -> str:
    return _get(PHASE_CN, phase)


def action_cn(action_type) -> str:
    return _get(ACTION_CN, action_type)


def cause_cn(cause) -> str:
    return _get(CAUSE_CN, cause)


def when_cn(when) -> str:
    return _get(WHEN_CN, when)


def release_cn(reason) -> str:
    return _get(RELEASE_CN, reason)


def check_cn(result) -> str:
    return _get(CHECK_CN, result)


def position_cn(pos) -> str:
    return _get(POSITION_CN, pos)


def role_cn(value) -> str:
    """角色枚举值或 Role 对象 → 中文。"""
    if value is None:
        return ""
    if isinstance(value, Role):
        return value.cn
    try:
        return Role(value).cn
    except ValueError:
        return str(value)


def seats_cn(seats) -> str:
    """[3, 7] → '3号、7号'"""
    return "、".join(f"{s}号" for s in (seats or []))


def describe_action(action_type: str, action: dict | None) -> str:
    """把一个动作渲染成一句中文，用来替代直接 dump 英文字典。"""
    if not action:
        return ""
    a, parts = action, []

    def seat(v):
        return f"{v}号" if v is not None else None

    if action_type == "wolf_chat":
        if a.get("my_position"):
            parts.append(f"我打{position_cn(a['my_position'])}")
        if a.get("kill_suggestion"):
            parts.append(f"建议刀{seat(a['kill_suggestion'])}")
        if a.get("position_plan"):
            parts.append("分工：" + "、".join(
                f"{k}号{position_cn(v)}" for k, v in a["position_plan"].items()))
    elif action_type == "wolf_kill":
        parts.append(f"刀{seat(a.get('target'))}" if a.get("target") else "空刀")
    elif action_type == "seer_check":
        parts.append(f"验{seat(a.get('target'))}" if a.get("target") else "不验")
    elif action_type == "witch_action":
        parts.append("用解药" if a.get("heal") else "不用解药")
        parts.append(f"毒{seat(a['poison'])}" if a.get("poison") else "不用毒药")
    elif action_type == "sheriff_signup":
        parts.append("上警" if a.get("run") else "不上警")
    elif action_type in ("speech", "sheriff_speech", "last_words"):
        if a.get("explode"):
            return "自爆"
        if a.get("quit"):
            parts.append("退水")
        parts.append(f"跳{role_cn(a['claim'])}" if a.get("claim") else "不起跳")
        if a.get("claimed_check"):
            c = a["claimed_check"]
            parts.append(f"报{seat(c['target'])}={check_cn(c['result'])}")
        if a.get("badge_flow"):
            parts.append("警徽流" + seats_cn(a["badge_flow"]))
        if a.get("suspects"):
            parts.append("怀疑" + seats_cn(a["suspects"]))
        if a.get("trusts"):
            parts.append("信任" + seats_cn(a["trusts"]))
    elif action_type in ("vote", "sheriff_vote"):
        parts.append(f"投{seat(a['target'])}" if a.get("target") else "弃票")
    elif action_type == "hunter_shoot":
        parts.append(f"开枪带走{seat(a['target'])}" if a.get("target") else "不开枪")
    elif action_type == "badge_transfer":
        parts.append(f"警徽交给{seat(a['target'])}" if a.get("target") else "撕毁警徽")
    return "｜".join(p for p in parts if p)


# --------------------------------------------------------------------------
# 真人玩家座位：把合法动作 schema 和角色私有知识翻成浏览器能直接渲染的中文
# --------------------------------------------------------------------------

#: 动作字段名
FIELD_CN = {
    "speech": "发言", "claim": "宣称身份", "claim_detail": "补充说明",
    "claimed_check": "公布验人结果", "badge_flow": "警徽流", "suspects": "怀疑",
    "trusts": "信任", "explode": "自爆", "quit": "退水", "target": "目标",
    "heal": "解药", "poison": "毒药", "run": "竞选警长", "reason": "理由",
    "kill_suggestion": "建议刀谁", "my_position": "我的定位", "strategy_note": "战术备注",
}

#: 布尔字段的两个选项（是, 否）
_BOOL_CN = {
    "run": ("上警", "不上警"), "heal": ("用解药", "不用"), "explode": ("自爆", "不自爆"),
    "quit": ("退水", "继续竞选"),
}

#: 这些可选字段收进「更多」里，默认不展开
_ADVANCED_FIELDS = {"claim_detail", "reason", "strategy_note", "suspects", "trusts"}

#: 表单里不给真人填的字段（结构复杂、可选，留空即可）
_SKIPPED_FIELDS = {"position_plan"}

#: 多选座位字段的数量上限
_MAX_ITEMS = {"badge_flow": 3}


def _null_label(desc: str, default: str = "不选") -> str:
    """schema 描述里写着「null 表示弃票」这类说明，拿来当「空」选项的名字。"""
    m = re.search(r"null ?表示([^，。,（(]+)", desc or "")
    return m.group(1).strip() if m else default


#: 给 LLM 看的字段说明里有 JSON 示例，真人看不懂，换成人话
_HINT_CN = {
    "claimed_check": "以预言家身份公布验人结果：选一个座位，再选查杀或金水。不公布就都不选。",
    "run": "",  # 动作说明里已经讲过警长的权力
}


def _hint(name: str, desc: str) -> str:
    """字段说明给真人看：去掉「null 表示……」这类写给模型的话。"""
    if name in _HINT_CN:
        return _HINT_CN[name]
    desc = re.sub(r"[，,；;]?\s*null ?表示[^，。,；;]*[，,；;]?", "", desc or "").strip()
    return desc


def _option(value) -> dict:
    return {"value": value, "label": f"{value}号" if isinstance(value, int) else str(value)}


def human_form(legal: dict | None, *, alive: list[int], me: int) -> dict | None:
    """合法动作 → 表单描述。前端只管照着渲染，不认识任何英文枚举。

    返回 ``{action_type, action_cn, description, fields: [...]}``，每个字段：
    ``{name, label, kind, required, desc, advanced, options?, max_items?, max_chars?}``，
    ``kind`` 取 ``choice``（单选）/ ``multi``（多选座位）/ ``text`` / ``textarea`` / ``check``（验人结果）。
    ``options`` 里的 ``value`` 原样回传给服务端即可。
    """
    if not legal:
        return None
    fields = []
    others = [s for s in alive if s != me]
    for name, spec in (legal.get("schema") or {}).items():
        if name in _SKIPPED_FIELDS:
            continue
        typ = str(spec.get("type", "string"))
        desc = spec.get("desc", "")
        f = {"name": name, "label": FIELD_CN.get(name, name), "required": bool(spec.get("required")),
             "desc": _hint(name, desc), "advanced": name in _ADVANCED_FIELDS}
        opts = spec.get("options")
        if typ == "bool":
            yes, no = _BOOL_CN.get(name, ("是", "否"))
            f.update(kind="choice", options=[
                {"value": v, "label": yes if v else no} for v in (opts or [True, False])])
        elif typ == "enum":
            pos = name == "my_position"
            f.update(kind="choice", options=[
                {"value": v,
                 "label": (position_cn(v) if pos else role_cn(v)) if v is not None
                 else ("不认领" if pos else "不起跳")}
                for v in (opts or [])])
        elif typ.startswith("int"):
            f.update(kind="choice", options=[
                _option(v) if v is not None else {"value": None, "label": _null_label(desc)}
                for v in (opts or [])])
        elif typ.startswith("array"):
            f.update(kind="multi", options=[_option(s) for s in others],
                     max_items=_MAX_ITEMS.get(name))
        elif typ.startswith("object"):
            f.update(kind="check", options=[_option(s) for s in others],
                     results=[{"value": k, "label": v} for k, v in CHECK_CN.items()])
        elif name == "speech":
            f.update(kind="textarea")
            m = re.search(r"最多 (\d+) 字", desc)
            if m:
                f["max_chars"] = int(m.group(1))
        else:
            f.update(kind="text")
        fields.append(f)
    return {
        "action_type": legal.get("action_type"),
        "action_cn": action_cn(legal.get("action_type")),
        "description": legal.get("description", ""),
        "fields": fields,
    }


def knowledge_cn(identity: dict) -> list[str]:
    """个人视角里的角色私有知识 → 几行中文。"""
    k = identity.get("role_knowledge") or {}
    role = identity.get("role")
    out: list[str] = []
    if role == Role.SEER.value:
        for c in k.get("checks", []):
            out.append(f"第{c.get('day')}夜 查验{c.get('target')}号：{check_cn(c.get('result'))}")
        if not k.get("checks"):
            out.append("还没有查验过任何人")
    elif role == Role.WITCH.value:
        out.append(f"解药：{'还在' if k.get('has_antidote') else '已用'}；"
                   f"毒药：{'还在' if k.get('has_poison') else '已用'}")
        for x in k.get("potion_log", []):
            what = "救了" if x.get("potion") == "antidote" else "毒了"
            out.append(f"第{x.get('day')}夜 {what}{x.get('target')}号")
    elif role == Role.HUNTER.value:
        out.append("可以开枪" if k.get("can_shoot") else "被毒死，不能开枪")
    elif role == Role.IDIOT.value:
        out.append("已翻牌，失去投票权" if k.get("revealed") else "还没翻牌")
    elif role == Role.WEREWOLF.value:
        mates = k.get("teammates", [])
        alive = set(k.get("alive_teammates", []))
        out.append("狼队友：" + ("、".join(
            f"{s}号{'' if s in alive else '（已出局）'}" for s in mates) or "无"))
    return out
