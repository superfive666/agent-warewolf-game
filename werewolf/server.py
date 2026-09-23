"""沙箱 Web 服务：配置 → 开局 → 自动跑 → 复盘。只用标准库，不需要任何前端构建。

  python3 run_server.py            # 然后打开 http://127.0.0.1:8000
"""
from __future__ import annotations

import json
import mimetypes
import threading
import traceback
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .agents.llm import LLMAgent
from .engine import Engine
from .events import Audience
from .lineup import AVAILABLE_BACKENDS, AVAILABLE_MODELS, EFFORT_LEVELS, Lineup
from .replay import render_replay, result_summary
from .roles import BOARDS, board_summary
from .state import GameConfig, new_game
from .views import build_all_views

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


class GameRunner:
    """一局游戏 = 一个后台线程。前端靠轮询拿增量事件。"""

    def __init__(self, config: GameConfig, lineup: Lineup) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.config = config
        self.lineup = lineup
        self.state = new_game(config)
        self.agents = lineup.build_agents(self.state)
        self.status = "pending"  # pending | running | finished | failed | stopped
        self.error: str | None = None
        self.created_at = datetime.now().isoformat(timespec="seconds")
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
            engine = Engine(
                self.state, self.agents,
                on_event=self._on_event,
                view_recorder=self._on_view,
            )
            engine.run()
            self.status = "stopped" if self._stop.is_set() else "finished"
        except _Stopped:
            self.status = "stopped"
        except Exception:
            self.status = "failed"
            self.error = traceback.format_exc()

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
                "agent": self.lineup.specs[s].label,
                # 真实身份只在结束后或开了上帝视角时给
                "role": p.role.value if (finished or god) else None,
                "role_cn": p.role.cn if (finished or god) else None,
                "claim": st.public_claims.get(s, {}).get("claim"),
            })
        return {
            "id": self.id,
            "status": self.status,
            "error": self.error,
            "created_at": self.created_at,
            "board": board_summary(st.config.n_players),
            "config": st.config.as_dict(),
            "lineup": self.lineup.as_list(),
            "day": st.day,
            "phase": st.phase,
            "current": self.current,
            "players": players,
            "sheriff": st.sheriff_seat,
            "sheriff_status": st.sheriff_status,
            "total_events": len(self._events),
            "winner": st.winner.value if st.winner else None,
            "winner_cn": st.winner.cn if st.winner else None,
            "end_reason": st.end_reason,
            "n_thoughts": len([t for t in st.thought_log if t["thought"]]),
        }

    def thoughts(self) -> list[dict]:
        return [t for t in self.state.thought_log if t["thought"]]


class _Stopped(Exception):
    pass


GAMES: dict[str, GameRunner] = {}


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
            self._json({"error": f"game {gid} not found"}, 404)
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
                "efforts": EFFORT_LEVELS,
                "llm_ready": LLMAgent is not None,
                "defaults": {
                    "n_players": 12, "max_speech_chars": 450,
                    "max_iterations": 3, "sheriff": True, "wolf_explode": True,
                },
            })

        if u.path == "/api/games":
            return self._json([g.snapshot() for g in GAMES.values()])

        if len(parts) >= 3 and parts[0] == "api" and parts[1] == "games":
            g = self._game(parts[2])
            if g is None:
                return
            tail = parts[3] if len(parts) > 3 else ""
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
                })
            if tail == "views":
                return self._json(build_all_views(g.state))
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
                # GameRunner 会发牌，板子不合法在这里就会报错，必须一起包住
                runner = GameRunner(config, lineup)
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


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"狼人杀沙箱已启动： http://{host}:{port}")
    print("按 Ctrl+C 停止")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
