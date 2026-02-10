import os
from typing import Optional

from .base import BaseChatModel


class KimiModel(BaseChatModel):
    def __init__(self, api_key: Optional[str] = None, model_name: str = "kimi-k2.5"):
        super().__init__(
            api_key=api_key or os.getenv("MOONSHOT_API_KEY"),
            model_name=model_name,
            base_url="https://api.moonshot.cn/v1",
            missing_key_error="MOONSHOT_API_KEY not found.",
        )

