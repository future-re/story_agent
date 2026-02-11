"""Writing skill runtime adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from .registry import SkillDocument, SkillRegistry

DEFAULT_CHAT_SYSTEM_PROMPT = """你是一位资深网络小说编辑和创作顾问。你的任务是：
1. 帮助用户构思故事点子、人物设定、世界观
2. 讨论剧情走向、冲突设计、爽点安排
3. 提供专业的网文创作建议
请用简洁专业的语言回答。"""


class WritingSkillRuntime:
    """将 SKILL.md 中的写作规范注入到模型调用链路。"""

    def __init__(
        self,
        *,
        registry: SkillRegistry,
        skill_name: str,
        enabled: bool = True,
    ):
        self.registry = registry
        self.skill_name = skill_name
        self.enabled = enabled
        self.document: Optional[SkillDocument] = registry.load(skill_name) if enabled else None
        self.learned_reference = self._load_learned_reference()

    @property
    def active(self) -> bool:
        return self.enabled and self.document is not None

    def build_system_prompt(self, task_type: str, fallback: str) -> str:
        if not self.active or self.document is None:
            return fallback

        brief = self._extract_core_guidelines(self.document.body)
        return (
            f"你正在执行技能：{self.document.name}\n"
            f"技能描述：{self.document.description}\n"
            f"当前任务类型：{task_type}\n\n"
            "必须遵守以下技能规范：\n"
            f"{brief}\n"
            f"{self._build_learned_reference_block()}\n"
            "如与用户新指令冲突，优先执行用户最新指令。"
        )

    def wrap_prompt(self, task_type: str, base_prompt: str) -> str:
        if not self.active:
            return base_prompt
        return (
            f"【技能任务】{task_type}\n"
            "请按技能中的流程：先提取约束，再给结构，最后给正文/结果。\n\n"
            f"{base_prompt}"
        )

    def build_outline_from_idea_prompt(self, idea: str) -> str:
        base_prompt = f"""请根据以下创意生成完整小说大纲，要求可直接用于章节创作。

【创意点子】
{idea}

输出结构建议：
1. 故事定位（题材、卖点、目标读者）
2. 角色与核心冲突
3. 三幕或多卷推进（每卷目标+关键转折）
4. 前10章章节提纲（每章1-2句）
5. 长线伏笔与结尾方向
"""
        return self.wrap_prompt("新写-大纲生成", base_prompt)

    def build_outline_from_chapters_prompt(
        self,
        *,
        chapters_content: str,
        chapter_count: int,
        word_count: int,
        next_chapter: int,
        plan_count: int,
    ) -> str:
        base_prompt = f"""请基于已有章节续写后续剧情大纲。

【已完成进度】
- 章节数：{chapter_count}
- 总字数：{word_count}
- 下一章：第{next_chapter}章

【最近章节内容】
{chapters_content}

请给出后续 {plan_count} 章规划，要求：
1. 明确主线推进与角色变化
2. 每章包含“目标/冲突/结尾钩子”
3. 保持与现有剧情连续且不OOC
"""
        return self.wrap_prompt("续写-后续大纲", base_prompt)

    def build_outline_expand_prompt(self, *, existing_outline: str, expansion_request: str) -> str:
        base_prompt = f"""请扩展以下已有大纲，满足用户要求。

【已有大纲】
{existing_outline}

【扩展要求】
{expansion_request}

输出：
1. 保留原框架后的新版本大纲
2. 标出新增或变更的关键点
3. 给出受影响章节建议
"""
        return self.wrap_prompt("改写-大纲扩展", base_prompt)

    def build_refine_volume_prompt(
        self,
        *,
        story_context: str,
        volume_title: str,
        volume_summary: str,
        chapter_count: int,
        word_count: int,
    ) -> str:
        base_prompt = f"""请将分卷概述细化为章节大纲。

【全书上下文】
{story_context}

【分卷标题】
{volume_title}

【分卷概述】
{volume_summary}

【目标规模】
- 章节数：{chapter_count}
- 字数：{word_count}

请输出每章的：章节标题、核心事件、冲突、钩子。
"""
        return self.wrap_prompt("扩写-分卷细化", base_prompt)

    def _extract_core_guidelines(self, body: str) -> str:
        text = str(body or "").strip()
        if not text:
            return "遵循用户需求，保持叙事连贯和角色一致。"

        target_headers = ("## 目标", "## 工作流", "## 续写规则", "## 润色规则", "## 质量检查清单")
        lines = text.splitlines()
        selected = []
        capture = False
        current_header = ""
        for line in lines:
            if line.startswith("## "):
                current_header = line.strip()
                capture = current_header in target_headers
            if capture:
                selected.append(line)
        merged = "\n".join(selected).strip()
        if not merged:
            merged = text
        return merged[:3500]

    def _load_learned_reference(self) -> str:
        if not self.document:
            return ""
        skill_dir = Path(self.document.path).parent
        learned_path = skill_dir / "references" / "learned_techniques.md"
        if not learned_path.exists():
            return ""
        try:
            return learned_path.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    def _build_learned_reference_block(self) -> str:
        learned = str(self.learned_reference or "").strip()
        if not learned:
            return ""
        return f"\n【语料学习到的附加技巧】\n{learned[:1800]}\n"
