"""Automatic skill routing for writing-related tasks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from .registry import SkillRegistry
from .writing import WritingSkillRuntime


@dataclass(frozen=True)
class SkillRoutingDecision:
    """Routing result for a writing task."""

    task: str
    skill_name: str
    reason: str


class WritingSkillRouter:
    """Map task categories to specialized writing skills."""

    def __init__(
        self,
        *,
        registry: SkillRegistry,
        outline_skill_name: str = "outline-skill",
        continuation_skill_name: str = "continuation-skill",
        rewrite_skill_name: str = "rewrite-skill",
        fallback_skill_name: str = "writing-skill",
        enabled: bool = True,
    ):
        self.registry = registry
        self.enabled = enabled
        self.outline_skill_name = outline_skill_name
        self.continuation_skill_name = continuation_skill_name
        self.rewrite_skill_name = rewrite_skill_name
        self.fallback_skill_name = fallback_skill_name
        self._runtime_cache: Dict[str, WritingSkillRuntime] = {}

    def route(self, task: str, user_text: str = "") -> WritingSkillRuntime:
        decision = self.route_decision(task, user_text=user_text)
        return self._runtime_for(decision.skill_name)

    def route_decision(self, task: str, user_text: str = "") -> SkillRoutingDecision:
        normalized_task = str(task or "").strip().lower()
        text = str(user_text or "").strip().lower()

        if normalized_task in {"outline-from-idea", "outline-refine-volume"}:
            return SkillRoutingDecision(normalized_task, self.outline_skill_name, "大纲规划任务")
        if normalized_task in {"outline-continue", "chapter-generate", "chapter-append"}:
            return SkillRoutingDecision(normalized_task, self.continuation_skill_name, "续写推进任务")
        if normalized_task in {"outline-expand", "rewrite", "polish", "style-rewrite"}:
            return SkillRoutingDecision(normalized_task, self.rewrite_skill_name, "改写润色任务")
        if normalized_task == "chat-consult":
            if any(keyword in text for keyword in ("续写", "接着写", "下一章", "后续")):
                return SkillRoutingDecision(normalized_task, self.continuation_skill_name, "咨询中命中续写关键词")
            if any(keyword in text for keyword in ("润色", "改写", "重写", "风格", "压缩", "扩写")):
                return SkillRoutingDecision(normalized_task, self.rewrite_skill_name, "咨询中命中改写关键词")
            if any(keyword in text for keyword in ("大纲", "主线", "分卷", "设定", "结构")):
                return SkillRoutingDecision(normalized_task, self.outline_skill_name, "咨询中命中大纲关键词")

        return SkillRoutingDecision(normalized_task or "unknown", self.fallback_skill_name, "回退通用写作技能")

    def describe_active_skills(self) -> Dict[str, bool]:
        return {
            self.outline_skill_name: self._runtime_for(self.outline_skill_name).active,
            self.continuation_skill_name: self._runtime_for(self.continuation_skill_name).active,
            self.rewrite_skill_name: self._runtime_for(self.rewrite_skill_name).active,
            self.fallback_skill_name: self._runtime_for(self.fallback_skill_name).active,
        }

    def _runtime_for(self, skill_name: str) -> WritingSkillRuntime:
        normalized = str(skill_name or "").strip() or self.fallback_skill_name
        if normalized not in self._runtime_cache:
            self._runtime_cache[normalized] = WritingSkillRuntime(
                registry=self.registry,
                skill_name=normalized,
                enabled=self.enabled,
            )

        runtime = self._runtime_cache[normalized]
        if runtime.active:
            return runtime

        fallback = self._runtime_cache.get(self.fallback_skill_name)
        if fallback is None:
            fallback = WritingSkillRuntime(
                registry=self.registry,
                skill_name=self.fallback_skill_name,
                enabled=self.enabled,
            )
            self._runtime_cache[self.fallback_skill_name] = fallback
        return fallback
