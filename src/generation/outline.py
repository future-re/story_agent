"""
大纲生成器

支持三种模式：从零、从章节、从大纲。
"""
import os
from enum import Enum
from storage import StorageManager
from .prompts import PROMPT_FROM_IDEA, PROMPT_FROM_CHAPTERS, PROMPT_FROM_OUTLINE, PROMPT_REFINE_VOLUME


class OutlineMode(Enum):
    FROM_IDEA = "from_idea"
    FROM_CHAPTERS = "from_chapters"
    FROM_OUTLINE = "from_outline"


class OutlineGenerator:
    """大纲生成器"""
    
    def __init__(self, ai_client=None, storage: StorageManager = None):
        if ai_client is None:
            from models import get_client
            ai_client = get_client()
        self.ai = ai_client
        self.storage = storage or StorageManager()
    
    def from_idea(self, idea: str, save_to: str = None) -> str:
        """从点子生成大纲"""
        prompt = PROMPT_FROM_IDEA.format(idea=idea)
        response = self.ai.chat(prompt, system_prompt="你是资深网络小说总编。")
        outline = response if isinstance(response, str) else str(response)
        
        if save_to:
            self.storage.save_outline(save_to, outline)
        return outline
    
    def from_chapters(self, project_name: str, plan_count: int = 10) -> str:
        """从已有章节续写大纲"""
        chapters = self.storage.list_chapters(project_name)
        if not chapters:
            raise ValueError(f"项目 '{project_name}' 没有已写章节")
        
        info = self.storage.get_project_info(project_name)
        project_dir = info["project_dir"]
        
        chapters_content = []
        for f in chapters[-5:]:
            path = os.path.join(project_dir, "chapters", f)
            with open(path, 'r', encoding='utf-8') as file:
                content = file.read()
                if len(content) > 1000:
                    content = content[:500] + "\n...\n" + content[-500:]
                chapters_content.append(content)
        
        prompt = PROMPT_FROM_CHAPTERS.format(
            chapters_content="\n\n---\n\n".join(chapters_content),
            chapter_count=len(chapters),
            word_count=info["total_words"],
            next_chapter=len(chapters) + 1,
            plan_count=plan_count
        )
        
        response = self.ai.chat(prompt, system_prompt="你擅长续写和规划。")
        return response if isinstance(response, str) else str(response)
    
    def from_outline(self, existing_outline: str, expansion_request: str, save_to: str = None) -> str:
        """从已有大纲扩展"""
        prompt = PROMPT_FROM_OUTLINE.format(
            existing_outline=existing_outline,
            expansion_request=expansion_request
        )
        
        response = self.ai.chat(prompt, system_prompt="你擅长细化和扩展。")
        outline = response if isinstance(response, str) else str(response)
        
        if save_to:
            self.storage.save_outline(save_to, outline)
        return outline
    
    def refine_volume(self, story_context: str, volume_title: str,
                      volume_summary: str, chapter_count: int = 30, word_count: int = 100000) -> str:
        """将分卷概述细化为章节大纲"""
        prompt = PROMPT_REFINE_VOLUME.format(
            story_context=story_context,
            volume_title=volume_title,
            volume_summary=volume_summary,
            chapter_count=chapter_count,
            word_count=word_count
        )
        response = self.ai.chat(prompt, system_prompt="你擅长拆解故事线。")
        return response if isinstance(response, str) else str(response)
    
    def load_and_expand(self, project_name: str, expansion_request: str) -> str:
        """加载已有大纲并扩展"""
        project_dir = self.storage.get_project_dir(project_name)
        outline_path = os.path.join(project_dir, "大纲.txt")
        
        if not os.path.exists(outline_path):
            raise FileNotFoundError(f"项目 '{project_name}' 没有已保存的大纲")
        
        with open(outline_path, 'r', encoding='utf-8') as f:
            existing = f.read()
        
        return self.from_outline(existing, expansion_request, save_to=project_name)
