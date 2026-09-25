"""沙箱 Web 服务：配置 → 开局 → 自动跑 → 复盘。只用标准库，不需要任何前端构建。

  python3 run_server.py            # 然后打开 http://127.0.0.1:8000
"""
from __future__ import annotations

import json
import mimetypes
import os
import threading
import time
import traceback
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import i18n
from .events import Audience
from .lineup import AVAILABLE_BACKENDS, AVAILABLE_MODELS, EFFORT_LEVELS, Lineup
from .replay import (SPEECH_EVENT_TYPES, build_timeline, players_from_events,
                     render_replay, render_stored_replay, result_summary,
                     thoughts_from_events, thoughts_from_turns)
from .roles import BOARDS, Faction, board_summary
from .runtime import DEPLOYMENTS
from .session import GameSession
from .state import GameConfig
from .store import open_store
from .views import build_all_views

#: 全局会话存储。所有对局都往这里写，重启后还能复盘。
STORE_URI = os.environ.get("WEREWOLF_STORE", "sqlite:runs/werewolf.db")
DEFAULT_DEPLOYMENT = os.environ.get("WEREWOLF_DEPLOYMENT", "inprocess")
AGENT_IMAGE = os.environ.get("WEREWOLF_AGENT_IMAGE", "werewolf-agent:latest")
STORE = open_store(STORE_URI)

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


class GameRunner:
    """一局游戏 = 一个后台线程。前端靠轮询拿增量事件。"""

    def __init__(self, config: GameConfig, lineup: Lineup,
                 deployment: str = "inprocess") -> None:
        self.id = uuid.uuid4().hex[:12]
        self.config = config
        self.lineup = lineup
        self.deployment = deployment
        self.session = GameSession(
            config, lineup, deployment=deployment, store=STORE,
            game_id=self.id, image=AGENT_IMAGE,
        )
        self.state = self.session.state
        self.status = "pending"  # pending | running | finished | failed | stopped
        self.error: str | None = None
        self._t0 = time.time()
        self._t1: float | None = None
        self.created_at = _iso(self._t0)
        self.current: dict = {"phase": "SETUP", "day": 0, "seat": None, "action_type": None}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._events: list[dict] = []

    # ---------------- 生命周期 ----------------
    def start(self) -> None:
        self.status = "running"
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        try:
            self.session.run(on_event=self._on_event, view_recorder=self._on_view)
            self.status = "stopped" if self._stop.is_set() else "finished"
        except _Stopped:
            self.status = "stopped"
        except Exception:
            self.status = "failed"
            self.error = traceback.format_exc()
        finally:
            self._t1 = time.time()

    @property
    def finished_at(self) -> str | None:
        return _iso(self._t1) if self._t1 else None

    @property
    def duration_s(self) -> float:
        return round((self._t1 or time.time()) - self._t0, 3)

    def speech_progress(self) -> dict | None:
        """发言阶段的进度：{order: [座位], done: 已发言人数, total}；其他阶段为 None。"""
        st = self.state
        phase = st.phase
        events = list(st.event_log)
        if phase == "DAY_SPEECH":
            order, kinds, marker = list(st.speech_order), {"speech"}, "speech_order"
        elif phase == "SHERIFF_SPEECH":
            order, kinds, marker = None, {"sheriff_speech"}, "sheriff_signup"
        elif phase == "SHERIFF_PK":
            order, kinds, marker = None, {"sheriff_pk_speech"}, "phase"
        elif phase == "DAY_VOTE_PK":
            order, kinds, marker = None, {"pk_speech"}, "phase"
        else:
            return None
        start = 0
        for i in range(len(events) - 1, -1, -1):
            e = events[i]
            if e.type == marker and (marker == "sheriff_signup" or e.phase == phase):
                start = i + 1
                if order is None:
                    order = list(e.targets) if marker == "sheriff_signup" else []
                break
        if not order and phase in ("SHERIFF_PK", "DAY_VOTE_PK"):
            eng = self.session.engine
            order = list(getattr(eng, "_last_tied", None) or [])
        order = order or []
        done = sum(1 for e in events[start:]
                   if e.type in kinds and e.audience is Audience.PUBLIC)
        return {"order": order, "done": min(done, len(order)), "total": len(order)}

    # ---------------- 引擎回调 ----------------
    def _on_event(self, e) -> None:
        if self._stop.is_set():
            raise _Stopped
        with self._lock:
            self._events.append(e.as_dict())
        self.current = {"phase": e.phase, "day": e.day,
                        "seat": self.current.get("seat"),
                        "action_type": self.current.get("action_type")}

    def _on_view(self, turn, seat, action_type, view) -> None:
        if self._stop.is_set():
            raise _Stopped
        self.current = {"phase": self.state.phase, "day": self.state.day,
                        "seat": seat, "action_type": action_type}

    # ---------------- 给前端的数据 ----------------
    def events_since(self, since: int, god: bool) -> list[dict]:
        with self._lock:
            evts = self._events[since:]
        if god:
            return evts
        return [e for e in evts if e["audience"] == Audience.PUBLIC.value]

    def snapshot(self, god: bool = False) -> dict:
        st = self.state
        finished = self.status in ("finished", "failed", "stopped")
        players = []
        for s in st.seats:
            p = st.players[s]
            players.append({
                "seat": s, "name": p.name, "alive": p.alive,
                "is_sheriff": p.is_sheriff,
                "revealed_role": p.revealed_role.value if p.revealed_role else None,
                "revealed_role_cn": p.revealed_role.cn if p.revealed_role else None,
                "died_day": p.died_day, "died_cause": p.died_cause,
                "died_cause_cn": i18n.cause_cn(p.died_cause),
                "agent": self.lineup.specs[s].label,
                "released": self.session.pool.runtimes[s].released,
                # 真实身份只在结束后或开了上帝视角时给
                "role": p.role.value if (finished or god) else None,
                "role_cn": p.role.cn if (finished or god) else None,
                "claim": st.public_claims.get(s, {}).get("claim"),
                "claim_cn": i18n.role_cn(st.public_claims.get(s, {}).get("claim")),
            })
        return {
            "id": self.id,
            "status": self.status,
            "error": self.error,
            "created_at": self.created_at,
            "board": board_summary(st.config.n_players),
            "config": st.config.as_dict(),
            "lineup": self.lineup.as_list(),
            "deployment": self.deployment,
            "seats_released": sorted(
                s for s, rt in self.session.pool.runtimes.items() if rt.released),
            "day": st.day,
            "phase": st.phase,
            "phase_cn": i18n.phase_cn(st.phase),
            "current": {**self.current,
                        "phase_cn": i18n.phase_cn(self.current.get("phase")),
                        "action_cn": i18n.action_cn(self.current.get("action_type"))},
            "players": players,
            "sheriff": st.sheriff_seat,
            "sheriff_status": st.sheriff_status,
            "sheriff_status_cn": i18n.SHERIFF_STATUS_CN.get(st.sheriff_status, ""),
            "total_events": len(self._events),
            "winner": st.winner.value if st.winner else None,
            "winner_cn": st.winner.cn if st.winner else None,
            "end_reason": st.end_reason,
            "n_thoughts": len([t for t in st.thought_log if t["thought"]]),
            "speech_progress": self.speech_progress(),
            "started_at": self.created_at,
            "finished_at": self.finished_at,
            "duration_s": self.duration_s,
            "days": st.day,
            "n_players": st.config.n_players,
            "stored": False,
        }

    def thoughts(self) -> list[dict]:
        return [t for t in self.state.thought_log if t["thought"]]

    def agent_sessions(self) -> list[dict]:
        """每个座位的 agent 会话 —— 容器被销毁之前抓下来的那一份。"""
        return _decorate_sessions(STORE.load_agent_sessions(self.id))

    def all_events(self) -> list[dict]:
        with self._lock:
            return list(self._events)


class _Stopped(Exception):
    pass


GAMES: dict[str, GameRunner] = {}


def _iso(ts) -> str | None:
    if ts in (None, ""):
        return None
    if isinstance(ts, str):
        return ts
    return datetime.fromtimestamp(float(ts)).isoformat(timespec="seconds")


def _duration(g: dict) -> float | None:
    t0, t1 = g.get("created_at"), g.get("finished_at")
    if isinstance(t0, (int, float)) and isinstance(t1, (int, float)):
        return round(t1 - t0, 3)
    return None


# ---------------- 历史对局：只剩库里的数据时，拼出和内存对局一样形状的数据 ----------------

class StoredGame:
    """服务重启后，GAMES 里没有这局，但会话库里有。"""

    def __init__(self, gid: str, record: dict) -> None:
        self.id = gid
        self.record = record
        self.result = record.get("result") or {}
        self.config = record.get("config") or self.result.get("config") or {}
        self.lineup = record.get("lineup") or []
        self._events: list[dict] | None = None

    @classmethod
    def load(cls, gid: str) -> "StoredGame | None":
        rec = STORE.load_game(gid)
        return cls(gid, rec) if rec else None

    @property
    def events(self) -> list[dict]:
        if self._events is None:
            self._events = STORE.load_events(self.id)
        return self._events

    def events_since(self, since: int, god: bool) -> list[dict]:
        evts = [e for e in self.events if e.get("seq", 0) > since]
        if god:
            return evts
        return [e for e in evts if e.get("audience") == Audience.PUBLIC.value]

    @property
    def status(self) -> str:
        st = self.record.get("status") or "finished"
        # 库里还是 running，说明服务在对局中途被停掉了
        return "stopped" if st in ("running", "pending") else st

    @property
    def duration_s(self) -> float | None:
        return _duration(self.record)

    def players(self) -> list[dict]:
        base = self.result.get("players") or players_from_events(self.events, self.lineup)
        claims: dict[int, str] = {}
        revealed: dict[int, str] = {}
        for e in self.events:
            if e.get("audience") != Audience.PUBLIC.value:
                continue
            claim = (e.get("payload") or {}).get("claim")
            if e.get("type") in SPEECH_EVENT_TYPES and claim and e.get("actor"):
                claims[e["actor"]] = claim
            if e.get("type") == "idiot_reveal":
                revealed[e.get("actor")] = "IDIOT"
            elif e.get("type") == "explode":
                revealed[e.get("actor")] = "WEREWOLF"
        out = []
        for p in base:
            s = p["seat"]
            out.append({
                **p,
                "name": f"{s}号",
                "revealed_role": revealed.get(s),
                "revealed_role_cn": i18n.role_cn(revealed.get(s)),
                "released": True,
                "claim": claims.get(s),
                "claim_cn": i18n.role_cn(claims.get(s)),
            })
        return out

    def snapshot(self, god: bool = False) -> dict:
        res, rec = self.result, self.record
        n = self.config.get("n_players")
        try:
            board = board_summary(n)
        except (ValueError, KeyError, TypeError):
            board = None
        winner = res.get("winner", rec.get("winner"))
        sheriff_status = res.get("sheriff_status") or "none"
        players = self.players()
        error = res.get("error")
        if rec.get("status") in ("running", "pending"):
            error = "服务在对局进行中重启，这一局没有跑完。"
        return {
            "id": self.id,
            "status": self.status,
            "error": error,
            "created_at": _iso(rec.get("created_at")),
            "board": board,
            "config": self.config,
            "lineup": self.lineup,
            "deployment": rec.get("deployment"),
            "seats_released": [p["seat"] for p in players],
            "day": res.get("days", rec.get("days")) or 0,
            "phase": "GAME_OVER",
            "phase_cn": i18n.phase_cn("GAME_OVER"),
            "current": {"phase": "GAME_OVER", "day": res.get("days", rec.get("days")) or 0,
                        "seat": None, "action_type": None,
                        "phase_cn": i18n.phase_cn("GAME_OVER"), "action_cn": ""},
            "players": players,
            "sheriff": res.get("sheriff"),
            "sheriff_status": sheriff_status,
            "sheriff_status_cn": i18n.SHERIFF_STATUS_CN.get(sheriff_status, ""),
            "total_events": len(self.events),
            "winner": winner,
            "winner_cn": res.get("winner_cn") or i18n_winner_cn(winner),
            "end_reason": res.get("reason", rec.get("end_reason")) or "",
            "n_thoughts": len(self.thoughts()),
            "speech_progress": None,
            "started_at": _iso(rec.get("created_at")),
            "finished_at": _iso(rec.get("finished_at")),
            "duration_s": self.duration_s,
            "days": res.get("days", rec.get("days")) or 0,
            "n_players": n,
            "stored": True,
        }

    def thoughts(self) -> list[dict]:
        th = thoughts_from_events(self.events)
        return th or thoughts_from_turns(STORE.load_turns(self.id))

    def agent_sessions(self) -> list[dict]:
        return _decorate_sessions(STORE.load_agent_sessions(self.id))

    def replay(self) -> dict:
        thoughts = self.thoughts()
        rec = {**self.record, "config": self.config}
        return {
            "markdown": render_stored_replay(rec, self.events, thoughts),
            "result": self.result or None,
            "thoughts": thoughts,
            "sessions": self.agent_sessions(),
            "timeline": build_timeline(self.events),
            "duration_s": self.duration_s,
            "stored": True,
        }


def i18n_winner_cn(winner) -> str | None:
    try:
        return Faction(winner).cn if winner else None
    except ValueError:
        return None


def _decorate_sessions(rows: list[dict]) -> list[dict]:
    return [{**x,
             "role_cn": i18n.role_cn(x.get("role")),
             "backend_cn": i18n.BACKEND_CN.get(x.get("backend"), x.get("backend")),
             "release_reason_cn": i18n.release_cn(x.get("release_reason"))}
            for x in rows]


def _history_entry(g: dict) -> dict:
    """列表页用的历史对局条目：库里的原字段不动，只补展示要用的。"""
    rec = STORE.load_game(g["id"]) or {}
    cfg = rec.get("config") or {}
    res = rec.get("result") or {}
    status = g.get("status")
    return {
        **g,
        "status": "stopped" if status in ("running", "pending") else status,
        "winner_cn": res.get("winner_cn") or i18n_winner_cn(g.get("winner")),
        "n_players": cfg.get("n_players"),
        "started_at": _iso(g.get("created_at")),
        "ended_at": _iso(g.get("finished_at")),
        "duration_s": _duration(g),
        "stored": True,
    }


# --------------------------------------------------------------------------


class Handler(BaseHTTPRequestHandler):
    server_version = "Werewolf/1.0"

    def log_message(self, fmt, *args):  # 静音访问日志
        pass

    # ---------------- 工具 ----------------
    def _json(self, obj, code: int = 200) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _text(self, text: str, ctype="text/plain; charset=utf-8", code=200) -> None:
        body = text.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path) -> None:
        if not path.is_file():
            return self._json({"error": "not found"}, 404)
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype == "application/javascript":
            ctype += "; charset=utf-8"
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _game(self, gid: str) -> GameRunner | None:
        g = GAMES.get(gid)
        if g is None:
            self._json({"error": f"对局 {gid} 不存在"}, 404)
        return g

    # ---------------- 路由 ----------------
    def do_GET(self) -> None:
        u = urlparse(self.path)
        q = parse_qs(u.query)
        god = q.get("god", ["0"])[0] in ("1", "true")
        parts = [p for p in u.path.split("/") if p]

        if u.path in ("/", "/index.html"):
            return self._file(WEB_DIR / "index.html")
        if parts and parts[0] == "static":
            return self._file(WEB_DIR / Path(*parts[1:]))

        if u.path == "/api/options":
            return self._json({
                "boards": {str(n): board_summary(n) for n in sorted(BOARDS)},
                "models": AVAILABLE_MODELS,
                "backends": AVAILABLE_BACKENDS,
                # 哪些后端的密钥已经在环境里配好了，前端据此提示
                "keys_present": {
                    k: bool(os.environ.get(v["needs_key"]))
                    for k, v in AVAILABLE_BACKENDS.items() if v.get("needs_key")
                },
                "base_url_env": os.environ.get("OPENAI_BASE_URL", ""),
                # 只说环境里有没有，绝不把密钥本身发给前端
                "env_key_present": {
                    v["needs_key"]: bool(os.environ.get(v["needs_key"]))
                    for v in AVAILABLE_BACKENDS.values() if v.get("needs_key")
                },
                "efforts": EFFORT_LEVELS,
                "deployments": DEPLOYMENTS,
                "store": STORE_URI,
                "defaults": {
                    "n_players": 12, "max_speech_chars": 450,
                    "max_iterations": 3, "sheriff": True, "wolf_explode": True,
                    "deployment": DEFAULT_DEPLOYMENT,
                },
            })

        if u.path == "/api/games":
            live = []
            for g in GAMES.values():
                snap = g.snapshot()
                live.append({**snap, "ended_at": snap["finished_at"]})
            live_ids = {g["id"] for g in live}
            # 把库里的历史对局也列出来 —— 服务重启之后照样能复盘
            past = [_history_entry(g) for g in STORE.list_games(50) if g["id"] not in live_ids]
            return self._json({"live": live, "past": past, "store": STORE_URI})

        if len(parts) >= 3 and parts[0] == "api" and parts[1] == "games":
            tail = parts[3] if len(parts) > 3 else ""
            if parts[2] not in GAMES:
                stored = StoredGame.load(parts[2])
                if stored is not None:
                    return self._stored_get(stored, tail, q, god)
            g = self._game(parts[2])
            if g is None:
                return
            if not tail:
                return self._json(g.snapshot(god))
            if tail == "events":
                since = int(q.get("since", ["0"])[0])
                return self._json({
                    "events": g.events_since(since, god),
                    "total": len(g._events),
                    "snapshot": g.snapshot(god),
                })
            if tail == "replay":
                if g.status not in ("finished", "stopped"):
                    return self._json({"error": "对局还没结束"}, 409)
                return self._json({
                    "markdown": render_replay(g.state, lineup=g.lineup),
                    "result": result_summary(g.state, g.lineup),
                    "thoughts": g.thoughts(),
                    "sessions": g.agent_sessions(),
                    "timeline": build_timeline(g.all_events()),
                    "duration_s": g.duration_s,
                    "stored": False,
                })
            if tail == "sessions":
                return self._json({"sessions": g.agent_sessions()})
            if tail == "views":
                return self._json(build_all_views(g.state))
        return self._json({"error": "not found"}, 404)

    def _stored_get(self, g: StoredGame, tail: str, q: dict, god: bool) -> None:
        if not tail:
            return self._json(g.snapshot(god))
        if tail == "events":
            since = int(q.get("since", ["0"])[0])
            return self._json({
                "events": g.events_since(since, god),
                "total": len(g.events),
                "snapshot": g.snapshot(god),
            })
        if tail == "replay":
            return self._json(g.replay())
        if tail == "sessions":
            return self._json({"sessions": g.agent_sessions()})
        if tail == "views":
            return self._json({"error": "历史对局不保留逐座位视角，请看复盘"}, 404)
        return self._json({"error": "not found"}, 404)

    def do_POST(self) -> None:
        u = urlparse(self.path)
        parts = [p for p in u.path.split("/") if p]
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")

        if u.path == "/api/games":
            try:
                n = int(payload.get("n_players", 12))
                config = GameConfig(
                    n_players=n,
                    seed=payload.get("seed") if payload.get("seed") not in ("", None) else None,
                    sheriff=bool(payload.get("sheriff", True)),
                    wolf_explode=bool(payload.get("wolf_explode", True)),
                    win_rule=payload.get("win_rule", "edge"),
                    max_speech_chars=int(payload.get("max_speech_chars", 450)),
                    max_iterations=int(payload.get("max_iterations", 3)),
                )
                lineup = Lineup.from_payload(n, payload.get("seats"))
                deployment = payload.get("deployment", DEFAULT_DEPLOYMENT)
                if deployment not in DEPLOYMENTS:
                    raise ValueError(f"不认识的部署模式 {deployment!r}")
                missing = lineup.missing_keys()
                if missing:
                    raise ValueError(
                        f"这些座位配了 LLM 但拿不到 API key：{missing}。"
                        "请在「高级选项」里填 API Key，或在服务端设好对应的环境变量。"
                    )
                # GameRunner 会发牌，板子不合法在这里就会报错，必须一起包住
                runner = GameRunner(config, lineup, deployment)
            except (ValueError, KeyError, TypeError) as exc:
                return self._json({"error": f"配置不合法：{exc}"}, 400)

            GAMES[runner.id] = runner
            runner.start()
            return self._json(runner.snapshot(), 201)

        if len(parts) == 4 and parts[0] == "api" and parts[1] == "games" and parts[3] == "stop":
            g = self._game(parts[2])
            if g is None:
                return
            g.stop()
            return self._json({"ok": True, "status": g.status})
        return self._json({"error": "not found"}, 404)


def main(argv: list[str] | None = None) -> int:
    """`werewolf-server` 入口。"""
    import argparse

    ap = argparse.ArgumentParser(description="狼人杀 agent 沙箱")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args(argv)
    serve(a.host, a.port)
    return 0


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"狼人杀沙箱已启动： http://{host}:{port}")
    print("按 Ctrl+C 停止")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        httpd.server_close()
        STORE.close()
