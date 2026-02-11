"""
Story Agent - 统一入口

提供简洁的 API 使用所有功能。
"""
from typing import Dict, List, Optional

from models import get_client
from storage import StorageManager
from agents import StoryPlanner, CharacterAgent, Narrator
from generation import OutlineGenerator, ChapterGenerator
from simulation import WorldState, Event, EventType, SimulationRunner
from schema.story import Character, CharacterRole
from config import config


class StoryAgent:
    """Story Agent 统一入口"""
    
    def __init__(self, project_name: str = "我的小说", output_dir: str = "./output"):
        self.project_name = project_name
        self.storage = StorageManager(output_dir)
        self.ai = get_client(config.model_name)
        
        # 核心组件
        self.planner = StoryPlanner(project_name, self.storage, self.ai)
        self.outline_gen = OutlineGenerator(self.ai, self.storage)
        self.chapter_gen = ChapterGenerator(project_name, self.ai, self.storage)
        self.narrator = Narrator(ai_client=self.ai)
        
        # 仿真组件
        self.world = WorldState()
        self.characters: Dict[str, CharacterAgent] = {}
        self.runner: Optional[SimulationRunner] = None
    
    # ==================== 大纲 ====================
    
    def create_outline(self, idea: str) -> str:
        """从点子创建大纲"""
        return self.outline_gen.from_idea(idea, save_to=self.project_name)
    
    def expand_outline(self, request: str) -> str:
        """扩展大纲"""
        return self.outline_gen.load_and_expand(self.project_name, request)
    
    def continue_outline(self, plan_count: int = 10) -> str:
        """从已有章节续写大纲"""
        return self.outline_gen.from_chapters(self.project_name, plan_count)

    def create_story_pipeline(self, idea: str, chapter_count: int = 10) -> Dict:
        """按五阶段流程初始化故事基础（粗纲/细纲/世界/角色）。"""
        return self.outline_gen.build_story_pipeline(
            idea=idea,
            project_name=self.project_name,
            chapter_count=chapter_count,
        )
    
    # ==================== 角色 ====================
    
    def add_character(self, name: str, role: str = "supporting",
                      personality: str = "", desire: str = "", 
                      obstacle: str = "", background: str = "") -> CharacterAgent:
        """添加角色"""
        role_enum = CharacterRole(role) if role in [r.value for r in CharacterRole] else CharacterRole.SUPPORTING
        char = Character(
            name=name, role=role_enum, personality=personality,
            desire=desire, obstacle=obstacle, background=background
        )
        agent = CharacterAgent(char, self.ai)
        self.characters[name] = agent
        
        # 保存角色档案
        self.storage.save_character_profile(self.project_name, name, {
            "角色类型": role,
            "性格": personality,
            "渴望": desire,
            "障碍": obstacle,
            "背景": background
        })
        
        return agent
    
    # ==================== 章节 ====================
    
    def write_chapter(self, chapter_index: int, title: str, 
                      context: str, previous_summary: str = "") -> str:
        """生成章节"""
        return self.chapter_gen.generate_full(chapter_index, title, context, previous_summary)
    
    # ==================== 仿真 ====================
    
    def init_simulation(self):
        """初始化仿真器"""
        self.runner = SimulationRunner(self.world, self.characters)
    
    def add_event(
        self,
        description: str,
        event_type: str = "action",
        initiator: Optional[str] = None,
        participants: Optional[List[str]] = None,
    ):
        """添加事件"""
        if self.runner is None:
            self.init_simulation()

        normalized_type = event_type.lower()
        try:
            event_enum = EventType(normalized_type)
        except ValueError:
            event_enum = EventType.ACTION

        event = Event(
            type=event_enum,
            description=description,
            initiator_id=initiator,
            participant_ids=participants or []
        )
        self.runner.push_event(event)
        return event
    
    def run_simulation(self):
        """运行仿真"""
        if self.runner is None:
            raise ValueError("请先调用 init_simulation()")
        return self.runner.run_all()
    
    # ==================== 导出 ====================
    
    def export(self) -> str:
        """导出完整小说"""
        return self.storage.export_full_novel(self.project_name)
    
    def status(self) -> dict:
        """获取项目状态"""
        return self.storage.get_project_info(self.project_name)


def quick_start(idea: str, project_name: str = "我的小说") -> StoryAgent:
    """快速开始一个项目"""
    agent = StoryAgent(project_name)
    agent.create_outline(idea)
    return agent
