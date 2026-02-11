"""Models 模块 - AI 模型适配层。"""

from typing import Optional

from config import config

from .base import BaseModel
from .deepseek import DeepSeekModel
from .glm import GLMModel
from .kimi import KimiModel


def _normalize_model_name(model_name: Optional[str]) -> str:
    """规范化模型名；为空时回退到全局配置。"""
    return (model_name or config.model_name or "deepseek").strip()


def get_client(model_name: Optional[str] = None):
    """获取内容生成模型客户端。"""
    resolved_name = _normalize_model_name(model_name)
    lowered = resolved_name.lower()

    if lowered == "deepseek":
        return DeepSeekModel()
    if "deepseek" in lowered:
        return DeepSeekModel(model_name=resolved_name)
    if lowered == "glm":
        return GLMModel()
    if "glm" in lowered:
        return GLMModel(model_name=resolved_name)
    if "zhipu" in lowered or "bigmodel" in lowered:
        return GLMModel(model_name=resolved_name)
    if "moonshot" in lowered or "kimi" in lowered:
        return KimiModel(model_name=resolved_name)
    raise ValueError(f"不支持的模型: {resolved_name}")


def get_thinking_client():
    """获取思考模型客户端（用于剧情分析）。"""
    return get_client(config.thinking_model)


__all__ = [
    "BaseModel",
    "DeepSeekModel",
    "GLMModel",
    "KimiModel",
    "get_client",
    "get_thinking_client",
]
