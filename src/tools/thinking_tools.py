"""Thinking pipeline tools.

Small pure helpers used by generation/thinking modules to keep orchestration code thin.
"""

from __future__ import annotations

import hashlib
import json
from typing import Dict, Tuple


def clip_tail(text: str, max_chars: int) -> str:
    """Return the tail of text with bounded length."""
    if not text:
        return ""
    if max_chars <= 0:
        return text
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def normalize_thinking_mode(mode: str) -> str:
    """Normalize to auto/fast/deep with safe fallback."""
    normalized = (mode or "auto").strip().lower()
    if normalized not in {"auto", "fast", "deep"}:
        return "auto"
    return normalized


def resolve_thinking_mode(
    requested_mode: str,
    *,
    is_append: bool,
    chapter_num: int,
    previous_content: str,
) -> Tuple[str, str]:
    """Resolve the final thinking mode and return a short reason."""
    normalized = normalize_thinking_mode(requested_mode)
    if normalized in {"fast", "deep"}:
        return normalized, "由配置显式指定"

    if is_append:
        return "fast", "续写模式优先快速规划"
    if chapter_num <= 3:
        return "deep", "前期章节需要完整定调"
    if len(previous_content or "") > 7000:
        return "fast", "历史上下文较长，优先压缩规划"
    return "deep", "默认深度规划"


def build_thinking_cache_key(
    *,
    chapter_num: int,
    thinking_mode: str,
    outline_info: Dict[str, str],
    world_context: str,
    previous_content: str,
) -> str:
    """Build a stable hash key for thinking result cache."""
    payload = {
        "chapter_num": chapter_num,
        "thinking_mode": normalize_thinking_mode(thinking_mode),
        "outline_info": outline_info or {},
        "world_context": world_context or "",
        "previous_content": previous_content or "",
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha1(encoded.encode("utf-8")).hexdigest()
    return f"{chapter_num}:{thinking_mode}:{digest}"
