"""SQLite 会话存储（默认）。

单文件、零依赖、可跨局查询、支持事务性追加。想换 Postgres 只要照着
SessionStore 再写一个实现，其余代码不用动。

线程安全：引擎跑在后台线程、HTTP 请求跑在另一批线程，所以连接用
check_same_thread=False 配一把锁；WAL 模式让读不阻塞写。
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    id            TEXT PRIMARY KEY,
    created_at    REAL NOT NULL,
    finished_at   REAL,
    status        TEXT NOT NULL,
    deployment    TEXT NOT NULL DEFAULT 'inprocess',
    config_json   TEXT NOT NULL,
    lineup_json   TEXT NOT NULL,
    winner        TEXT,
    end_reason    TEXT,
    days          INTEGER,
    result_json   TEXT
);

CREATE TABLE IF NOT EXISTS events (
    game_id   TEXT NOT NULL,
    seq       INTEGER NOT NULL,
    day       INTEGER NOT NULL,
    phase     TEXT NOT NULL,
    type      TEXT NOT NULL,
    audience  TEXT NOT NULL,
    actor     INTEGER,
    text      TEXT NOT NULL,
    body_json TEXT NOT NULL,
    PRIMARY KEY (game_id, seq)
);
CREATE INDEX IF NOT EXISTS idx_events_game ON events(game_id, seq);
CREATE INDEX IF NOT EXISTS idx_events_aud  ON events(game_id, audience);

CREATE TABLE IF NOT EXISTS turns (
    game_id     TEXT NOT NULL,
    turn        INTEGER NOT NULL,
    attempt     INTEGER NOT NULL,
    seat        INTEGER NOT NULL,
    role        TEXT,
    day         INTEGER,
    phase       TEXT,
    action_type TEXT NOT NULL,
    accepted    INTEGER NOT NULL,
    error       TEXT,
    thought     TEXT,
    action_json TEXT,
    latency_ms  INTEGER,
    created_at  REAL NOT NULL,
    PRIMARY KEY (game_id, turn, attempt)
);
CREATE INDEX IF NOT EXISTS idx_turns_game ON turns(game_id, turn);
CREATE INDEX IF NOT EXISTS idx_turns_seat ON turns(game_id, seat);

-- 每个座位的 agent 会话。容器被销毁之前必须先写进来。
CREATE TABLE IF NOT EXISTS agent_sessions (
    game_id       TEXT NOT NULL,
    seat          INTEGER NOT NULL,
    backend       TEXT,
    model         TEXT,
    role          TEXT,
    system_prompt TEXT,
    messages_json TEXT,
    usage_json    TEXT,
    memory_uri    TEXT,      -- agent 私有 memory 卷的位置（卷本身不在 DB 里）
    released_at   REAL,
    release_reason TEXT,
    PRIMARY KEY (game_id, seat)
);
"""


class SqliteStore:
    def __init__(self, path: str | Path = "runs/werewolf.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # ---------- 写 ----------
    def _exec(self, sql: str, params: tuple = ()) -> None:
        with self._lock:
            self._conn.execute(sql, params)
            self._conn.commit()

    def create_game(self, game_id, *, config, lineup, deployment="inprocess") -> None:
        self._exec(
            "INSERT OR REPLACE INTO games (id, created_at, status, deployment,"
            " config_json, lineup_json) VALUES (?,?,?,?,?,?)",
            (game_id, time.time(), "running", deployment,
             json.dumps(config, ensure_ascii=False),
             json.dumps(lineup, ensure_ascii=False)),
        )

    def append_event(self, game_id, event) -> None:
        self._exec(
            "INSERT OR REPLACE INTO events (game_id, seq, day, phase, type, audience,"
            " actor, text, body_json) VALUES (?,?,?,?,?,?,?,?,?)",
            (game_id, event["seq"], event["day"], event["phase"], event["type"],
             event["audience"], event.get("actor"), event["text"],
             json.dumps(event, ensure_ascii=False)),
        )

    def append_turn(self, game_id, turn) -> None:
        self._exec(
            "INSERT OR REPLACE INTO turns (game_id, turn, attempt, seat, role, day, phase,"
            " action_type, accepted, error, thought, action_json, latency_ms, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (game_id, turn["turn"], turn.get("attempt", 1), turn["seat"], turn.get("role"),
             turn.get("day"), turn.get("phase"), turn["action_type"],
             1 if turn.get("accepted") else 0, turn.get("error"), turn.get("thought"),
             json.dumps(turn.get("action"), ensure_ascii=False) if turn.get("action") else None,
             turn.get("latency_ms"), time.time()),
        )

    def save_agent_session(self, game_id, seat, session) -> None:
        self._exec(
            "INSERT OR REPLACE INTO agent_sessions (game_id, seat, backend, model, role,"
            " system_prompt, messages_json, usage_json, memory_uri, released_at, release_reason)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (game_id, seat, session.get("backend"), session.get("model"), session.get("role"),
             session.get("system_prompt"),
             json.dumps(session.get("messages") or [], ensure_ascii=False),
             json.dumps(session.get("usage") or {}, ensure_ascii=False),
             session.get("memory_uri"), session.get("released_at") or time.time(),
             session.get("release_reason")),
        )

    def finish_game(self, game_id, result) -> None:
        self._exec(
            "UPDATE games SET finished_at=?, status=?, winner=?, end_reason=?, days=?,"
            " result_json=? WHERE id=?",
            (time.time(), result.get("status", "finished"), result.get("winner"),
             result.get("reason"), result.get("days"),
             json.dumps(result, ensure_ascii=False), game_id),
        )

    # ---------- 读 ----------
    def _query(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def list_games(self, limit: int = 50) -> list[dict]:
        rows = self._query(
            "SELECT id, created_at, finished_at, status, deployment, winner, end_reason, days"
            " FROM games ORDER BY created_at DESC LIMIT ?", (limit,))
        return rows

    def load_game(self, game_id: str) -> dict | None:
        rows = self._query("SELECT * FROM games WHERE id=?", (game_id,))
        if not rows:
            return None
        g = rows[0]
        g["config"] = json.loads(g.pop("config_json"))
        g["lineup"] = json.loads(g.pop("lineup_json"))
        g["result"] = json.loads(g.pop("result_json")) if g.get("result_json") else None
        return g

    def load_events(self, game_id: str, since: int = 0) -> list[dict]:
        return [
            json.loads(r["body_json"]) for r in
            self._query("SELECT body_json FROM events WHERE game_id=? AND seq>? ORDER BY seq",
                        (game_id, since))
        ]

    def load_turns(self, game_id: str) -> list[dict]:
        out = []
        for r in self._query(
                "SELECT * FROM turns WHERE game_id=? ORDER BY turn, attempt", (game_id,)):
            r["accepted"] = bool(r["accepted"])
            r["action"] = json.loads(r.pop("action_json")) if r.get("action_json") else None
            out.append(r)
        return out

    def load_agent_sessions(self, game_id: str) -> list[dict]:
        out = []
        for r in self._query(
                "SELECT * FROM agent_sessions WHERE game_id=? ORDER BY seat", (game_id,)):
            r["messages"] = json.loads(r.pop("messages_json") or "[]")
            r["usage"] = json.loads(r.pop("usage_json") or "{}")
            out.append(r)
        return out

    def close(self) -> None:
        with self._lock:
            self._conn.close()
