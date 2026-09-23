"""Agent 接口。引擎只依赖这一个方法。"""
from __future__ import annotations

from typing import Protocol

from ..views import PlayerView


class Agent(Protocol):
    name: str

    def act(self, view: PlayerView, error: str | None = None) -> dict:
        """根据视角返回一个动作 dict。

        :param view: 该座位的个人视角（狼人会附带狼队视角）
        :param error: 上一次动作被引擎判为非法时的错误信息，用于自我修正
        """
        ...
