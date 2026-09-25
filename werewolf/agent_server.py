"""跑在【单个 agent 容器】里的服务。一个容器 = 一个座位 = 一个玩家。

容器只认识自己那一个座位，它拿不到 GameState，也不知道别人的身份 ——
编排端把 PlayerView 序列化发过来，容器在自己这边重建视角、组装 prompt、
调自己的模型、读写自己的私有笔记本。

  GET  /healthz   就绪探针（k8s readinessProbe 用）
  POST /act       {"view": {...}, "error": "..."} -> 动作 dict
  GET  /session   导出完整会话（编排端在销毁容器【之前】必须调一次）

环境变量：
  WEREWOLF_SEAT         座位号（必填）
  WEREWOLF_BACKEND      heuristic | claude | openai
  WEREWOLF_MODEL        模型 id
  WEREWOLF_EFFORT       low/medium/high/xhigh/max
  WEREWOLF_BASE_URL     OpenAI 兼容网关地址（自建网关用）
  WEREWOLF_API_KEY_ENV  去哪个环境变量取密钥（默认按后端取）
  WEREWOLF_MEMORY_DIR   私有 memory 卷的挂载点，默认 /memory
  ANTHROPIC_API_KEY / OPENAI_API_KEY   对应后端的密钥
"""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .roles import Role
from .views import PlayerView


def build_agent():
    seat = int(os.environ["WEREWOLF_SEAT"])
    backend = os.environ.get("WEREWOLF_BACKEND", "heuristic")
    role = Role(os.environ["WEREWOLF_ROLE"]) if os.environ.get("WEREWOLF_ROLE") else None
    memory_dir = Path(os.environ.get("WEREWOLF_MEMORY_DIR", "/memory")) / f"seat_{seat:02d}"

    effort = os.environ.get("WEREWOLF_EFFORT", "medium")
    max_tokens = int(os.environ.get("WEREWOLF_MAX_TOKENS", "16000"))
    key_env = os.environ.get("WEREWOLF_API_KEY_ENV") or ""

    if backend in ("llm", "claude"):
        from .agents.llm import LLMAgent

        return LLMAgent(
            seat, role,
            model=os.environ.get("WEREWOLF_MODEL", "claude-opus-5"),
            effort=effort, max_tokens=max_tokens, memory_dir=memory_dir,
            api_key_env=key_env or "ANTHROPIC_API_KEY",
        )
    if backend == "openai":
        from .agents.openai_agent import OpenAIAgent

        return OpenAIAgent(
            seat, role,
            model=os.environ.get("WEREWOLF_MODEL", "gpt-5"),
            base_url=os.environ.get("WEREWOLF_BASE_URL") or None,
            max_tokens=max_tokens, memory_dir=memory_dir,
            api_key_env=key_env or "OPENAI_API_KEY",
            effort=effort if effort in ("low", "medium", "high") else None,
        )
    from .agents.heuristic import HeuristicAgent

    seed = os.environ.get("WEREWOLF_SEED")
    return HeuristicAgent(seat, role, seed=int(seed) if seed else None)


class AgentHandler(BaseHTTPRequestHandler):
    agent = None
    seat = 0

    def log_message(self, fmt, *args):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/healthz"):
            return self._json({"ok": True, "seat": self.seat})
        if self.path.startswith("/session"):
            a = self.agent
            return self._json({
                "seat": self.seat,
                "backend": getattr(a, "provider", "heuristic"),
                "model": getattr(a, "model", None),
                "role": getattr(getattr(a, "role", None), "value", None),
                "system_prompt": getattr(a, "_system", None),
                "messages": list(getattr(a, "_messages", []) or []),
                "usage": dict(getattr(a, "usage", {}) or {}),
                # memory 卷的位置照实报：规则 bot 不写笔记，但卷照样是挂着的，
                # 复盘时要知道去哪找
                "memory_uri": str(
                    getattr(a, "memory_dir", None)
                    or Path(os.environ.get("WEREWOLF_MEMORY_DIR", "/memory")) / f"seat_{self.seat:02d}"
                ),
                "notes": a.read_notes() if hasattr(a, "read_notes") else "",
            })
        return self._json({"error": "not found"}, 404)

    def do_POST(self):
        if not self.path.startswith("/act"):
            return self._json({"error": "not found"}, 404)
        n = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(n) or b"{}")
        try:
            view = PlayerView.from_dict(payload["view"])
            action = self.agent.act(view, error=payload.get("error"))
        except Exception as exc:
            return self._json({"error": f"{type(exc).__name__}: {exc}"}, 500)
        return self._json({"action": action})


def serve(host: str = "0.0.0.0", port: int | None = None) -> None:
    port = port or int(os.environ.get("WEREWOLF_PORT", "8100"))
    AgentHandler.agent = build_agent()
    AgentHandler.seat = int(os.environ["WEREWOLF_SEAT"])
    httpd = ThreadingHTTPServer((host, port), AgentHandler)
    print(f"agent 容器就绪：座位 {AgentHandler.seat} @ {host}:{port}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    serve()
