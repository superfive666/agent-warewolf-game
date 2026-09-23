"""内置规则 bot：零依赖、毫秒级跑完一局。

它不是为了"玩得好"，而是为了：
  1. 让整套流程在没有 API key 的环境下也能完整跑起来；
  2. 给回归测试和信息隔离测试提供确定性的对局；
  3. 作为 LLM agent 的陪练/对照组。

每个 bot 只读自己的 PlayerView —— 和 LLM agent 走完全相同的信息通道。
"""
from __future__ import annotations

import random
from collections import defaultdict

from ..roles import Role
from ..views import PlayerView


class HeuristicAgent:
    def __init__(self, seat: int, role: Role, seed: int | None = None) -> None:
        self.seat = seat
        self.role = role
        self.name = f"heuristic-{seat}"
        self.rng = random.Random((seed or 0) * 100 + seat)
        self.believed_seer: int | None = None
        self.claimed_seer_already = False

    # ------------------------------------------------------------------
    def act(self, view: PlayerView, error: str | None = None) -> dict:
        at = view.legal_actions["action_type"]
        out = getattr(self, "_" + at)(view)
        out["private_thought"] = self._explain(view, at, out, error)
        return out

    # ------------------------------------------------------------------
    # 心路历程：把 bot 的打分过程翻译成人话，进复盘用
    # ------------------------------------------------------------------
    def _explain(self, view: PlayerView, at: str, out: dict, error: str | None) -> str:
        bits = []
        if error:
            bits.append(f"上一次动作被判非法（{error}），这次改。")
        idt = view.identity
        bits.append(f"我是 {idt['seat']}号{idt['role_cn']}。")

        score = self._suspicion(view)
        ranked = sorted(
            ((s, v) for s, v in score.items() if v > -50),
            key=lambda kv: (-kv[1], kv[0]),
        )[:3]
        if ranked:
            bits.append(
                "当前嫌疑排序：" + "、".join(f"{s}号({v:+.1f})" for s, v in ranked) + "。"
            )
        if view.is_wolf:
            wt = view.wolf_team
            bits.append(f"狼队还剩 {wt.intel['alive_wolf_count']} 人，好人 {wt.intel['alive_good_count']} 人。")
            if wt.intel["checks_on_us"]:
                bits.append(
                    "我方已被公开查杀：" + "、".join(
                        f"{c['target']}号(被{c['by']}号)" for c in wt.intel["checks_on_us"]
                    ) + "。"
                )
            if wt.intel["suspected_god_seats"]:
                bits.append(f"疑似神职：{wt.intel['suspected_god_seats']}，屠边优先照顾他们。")
        elif self.believed_seer is not None:
            bits.append(
                f"我选择相信 {self.believed_seer}号 是真预言家"
                + ("（就是我自己）。" if self.believed_seer == view.seat else "，跟着他的查杀走。")
            )
        else:
            bits.append("场上还没人起跳预言家，我没有硬信息，只能看发言和票型。")

        bits.append(self._explain_action(view, at, out))
        return "".join(bits)

    def _explain_action(self, view: PlayerView, at: str, out: dict) -> str:
        if at == "wolf_chat":
            return f"我建议今晚刀 {out['kill_suggestion']}号。"
        if at == "wolf_kill":
            return f"我投票刀 {out['target']}号。" if out["target"] else "我投空刀。"
        if at == "seer_check":
            return f"今晚验 {out['target']}号，他是目前我最想确认的人。"
        if at == "witch_action":
            parts = []
            parts.append("用解药救刀口。" if out["heal"] else "不用解药。")
            parts.append(f"毒 {out['poison']}号。" if out["poison"] else "不用毒药。")
            return "".join(parts)
        if at == "sheriff_signup":
            return "我决定上警。" if out["run"] else "我不上警。"
        if at in ("speech", "sheriff_speech", "last_words"):
            if out.get("explode"):
                return "局势太差了，我选择自爆打断白天，给队友争取一晚。"
            claim = out.get("claim")
            c = f"我公开跳{Role(claim).cn}。" if claim else "我不起跳。"
            if out.get("suspects"):
                c += f"我指认 {out['suspects']}。"
            return c
        if at == "vote":
            return f"我投 {out['target']}号。" if out["target"] else "我弃票。"
        if at == "sheriff_vote":
            return f"警长票投给 {out['target']}号。" if out["target"] else "警长票弃票。"
        if at == "hunter_shoot":
            return f"开枪带走 {out['target']}号。" if out["target"] else "我不开枪。"
        if at == "badge_transfer":
            return f"警徽交给 {out['target']}号。" if out["target"] else "我撕掉警徽。"
        return ""

    # ------------------------------------------------------------------
    def _should_explode(self, view: PlayerView) -> bool:
        """自爆判断：我马上要被票出去，而且自爆能给队友换一个晚上。"""
        if not view.is_wolf or not view.wolf_team:
            return False
        if "explode" not in view.legal_actions["schema"]:
            return False
        alive_mates = [s for s in view.wolf_team.alive_wolves if s != view.seat]
        if not alive_mates:
            return False  # 最后一只狼自爆等于直接输，不如赌投票
        ps = view.public_state
        alive = ps["alive_seats"]
        # 今天有多少人公开点了我的名
        pressure = 0
        for e in view.timeline:
            if e["day"] != ps["day"] or e["type"] not in ("speech", "sheriff_speech", "pk_speech"):
                continue
            if view.seat in (e.get("payload") or {}).get("suspects", []):
                pressure += 1
        # 被真预言家查杀也是极大压力
        checked = any(
            c["target"] == view.seat and c["result"] == "WOLF"
            for c in ps["public_check_claims"]
        )
        threshold = max(2, len(alive) // 3)
        if pressure < threshold and not (checked and pressure >= 1):
            return False
        return self.rng.random() < 0.45

    # ------------------------------------------------------------------
    # 局势判断（只用视角里的信息）
    # ------------------------------------------------------------------
    def _teammates(self, view: PlayerView) -> set[int]:
        if not view.is_wolf:
            return set()
        return set(view.identity["role_knowledge"]["teammates"]) | {view.seat}

    def _suspicion(self, view: PlayerView) -> dict[int, float]:
        """给每个存活玩家打一个"像狼"的分数。"""
        ps = view.public_state
        alive = [s for s in ps["alive_seats"] if s != view.seat]
        mates = self._teammates(view)
        score: dict[int, float] = {s: 0.0 for s in alive}

        claimed_seers = [
            int(s) for s, c in ps["public_claims"].items() if c.get("claim") == "SEER"
        ]

        if view.is_wolf:
            # 狼人：队友 0 分，优先怀疑（其实是"优先推"）起跳的神
            for s in alive:
                if s in mates:
                    score[s] = -99.0
                    continue
                claim = ps["public_claims"].get(str(s), {}).get("claim")
                if claim in ("SEER", "WITCH", "HUNTER"):
                    score[s] += 3.0
                if s in claimed_seers:
                    score[s] += 1.0
            # 被公开查杀的队友要被保，指认查杀他的人
            for c in ps["public_check_claims"]:
                if c["target"] in mates and c["result"] == "WOLF" and c["by"] in score:
                    score[c["by"]] += 4.0
        else:
            # 好人：相信一个预言家，跟他的查杀走
            self._update_believed_seer(view, claimed_seers)
            for c in ps["public_check_claims"]:
                if c["target"] not in score:
                    continue
                if c["by"] == self.believed_seer:
                    score[c["target"]] += 5.0 if c["result"] == "WOLF" else -4.0
                else:
                    score[c["target"]] += 0.5 if c["result"] == "WOLF" else 0.0
            # 冒充预言家的那个（我不信的那个）嫌疑很大
            for s in claimed_seers:
                if s in score and s != self.believed_seer:
                    score[s] += 4.0
            # 我自己是神但被查杀了 → 查杀我的人是狼
            for c in ps["public_check_claims"]:
                if c["target"] == view.seat and c["result"] == "WOLF" and c["by"] in score:
                    score[c["by"]] += 6.0

        if not view.is_wolf and self.believed_seer is not None:
            # 站边分析：投票行为比发言更难伪装
            golden = {
                c["target"] for c in ps["public_check_claims"]
                if c["by"] == self.believed_seer and c["result"] == "GOOD"
            } | {self.believed_seer}
            checked_wolves = {
                c["target"] for c in ps["public_check_claims"]
                if c["by"] == self.believed_seer and c["result"] == "WOLF"
            }
            for rnd in ps["vote_history"]:
                if rnd["type"] != "exile":
                    continue
                for voter, target in rnd["votes"].items():
                    v = int(voter)
                    if v not in score or v == view.seat or target is None:
                        continue
                    if target in golden:
                        score[v] += 1.5      # 投我信的预言家/金水 → 很可能是狼
                    elif target in checked_wolves:
                        score[v] -= 1.0      # 跟着票查杀 → 偏好人

        # 大家公开表达的怀疑，作为弱信号
        for e in view.timeline:
            if e["type"] in ("speech", "sheriff_speech", "last_words", "pk_speech"):
                for t in (e.get("payload") or {}).get("suspects", []):
                    if t in score and e["actor"] != view.seat:
                        score[t] += 0.3
        # 划水的（一直没被人怀疑也没怀疑别人的）微弱加分，避免完全无脑
        for s in score:
            score[s] += self.rng.random() * 0.2
        return score

    def _update_believed_seer(self, view: PlayerView, claimed_seers: list[int]) -> None:
        """好人选择相信哪个起跳的预言家。"""
        if view.role is Role.SEER:
            self.believed_seer = view.seat
            return
        if not claimed_seers:
            self.believed_seer = None
            return
        ps = view.public_state
        # 查杀过我的一定是假预言家 —— 我自己知道我不是狼
        liars = {
            c["by"] for c in ps["public_check_claims"]
            if c["target"] == view.seat and c["result"] == "WOLF"
        }
        candidates = [s for s in claimed_seers if s not in liars] or claimed_seers
        if self.believed_seer in candidates:
            return
        # 其余按"谁先起跳"排（真预言家通常首日就跳），死了也继续信他的验人结果
        self.believed_seer = sorted(
            candidates,
            key=lambda s: (ps["public_claims"][str(s)].get("day", 99), s),
        )[0]

    def _top_suspect(self, view: PlayerView, exclude: set[int] | None = None) -> int | None:
        score = self._suspicion(view)
        exclude = exclude or set()
        pool = {s: v for s, v in score.items() if s not in exclude and v > -50}
        if not pool:
            return None
        return max(pool, key=lambda s: (pool[s], -s))

    # ------------------------------------------------------------------
    # 夜晚
    # ------------------------------------------------------------------
    def _wolf_chat(self, view: PlayerView) -> dict:
        wt = view.wolf_team
        target = self._pick_kill_target(view)
        board = wt.strategy_board if wt else {}
        gods = (wt.intel["suspected_god_seats"] if wt else []) or []
        if gods:
            reason = f"{gods[0]}号公开跳了神，优先屠边"
        else:
            reason = "场上还没人起跳，先刀一个位置好的"
        return {
            "speech": f"我建议今晚刀 {target}号 —— {reason}。白天我走好人路线，别互相踩。",
            "kill_suggestion": target,
            "strategy_note": board.get("notes") or f"优先屠神，当前目标 {target}号",
        }

    def _pick_kill_target(self, view: PlayerView) -> int | None:
        wt = view.wolf_team
        mates = self._teammates(view)
        alive_goods = [s for s in view.public_state["alive_seats"] if s not in mates]
        if not alive_goods:
            return None
        if wt:
            # 优先杀公开起跳的神（屠边最快），且不杀自己人悍跳的那张牌
            for s in wt.intel["suspected_god_seats"]:
                if s in alive_goods:
                    return s
            # 队友刚被谁查杀，就刀谁
            for c in reversed(wt.intel["checks_on_us"]):
                if c["by"] in alive_goods:
                    return c["by"]
        return self.rng.choice(alive_goods)

    def _wolf_kill(self, view: PlayerView) -> dict:
        wt = view.wolf_team
        options = view.legal_actions["schema"]["target"]["options"]
        # 跟随狼队频道里今晚出现最多的建议
        suggestions = [
            c["kill_suggestion"]
            for c in (wt.chat_log if wt else [])
            if c["day"] == view.public_state["day"] and c["kill_suggestion"] in options
        ]
        if suggestions:
            counts = defaultdict(int)
            for s in suggestions:
                counts[s] += 1
            return {"target": max(counts, key=lambda s: (counts[s], -s))}
        t = self._pick_kill_target(view)
        return {"target": t if t in options else None}

    def _witch_action(self, view: PlayerView) -> dict:
        sch = view.legal_actions["schema"]
        rk = view.identity["role_knowledge"]
        day = view.public_state["day"]
        can_heal = True in sch["heal"]["options"]
        heal = bool(can_heal and rk["has_antidote"] and day == 1)

        poison = None
        if rk["has_poison"] and not heal and day >= 2:
            # 只毒"被我信的预言家公开查杀"的人，避免瞎毒好人
            believed = None
            claimed = [int(s) for s, c in view.public_state["public_claims"].items()
                       if c.get("claim") == "SEER"]
            if claimed:
                believed = sorted(
                    claimed,
                    key=lambda s: (view.public_state["public_claims"][str(s)].get("day", 99), s),
                )[0]
            for c in view.public_state["public_check_claims"]:
                if (
                    c["by"] == believed
                    and c["result"] == "WOLF"
                    and c["target"] in sch["poison"]["options"]
                ):
                    poison = c["target"]
                    break
        return {"heal": heal, "poison": poison}

    def _seer_check(self, view: PlayerView) -> dict:
        options = view.legal_actions["schema"]["target"]["options"]
        if not options:
            return {"target": None}
        # 优先验"还没被验过、且当前嫌疑最高"的人
        score = self._suspicion(view)
        ranked = sorted(options, key=lambda s: (-score.get(s, 0.0), s))
        return {"target": ranked[0]}

    # ------------------------------------------------------------------
    # 警长竞选
    # ------------------------------------------------------------------
    def _sheriff_signup(self, view: PlayerView) -> dict:
        if view.role is Role.SEER:
            return {"run": True, "reason": "预言家必须上警拿警徽"}
        if view.is_wolf:
            # 一名狼负责悍跳（座位号最小的存活狼），其余按概率上警做陪跑
            mates = sorted(view.wolf_team.alive_wolves) if view.wolf_team else []
            if mates and view.seat == mates[0]:
                return {"run": True, "reason": "我来悍跳预言家"}
            return {"run": self.rng.random() < 0.4, "reason": "陪跑混淆视线"}
        if view.role in (Role.WITCH, Role.HUNTER):
            return {"run": self.rng.random() < 0.3, "reason": "神职谨慎上警"}
        return {"run": self.rng.random() < 0.35, "reason": "试试"}

    def _sheriff_speech(self, view: PlayerView) -> dict:
        out = self._speech(view)
        out["quit"] = False
        return out

    def _sheriff_vote(self, view: PlayerView) -> dict:
        cands = view.legal_actions["schema"]["target"]["options"]
        cands = [c for c in cands if c is not None]
        if not cands:
            return {"target": None}
        score = self._suspicion(view)
        # 投给最不像狼的候选人
        return {"target": min(cands, key=lambda s: (score.get(s, 0.0), s))}

    def _badge_transfer(self, view: PlayerView) -> dict:
        opts = [o for o in view.legal_actions["schema"]["target"]["options"] if o is not None]
        if not opts:
            return {"target": None, "reason": ""}
        score = self._suspicion(view)
        if view.is_wolf:
            mates = [s for s in self._teammates(view) if s in opts]
            if mates:
                return {"target": mates[0], "reason": "给队友"}
        return {"target": min(opts, key=lambda s: (score.get(s, 0.0), s)), "reason": "交给我最信的人"}

    # ------------------------------------------------------------------
    # 白天
    # ------------------------------------------------------------------
    def _speech(self, view: PlayerView) -> dict:
        ps = view.public_state
        score = self._suspicion(view)
        suspect = self._top_suspect(view)
        trust = min(score, key=lambda s: (score[s], s)) if score else None

        claim = None
        claim_detail = ""
        claimed_check = None
        rk = view.identity["role_knowledge"]

        if view.role is Role.SEER and rk["checks"]:
            last = rk["checks"][-1]
            claim, self.claimed_seer_already = "SEER", True
            claim_detail = "；".join(
                f"第{c['day']}夜验{c['target']}号={'查杀' if c['result'] == 'WOLF' else '金水'}"
                for c in rk["checks"]
            )
            claimed_check = {"target": last["target"], "result": last["result"]}
            text = (
                f"我是预言家。{claim_detail}。"
                f"今天请归票 {last['target'] if last['result'] == 'WOLF' else suspect}号。"
            )
            if last["result"] == "WOLF":
                suspect = last["target"]
        elif view.is_wolf:
            mates = sorted(view.wolf_team.alive_wolves) if view.wolf_team else []
            already_faked = view.wolf_team.intel["our_claimed_gods"] if view.wolf_team else []
            if mates and view.seat == mates[0] and not already_faked and ps["day"] <= 1:
                # 悍跳预言家：给一个好人发查杀
                fake_target = suspect or (
                    [s for s in ps["alive_seats"] if s not in self._teammates(view)] or [None]
                )[0]
                claim = "SEER"
                claim_detail = f"第1夜验{fake_target}号=查杀"
                claimed_check = {"target": fake_target, "result": "WOLF"}
                text = f"我是预言家，昨晚验的 {fake_target}号 是查杀，今天必须走掉他。"
                suspect = fake_target
            else:
                claim = "VILLAGER"
                text = f"我是个普通村民。听下来 {suspect}号 的发言最有问题，我站边票他。"
        elif view.role is Role.WITCH and rk["potion_log"] and ps["day"] >= 2:
            claim = "WITCH"
            claim_detail = "；".join(
                f"第{x['day']}夜{'解药救' if x['potion'] == 'antidote' else '毒'}{x['target']}号"
                for x in rk["potion_log"]
            )
            text = f"我是女巫，{claim_detail}。我怀疑 {suspect}号。"
        else:
            text = f"我是好人。目前我最怀疑 {suspect}号，最信任 {trust}号。"

        if self._should_explode(view):
            mates = [s for s in view.wolf_team.alive_wolves if s != view.seat]
            return {
                "speech": f"不用投了，我自爆。{mates[0] if mates else ''}号你们继续，今天到此为止。",
                "claim": "WEREWOLF",
                "claim_detail": "自爆",
                "claimed_check": None,
                "suspects": [],
                "trusts": [],
                "explode": True,
            }

        return {
            "speech": text,
            "claim": claim,
            "claim_detail": claim_detail,
            "claimed_check": claimed_check,
            "suspects": [suspect] if suspect else [],
            "trusts": [trust] if trust and trust != suspect else [],
            "explode": False,
        }

    def _vote(self, view: PlayerView) -> dict:
        cands = [c for c in view.legal_actions["schema"]["target"]["options"] if c is not None]
        if not cands:
            return {"target": None, "reason": "没有可投的目标"}
        score = self._suspicion(view)
        pool = {s: score.get(s, 0.0) for s in cands}
        if view.is_wolf:
            mates = self._teammates(view)
            pool = {s: v for s, v in pool.items() if s not in mates} or pool
        target = max(pool, key=lambda s: (pool[s], -s))
        return {"target": target, "reason": f"我认为 {target}号 嫌疑最大"}

    def _last_words(self, view: PlayerView) -> dict:
        out = self._speech(view)
        out.pop("trusts", None)
        out["speech"] = "（遗言）" + out["speech"]
        return out

    def _hunter_shoot(self, view: PlayerView) -> dict:
        t = self._top_suspect(view)
        opts = [o for o in view.legal_actions["schema"]["target"]["options"] if o is not None]
        return {"target": t if t in opts else (opts[0] if opts else None)}
