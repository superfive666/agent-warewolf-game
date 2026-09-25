"""事件与可见性模型 —— 信息隔离的全部实现都在这里。

对应 docs/03-技术设计.md §3。设计要点：一局游戏就是一条只追加的事件流，
每条事件带一个 ``audience`` 标签；某个座位的"视角"就是这条流按 ``audience``
过滤后的子序列。过滤逻辑只有 4 行，泄密只可能来自标错 audience，
因此 tests/test_visibility.py 对全部事件做了穷举断言。
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum


class Audience(str, Enum):
    #: 所有 12 名玩家（含已出局者）都能看到
    PUBLIC = "public"
    #: 所有狼人（含已出局的狼人）都能看到
    WOLVES = "wolves"
    #: 只有 visible_to 里列出的座位能看到
    PRIVATE = "private"
    #: 谁都看不到，只进上帝日志和复盘
    GOD = "god"


@dataclass
class Event:
    seq: int
    day: int
    phase: str
    type: str
    audience: Audience
    text: str
    actor: int | None = None
    targets: list[int] = field(default_factory=list)
    visible_to: list[int] = field(default_factory=list)
    payload: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        from .i18n import audience_cn_of, phase_cn

        d = asdict(self)
        d["audience"] = self.audience.value
        # 数据模型保留英文标识符（好查询），同时带一份中文给所有展示端用
        d["phase_cn"] = phase_cn(self.phase)
        d["audience_cn"] = audience_cn_of(self.audience.value)
        return d

    def as_view_entry(self) -> dict:
        """渲染进玩家视角 timeline 的形态。

        payload 一并带上是安全的：可见性在事件层面已经过滤完毕，
        能看到这条事件的人本来就有权看到它的全部内容（GOD 级事件谁也看不到）。
        """
        from .i18n import phase_cn

        return {
            "seq": self.seq,
            "day": self.day,
            "phase": self.phase,
            "phase_cn": phase_cn(self.phase),
            "type": self.type,
            "vis": self.audience.value,
            "actor": self.actor,
            "text": self.text,
            "payload": self.payload,
        }


def visible_to_seat(event: Event, seat: int, is_wolf: bool) -> bool:
    """某个座位能否看到某条事件。这 4 行就是整个信息隔离模型。"""
    if event.audience is Audience.PUBLIC:
        return True
    if event.audience is Audience.WOLVES:
        return is_wolf
    if event.audience is Audience.PRIVATE:
        return seat in event.visible_to
    return False  # Audience.GOD


class EventLog:
    """只追加的事件流。"""

    def __init__(self) -> None:
        self._events: list[Event] = []

    def __len__(self) -> int:
        return len(self._events)

    def __iter__(self):
        return iter(self._events)

    @property
    def next_seq(self) -> int:
        return len(self._events) + 1

    def append(
        self,
        *,
        day: int,
        phase: str,
        type: str,
        audience: Audience,
        text: str,
        actor: int | None = None,
        targets: list[int] | None = None,
        visible_to: list[int] | None = None,
        payload: dict | None = None,
    ) -> Event:
        event = Event(
            seq=self.next_seq,
            day=day,
            phase=phase,
            type=type,
            audience=audience,
            text=text,
            actor=actor,
            targets=list(targets or []),
            visible_to=sorted(visible_to or []),
            payload=dict(payload or {}),
        )
        self._events.append(event)
        return event

    def visible(self, seat: int, is_wolf: bool, since_seq: int = 0) -> list[Event]:
        """某个座位可见的事件，可从 since_seq 之后开始取增量。"""
        return [
            e
            for e in self._events
            if e.seq > since_seq and visible_to_seat(e, seat, is_wolf)
        ]

    def of_audience(self, audience: Audience) -> list[Event]:
        return [e for e in self._events if e.audience is audience]

    def to_jsonl(self) -> str:
        return "\n".join(
            json.dumps(e.as_dict(), ensure_ascii=False) for e in self._events
        )
