import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from skills_runtime import SkillRegistry, WritingSkillRuntime


def test_skill_registry_loads_writing_skill():
    registry = SkillRegistry.default()
    doc = registry.load("writing-skill")
    assert doc is not None
    assert doc.name == "writing-skill"
    assert "中文叙事写作与编辑技能" in doc.description
    assert "## 工作流" in doc.body


def test_writing_skill_runtime_builds_system_prompt_and_wrap_prompt():
    runtime = WritingSkillRuntime(
        registry=SkillRegistry.default(),
        skill_name="writing-skill",
        enabled=True,
    )
    assert runtime.active is True

    system_prompt = runtime.build_system_prompt("续写", "fallback")
    wrapped = runtime.wrap_prompt("新写-章节正文", "base-prompt")

    assert "当前任务类型：续写" in system_prompt
    assert "技能规范" in system_prompt
    assert "【技能任务】新写-章节正文" in wrapped
    assert "base-prompt" in wrapped


def test_writing_skill_runtime_fallback_when_skill_missing():
    runtime = WritingSkillRuntime(
        registry=SkillRegistry.default(),
        skill_name="missing-skill",
        enabled=True,
    )
    assert runtime.active is False
    assert runtime.build_system_prompt("新写", "fallback") == "fallback"
    assert runtime.wrap_prompt("任务", "base-prompt") == "base-prompt"
