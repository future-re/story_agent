"""共享模型基类，封装 OpenAI 兼容接口的通用逻辑。"""

from typing import Any, Dict, Generator, List, Optional

from openai import OpenAI


class BaseChatModel:
    """基于 OpenAI SDK 的通用对话模型封装。"""

    def __init__(self, api_key: Optional[str], model_name: str, base_url: str, missing_key_error: str):
        self.api_key = api_key
        self.model_name = model_name
        if not self.api_key:
            raise ValueError(missing_key_error)

        self.client = OpenAI(api_key=self.api_key, base_url=base_url)

    def _prepare_messages(
        self,
        prompt: str,
        history: Optional[List[Dict[str, Any]]] = None,
        system_prompt: str = "You are a helpful assistant.",
    ) -> List[Dict[str, Any]]:
        messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})
        return messages

    def chat(
        self,
        prompt: str,
        history: Optional[List[Dict[str, Any]]] = None,
        system_prompt: str = "You are a helpful assistant.",
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Any:
        """同步对话接口。"""
        try:
            messages = self._prepare_messages(prompt, history, system_prompt)
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=tools,
                stream=False,
                **kwargs,
            )
            message = response.choices[0].message
            if message.tool_calls:
                return message
            return message.content or ""
        except Exception as exc:
            return f"Error: {exc}"

    def stream_chat(
        self,
        prompt: str,
        history: Optional[List[Dict[str, Any]]] = None,
        system_prompt: str = "You are a helpful assistant.",
        **kwargs: Any,
    ) -> Generator[str, None, None]:
        """流式对话接口。"""
        try:
            messages = self._prepare_messages(prompt, history, system_prompt)
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                stream=True,
                **kwargs,
            )
            for chunk in response:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
        except Exception as exc:
            yield f"Error: {exc}"


# 兼容已有对外命名
BaseModel = BaseChatModel

