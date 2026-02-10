"""
世界状态管理

管理故事世界的全局状态：时间线、地点、势力关系等。
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum


class TimeUnit(Enum):
    """时间单位"""
    MOMENT = "moment"       # 瞬间（对话、动作）
    SCENE = "scene"         # 场景（一个连续场景）
    CHAPTER = "chapter"     # 章节
    ARC = "arc"             # 卷/篇章
    

@dataclass
class TimePoint:
    """时间点"""
    chapter: int = 1                    # 章节号
    scene: int = 1                      # 场景号
    description: str = ""               # 时间描述（如"清晨"、"三天后"）
    absolute_order: int = 0             # 绝对顺序（用于排序）
    
    def advance(self, unit: TimeUnit = TimeUnit.SCENE):
        """推进时间"""
        if unit == TimeUnit.SCENE:
            self.scene += 1
        elif unit == TimeUnit.CHAPTER:
            self.chapter += 1
            self.scene = 1
        self.absolute_order += 1


@dataclass
class Location:
    """地点/场景"""
    id: str                             # 唯一标识
    name: str                           # 名称
    description: str = ""               # 描述
    parent_id: Optional[str] = None     # 上级地点（如：城市 -> 街道 -> 酒楼）
    attributes: Dict[str, Any] = field(default_factory=dict)  # 自定义属性


@dataclass
class Faction:
    """势力/阵营"""
    id: str
    name: str
    description: str = ""
    leader_id: Optional[str] = None     # 领导者角色ID
    members: List[str] = field(default_factory=list)  # 成员角色ID列表
    relationships: Dict[str, str] = field(default_factory=dict)  # 与其他势力的关系


@dataclass
class WorldState:
    """世界状态 - 全局状态容器"""
    
    # 时间
    current_time: TimePoint = field(default_factory=TimePoint)
    
    # 空间
    locations: Dict[str, Location] = field(default_factory=dict)
    
    # 势力
    factions: Dict[str, Faction] = field(default_factory=dict)
    
    # 全局变量（灵活扩展）
    global_vars: Dict[str, Any] = field(default_factory=dict)
    
    # 历史记录
    event_history: List[str] = field(default_factory=list)  # 事件ID列表
    
    def add_location(self, location: Location):
        """添加地点"""
        self.locations[location.id] = location
    
    def add_faction(self, faction: Faction):
        """添加势力"""
        self.factions[faction.id] = faction
    
    def set_var(self, key: str, value: Any):
        """设置全局变量"""
        self.global_vars[key] = value
    
    def get_var(self, key: str, default: Any = None) -> Any:
        """获取全局变量"""
        return self.global_vars.get(key, default)
    
    def advance_time(self, unit: TimeUnit = TimeUnit.SCENE, description: str = ""):
        """推进时间"""
        self.current_time.advance(unit)
        if description:
            self.current_time.description = description
    
    def record_event(self, event_id: str):
        """记录事件到历史"""
        self.event_history.append(event_id)
