"""OpenAI（以及任何 OpenAI 兼容网关）后端。

自建网关的能力千差万别：有的支持严格 json_schema，有的只认 json_object，
有的两个都不认；有的要 max_completion_tokens，有的只认 max_tokens。
所以这里的策略是**逐级退让并记住哪一档能用**，第一次试出来之后就不再浪费调用：

    json_schema(strict) → json_schema(宽松) → json_object → 纯文本自己抠 JSON

不管退到哪一档，返回值最后都要过 actions.validate()，所以格式没守住也不会串进游戏。

需要 `pip install -r requirements-openai.txt`。
凭据从环境变量读，**永远不从前端传进来**（阵容配置会写进会话库）。
"""
from __future__ import annotations

import json
import os

from ..prompts import output_schema
from ..roles import Role
from .chat_base import ChatAgent

DEFAULT_MODEL = "gpt-5"

#: 输出格式的退让阶梯
_MODES = ("json_schema_strict", "json_schema", "json_object", "text")


class OpenAIAgent(ChatAgent):
    provider = "openai"

    def __init__(self, seat: int, role: Role | None, *,
                 model: str = DEFAULT_MODEL,
                 base_url: str | None = None,
                 api_key_env: str = "OPENAI_API_KEY",
                 base_url_env: str = "OPENAI_BASE_URL",
                 effort: str | None = None,
                 temperature: float | None = None,
                 max_tokens: int = 16000,
                 client=None, verbose: bool = False, memory_dir=None,
                 response_mode: str | None = None) -> None:
        super().__init__(seat, role, model=model, max_tokens=max_tokens,
                         verbose=verbose, memory_dir=memory_dir)
        self.api_key_env = api_key_env
        self.base_url = base_url or os.environ.get(base_url_env) or None
        self.effort = effort
        self.temperature = temperature
        self._client = client
        #: 试出来能用的那一档，试出来之后就固定
        self._mode = response_mode if response_mode in _MODES else None
        #: 这个网关认哪个 token 参数名
        self._token_param: str | None = None

    # ------------------------------------------------------------------
    @property
    def client(self):
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError(
                    "OpenAI 后端需要 SDK：pip install -r requirements-openai.txt"
                ) from exc
            key = os.environ.get(self.api_key_env)
            if not key:
                raise RuntimeError(
                    f"没有找到 API key：请设置环境变量 {self.api_key_env}"
                )
            self._client = OpenAI(api_key=key, base_url=self.base_url)
        return self._client

    # ------------------------------------------------------------------
    def _messages_payload(self, action_type: str, mode: str) -> list[dict]:
        msgs = [{"role": "system", "content": self._system}, *self._messages]
        if mode in ("json_object", "text"):
            # 端点没法在协议层约束格式，那就把 schema 直接写进 prompt。
            # 不这么做的话，弱一点的网关模型会漏字段或者自己发明字段。
            schema = output_schema(action_type, memory=bool(self.memory_dir))["schema"]
            msgs.append({
                "role": "system",
                "content": (
                    "你这次的回复必须是**一个 JSON 对象**，严格符合下面这份 JSON Schema，"
                    "不要多字段也不要少字段，不要用 markdown 代码块包裹：\n"
                    + json.dumps(schema, ensure_ascii=False)
                ),
            })
        return msgs

    def _response_format(self, action_type: str, mode: str):
        if mode == "text":
            return None
        if mode == "json_object":
            return {"type": "json_object"}
        schema = output_schema(action_type, memory=bool(self.memory_dir))["schema"]
        return {
            "type": "json_schema",
            "json_schema": {
                "name": f"werewolf_{action_type}",
                "schema": schema,
                "strict": mode == "json_schema_strict",
            },
        }

    def _call_once(self, action_type: str, mode: str, token_param: str):
        kw = {
            "model": self.model,
            "messages": self._messages_payload(action_type, mode),
            token_param: self.max_tokens,
        }
        rf = self._response_format(action_type, mode)
        if rf is not None:
            kw["response_format"] = rf
        if self.temperature is not None:
            kw["temperature"] = self.temperature
        if self.effort:
            # 推理模型的思考强度。不认这个参数的网关会在下面被降级逻辑接住
            kw["reasoning_effort"] = self.effort
        return self.client.chat.completions.create(**kw)

    def _complete(self, action_type: str) -> str:
        modes = [self._mode] if self._mode else list(_MODES)
        tokens = [self._token_param] if self._token_param else ["max_completion_tokens", "max_tokens"]
        errors: list[str] = []

        for mode in modes:
            for tp in tokens:
                try:
                    resp = self._call_once(action_type, mode, tp)
                except Exception as exc:
                    errors.append(f"[{mode}/{tp}] {type(exc).__name__}: {exc}")
                    if not _is_capability_error(exc):
                        # 不是"网关不支持这个参数"，再退让也没意义
                        raise
                    continue
                # 成功：记住这一档，后面不再试探
                self._mode, self._token_param = mode, tp
                self._track(resp)
                choice = resp.choices[0] if resp.choices else None
                text = (getattr(choice.message, "content", None) if choice else None) or ""
                if not text.strip():
                    raise ValueError(
                        f"模型返回了空内容（finish_reason="
                        f"{getattr(choice, 'finish_reason', '?')}），"
                        "可能是 max_tokens 太小或被内容过滤拦了"
                    )
                return text
        raise RuntimeError(
            "这个 OpenAI 兼容端点把所有输出格式和参数组合都拒绝了：\n  "
            + "\n  ".join(errors[-4:])
        )

    def _track(self, resp) -> None:
        u = getattr(resp, "usage", None)
        if not u:
            return
        cached = 0
        details = getattr(u, "prompt_tokens_details", None)
        if details is not None:
            cached = getattr(details, "cached_tokens", 0) or 0
        self._add_usage(
            input_tokens=getattr(u, "prompt_tokens", 0) or 0,
            output_tokens=getattr(u, "completion_tokens", 0) or 0,
            cache_read_input_tokens=cached,
        )


_CAPABILITY_HINTS = (
    "response_format", "json_schema", "unsupported", "not supported",
    "unrecognized", "unknown parameter", "invalid parameter", "max_tokens",
    "max_completion_tokens", "reasoning_effort", "temperature", "does not support",
    "extra fields", "additionalproperties", "unexpected keyword",
)


def _is_capability_error(exc: Exception) -> bool:
    """判断这个错误是不是"端点不支持某个参数"，只有这种才值得降级重试。

    认证失败、余额不足、限流这些降级一百次也没用，要直接抛给上层。
    """
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if status in (401, 403, 429) or (isinstance(status, int) and status >= 500):
        return False
    if isinstance(exc, TypeError):
        return True
    blob = f"{type(exc).__name__} {exc}".lower()
    if any(w in blob for w in ("api key", "authentication", "unauthorized",
                               "quota", "insufficient", "rate limit")):
        return False
    return any(h in blob for h in _CAPABILITY_HINTS)
