import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from skills_runtime import SkillRegistry, WritingSkillRouter


def test_skill_router_routes_core_tasks():
    router = WritingSkillRouter(
        registry=SkillRegistry.default(),
        outline_skill_name="outline-skill",
        continuation_skill_name="continuation-skill",
        rewrite_skill_name="rewrite-skill",
        fallback_skill_name="writing-skill",
        enabled=True,
    )

    assert router.route_decision("outline-from-idea").skill_name == "outline-skill"
    assert router.route_decision("outline-continue").skill_name == "continuation-skill"
    assert router.route_decision("chapter-generate").skill_name == "continuation-skill"
    assert router.route_decision("outline-expand").skill_name == "rewrite-skill"


def test_skill_router_routes_chat_consult_by_keywords():
    router = WritingSkillRouter(
        registry=SkillRegistry.default(),
        outline_skill_name="outline-skill",
        continuation_skill_name="continuation-skill",
        rewrite_skill_name="rewrite-skill",
        fallback_skill_name="writing-skill",
        enabled=True,
    )

    assert router.route_decision("chat-consult", user_text="帮我续写下一章").skill_name == "continuation-skill"
    assert router.route_decision("chat-consult", user_text="帮我润色并改写这段").skill_name == "rewrite-skill"
    assert router.route_decision("chat-consult", user_text="给我做分卷大纲").skill_name == "outline-skill"


def test_skill_router_fallbacks_when_specific_skill_missing():
    router = WritingSkillRouter(
        registry=SkillRegistry.default(),
        outline_skill_name="missing-outline-skill",
        continuation_skill_name="missing-continuation-skill",
        rewrite_skill_name="missing-rewrite-skill",
        fallback_skill_name="writing-skill",
        enabled=True,
    )
    runtime = router.route("outline-from-idea")
    assert runtime.active is True
    assert runtime.skill_name == "writing-skill"
