"""Edit toolset for project/story persistence actions."""

from __future__ import annotations

from typing import Any, Dict


class StoryEditTools:
    """统一的编辑工具，封装写入与导出动作。"""

    def __init__(self, storage: Any):
        self.storage = storage

    def save_outline(self, project_name: str, outline_content: str) -> str:
        return self.storage.save_outline(project_name, outline_content)

    def save_story_blueprint(self, project_name: str, blueprint_data: Dict[str, Any]) -> str:
        return self.storage.save_story_blueprint(project_name, blueprint_data)

    def save_detailed_outline_json(self, project_name: str, outline_data: Dict[str, Any]) -> str:
        return self.storage.save_detailed_outline_json(project_name, outline_data)

    def save_world_state(self, project_name: str, state_data: Dict[str, Any]) -> str:
        return self.storage.save_world_state(project_name, state_data)

    def save_chapter(self, project_name: str, chapter_index: int, title: str, content: str) -> str:
        return self.storage.save_chapter(project_name, chapter_index, title, content)

    def export_full_novel(self, project_name: str) -> str:
        return self.storage.export_full_novel(project_name)
