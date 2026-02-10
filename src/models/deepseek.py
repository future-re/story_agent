import os
from typing import Optional

from .base import BaseChatModel


class DeepSeekModel(BaseChatModel):
    def __init__(self, api_key: Optional[str] = None, model_name: str = "deepseek-chat"):
        super().__init__(
            api_key=api_key or os.getenv("DEEPSEEK_API_KEY"),
            model_name=model_name,
            base_url="https://api.deepseek.com",
            missing_key_error="DEEPSEEK_API_KEY not found.",
        )

