"""上帝（引擎）：驱动整局游戏的状态机。对应 docs/02-游戏流程.md。

引擎是唯一持有 GameState 的对象。它在每个决策点现场构造视角交给 agent，
拿回动作后校验、执行、追加事件。agent 之间没有任何直接通信渠道 ——
狼人之间的"通信"也是通过引擎写进 WOLVES 事件实现的。
"""
from __future__ import annotations

from collections import Counter, defaultdict

from . import actions as A
from . import i18n
from .agents.base import Agent
from .events import Audience
from .roles import Faction, Role
from .state import GameConfig, GameState, new_game
from .views import build_player_view


class DayInterrupted(Exception):
    """狼人自爆：白天立即结束，后续发言和投票全部取消，直接进入黑夜。"""


class Engine:
    def __init__(
        self,
        state: GameState,
        agents: dict[int, Agent],
        *,
        max_iterations: int | None = None,
        on_event=None,
        view_recorder=None,
        store=None,
        game_id: str = "",
        pool=None,
    ) -> None:
        self.state = state
        self.agents = agents
        #: 会话存储。边跑边写 —— 不能等整局跑完，否则崩了就什么都不剩
        self.store = store
        self.game_id = game_id
        #: 座位运行时池。玩家离场时用它「先存会话、再销毁容器」
        self.pool = pool
        #: 单个决策点最多向 agent 索要几次动作。思考长度不限，但迭代次数有上限。
        self.max_iterations = max_iterations or state.config.max_iterations
        self.on_event = on_event
        self.view_recorder = view_recorder
        self._last_seen: dict[int, int] = {s: 0 for s in state.seats}
        self._turn = 0

    # ---------------- 基础设施 ----------------

    def emit(self, *, type: str, audience: Audience, text: str, **kw):
        e = self.state.event_log.append(
            day=self.state.day, phase=self.state.phase, type=type,
            audience=audience, text=text, **kw,
        )
        if self.store is not None and self.game_id:
            self.store.append_event(self.game_id, e.as_dict())
        if self.on_event:
            self.on_event(e)
        return e

    def ask(self, seat: int, action_type: str, ctx: dict | None = None) -> dict:
        """向某个座位索要一个动作：构造视角 → agent 决策 → 校验 → (重试) → 回退。

        agent 的思考长度不受限制，但索要次数受 ``max_iterations`` 约束：
        每次失败都会把错误信息回灌给 agent，用尽次数后走安全回退，流程永不卡死。
        """
        st = self.state
        ctx = ctx or {}
        self._turn += 1
        agent = self.agents[seat]
        error = None
        # 真人座位会要求更宽的迭代上限（人会手滑），其余座位用全局配置
        limit = getattr(agent, "max_iterations", None) or self.max_iterations

        for attempt in range(limit):
            view = build_player_view(
                st, seat,
                action_type=action_type,
                action_ctx=ctx,
                since_seq=self._last_seen[seat],
            )
            if self.view_recorder:
                self.view_recorder(self._turn, seat, action_type, view)

            thought = None
            try:
                raw = agent.act(view, error=error)
                if isinstance(raw, dict):
                    raw = dict(raw)
                    # 心路历程：从动作里摘出来，只进上帝日志，绝不进任何玩家视角
                    thought = raw.pop("private_thought", None) or None
                cleaned = A.validate(st, seat, action_type, raw, ctx)
            except A.InvalidAction as exc:
                error = str(exc)
                self._record_thought(seat, action_type, attempt, thought,
                                     action=None, accepted=False, error=error)
                self.emit(
                    type="invalid_action", audience=Audience.GOD, actor=seat,
                    text=f"{seat}号的「{i18n.action_cn(action_type)}」动作非法"
                 f"（第{attempt + 1}/{limit}次）：{error}",
                    payload={"action_type": action_type, "error": error},
                )
                continue
            except Exception as exc:  # agent 后端本身出错（网络、解析等）
                error = f"{type(exc).__name__}: {exc}"
                self._record_thought(seat, action_type, attempt, thought,
                                     action=None, accepted=False, error=error)
                self.emit(
                    type="agent_error", audience=Audience.GOD, actor=seat,
                    text=f"{seat}号的 agent 报错（第{attempt + 1}/{limit}次）：{error}",
                    payload={"action_type": action_type, "error": error},
                )
                continue

            self._record_thought(seat, action_type, attempt, thought,
                                 action=cleaned, accepted=True, error=None)
            self._last_seen[seat] = len(st.event_log)
            return cleaned

        fallback = A.default_action(st, seat, action_type, ctx)
        self.emit(
            type="fallback_action", audience=Audience.GOD, actor=seat,
            text=f"{seat}号用尽 {limit} 次迭代，"
                 f"「{i18n.action_cn(action_type)}」改用安全默认动作："
                 f"{i18n.describe_action(action_type, fallback) or '无'}",
            payload={"action_type": action_type, "action": fallback},
        )
        self._last_seen[seat] = len(st.event_log)
        return fallback

    def _record_thought(self, seat, action_type, attempt, thought, *, action, accepted, error):
        """记录心路历程。这是 GOD 级信息，复盘可见，任何玩家视角都看不到。"""
        st = self.state
        entry = {
            "turn": self._turn,
            "attempt_seq": len(st.event_log),
            "seq": len(st.event_log),
            "day": st.day,
            "phase": st.phase,
            "seat": seat,
            "role": st.players[seat].role.value,
            "role_cn": st.players[seat].role.cn,
            "action_type": action_type,
            "action_cn": i18n.action_cn(action_type),
            "phase_cn": i18n.phase_cn(st.phase),
            "attempt": attempt + 1,
            "thought": thought or "",
            "action": action,
            "action_desc": i18n.describe_action(action_type, action),
            "accepted": accepted,
            "error": error,
        }
        if thought or not accepted:
            st.thought_log.append(entry)
        if self.store is not None and self.game_id:
            self.store.append_turn(self.game_id, entry)
        if thought:
            self.emit(
                type="thought", audience=Audience.GOD, actor=seat,
                text=f"[{seat}号 {st.players[seat].role.cn} 内心] {thought}",
                payload=entry,
            )

    # ---------------- 公开信息记账 ----------------

    def _record_public_speech(self, seat: int, act: dict, kind: str = "speech") -> None:
        st = self.state
        text = f"{st.players[seat].name}：{act['speech']}"
        if act.get("claim"):
            claim = act["claim"]
            st.public_claims[seat] = {
                "claim": claim, "day": st.day, "detail": act.get("claim_detail", ""),
            }
            text += f"　【公开身份宣称：{Role(claim).cn}】"
        if act.get("claimed_check"):
            c = act["claimed_check"]
            st.public_check_claims.append(
                {"day": st.day, "by": seat, "target": c["target"], "result": c["result"]}
            )
            text += f"　【宣称验人：{c['target']}号 = {'查杀' if c['result'] == 'WOLF' else '金水'}】"
        if act.get("badge_flow"):
            st.public_badge_flows.append(
                {"day": st.day, "by": seat, "targets": list(act["badge_flow"])}
            )
            text += "　【警徽流：" + "、".join(f"{t}号" for t in act["badge_flow"]) + "】"
        # 发言原文进档案，供所有人日后"盘逻辑"
        st.speech_log.append({
            "day": st.day, "phase": st.phase, "kind": kind, "seat": seat,
            "text": act["speech"], "claim": act.get("claim"),
            "claim_detail": act.get("claim_detail", ""),
            "claimed_check": act.get("claimed_check"),
            "badge_flow": list(act.get("badge_flow") or []),
            "suspects": list(act.get("suspects") or []),
            "trusts": list(act.get("trusts") or []),
        })
        self.emit(
            type=kind, audience=Audience.PUBLIC, actor=seat, text=text,
            payload={k: v for k, v in act.items() if k != "speech"},
        )

    def _handle_explode(self, seat: int, act: dict) -> None:
        """狼人自爆：亮身份、立刻出局、白天当场结束。没有遗言，警徽销毁。"""
        st = self.state
        p = st.players[seat]
        # 自爆前说的那句话仍然进公开记录，也要进发言档案 —— 那是他最后一次公开表态
        if act.get("speech") and act["speech"] != "（该玩家没有发言）":
            st.speech_log.append({
                "day": st.day, "phase": st.phase, "kind": "speech", "seat": seat,
                "text": act["speech"], "claim": None, "claim_detail": "",
                "claimed_check": None, "badge_flow": [], "suspects": [], "trusts": [],
            })
            self.emit(type="speech", audience=Audience.PUBLIC, actor=seat,
                      text=f"{p.name}：{act['speech']}")
        p.exploded = True
        p.revealed_role = Role.WEREWOLF
        badge_note = ""
        if p.is_sheriff or st.sheriff_seat == seat:
            p.is_sheriff = False
            st.sheriff_seat, st.sheriff_status = None, "destroyed"
            badge_note = "（自爆销毁警徽，本局不再有警长）"
        self.emit(
            type="explode", audience=Audience.PUBLIC, actor=seat, targets=[seat],
            text=f"💥 {seat}号自爆！亮明【狼人】身份并立刻出局。今天的发言和投票全部中止，"
                 f"直接进入黑夜。{badge_note}",
            payload={"seat": seat, "phase": st.phase},
        )
        st.explode_log.append({"day": st.day, "seat": seat, "phase": st.phase,
                               "phase_cn": i18n.phase_cn(st.phase)})
        self.kill(seat, when="explode", cause="exploded")

    # ---------------- 死亡与结算 ----------------

    def kill(self, seat: int, *, when: str, cause: str) -> None:
        p = self.state.players[seat]
        if not p.alive:
            return
        p.alive = False
        p.died_day = self.state.day
        p.died_when = when
        p.died_cause = cause
        if p.is_sheriff:
            p.is_sheriff = False  # 警徽处理在 badge_transfer 里
        self.state.death_record.append(
            {"day": self.state.day, "seat": seat, "when": when, "cause": cause}
        )
        self.emit(
            type="death", audience=Audience.GOD, targets=[seat],
            text=f"{seat}号（{p.role.cn}）死亡，原因：{i18n.cause_cn(cause)}",
            payload={"seat": seat, "cause": cause, "role": p.role.value},
        )

    def _handle_badge(self, seat: int) -> None:
        """出局者若是警长，移交或撕毁警徽。"""
        st = self.state
        if st.sheriff_seat != seat:
            return
        if not st.alive_seats():
            st.sheriff_seat, st.sheriff_status = None, "destroyed"
            return
        act = self.ask(seat, "badge_transfer")
        target = act["target"]
        if target is None or not st.players[target].alive:
            st.sheriff_seat, st.sheriff_status = None, "destroyed"
            self.emit(type="badge", audience=Audience.PUBLIC, actor=seat,
                      text=f"{seat}号撕毁了警徽，本局不再有警长。")
        else:
            st.sheriff_seat, st.sheriff_status = target, "elected"
            st.players[target].is_sheriff = True
            self.emit(type="badge", audience=Audience.PUBLIC, actor=seat, targets=[target],
                      text=f"{seat}号把警徽移交给了 {target}号。")

    def _release(self, seat: int, reason: str) -> None:
        """该座位再也不会被 ask() 到了 —— 先存会话，再销毁它的容器/Pod。"""
        if self.pool is not None and seat in self.pool:
            self.pool.release(seat, reason)

    def _after_death(self, seat: int, *, allow_last_words: bool, allow_hunter: bool) -> None:
        """出局后的连锁处理：遗言 → 警徽 → 猎人开枪。

        全部处理完之后才释放运行时 —— 死了不等于能立刻拆：
        被票出的还要留遗言、猎人还要开枪、警长还要移交警徽。
        """
        st = self.state
        p = st.players[seat]
        if allow_last_words:
            act = self.ask(seat, "last_words")
            self._record_public_speech(seat, act, kind="last_words")
        self._handle_badge(seat)
        if allow_hunter and p.role is Role.HUNTER and p.died_cause != "poisoned":
            self.emit(type="hunter_ready", audience=Audience.PUBLIC, actor=seat,
                      text=f"{seat}号翻开猎人身份牌，可以开枪。")
            act = self.ask(seat, "hunter_shoot")
            target = act["target"]
            if target is None:
                self.emit(type="hunter_shot", audience=Audience.PUBLIC, actor=seat,
                          text=f"{seat}号选择不开枪。")
            else:
                self.emit(type="hunter_shot", audience=Audience.PUBLIC, actor=seat, targets=[target],
                          text=f"{seat}号开枪带走了 {target}号。")
                self.kill(target, when="shot", cause="shot")
                self._after_death(target, allow_last_words=False, allow_hunter=False)
        # 到这里这名玩家的所有后续动作都处理完了，可以安全释放
        self._release(seat, p.died_cause or "dead")

    # ====================== 夜晚 ======================

    def run_night(self) -> None:
        st = self.state
        st.night_kill_target = None
        st.night_poison_target = None
        st.night_saved = False
        st.phase = "NIGHT"
        self.emit(type="phase", audience=Audience.PUBLIC, text=f"—— 第 {st.day} 夜 —— 天黑请闭眼。")

        self._night_wolves()
        self._night_witch()
        self._night_seer()
        self._night_hunter_notify()

    def _night_wolves(self) -> None:
        st = self.state
        wolves = st.alive_wolf_seats()
        if not wolves:
            return

        # --- 狼人频道讨论 ---
        st.phase = "NIGHT_WOLF_CHAT"
        self.emit(type="phase", audience=Audience.WOLVES,
                  text=f"狼人请睁眼。存活狼人：{wolves}。请讨论今晚的行动。")
        for _ in range(max(1, st.config.wolf_chat_rounds)):
            for seat in wolves:
                act = self.ask(seat, "wolf_chat")
                st.wolf_chat_log.append(
                    {"day": st.day, "seat": seat, "text": act["speech"],
                     "kill_suggestion": act["kill_suggestion"]}
                )
                if act.get("strategy_note"):
                    st.wolf_strategy_board["notes"] = act["strategy_note"]
                # 狼队分工：自己认领的写死，给队友的建议只在队友还没认领时生效
                assign = st.wolf_strategy_board.setdefault("assignments", {})
                for mate, pos in (act.get("position_plan") or {}).items():
                    assign.setdefault(str(mate), pos)
                if act.get("my_position"):
                    assign[str(seat)] = act["my_position"]
                sug = act["kill_suggestion"]
                self.emit(
                    type="wolf_chat", audience=Audience.WOLVES, actor=seat,
                    text=f"[狼人频道] {st.players[seat].name}：{act['speech']}"
                         + (f"（建议刀 {sug}号）" if sug else "")
                         + (f"（我打{A.WOLF_POSITIONS[act['my_position']].split(' ')[0]}）"
                            if act.get("my_position") else ""),
                    payload={"kill_suggestion": sug, "my_position": act.get("my_position"),
                             "position_plan": act.get("position_plan")},
                )

        # --- 击杀投票 ---
        st.phase = "NIGHT_WOLF_KILL"
        votes: dict[int, int | None] = {}
        for seat in wolves:
            votes[seat] = self.ask(seat, "wolf_kill")["target"]
        tally = Counter(v for v in votes.values() if v is not None)
        abstain = sum(1 for v in votes.values() if v is None)

        if not tally or abstain > sum(tally.values()):
            target, how = None, "empty_knife"
        else:
            top = max(tally.values())
            leading = sorted(s for s, c in tally.items() if c == top)
            if len(leading) == 1:
                target, how = leading[0], "majority"
            else:
                captain = wolves[0]  # 座位号最小的存活狼人拍板
                target = votes.get(captain) or leading[0]
                if target not in leading:
                    target = leading[0]
                how = f"captain_{captain}"

        st.night_kill_target = target
        st.wolf_kill_history.append(
            {"day": st.day, "votes": {str(k): v for k, v in votes.items()},
             "decided": target, "decided_by": how, "outcome": "pending", "extra_deaths": []}
        )
        self.emit(
            type="wolf_kill", audience=Audience.WOLVES, targets=[target] if target else [],
            text=f"[狼人频道] 投票结果：{ {k: v for k, v in votes.items()} }　→ "
                 + (f"今晚刀 {target}号。" if target else "今晚空刀。"),
            payload={"votes": votes, "target": target, "decided_by": how},
        )

    def _night_witch(self) -> None:
        st = self.state
        seat = st.seat_of_role(Role.WITCH)
        if seat is None or not st.players[seat].alive:
            return
        st.phase = "NIGHT_WITCH"
        tell = st.config.witch_knows_victim == "always" or st.day == 1
        victim = st.night_kill_target if tell else None
        self.emit(
            type="witch_info", audience=Audience.PRIVATE, visible_to=[seat],
            text=("上帝：女巫请睁眼。" + (
                f"今晚 {victim}号 倒牌，你要救吗？" if victim
                else ("今晚是平安夜，没有人被刀。" if tell else "今晚的刀口对你保密。")
            )),
            payload={"victim": victim},
        )
        act = self.ask(seat, "witch_action", {"victim": victim})
        p = st.players[seat]
        if act["heal"]:
            p.witch_has_antidote = False
            st.night_saved = True
            st.witch_potion_log.append({"day": st.day, "potion": "antidote", "target": victim})
            self.emit(type="witch_heal", audience=Audience.PRIVATE, visible_to=[seat],
                      targets=[victim] if victim else [],
                      text=f"上帝：你对 {victim}号 使用了解药。")
        if act["poison"] is not None:
            p.witch_has_poison = False
            st.night_poison_target = act["poison"]
            st.witch_potion_log.append({"day": st.day, "potion": "poison", "target": act["poison"]})
            self.emit(type="witch_poison", audience=Audience.PRIVATE, visible_to=[seat],
                      targets=[act["poison"]],
                      text=f"上帝：你对 {act['poison']}号 使用了毒药。")

    def _night_seer(self) -> None:
        st = self.state
        seat = st.seat_of_role(Role.SEER)
        if seat is None or not st.players[seat].alive:
            return
        st.phase = "NIGHT_SEER"
        self.emit(type="seer_wake", audience=Audience.PRIVATE, visible_to=[seat],
                  text="上帝：预言家请睁眼，请选择今晚要查验的玩家。")
        target = self.ask(seat, "seer_check")["target"]
        if target is None:
            return
        result = "WOLF" if st.is_wolf(target) else "GOOD"
        st.seer_checks.append({"day": st.day, "target": target, "result": result})
        self.emit(
            type="seer_result", audience=Audience.PRIVATE, visible_to=[seat], targets=[target],
            text=f"上帝：你查验了 {target}号，结果是【{'狼人' if result == 'WOLF' else '好人'}】。",
            payload={"target": target, "result": result},
        )

    def _night_hunter_notify(self) -> None:
        st = self.state
        seat = st.seat_of_role(Role.HUNTER)
        if seat is None or not st.players[seat].alive:
            return
        st.phase = "NIGHT_HUNTER"
        poisoned = st.night_poison_target == seat
        self.emit(
            type="hunter_status", audience=Audience.PRIVATE, visible_to=[seat],
            text="上帝：猎人请睁眼。" + ("你今晚不能开枪。" if poisoned else "你当前可以开枪。"),
            payload={"can_shoot": not poisoned},
        )

    # ====================== 天亮结算 ======================

    def announce_daybreak(self) -> None:
        """只宣布天亮，不公布死讯。

        第一天的警长竞选要在公布死讯【之前】进行 —— 竞选时全场（包括昨晚被刀的人
        自己）都还不知道谁死了，这是这个环节博弈的前提。
        """
        st = self.state
        st.phase = "DAWN"
        extra = ("首先进行警长竞选，竞选结束后再公布昨晚的情况。"
                 if st.day == 1 and st.config.sheriff else "")
        self.emit(type="daybreak", audience=Audience.PUBLIC,
                  text=f"—— 第 {st.day} 天 白天 —— 上帝：天亮了。{extra}")

    def run_dawn(self, *, allow_last_words: bool = True) -> bool:
        """公布死讯并处理首夜遗言。返回游戏是否继续。"""
        st = self.state
        st.phase = "DAWN"
        deaths: list[int] = []
        killed = st.night_kill_target
        if killed is not None and not st.night_saved:
            deaths.append(killed)
        poisoned = st.night_poison_target
        if poisoned is not None and poisoned not in deaths:
            deaths.append(poisoned)

        if st.wolf_kill_history and st.wolf_kill_history[-1]["day"] == st.day:
            rec = st.wolf_kill_history[-1]
            rec["outcome"] = (
                "saved_by_witch" if (killed is not None and st.night_saved)
                else ("died" if killed is not None else "empty_knife")
            )
            rec["extra_deaths"] = [d for d in deaths if d != killed]

        # 被毒优先于被刀：同时中刀和中毒时按"被毒"处理，猎人不能开枪
        for seat in sorted(deaths):
            self.kill(seat, when="night", cause="poisoned" if seat == poisoned else "killed")

        if deaths:
            self.emit(type="dawn", audience=Audience.PUBLIC, targets=sorted(deaths),
                      text=f"上帝：昨晚，{ '、'.join(f'{s}号' for s in sorted(deaths)) } 倒牌出局。")
        else:
            self.emit(type="dawn", audience=Audience.PUBLIC, text="上帝：昨晚是平安夜。")

        if st.check_winner():
            return False

        # 遗言：仅首夜死者有遗言（白天被自爆打断时没有遗言）
        if deaths and st.day == 1 and st.config.first_night_last_words and allow_last_words:
            st.phase = "LAST_WORDS"
            for seat in sorted(deaths):
                self._after_death(seat, allow_last_words=True, allow_hunter=True)
                if st.check_winner():
                    return False
        else:
            for seat in sorted(deaths):
                self._after_death(seat, allow_last_words=False, allow_hunter=True)
                if st.check_winner():
                    return False
        return True

    # ====================== 警长竞选 ======================

    def run_sheriff_election(self) -> None:
        st = self.state
        if not st.config.sheriff:
            st.sheriff_status = "none"
            return
        st.phase = "SHERIFF_SIGNUP"
        self.emit(type="phase", audience=Audience.PUBLIC, text="上帝：现在开始警长竞选，请要竞选的玩家举手。")

        alive = st.alive_seats()
        candidates = [s for s in alive if self.ask(s, "sheriff_signup")["run"]]
        self.emit(type="sheriff_signup", audience=Audience.PUBLIC, targets=candidates,
                  text=f"上帝：上警的玩家是 { '、'.join(f'{s}号' for s in candidates) or '无人上警' }。")

        if not candidates or len(candidates) == len(alive):
            st.sheriff_status = "lost"
            self.emit(type="sheriff_result", audience=Audience.PUBLIC,
                      text="上帝：" + ("无人上警" if not candidates else "全员上警") + "，警徽流失，本局没有警长。")
            return

        # 警上发言 + 退水
        st.phase = "SHERIFF_SPEECH"
        withdrawn: list[int] = []
        for seat in candidates:
            act = self.ask(seat, "sheriff_speech")
            if act.get("explode"):
                self._handle_explode(seat, act)
                st.sheriff_status = "lost"
                self.emit(type="sheriff_result", audience=Audience.PUBLIC,
                          text="上帝：警上有人自爆，警长竞选中止，本局没有警长。")
                raise DayInterrupted
            self._record_public_speech(seat, act, kind="sheriff_speech")
            if act.get("quit"):
                withdrawn.append(seat)
                self.emit(type="sheriff_quit", audience=Audience.PUBLIC, actor=seat,
                          text=f"{seat}号宣布退水，退出警长竞选。")
        running = [s for s in candidates if s not in withdrawn]
        if not running:
            st.sheriff_status = "lost"
            self.emit(type="sheriff_result", audience=Audience.PUBLIC,
                      text="上帝：所有候选人都退水了，警徽流失。")
            return
        if len(running) == 1:
            self._elect_sheriff(running[0])
            return

        voters = [s for s in alive if s not in candidates]
        winner = self._sheriff_vote_round(running, voters, rnd=1)
        if winner is None:
            st.phase = "SHERIFF_PK"
            self.emit(type="phase", audience=Audience.PUBLIC, text="上帝：警长竞选平票，平票玩家进行 PK 发言。")
            tied = self._last_tied
            for seat in tied:
                act = self.ask(seat, "sheriff_speech")
                if act.get("explode"):
                    self._handle_explode(seat, act)
                    st.sheriff_status = "lost"
                    raise DayInterrupted
                self._record_public_speech(seat, act, kind="sheriff_pk_speech")
            voters2 = [s for s in alive if s not in tied and s not in candidates]
            winner = self._sheriff_vote_round(tied, voters2, rnd=2)
        if winner is None:
            st.sheriff_status = "lost"
            self.emit(type="sheriff_result", audience=Audience.PUBLIC,
                      text="上帝：再次平票，警徽流失，本局没有警长。")
        else:
            self._elect_sheriff(winner)

    def _sheriff_vote_round(self, candidates: list[int], voters: list[int], rnd: int) -> int | None:
        st = self.state
        st.phase = "SHERIFF_VOTE"
        votes: dict[int, int | None] = {}
        for seat in voters:
            votes[seat] = self.ask(seat, "sheriff_vote", {"candidates": candidates})["target"]
        tally: dict[int, float] = defaultdict(float)
        for voter, target in votes.items():
            if target is not None:
                tally[target] += 1.0
        st.vote_history.append(
            {"day": st.day, "round": rnd, "type": "sheriff",
             "votes": {str(k): v for k, v in votes.items()},
             "tally": {str(k): v for k, v in tally.items()}, "result": None}
        )
        desc = "、".join(
            f"{v}号→{t}号" if t else f"{v}号弃票" for v, t in votes.items()
        ) or "无人投票"
        self.emit(type="sheriff_vote", audience=Audience.PUBLIC,
                  text=f"上帝：警长投票结果 —— {desc}。计票：{dict(tally) or '全部弃票'}",
                  payload={"votes": votes, "tally": dict(tally), "round": rnd})
        if not tally:
            self._last_tied = list(candidates)
            return None
        top = max(tally.values())
        leading = sorted(s for s, c in tally.items() if c == top)
        st.vote_history[-1]["result"] = leading[0] if len(leading) == 1 else None
        if len(leading) == 1:
            return leading[0]
        self._last_tied = leading
        return None

    def _elect_sheriff(self, seat: int) -> None:
        st = self.state
        st.sheriff_seat = seat
        st.sheriff_status = "elected"
        st.players[seat].is_sheriff = True
        self.emit(type="sheriff_result", audience=Audience.PUBLIC, targets=[seat],
                  text=f"上帝：{seat}号当选警长，拥有 1.5 票并决定每天的发言顺序。")

    # ====================== 白天 ======================

    def _compute_speech_order(self) -> list[int]:
        st = self.state
        alive = st.alive_seats()
        if not alive:
            return []
        n = len(st.seats)
        if st.sheriff_seat in alive:
            # 警长决定方向（这里用 rng 代表警长的选择；LLM 版可改为向警长索要动作）
            direction = st.rng.choice([1, -1])
            start = st.sheriff_seat
            order = []
            cur = start
            for _ in range(n):
                cur = (cur - 1 + direction) % n + 1
                if cur in alive and cur != st.sheriff_seat:
                    order.append(cur)
            order.append(st.sheriff_seat)  # 警长最后发言
            self.emit(
                type="speech_order", audience=Audience.PUBLIC,
                text=f"上帝：警长 {st.sheriff_seat}号 决定从{'下家' if direction == 1 else '上家'}开始发言，"
                     f"顺序为 { '→'.join(f'{s}号' for s in order) }。",
            )
            return order
        last_night_dead = [d["seat"] for d in st.death_record if d["day"] == st.day and d["when"] == "night"]
        start = (min(last_night_dead) % n) + 1 if last_night_dead else 1
        order = []
        cur = start
        for _ in range(n):
            if cur in alive:
                order.append(cur)
            cur = cur % n + 1
        self.emit(type="speech_order", audience=Audience.PUBLIC,
                  text=f"上帝：本轮发言顺序为 { '→'.join(f'{s}号' for s in order) }。")
        return order

    def run_day_speeches(self) -> None:
        st = self.state
        st.phase = "DAY_SPEECH"
        st.speech_order = self._compute_speech_order()
        self.emit(type="phase", audience=Audience.PUBLIC, text=f"—— 第 {st.day} 天 白天 —— 开始依次发言。")
        for i, seat in enumerate(st.speech_order):
            if not st.players[seat].alive:
                continue
            act = self.ask(seat, "speech", {
                "description": f"轮到你发言了，你是本轮第 {i + 1} / {len(st.speech_order)} 位发言者。"
            })
            if act.get("explode"):
                self._handle_explode(seat, act)
                raise DayInterrupted
            self._record_public_speech(seat, act)

    def run_day_vote(self) -> None:
        st = self.state
        st.phase = "DAY_VOTE"
        exiled = self._vote_round([s for s in st.alive_seats()], rnd=1)
        if exiled is None and getattr(self, "_last_tied", None):
            tied = self._last_tied
            if len(tied) < len(st.alive_seats()):
                st.phase = "DAY_VOTE_PK"
                self.emit(type="phase", audience=Audience.PUBLIC,
                          text=f"上帝：平票！{ '、'.join(f'{s}号' for s in tied) } 进入 PK，各发言一轮。")
                for seat in tied:
                    act = self.ask(seat, "speech", {"description": "你进入了 PK 台，这是你最后的辩解机会。"})
                    if act.get("explode"):
                        self._handle_explode(seat, act)
                        raise DayInterrupted
                    self._record_public_speech(seat, act, kind="pk_speech")
                st.phase = "DAY_VOTE"
                exiled = self._vote_round(
                    [s for s in st.alive_seats() if s not in tied], rnd=2, candidates=tied
                )
        if exiled is None:
            self.emit(type="exile", audience=Audience.PUBLIC, text="上帝：再次平票，今天是平安日，无人出局。")
            return

        p = st.players[exiled]
        if p.role is Role.IDIOT and not p.idiot_revealed:
            p.idiot_revealed = True
            p.can_vote = False
            p.revealed_role = Role.IDIOT
            if p.is_sheriff:
                p.is_sheriff = False
                st.sheriff_seat, st.sheriff_status = None, "destroyed"
            self.emit(type="idiot_reveal", audience=Audience.PUBLIC, actor=exiled,
                      text=f"上帝：{exiled}号翻开了【白痴】身份牌！他不会出局，但从此失去投票权，今天不再有人出局。")
            return

        self.emit(type="exile", audience=Audience.PUBLIC, targets=[exiled],
                  text=f"上帝：{exiled}号被投票放逐出局，请留遗言。")
        self.kill(exiled, when="vote", cause="exiled")
        self._after_death(exiled, allow_last_words=True, allow_hunter=True)

    def _vote_round(self, voters: list[int], rnd: int, candidates: list[int] | None = None) -> int | None:
        st = self.state
        votes: dict[int, int | None] = {}
        for seat in voters:
            if not st.players[seat].can_vote or not st.players[seat].alive:
                continue
            cands = candidates or [s for s in st.alive_seats() if s != seat]
            votes[seat] = self.ask(seat, "vote", {"candidates": cands})["target"]

        tally: dict[int, float] = defaultdict(float)
        for voter, target in votes.items():
            if target is not None:
                tally[target] += st.vote_weight(voter)
        desc = "、".join(f"{v}号→{t}号" if t else f"{v}号弃票" for v, t in votes.items()) or "无人投票"
        result = None
        if tally:
            top = max(tally.values())
            leading = sorted(s for s, c in tally.items() if c == top)
            result = leading[0] if len(leading) == 1 else None
            self._last_tied = leading if len(leading) > 1 else []
        else:
            self._last_tied = []
        st.vote_history.append(
            {"day": st.day, "round": rnd, "type": "exile",
             "votes": {str(k): v for k, v in votes.items()},
             "tally": {str(k): v for k, v in tally.items()}, "result": result}
        )
        self.emit(type="vote", audience=Audience.PUBLIC,
                  text=f"上帝：投票结果 —— {desc}。计票：{ {k: round(v, 1) for k, v in tally.items()} or '全部弃票' }",
                  payload={"votes": votes, "tally": dict(tally), "result": result, "round": rnd})
        return result

    # ====================== 主循环 ======================

    def run(self) -> GameState:
        st = self.state
        self._setup()
        while st.winner is None and st.day < st.config.max_days:
            st.day += 1
            self.run_night()
            self.announce_daybreak()

            # 第一天：先竞选警长，此时全场都还不知道昨晚谁死了
            interrupted = False
            if st.day == 1 and st.config.sheriff:
                try:
                    self.run_sheriff_election()
                except DayInterrupted:
                    # 警上有人自爆：竞选作废，白天到此为止。
                    # 但昨晚的死亡是既成事实，仍然要结算和公布。
                    interrupted = True

            # 警徽发完了，现在才公布昨晚的死讯
            if not self.run_dawn(allow_last_words=not interrupted):
                break
            if interrupted:
                continue  # 自爆已经终结这个白天，跳过发言和投票

            try:
                self.run_day_speeches()
                self.run_day_vote()
            except DayInterrupted:
                # 狼人自爆：白天到此为止，直接进入下一个黑夜
                pass
            if st.check_winner():
                break
        st.phase = "GAME_OVER"
        if st.winner is None:
            st.end_reason = f"达到最大天数 {st.config.max_days}，判平局"
        self.emit(
            type="game_over", audience=Audience.PUBLIC,
            text=f"游戏结束：{st.winner.cn if st.winner else '平局'}（{st.end_reason}）",
            payload={"winner": st.winner.value if st.winner else None, "reason": st.end_reason},
        )
        if self.pool is not None:
            self.pool.release_all("game_over")
        if self.store is not None and self.game_id:
            from .replay import result_summary

            self.store.finish_game(self.game_id, {**result_summary(st), "status": "finished"})
        return st

    def _setup(self) -> None:
        st = self.state
        st.phase = "SETUP"
        self.emit(
            type="setup", audience=Audience.GOD,
            text="发牌：" + "，".join(f"{s}号={st.players[s].role.cn}" for s in st.seats),
            payload={"roles": {str(s): st.players[s].role.value for s in st.seats}},
        )
        for seat in st.seats:
            p = st.players[seat]
            self.emit(
                type="deal", audience=Audience.PRIVATE, visible_to=[seat],
                text=f"上帝：你是 {p.name}，你的身份是【{p.role.cn}】。",
                payload={"role": p.role.value},
            )
        wolves = st.wolf_seats()
        self.emit(
            type="wolf_intro", audience=Audience.WOLVES, targets=wolves,
            text=f"上帝：狼人请睁眼，你们互相确认身份。狼队成员是 { '、'.join(f'{s}号' for s in wolves) }。",
            payload={"wolves": wolves},
        )


def play_game(config: GameConfig, agent_factory, **kw) -> GameState:
    """便捷入口：建局 → 造 agent → 跑完。agent_factory(seat, role) -> Agent"""
    state = new_game(config)
    agents = {s: agent_factory(s, state.players[s].role) for s in state.seats}
    return Engine(state, agents, **kw).run()
