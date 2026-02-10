"""
规划器智能体

按照"粗纲 -> 设定 -> 细纲"的流程编排故事创作。
"""
from typing import Optional
from storage import StorageManager
from schema.outline import RoughOutline, DetailedOutline


class StoryPlanner:
    """剧情规划器"""
    
    def __init__(self, project_name: str = "未命名", storage: StorageManager = None, ai_client=None):
        self.project_name = project_name
        self.storage = storage or StorageManager()
        
        if ai_client is None:
            from models import get_client
            ai_client = get_client()
        self.ai = ai_client
        
        self._rough_outline: Optional[RoughOutline] = None
        self._detailed_outline: Optional[DetailedOutline] = None
    
    def create_outline_from_idea(self, idea: str) -> str:
        """从点子生成大纲"""
        from generation import OutlineGenerator
        gen = OutlineGenerator(ai_client=self.ai, storage=self.storage)
        outline = gen.from_idea(idea, save_to=self.project_name)
        return outline
    
    def expand_outline(self, expansion_request: str) -> str:
        """扩展已有大纲"""
        from generation import OutlineGenerator
        gen = OutlineGenerator(ai_client=self.ai, storage=self.storage)
        return gen.load_and_expand(self.project_name, expansion_request)
    
    def continue_from_chapters(self, plan_count: int = 10) -> str:
        """从已有章节续写大纲"""
        from generation import OutlineGenerator
        gen = OutlineGenerator(ai_client=self.ai, storage=self.storage)
        return gen.from_chapters(self.project_name, plan_count)
    
    def save_progress(self) -> str:
        """保存当前进度"""
        return self.storage.get_project_dir(self.project_name)
    
    def get_status(self) -> dict:
        """获取当前规划状态"""
        info = self.storage.get_project_info(self.project_name)
        return {
            "project_name": self.project_name,
            "chapter_count": info.get("chapter_count", 0),
            "total_words": info.get("total_words", 0)
        }
