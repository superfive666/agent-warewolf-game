"""OpenAI（以及任何 OpenAI 兼容网关）后端。

自建网关的能力千差万别：有的支持严格 json_schema，有的只认 json_object，
有的两个都不认；有的要 max_completion_tokens，有的只认 max_tokens。
所以这里的策略是**逐级退让并记住哪一档能用**，第一次试出来之后就不再浪费调用：

    json_schema(strict) → json_schema(宽松) → json_object → 纯文本自己抠 JSON

不管退到哪一档，返回值最后都要过 actions.validate()，所以格式没守住也不会串进游戏。

挂自己的 provider 只需要三个参数：**base_url + model + api_key**。
密钥可以直接给，也可以给一个环境变量名让它自己去取。
不管哪种给法，密钥都只活在内存里 —— 阵容入库和回传前端时都会脱敏。

需要 `pip install -r requirements-openai.txt`。
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
                 api_key: str | None = None,
                 api_key_env: str = "OPENAI_API_KEY",
                 base_url_env: str = "OPENAI_BASE_URL",
                 effort: str | None = None,
                 temperature: float | None = None,
                 max_tokens: int = 16000,
                 timeout: float = 120.0,
                 max_retries: int = 0,
                 client=None, verbose: bool = False, memory_dir=None,
                 response_mode: str | None = None) -> None:
        super().__init__(seat, role, model=model, max_tokens=max_tokens,
                         verbose=verbose, memory_dir=memory_dir)
        self.api_key_env = api_key_env
        #: 直接给的密钥。不进任何日志、不进会话存档
        self._api_key = api_key or None
        self.base_url = base_url or os.environ.get(base_url_env) or None
        self.effort = effort
        self.temperature = temperature
        #: 引擎自己已经有 max_iterations 的重试循环了，SDK 再叠一层指数退避
        #: 会让"网关连不上"从秒级变成分钟级。所以这里默认不让 SDK 重试。
        self.timeout = timeout
        self.max_retries = max_retries
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
            key = self._api_key or os.environ.get(self.api_key_env)
            if not key:
                raise RuntimeError(
                    f"{self.seat}号没有拿到 API key：请直接传 api_key，"
                    f"或者设置环境变量 {self.api_key_env}"
                )
            self._client = OpenAI(
                api_key=key, base_url=self.base_url,
                timeout=self.timeout, max_retries=self.max_retries,
            )
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
                    if _is_connection_error(exc):
                        # 连不上就别试了，把地址原样报出来，比重试半天有用
                        raise RuntimeError(
                            f"连不上 {self.base_url or 'OpenAI 默认地址'} —— "
                            f"检查 base_url 是否正确、网关是否在跑。原始错误：{exc}"
                        ) from exc
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


def _is_connection_error(exc: Exception) -> bool:
    """网关压根连不上。这种要立刻报错，不能陪着重试。"""
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return True
    name = type(exc).__name__
    if name in ("APIConnectionError", "APITimeoutError", "ConnectError", "ConnectTimeout"):
        return True
    blob = f"{name} {exc}".lower()
    return any(w in blob for w in
               ("connection error", "connection refused", "failed to establish",
                "name or service not known", "timed out", "max retries exceeded"))


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
