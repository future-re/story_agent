"""
Story Agent 数据模型 - 故事结构

定义故事项目中的核心实体：角色、世界观设定、故事项目。
"""
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class CharacterRole(Enum):
    """角色类型"""
    PROTAGONIST = "protagonist"  # 主角
    ANTAGONIST = "antagonist"    # 反派
    SUPPORTING = "supporting"    # 配角
    MENTOR = "mentor"            # 导师
    LOVE_INTEREST = "love_interest"  # 情感线角色


@dataclass
class CultivationRank:
    """修炼等级"""
    name: str                           # 等级名 (如: 厉鬼)
    level_index: int                    # 排序 (1, 2, 3...)
    description: str = ""               # 描述/特征
    abilities: List[str] = field(default_factory=list)  # 该等级典型能力


@dataclass
class CultivationSystem:
    """修炼体系"""
    name: str                           # 体系名 (如: 幽冥鬼道)
    ranks: List[CultivationRank] = field(default_factory=list) # 等级列表
    description: str = ""               # 体系描述
    methods: List[str] = field(default_factory=list)      # 常见功法
    

@dataclass
class CharacterRelationship:
    """角色关系"""
    target: str          # 目标角色名
    relation_type: str   # 关系类型 (e.g. 父亲, 仇敌, 盟友)
    description: str = "" # 具体描述

@dataclass
class Character:
    """角色定义"""
    name: str                           # 姓名
    role: CharacterRole                 # 角色类型
    personality: str = ""               # 性格特征
    desire: str = ""                    # 渴望（动机）
    obstacle: str = ""                  # 障碍
    background: str = ""                # 身世背景
    relationships: List[CharacterRelationship] = field(default_factory=list)  # 与其他角色的关系
    
    # 修仙特定属性
    level: str = "凡人"                 # 境界/等级
    abilities: List[str] = field(default_factory=list)      # 功法/技能
    items: List[str] = field(default_factory=list)          # 法宝/物品


@dataclass
class WorldSetting:
    """世界观设定"""
    environment: str = ""               # 环境设定（故事发生的背景）
    power_system: str = ""              # 等级体系/力量体系
    levels: List[str] = field(default_factory=list)  # 等级列表
    cheat_code: str = ""                # 金手指（主角特殊能力）
    factions: List[str] = field(default_factory=list)  # 势力/阵营
    
    # 世界宝藏/传承
    known_methods: List[str] = field(default_factory=list)  # 知名功法
    known_artifacts: List[str] = field(default_factory=list) # 知名法宝
    
    # 结构化修炼体系
    cultivation_systems: List[CultivationSystem] = field(default_factory=list)


@dataclass
class Chapter:
    """章节"""
    index: int                          # 章节序号
    title: str = ""                     # 章节标题
    summary: str = ""                   # 章节概述
    word_count_target: int = 3000       # 目标字数
    content: str = ""                   # 正文内容（后续填充）


@dataclass
class StoryProject:
    """故事项目 - 整合所有故事元素"""
    title: str = "未命名"                # 书名
    genre: str = ""                     # 题材（玄幻、都市、言情等）
    target_audience: str = ""           # 目标读者群
    selling_points: List[str] = field(default_factory=list)  # 卖点/特色
    logline: str = ""                   # 一句话粗纲
    
    world: WorldSetting = field(default_factory=WorldSetting)
    characters: List[Character] = field(default_factory=list)
    chapters: List[Chapter] = field(default_factory=list)
    
    # 元数据
    created_at: str = ""
    updated_at: str = ""
    
    def add_character(self, character: Character):
        """添加角色"""
        self.characters.append(character)
    
    def add_chapter(self, chapter: Chapter):
        """添加章节"""
        self.chapters.append(chapter)
    
    def get_protagonist(self) -> Optional[Character]:
        """获取主角"""
        for char in self.characters:
            if char.role == CharacterRole.PROTAGONIST:
                return char
        return None
