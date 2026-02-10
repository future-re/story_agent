"""
事件系统

定义事件结构和事件队列，驱动故事推进。
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
import uuid


class EventType(Enum):
    """事件类型"""
    DIALOGUE = "dialogue"           # 对话
    ACTION = "action"               # 动作/行为
    ENCOUNTER = "encounter"         # 相遇/冲突
    DISCOVERY = "discovery"         # 发现/获知信息
    TRANSITION = "transition"       # 场景转换
    INTERNAL = "internal"           # 内心活动
    WORLD_CHANGE = "world_change"   # 世界变化（天灾、战争等）


class EventStatus(Enum):
    """事件状态"""
    PENDING = "pending"             # 待处理
    PROCESSING = "processing"       # 处理中
    COMPLETED = "completed"         # 已完成
    CANCELLED = "cancelled"         # 已取消


@dataclass
class Event:
    """事件"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    
    # 基本信息
    type: EventType = EventType.ACTION
    description: str = ""           # 事件描述
    
    # 参与者
    initiator_id: Optional[str] = None      # 发起者角色ID
    participant_ids: List[str] = field(default_factory=list)  # 参与者角色ID列表
    
    # 时空
    location_id: Optional[str] = None       # 发生地点
    time_description: str = ""              # 时间描述
    
    # 状态
    status: EventStatus = EventStatus.PENDING
    
    # 结果
    outcomes: List[str] = field(default_factory=list)   # 事件结果描述
    triggered_events: List[str] = field(default_factory=list)  # 触发的后续事件ID
    
    # 对角色的影响
    character_effects: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # 格式: {character_id: {"emotion": "愤怒", "relationship_change": {...}}}
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_participant(self, character_id: str):
        """添加参与者"""
        if character_id not in self.participant_ids:
            self.participant_ids.append(character_id)
    
    def set_effect(self, character_id: str, effect: Dict[str, Any]):
        """设置对角色的影响"""
        self.character_effects[character_id] = effect
    
    def complete(self, outcomes: List[str] = None):
        """完成事件"""
        self.status = EventStatus.COMPLETED
        if outcomes:
            self.outcomes = outcomes


@dataclass
class EventQueue:
    """事件队列"""
    pending: List[Event] = field(default_factory=list)
    processing: List[Event] = field(default_factory=list)
    completed: List[Event] = field(default_factory=list)
    
    def push(self, event: Event):
        """添加事件到队列"""
        event.status = EventStatus.PENDING
        self.pending.append(event)
    
    def pop(self) -> Optional[Event]:
        """取出下一个待处理事件"""
        if not self.pending:
            return None
        event = self.pending.pop(0)
        event.status = EventStatus.PROCESSING
        self.processing.append(event)
        return event
    
    def complete_current(self, event: Event, outcomes: List[str] = None):
        """完成当前处理的事件"""
        if event in self.processing:
            self.processing.remove(event)
            event.complete(outcomes)
            self.completed.append(event)
    
    def has_pending(self) -> bool:
        """是否有待处理事件"""
        return len(self.pending) > 0
    
    def get_history(self) -> List[Event]:
        """获取已完成的事件历史"""
        return self.completed.copy()
