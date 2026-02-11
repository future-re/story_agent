import os
from typing import Any, Dict, Generator, List, Optional

from .base import BaseChatModel


class GLMModel(BaseChatModel):
    def __init__(self, api_key: Optional[str] = None, model_name: str = "glm-4-plus"):
        self.default_thinking_type = os.getenv("GLM_THINKING_TYPE", "disabled").strip().lower()
        self.default_max_tokens = self._safe_int(os.getenv("GLM_MAX_TOKENS"), 8192)
        super().__init__(
            api_key=api_key or os.getenv("GLM_API_KEY"),
            model_name=model_name,
            base_url="https://open.bigmodel.cn/api/paas/v4",
            missing_key_error="GLM_API_KEY not found.",
        )

    @staticmethod
    def _safe_int(value: Optional[str], default: int) -> int:
        if value is None:
            return default
        try:
            return int(value.strip())
        except ValueError:
            return default

    def _inject_glm_defaults(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        params = dict(kwargs)
        extra_body = dict(params.get("extra_body") or {})

        # OpenAI SDK 对非标准字段需通过 extra_body 传递，不能直接传 thinking=...
        if "thinking" in params:
            extra_body.setdefault("thinking", params.pop("thinking"))
        if "thinking" not in extra_body and self.default_thinking_type in {"enabled", "disabled"}:
            extra_body["thinking"] = {"type": self.default_thinking_type}
        if extra_body:
            params["extra_body"] = extra_body

        if "max_tokens" not in params:
            params["max_tokens"] = self.default_max_tokens
        return params

    def chat(
        self,
        prompt: str,
        history: Optional[List[Dict[str, Any]]] = None,
        system_prompt: str = "You are a helpful assistant.",
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Any:
        return super().chat(
            prompt,
            history=history,
            system_prompt=system_prompt,
            tools=tools,
            **self._inject_glm_defaults(kwargs),
        )

    def stream_chat(
        self,
        prompt: str,
        history: Optional[List[Dict[str, Any]]] = None,
        system_prompt: str = "You are a helpful assistant.",
        **kwargs: Any,
    ) -> Generator[str, None, None]:
        yield from super().stream_chat(
            prompt,
            history=history,
            system_prompt=system_prompt,
            **self._inject_glm_defaults(kwargs),
        )
