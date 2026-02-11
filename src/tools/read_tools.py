"""Read-only toolset for project/story state access."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from utils.word_count import count_chinese_words


class StoryReadTools:
    """统一的读取工具，隔离业务层对底层存储细节的依赖。"""

    def __init__(self, storage: Any):
        self.storage = storage

    def list_projects(self) -> List[str]:
        base_dir = str(getattr(self.storage, "base_dir", "") or "").strip()
        if not base_dir or not os.path.exists(base_dir):
            return []
        return sorted(
            [
                name
                for name in os.listdir(base_dir)
                if os.path.isdir(os.path.join(base_dir, name))
            ]
        )

    def get_project_info(self, project_name: str) -> Dict[str, Any]:
        return self.storage.get_project_info(project_name)

    def list_chapters(self, project_name: str) -> List[str]:
        return self.storage.list_chapters(project_name)

    def load_world_state(self, project_name: str) -> Optional[Dict[str, Any]]:
        return self.storage.load_world_state(project_name)

    def load_outline_text(self, project_name: str, max_chars: int = 12000) -> str:
        outline_path = os.path.join(self.storage.get_project_dir(project_name), "大纲.txt")
        if not os.path.exists(outline_path):
            return ""
        try:
            with open(outline_path, "r", encoding="utf-8") as file:
                text = file.read()
            if max_chars > 0:
                return text[:max_chars]
            return text
        except OSError:
            return ""

    def load_style_reference(self, max_chars: int = 2000) -> str:
        ref_path = os.path.join(self.storage.base_dir, "reference.txt")
        if not os.path.exists(ref_path):
            return ""
        try:
            with open(ref_path, "r", encoding="utf-8") as file:
                text = file.read()
            if max_chars > 0:
                return text[:max_chars]
            return text
        except OSError:
            return ""

    def get_latest_chapter(self, project_name: str) -> Tuple[int, str, str, int]:
        chapters = self.storage.list_chapters(project_name)
        if not chapters:
            return (0, "", "", 0)

        latest = chapters[-1]
        try:
            chapter_index = int(latest.split("_")[0])
            chapter_title = latest.split("_", 1)[1].replace(".txt", "")
        except (IndexError, ValueError):
            chapter_index = len(chapters)
            chapter_title = "未命名"

        chapter_path = os.path.join(
            self.storage.get_project_dir(project_name),
            "chapters",
            latest,
        )
        try:
            with open(chapter_path, "r", encoding="utf-8") as file:
                content = file.read()
            return (chapter_index, chapter_title, content, count_chinese_words(content))
        except OSError:
            return (chapter_index, chapter_title, "", 0)

    def get_recent_chapter_fragments(
        self,
        project_name: str,
        *,
        limit: int = 5,
        preview_chars: int = 1000,
    ) -> List[str]:
        info = self.storage.get_project_info(project_name)
        project_dir = info["project_dir"]
        chapters = self.storage.list_chapters(project_name)
        fragments: List[str] = []
        for filename in chapters[-limit:]:
            path = os.path.join(project_dir, "chapters", filename)
            try:
                with open(path, "r", encoding="utf-8") as file:
                    content = file.read()
            except OSError:
                continue
            if preview_chars > 0 and len(content) > preview_chars:
                content = content[: preview_chars // 2] + "\n...\n" + content[-preview_chars // 2 :]
            fragments.append(content)
        return fragments
