import os
import sys
from typing import Any, Dict, Generator, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from interactive.workflow import StoryWriteWorkflow


class MockStorage:
    def __init__(self):
        self.saved: List[Dict[str, Any]] = []

    def save_chapter(self, project_name: str, chapter_index: int, title: str, content: str) -> str:
        self.saved.append(
            {
                "project_name": project_name,
                "chapter_index": chapter_index,
                "title": title,
                "content": content,
            }
        )
        return f"/tmp/{project_name}_{chapter_index:03d}.txt"


class MockThinkingEngine:
    def format_full_plan_display(self, plan: Dict[str, Any]) -> str:
        return f"规划摘要: {plan.get('summary', 'N/A')}"


class MockChapterGenerator:
    def __init__(self, with_plan: bool = True):
        self.with_plan = with_plan
        self.thinking_engine = MockThinkingEngine() if with_plan else None

    def prepare_writing(self) -> Generator[Any, None, Dict[str, Any]]:
        yield "准备中..."
        yield {
            "mode": "new",
            "chapter_num": 1,
            "chapter_title": "序章",
            "chapter_content": "",
            "chapter_len": 0,
            "target_words": 3000,
            "world_context": "世界",
            "outline_info": {"volume": "卷一", "phase": "开局"},
            "style_ref": "",
            "thinking_plan": {"summary": "先稳住冲突后推进主线"} if self.with_plan else None,
            "character_action_plan": None,
            "character_action_context": "",
        }

    def generate_from_plan(self, preparation: Dict[str, Any]) -> Generator[Any, None, Dict[str, Any]]:
        _ = preparation
        yield "第一段。"
        yield "第二段。"
        yield {
            "mode": "new",
            "chapter": 1,
            "title": "序章",
            "added_words": 3200,
            "total_words": 3200,
            "new_content": "第一段。第二段。",
            "full_text": "第一段。第二段。",
        }

    def update_world_state(self, new_content: str) -> Generator[Any, None, Dict[str, Any]]:
        _ = new_content
        yield "更新世界状态..."
        yield {"updated": True}


class MockBrokenGenerateChapterGenerator(MockChapterGenerator):
    def generate_from_plan(self, preparation: Dict[str, Any]) -> Generator[Any, None, Dict[str, Any]]:
        _ = preparation
        yield "只有文本，没有结构化结果。"


def test_write_workflow_requires_approval_and_persists_after_approve():
    storage = MockStorage()
    gen = MockChapterGenerator(with_plan=True)
    workflow = StoryWriteWorkflow(
        "测试项目",
        storage=storage,
        chapter_generator=gen,
        enable_langgraph=False,
    )

    pending_state = workflow.invoke(approved=False)
    assert pending_state.get("awaiting_approval") is True
    assert "规划摘要" in pending_state.get("plan_text", "")
    assert "saved_path" not in pending_state

    done_state = workflow.invoke(approved=True, preparation=pending_state.get("preparation"))
    assert done_state.get("error") is None
    assert done_state.get("saved_path") == "/tmp/测试项目_001.txt"
    assert done_state.get("result", {}).get("added_words") == 3200
    assert "更新世界状态" in "".join(done_state.get("world_update_logs", []))
    assert len(storage.saved) == 1


def test_write_workflow_auto_runs_when_no_plan():
    storage = MockStorage()
    gen = MockChapterGenerator(with_plan=False)
    workflow = StoryWriteWorkflow(
        "自动项目",
        storage=storage,
        chapter_generator=gen,
        enable_langgraph=False,
    )

    state = workflow.invoke(approved=False)
    assert state.get("awaiting_approval") is False
    assert state.get("saved_path") == "/tmp/自动项目_001.txt"
    assert state.get("result", {}).get("chapter") == 1
    assert len(storage.saved) == 1


def test_write_workflow_returns_error_when_generation_has_no_result():
    workflow = StoryWriteWorkflow(
        "坏结果项目",
        storage=MockStorage(),
        chapter_generator=MockBrokenGenerateChapterGenerator(with_plan=False),
        enable_langgraph=False,
    )

    state = workflow.invoke(approved=False)
    assert state.get("error") == "生成阶段未返回结果"
