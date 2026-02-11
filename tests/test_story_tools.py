import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from storage import StorageManager
from tools import StoryEditTools, StoryReadTools


def test_read_and_edit_tools_roundtrip(tmp_path):
    storage = StorageManager(str(tmp_path))
    read_tools = StoryReadTools(storage)
    edit_tools = StoryEditTools(storage)

    project = "工具测试"
    edit_tools.save_outline(project, "这是测试大纲")
    edit_tools.save_world_state(project, {"world": {"environment": "测试环境"}, "characters": []})
    chapter_path = edit_tools.save_chapter(project, 1, "开篇", "第一段内容")

    assert os.path.exists(chapter_path)
    assert "这是测试大纲" in read_tools.load_outline_text(project)
    assert read_tools.load_world_state(project)["world"]["environment"] == "测试环境"

    latest_num, latest_title, latest_content, latest_words = read_tools.get_latest_chapter(project)
    assert latest_num == 1
    assert latest_title == "开篇"
    assert "第一段内容" in latest_content
    assert latest_words > 0


def test_read_tools_list_projects(tmp_path):
    storage = StorageManager(str(tmp_path))
    edit_tools = StoryEditTools(storage)
    read_tools = StoryReadTools(storage)

    edit_tools.save_outline("A项目", "a")
    edit_tools.save_outline("B项目", "b")
    projects = read_tools.list_projects()

    assert any(name.startswith("A") for name in projects)
    assert any(name.startswith("B") for name in projects)
