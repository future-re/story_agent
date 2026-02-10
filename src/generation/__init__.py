"""
Generation 模块 - 生成层

包含所有 Prompt 模板和生成器。
"""
from .prompts import PROMPT_FROM_IDEA, PROMPT_FROM_CHAPTERS, PROMPT_FROM_OUTLINE
from .outline import OutlineGenerator, OutlineMode
from .chapter import ChapterGenerator
from .thinking import PlotThinkingEngine

__all__ = [
    "PROMPT_FROM_IDEA", "PROMPT_FROM_CHAPTERS", "PROMPT_FROM_OUTLINE",
    "OutlineGenerator", "OutlineMode",
    "ChapterGenerator",
    "PlotThinkingEngine",
]

