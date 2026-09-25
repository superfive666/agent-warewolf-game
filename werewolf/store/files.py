"""文件系统会话存储（append-only JSONL）。

不想上数据库时用这个。同样是**边跑边写**：每条事件、每次决策立刻 append，
所以中途崩了也只丢最后一条。代价是跨局查询只能自己扫目录。
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path


class FileStore:
    def __init__(self, root: str | Path = "runs") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _dir(self, game_id: str) -> Path:
        d = self.root / game_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _append(self, game_id: str, name: str, obj: dict) -> None:
        with self._lock:
            with (self._dir(game_id) / name).open("a", encoding="utf-8") as f:
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")
                f.flush()

    def _write(self, game_id: str, name: str, obj) -> None:
        with self._lock:
            (self._dir(game_id) / name).write_text(
                json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read(self, game_id: str, name: str):
        p = self.root / game_id / name
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None

    def _read_lines(self, game_id: str, name: str) -> list[dict]:
        p = self.root / game_id / name
        if not p.is_file():
            return []
        return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]

    # ---------- 写 ----------
    def create_game(self, game_id, *, config, lineup, deployment="inprocess") -> None:
        self._write(game_id, "game.json", {
            "id": game_id, "created_at": time.time(), "status": "running",
            "deployment": deployment, "config": config, "lineup": lineup,
        })

    def append_event(self, game_id, event) -> None:
        self._append(game_id, "events.jsonl", event)

    def append_turn(self, game_id, turn) -> None:
        self._append(game_id, "turns.jsonl", {**turn, "created_at": time.time()})

    def save_agent_session(self, game_id, seat, session) -> None:
        d = self._dir(game_id) / "sessions"
        d.mkdir(exist_ok=True)
        with self._lock:
            (d / f"seat_{seat:02d}.json").write_text(
                json.dumps({**session, "seat": seat,
                            "released_at": session.get("released_at") or time.time()},
                           ensure_ascii=False, indent=2), encoding="utf-8")

    def finish_game(self, game_id, result) -> None:
        g = self._read(game_id, "game.json") or {"id": game_id}
        g.update(status=result.get("status", "finished"), finished_at=time.time(),
                 winner=result.get("winner"), end_reason=result.get("reason"),
                 days=result.get("days"), result=result)
        self._write(game_id, "game.json", g)

    # ---------- 读 ----------
    def list_games(self, limit: int = 50) -> list[dict]:
        out = []
        for d in self.root.iterdir():
            if d.is_dir() and (d / "game.json").is_file():
                g = self._read(d.name, "game.json")
                out.append({k: g.get(k) for k in
                            ("id", "created_at", "finished_at", "status",
                             "deployment", "winner", "end_reason", "days")})
        return sorted(out, key=lambda g: g.get("created_at") or 0, reverse=True)[:limit]

    def load_game(self, game_id): return self._read(game_id, "game.json")

    def load_events(self, game_id, since: int = 0):
        return [e for e in self._read_lines(game_id, "events.jsonl") if e["seq"] > since]

    def load_turns(self, game_id): return self._read_lines(game_id, "turns.jsonl")

    def load_agent_sessions(self, game_id):
        d = self.root / game_id / "sessions"
        if not d.is_dir():
            return []
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("seat_*.json"))]

    def close(self) -> None:
        pass
