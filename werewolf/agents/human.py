"""真人玩家座位。对应 docs/03-技术设计.md「真人玩家座位」。

对引擎来说真人和 agent 没有区别：都只是一个 ``act(view)``。区别在于 ``act`` 里没有模型，
而是把视角挂成一条「待办」，阻塞等浏览器那头的人提交动作。

    引擎线程：act(view) ──挂待办──► 等待 ──拿到动作──► 返回给引擎校验
    HTTP 线程：pending() 读待办；submit() 交动作；cancel() 中止对局时唤醒引擎线程
"""
from __future__ import annotations

import threading

from ..roles import Role
from ..views import PlayerView

#: 真人的迭代上限单独放宽：人会手滑，不能三次填错就被系统代打
HUMAN_MAX_ITERATIONS = 10


class HumanCancelled(BaseException):
    """对局被中止时，从阻塞中的 ``act()`` 里抛出。

    继承 BaseException 而不是 Exception：引擎会把 agent 抛的 Exception 当成「后端出错」
    记一笔再重试，而中止对局必须一路冲出引擎。
    """


class HumanNotWaiting(RuntimeError):
    """真人提交了动作，但此刻并没有在等他（不是他的回合，或者待办已经过期）。"""


class HumanAgent:
    provider = "human"
    max_iterations = HUMAN_MAX_ITERATIONS

    def __init__(self, seat: int, role: Role) -> None:
        self.seat = seat
        self.role = role
        self.name = f"真人玩家-{seat}"
        self._cond = threading.Condition()
        self._request_id = 0
        self._pending: dict | None = None
        self._answer: dict | None = None
        self._cancelled = False

    # ---------------- 引擎线程 ----------------
    def act(self, view: PlayerView, error: str | None = None) -> dict:
        with self._cond:
            if self._cancelled:
                raise HumanCancelled
            self._request_id += 1
            rid = self._request_id
            legal = view.legal_actions or {}
            self._pending = {
                "request_id": rid,
                "action_type": legal.get("action_type"),
                "legal_actions": legal,
                "error": error,
            }
            self._answer = None
            # 不限时：人要想多久就想多久。中止对局时 cancel() 会把这里唤醒
            self._cond.wait_for(lambda: self._answer is not None or self._cancelled)
            self._pending = None
            if self._cancelled:
                raise HumanCancelled
            answer, self._answer = self._answer, None
            return answer

    # ---------------- HTTP 线程 ----------------
    def pending(self) -> dict | None:
        """当前待办（副本）；不是他的回合时为 None。"""
        with self._cond:
            return dict(self._pending) if self._pending else None

    def submit(self, request_id: int, action: dict) -> None:
        if not isinstance(action, dict):
            raise ValueError("动作必须是一个 JSON 对象")
        with self._cond:
            if self._pending is None:
                raise HumanNotWaiting("现在不是你的回合")
            if int(request_id) != self._pending["request_id"]:
                raise HumanNotWaiting("这条待办已经过期，请刷新后重新提交")
            # 心路历程只属于 agent；真人的动作里不接受这个字段，免得混进上帝日志
            self._answer = {k: v for k, v in action.items() if k != "private_thought"}
            self._pending = None
            self._cond.notify_all()

    def cancel(self) -> None:
        with self._cond:
            self._cancelled = True
            self._cond.notify_all()
