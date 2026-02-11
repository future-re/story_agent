"""Runtime loaders/adapters for local skills."""

from .miner import NovelSample, NovelSkillMiner
from .registry import SkillDocument, SkillRegistry
from .router import SkillRoutingDecision, WritingSkillRouter
from .writing import DEFAULT_CHAT_SYSTEM_PROMPT, WritingSkillRuntime

__all__ = [
    "NovelSample",
    "NovelSkillMiner",
    "SkillDocument",
    "SkillRegistry",
    "SkillRoutingDecision",
    "WritingSkillRouter",
    "WritingSkillRuntime",
    "DEFAULT_CHAT_SYSTEM_PROMPT",
]
