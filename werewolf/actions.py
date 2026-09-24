"""动作 schema、合法性校验与安全回退。对应 docs/02-游戏流程.md §6。

引擎向 agent 索要动作时，先用 ``legal_actions`` 把"现在能做什么、参数范围是什么"
放进视角；拿回动作后用 ``validate`` 校验。非法 → 带错误信息重试；重试用尽 →
``default_action`` 给一个绝不会卡死流程的安全默认值。
"""
from __future__ import annotations

from .roles import Role
from .state import GameState

CLAIMABLE_ROLES = [r.value for r in Role]

#: 狼队的四种白天定位。真人狼队第一夜就会分工，这是狼人配合的基本盘。
WOLF_POSITIONS = {
    "HARD_CLAIM": "悍跳 —— 冒充预言家，给一个好人发查杀，跟真预言家对跳抢警徽",
    "CHARGE": "冲锋 —— 扮平民，但强势站边自家悍跳，帮他归票、打真预言家",
    "BACKHOOK": "倒钩 —— 扮平民，反过来站边【真】预言家骗信任，后期再反水",
    "DEEP": "深水 —— 扮平民，少说少错，把发言权让给队友，保存到后期",
}

ACTION_TYPES = (
    "wolf_chat",
    "wolf_kill",
    "witch_action",
    "seer_check",
    "sheriff_signup",
    "sheriff_speech",
    "sheriff_vote",
    "badge_transfer",
    "speech",
    "vote",
    "last_words",
    "hunter_shoot",
)


class InvalidAction(ValueError):
    pass


# --------------------------------------------------------------------------
# 合法动作描述（进视角的 legal_actions 区块）
# --------------------------------------------------------------------------

_EXPLODE_DESC = (
    "是否自爆。自爆 = 当场亮明狼人身份并立刻出局，白天立即结束"
    "（后续发言取消、今天不投票），直接进入黑夜。没有遗言，若你是警长则警徽销毁。"
    "这是狼队在局势极度不利时打断好人节奏、保护队友的最后手段。"
)


def _speech_schema(max_chars: int) -> dict:
    return {
        "speech": {"type": "string", "required": True,
                   "desc": f"你的公开发言，最多 {max_chars} 字（约等于真人讲 2 分钟）"},
        "claim": {
            "type": "enum",
            "required": False,
            "options": CLAIMABLE_ROLES + [None],
            "desc": "你公开宣称的身份，null 表示不起跳。可以说谎。",
        },
        "claim_detail": {"type": "string", "required": False,
                         "desc": "补充说明，比如验人结果、警徽流、用药情况"},
        "claimed_check": {
            "type": "object|null",
            "required": False,
            "desc": '若你以预言家身份公布验人结果，填 {"target": 座位号, "result": "WOLF" 或 "GOOD"}',
        },
        "badge_flow": {
            "type": "array<int>", "required": False,
            "desc": "警徽流：你以预言家身份公布的【今晚和明晚要验谁】，最多 3 个座位。"
                    "真预言家靠它在自己死后仍然指挥好人；悍跳狼也会报假警徽流。不报就留空数组。",
        },
        "suspects": {"type": "array<int>", "required": False, "desc": "你本轮怀疑的座位"},
        "trusts": {"type": "array<int>", "required": False, "desc": "你本轮信任的座位"},
    }


def legal_actions(state: GameState, seat: int, action_type: str, ctx: dict | None = None) -> dict:
    ctx = ctx or {}
    alive = state.alive_seats()
    others = [s for s in alive if s != seat]
    p = state.players[seat]

    if action_type == "wolf_chat":
        return {
            "action_type": "wolf_chat",
            "description": "狼人频道内部讨论（好人永远看不到）。说出你的判断和今晚刀谁的建议。",
            "schema": {
                "speech": {"type": "string", "required": True, "desc": "对狼队友说的话"},
                "kill_suggestion": {"type": "int|null", "options": alive + [None], "desc": "建议今晚刀谁"},
                "my_position": {
                    "type": "enum", "required": False,
                    "options": list(WOLF_POSITIONS) + [None],
                    "desc": "你认领今天白天打哪个定位。" + "；".join(WOLF_POSITIONS.values()),
                },
                "position_plan": {
                    "type": "object", "required": False,
                    "desc": '给全队的分工建议，形如 {"4": "HARD_CLAIM", "7": "CHARGE"}。'
                            "一队通常只出一个悍跳，其余分倒钩和深水。",
                },
                "strategy_note": {"type": "string", "required": False, "desc": "写进狼队战术板的备注（跨夜保留）"},
            },
        }

    if action_type == "wolf_kill":
        targets = alive if state.config.wolves_can_self_knife else [
            s for s in alive if not state.is_wolf(s)
        ]
        return {
            "action_type": "wolf_kill",
            "description": "提交你今晚的击杀目标。全体狼人票数最高者被刀，平票由座位号最小的存活狼人拍板。",
            "schema": {"target": {"type": "int|null", "options": targets + [None], "desc": "null 表示空刀"}},
        }

    if action_type == "witch_action":
        victim = ctx.get("victim")
        can_heal = (
            p.witch_has_antidote
            and victim is not None
            and (victim != seat or (state.day == 1 and state.config.witch_self_rescue_first_night))
        )
        return {
            "action_type": "witch_action",
            "description": (
                f"今晚被刀的是 {victim} 号。" if victim is not None else "今晚没有人被刀（平安夜）。"
            )
            + f" 解药{'可用' if p.witch_has_antidote else '已用完'}，毒药{'可用' if p.witch_has_poison else '已用完'}。"
            + ("同一晚不能同时用解药和毒药。" if not state.config.witch_same_night_both_potions else ""),
            "schema": {
                "heal": {"type": "bool", "options": [True, False] if can_heal else [False], "desc": "是否用解药救刀口"},
                "poison": {
                    "type": "int|null",
                    "options": (others + [None]) if p.witch_has_poison else [None],
                    "desc": "毒杀目标，null 表示不用毒药",
                },
            },
        }

    if action_type == "seer_check":
        checked = {c["target"] for c in state.seer_checks}
        options = [s for s in others if s not in checked]
        return {
            "action_type": "seer_check",
            "description": "选择今晚查验的目标，上帝会立刻告诉你他是【狼人】还是【好人】。",
            "schema": {"target": {"type": "int", "options": options, "desc": "查验目标（不能重复验、不能验自己）"}},
        }

    if action_type == "sheriff_signup":
        return {
            "action_type": "sheriff_signup",
            "description": "是否竞选警长？警长有 1.5 票，并决定每天的发言顺序。上警意味着你会被重点审视。",
            "schema": {
                "run": {"type": "bool", "options": [True, False], "desc": "True = 上警"},
                "reason": {"type": "string", "required": False, "desc": "内心想法（不公开）"},
            },
        }

    if action_type == "sheriff_speech":
        schema = _speech_schema(state.config.max_speech_chars)
        schema["quit"] = {"type": "bool", "options": [True, False], "desc": "是否退水（放弃竞选）"}
        if state.is_wolf(seat) and state.config.wolf_explode:
            schema["explode"] = {"type": "bool", "options": [True, False],
                                 "desc": _EXPLODE_DESC + "（警上自爆会直接中止警长竞选）"}
        return {
            "action_type": "sheriff_speech",
            "description": "警上发言。这是全场第一次公开发言，你的定位会影响整局。",
            "schema": schema,
        }

    if action_type == "sheriff_vote":
        cands = ctx.get("candidates", [])
        return {
            "action_type": "sheriff_vote",
            "description": f"给警长候选人投票。候选人：{cands}",
            "schema": {"target": {"type": "int|null", "options": list(cands) + [None], "desc": "null 表示弃票"}},
        }

    if action_type == "badge_transfer":
        return {
            "action_type": "badge_transfer",
            "description": "你是警长且即将出局。把警徽移交给一名存活玩家，或撕毁警徽。",
            "schema": {
                "target": {"type": "int|null", "options": others + [None], "desc": "null 表示撕警徽"},
                "reason": {"type": "string", "required": False},
            },
        }

    if action_type == "speech":
        schema = _speech_schema(state.config.max_speech_chars)
        if state.is_wolf(seat) and state.config.wolf_explode and ctx.get("can_explode", True):
            schema["explode"] = {"type": "bool", "options": [True, False], "desc": _EXPLODE_DESC}
        return {
            "action_type": "speech",
            "description": ctx.get("description", "轮到你发言了。"),
            "schema": schema,
        }

    if action_type == "vote":
        options = ctx.get("candidates", others)
        return {
            "action_type": "vote",
            "description": "投票放逐。最高票者出局，平票则进入 PK。",
            "schema": {
                "target": {"type": "int|null", "options": list(options) + [None], "desc": "null 表示弃票"},
                "reason": {"type": "string", "required": False, "desc": "投票理由（会公开）"},
            },
        }

    if action_type == "last_words":
        schema = _speech_schema(state.config.max_speech_chars)
        schema.pop("trusts", None)
        return {
            "action_type": "last_words",
            "description": "你已出局，请留遗言。这是你最后一次向全场传递信息的机会。",
            "schema": schema,
        }

    if action_type == "hunter_shoot":
        return {
            "action_type": "hunter_shoot",
            "description": "你是猎人且可以开枪。选择带走一名存活玩家，或选择不开枪。",
            "schema": {"target": {"type": "int|null", "options": others + [None], "desc": "null 表示不开枪"}},
        }

    raise InvalidAction(f"未知动作类型: {action_type}")


# --------------------------------------------------------------------------
# 校验
# --------------------------------------------------------------------------

def _as_seat(value, allowed: list[int], field: str) -> int | None:
    if value is None or value == "" or value == "null":
        return None
    try:
        seat = int(value)
    except (TypeError, ValueError):
        raise InvalidAction(f"{field} 必须是座位号（整数）或 null，收到 {value!r}")
    if seat not in allowed:
        raise InvalidAction(f"{field}={seat} 不是合法目标，可选：{allowed}")
    return seat


def _as_text(value, field: str, default: str = "") -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        return str(value)
    return value.strip()


def _as_seat_list(value, allowed: list[int]) -> list[int]:
    if not isinstance(value, (list, tuple)):
        return []
    out = []
    for v in value:
        try:
            s = int(v)
        except (TypeError, ValueError):
            continue
        if s in allowed and s not in out:
            out.append(s)
    return out


def _check_length(text: str, max_chars: int) -> str:
    """发言字数上限：人类 2 分钟大约就这么多字，超了就打回让 agent 重说。"""
    if len(text) > max_chars:
        raise InvalidAction(
            f"发言太长了：{len(text)} 字，上限 {max_chars} 字"
            f"（真人 2 分钟大概只能说这么多）。请压缩到 {max_chars} 字以内重说。"
        )
    return text


def _clean_speech_fields(
    raw: dict, alive: list[int], max_chars: int = 450, *, alive_only: list[int] | None = None
) -> dict:
    claim = raw.get("claim")
    if isinstance(claim, str):
        claim = claim.strip().upper()
        if claim in ("", "NULL", "NONE"):
            claim = None
        elif claim not in CLAIMABLE_ROLES:
            claim = None
    else:
        claim = None

    checked = raw.get("claimed_check")
    claimed_check = None
    if isinstance(checked, dict):
        try:
            t = int(checked.get("target"))
        except (TypeError, ValueError):
            t = None
        r = str(checked.get("result", "")).strip().upper()
        if t is not None and r in ("WOLF", "GOOD"):
            claimed_check = {"target": t, "result": r}

    speech = _as_text(raw.get("speech"), "speech", "（该玩家没有发言）") or "（该玩家没有发言）"
    # 警徽流说的是"接下来要验谁"，只能指向活人。
    # 遗言里 alive 参数是全部座位（允许提到死人），所以这里要用单独的存活名单。
    badge_flow = _as_seat_list(raw.get("badge_flow"), alive_only if alive_only is not None else alive)[:3]
    return {
        "speech": _check_length(speech, max_chars),
        "badge_flow": badge_flow,
        "claim": claim,
        "claim_detail": _as_text(raw.get("claim_detail"), "claim_detail"),
        "claimed_check": claimed_check,
        "suspects": _as_seat_list(raw.get("suspects"), alive),
        "trusts": _as_seat_list(raw.get("trusts"), alive),
    }


def validate(state: GameState, seat: int, action_type: str, raw: dict, ctx: dict | None = None) -> dict:
    """校验并规范化一个动作。非法时抛 InvalidAction，错误信息会回灌给 agent。"""
    ctx = ctx or {}
    if not isinstance(raw, dict):
        raise InvalidAction(f"动作必须是一个 JSON 对象，收到 {type(raw).__name__}")

    spec = legal_actions(state, seat, action_type, ctx)
    schema = spec["schema"]
    alive = state.alive_seats()
    p = state.players[seat]

    if action_type == "wolf_chat":
        pos = raw.get("my_position")
        pos = pos if isinstance(pos, str) and pos.upper() in WOLF_POSITIONS else None
        plan = {}
        if isinstance(raw.get("position_plan"), dict):
            for k, v in raw["position_plan"].items():
                try:
                    k = int(k)
                except (TypeError, ValueError):
                    continue
                if k in state.wolf_seats() and isinstance(v, str) and v.upper() in WOLF_POSITIONS:
                    plan[k] = v.upper()
        return {
            "speech": _as_text(raw.get("speech"), "speech", "（沉默）") or "（沉默）",
            "kill_suggestion": _as_seat(raw.get("kill_suggestion"), alive, "kill_suggestion"),
            "my_position": pos.upper() if pos else None,
            "position_plan": plan,
            "strategy_note": _as_text(raw.get("strategy_note"), "strategy_note"),
        }

    if action_type == "wolf_kill":
        return {"target": _as_seat(raw.get("target"), schema["target"]["options"][:-1], "target")}

    if action_type == "witch_action":
        victim = ctx.get("victim")
        heal = bool(raw.get("heal"))
        poison = _as_seat(raw.get("poison"), [s for s in alive if s != seat], "poison")
        if heal and not p.witch_has_antidote:
            raise InvalidAction("你的解药已经用过了，heal 必须为 false")
        if heal and victim is None:
            raise InvalidAction("今晚没有人被刀，无法使用解药，heal 必须为 false")
        if (
            heal
            and victim == seat
            and not (state.day == 1 and state.config.witch_self_rescue_first_night)
        ):
            raise InvalidAction("女巫第二夜起不能自救，heal 必须为 false")
        if poison is not None and not p.witch_has_poison:
            raise InvalidAction("你的毒药已经用过了，poison 必须为 null")
        if heal and poison is not None and not state.config.witch_same_night_both_potions:
            raise InvalidAction("同一晚不能同时使用解药和毒药，请二选一")
        return {"heal": heal, "poison": poison}

    if action_type == "seer_check":
        options = schema["target"]["options"]
        if not options:
            return {"target": None}
        target = _as_seat(raw.get("target"), options, "target")
        if target is None:
            raise InvalidAction("预言家必须选择一个查验目标")
        return {"target": target}

    if action_type == "sheriff_signup":
        return {"run": bool(raw.get("run")), "reason": _as_text(raw.get("reason"), "reason")}

    if action_type == "sheriff_speech":
        out = _clean_speech_fields(raw, alive, state.config.max_speech_chars)
        out["quit"] = bool(raw.get("quit"))
        out["explode"] = bool(raw.get("explode")) and "explode" in schema
        return out

    if action_type == "sheriff_vote":
        return {"target": _as_seat(raw.get("target"), list(ctx.get("candidates", [])), "target")}

    if action_type == "badge_transfer":
        return {
            "target": _as_seat(raw.get("target"), [s for s in alive if s != seat], "target"),
            "reason": _as_text(raw.get("reason"), "reason"),
        }

    if action_type == "speech":
        out = _clean_speech_fields(raw, alive, state.config.max_speech_chars)
        out["explode"] = bool(raw.get("explode")) and "explode" in schema
        return out

    if action_type == "vote":
        candidates = list(ctx.get("candidates", [s for s in alive if s != seat]))
        return {
            "target": _as_seat(raw.get("target"), candidates, "target"),
            "reason": _as_text(raw.get("reason"), "reason"),
        }

    if action_type == "last_words":
        out = _clean_speech_fields(raw, state.seats, state.config.max_speech_chars,
                                   alive_only=alive)
        out.pop("trusts", None)
        return out

    if action_type == "hunter_shoot":
        return {"target": _as_seat(raw.get("target"), [s for s in alive if s != seat], "target")}

    raise InvalidAction(f"未知动作类型: {action_type}")


def default_action(state: GameState, seat: int, action_type: str, ctx: dict | None = None) -> dict:
    """agent 连续失败后的安全回退，保证流程永不卡死。"""
    ctx = ctx or {}
    alive = state.alive_seats()
    others = [s for s in alive if s != seat]
    rng = state.rng

    if action_type == "wolf_chat":
        return {"speech": "（沉默）", "kill_suggestion": None,
                "my_position": None, "position_plan": {}, "strategy_note": ""}
    if action_type == "wolf_kill":
        pool = [s for s in alive if not state.is_wolf(s)] or others
        return {"target": rng.choice(pool) if pool else None}
    if action_type == "witch_action":
        return {"heal": False, "poison": None}
    if action_type == "seer_check":
        checked = {c["target"] for c in state.seer_checks}
        pool = [s for s in others if s not in checked]
        return {"target": rng.choice(pool) if pool else None}
    if action_type == "sheriff_signup":
        return {"run": False, "reason": ""}
    if action_type in ("speech", "sheriff_speech", "last_words"):
        out = {
            "speech": "（该玩家没有发言）",
            "explode": False,
            "claim": None,
            "claim_detail": "",
            "claimed_check": None,
            "badge_flow": [],
            "suspects": [],
            "trusts": [],
        }
        if action_type == "sheriff_speech":
            out["quit"] = False
        if action_type == "last_words":
            out.pop("trusts")
            out.pop("explode")
        return out
    if action_type in ("vote", "sheriff_vote", "hunter_shoot", "badge_transfer"):
        out = {"target": None}
        if action_type in ("vote", "badge_transfer"):
            out["reason"] = ""
        return out
    raise InvalidAction(f"未知动作类型: {action_type}")
