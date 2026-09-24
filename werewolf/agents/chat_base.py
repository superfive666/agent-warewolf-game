"""两个 LLM 后端（Claude / OpenAI）共用的部分。

共用的东西：整局不变的 system prompt、每回合只发增量的对话历史、历史裁剪、
私人笔记本的读写、以及把返回的 JSON 交给引擎之前的整理。

不共用的：怎么调 API、怎么约束输出格式 —— 那是各自子类的事。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..prompts import system_prompt, turn_prompt
from ..roles import Role
from ..views import PlayerView

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def extract_json(text: str) -> dict:
    """从模型返回里抠出 JSON。

    自建网关后面的模型不一定严格遵守"只输出 JSON"，可能裹 markdown 代码块、
    或者在前面加一句废话。这里按"直接解析 → 去代码块 → 找第一个平衡的大括号"
    依次退让，都失败才报错。
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("模型返回了空内容")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = _FENCE.search(text)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    start = text.find("{")
    if start >= 0:
        depth, in_str, esc = 0, False, False
        for i, ch in enumerate(text[start:], start):
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(text[start:i + 1])
    raise ValueError(f"模型返回的不是合法 JSON：{text[:200]!r}")


class ChatAgent:
    """基于对话的 LLM agent 骨架。子类只需要实现 ``_complete``。"""

    #: 子类填上，进复盘用
    provider = "chat"

    def __init__(self, seat: int, role: Role | None, *, model: str,
                 max_tokens: int = 16000, verbose: bool = False,
                 memory_dir=None, keep_turns: int = 24) -> None:
        self.seat = seat
        self.role = role
        self.model = model
        self.max_tokens = max_tokens
        self.verbose = verbose
        self.keep_turns = keep_turns
        self.name = f"{self.provider}-{seat}-{model}"
        #: agent 的私有 memory 目录。容器化时挂一个生命周期长于容器的卷。
        self.memory_dir = Path(memory_dir) if memory_dir else None
        if self.memory_dir:
            self.memory_dir.mkdir(parents=True, exist_ok=True)
        self._system: str | None = None
        self._messages: list[dict] = []
        self.thoughts: list[dict] = []
        self.usage = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0}

    # ------------------------------------------------------------------
    def _complete(self, action_type: str) -> str:
        """调模型，返回它输出的原始文本。子类实现。"""
        raise NotImplementedError

    # ------------------------------------------------------------------
    def act(self, view: PlayerView, error: str | None = None) -> dict:
        first = self._system is None
        if first:
            # system 整局逐字不变 → 命中 prompt cache
            self._system = system_prompt(view)

        self._messages.append({
            "role": "user",
            "content": turn_prompt(view, full=first, error=error, notes=self.read_notes()),
        })

        action_type = view.legal_actions["action_type"]
        if self.memory_dir:
            view.legal_actions["_memory"] = True

        text = self._complete(action_type)
        self._messages.append({"role": "assistant", "content": text})
        self._trim_history()

        data = extract_json(text)
        if not isinstance(data, dict):
            raise ValueError(f"模型返回的 JSON 不是对象：{type(data).__name__}")

        if self.memory_dir and data.get("notes_update"):
            self.write_notes(str(data["notes_update"]))
        data.pop("notes_update", None)

        thought = data.get("private_thought", "")
        self.thoughts.append({
            "seq": view.generated_at_seq, "day": view.public_state["day"],
            "action_type": action_type, "thought": thought,
        })
        if self.verbose and thought:
            print(f"  [{self.seat}号 {self.role.cn if self.role else ''} · {action_type}] 💭 {thought}")
        return data

    # ------------------------------------------------------------------
    @property
    def notes_path(self):
        return self.memory_dir / "notes.md" if self.memory_dir else None

    def read_notes(self) -> str:
        p = self.notes_path
        return p.read_text(encoding="utf-8") if p and p.is_file() else ""

    def write_notes(self, text: str) -> None:
        if self.notes_path:
            self.notes_path.write_text(text, encoding="utf-8")

    def _trim_history(self) -> None:
        """只保留最近 N 轮对话。

        这样做是安全的，因为**每回合的 user 消息里都会重发一份完整的发言档案**
        （见 prompts._fmt_speech_archive）和全部票型 —— 盘逻辑需要的原始材料
        不依赖对话历史，裁掉的只是 agent 自己早期的措辞。
        """
        if len(self._messages) > self.keep_turns * 2:
            self._messages = self._messages[-self.keep_turns * 2:]
            while self._messages and self._messages[0]["role"] != "user":
                self._messages.pop(0)

    def _add_usage(self, **kw) -> None:
        for k, v in kw.items():
            if v:
                self.usage[k] = self.usage.get(k, 0) + v
