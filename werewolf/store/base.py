"""会话存储接口。

设计约束来自容器化部署：**玩家离场就销毁容器，但会话必须留下来复盘**。
所以有两条硬规则：

  1. **边跑边写**：每一轮决策结束就落库，不能等整局跑完。
     否则进程崩了、容器被杀了，这一局就什么都不剩。
  2. **销毁前先抓**：容器被拆掉之前，必须先把它里面的会话
     （system prompt + 完整对话历史 + token 用量）取出来存好。

agent 自己写的私有 memory 文件不走这里 —— 那是任意文件，挂在
生命周期长于容器的卷上（docker named volume / k8s PVC），这里只记它的 URI。
"""
from __future__ import annotations

from typing import Protocol


class SessionStore(Protocol):
    """一局游戏的全部可复盘数据。实现必须是线程安全的（引擎跑在后台线程里）。"""

    def create_game(self, game_id: str, *, config: dict, lineup: list[dict],
                    deployment: str = "inprocess") -> None: ...

    def append_event(self, game_id: str, event: dict) -> None:
        """追加一条事件（含 GOD 级）。引擎每 emit 一条就调一次。"""

    def append_turn(self, game_id: str, turn: dict) -> None:
        """追加一次决策记录：谁、做什么、想了什么、动作是否合法。"""

    def save_agent_session(self, game_id: str, seat: int, session: dict) -> None:
        """保存某个座位的 agent 会话。**销毁它的容器之前必须先调这个。**"""

    def finish_game(self, game_id: str, result: dict) -> None: ...

    # ---------- 读 ----------
    def list_games(self, limit: int = 50) -> list[dict]: ...
    def load_game(self, game_id: str) -> dict | None: ...
    def load_events(self, game_id: str, since: int = 0) -> list[dict]: ...
    def load_turns(self, game_id: str) -> list[dict]: ...
    def load_agent_sessions(self, game_id: str) -> list[dict]: ...
    def close(self) -> None: ...
