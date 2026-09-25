"""会话存储。默认 SQLite，可换文件系统或自己实现 SessionStore。"""
from __future__ import annotations

from .base import SessionStore  # noqa: F401
from .files import FileStore  # noqa: F401
from .sqlite import SqliteStore  # noqa: F401


def open_store(uri: str = "sqlite:runs/werewolf.db") -> SessionStore:
    """按 URI 打开存储。

      sqlite:runs/werewolf.db   单文件数据库（默认，可跨局查询）
      files:runs                append-only JSONL 目录
      none:                     不持久化（只跑一次、不复盘时用）
    """
    scheme, _, rest = uri.partition(":")
    if scheme == "sqlite":
        return SqliteStore(rest or "runs/werewolf.db")
    if scheme == "files":
        return FileStore(rest or "runs")
    if scheme == "none":
        return NullStore()
    raise ValueError(f"不认识的存储 URI：{uri!r}（支持 sqlite: / files: / none:）")


class NullStore:
    """什么都不存。用于测试和一次性跑批。"""

    def create_game(self, *a, **k): pass
    def append_event(self, *a, **k): pass
    def append_turn(self, *a, **k): pass
    def save_agent_session(self, *a, **k): pass
    def finish_game(self, *a, **k): pass
    def list_games(self, limit=50): return []
    def load_game(self, game_id): return None
    def load_events(self, game_id, since=0): return []
    def load_turns(self, game_id): return []
    def load_agent_sessions(self, game_id): return []
    def close(self): pass


__all__ = ["SessionStore", "SqliteStore", "FileStore", "NullStore", "open_store"]
