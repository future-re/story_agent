"""
仿真运行器

合并事件调度和状态同步，运行故事仿真。
"""
from typing import List, Dict, Optional, Any, TYPE_CHECKING
from dataclasses import dataclass, field

from .event import Event, EventQueue, EventStatus, EventType
from .world import WorldState, TimeUnit
from .memory import MemoryType, MemoryImportance

if TYPE_CHECKING:
    from agents.character import CharacterAgent, EmotionState


@dataclass
class SimulationResult:
    """仿真结果"""
    event: Event
    responses: Dict[str, str] = field(default_factory=dict)
    triggered_events: List[Event] = field(default_factory=list)


class SimulationRunner:
    """仿真运行器 - 事件调度 + 状态同步"""
    
    def __init__(self, world_state: WorldState, characters: Dict[str, 'CharacterAgent']):
        self.world_state = world_state
        self.characters = characters
        self.event_queue = EventQueue()
        self.results: List[SimulationResult] = []
    
    def push_event(self, event: Event):
        """添加事件"""
        self.event_queue.push(event)
    
    def run_next(self) -> Optional[SimulationResult]:
        """运行下一个事件"""
        event = self.event_queue.pop()
        if event is None:
            return None
        
        result = SimulationResult(event=event)
        
        # 收集参与者响应
        all_participants = set(event.participant_ids)
        if event.initiator_id:
            all_participants.add(event.initiator_id)
        
        for char_id in all_participants:
            if char_id in self.characters:
                agent = self.characters[char_id]
                context = self._build_context(event, char_id)
                response = agent.decide(event.description, context)
                result.responses[char_id] = response
        
        # 完成事件
        self.event_queue.complete_current(event, list(result.responses.values()))
        self.world_state.record_event(event.id)
        self.results.append(result)
        
        return result
    
    def run_all(self) -> List[SimulationResult]:
        """运行所有待处理事件"""
        results = []
        while self.event_queue.has_pending():
            result = self.run_next()
            if result:
                results.append(result)
        return results
    
    def sync_chapter_end(self, chapter_index: int):
        """章节结束，同步状态"""
        # 推进时间
        self.world_state.advance_time(TimeUnit.CHAPTER, f"第{chapter_index}章结束")
        
        # 为参与事件的角色添加记忆
        for result in self.results:
            event = result.event
            all_participants = set(event.participant_ids)
            if event.initiator_id:
                all_participants.add(event.initiator_id)
            
            for char_id in all_participants:
                if char_id in self.characters:
                    agent = self.characters[char_id]
                    importance = self._determine_importance(event)
                    agent.add_memory(
                        content=event.description,
                        memory_type=MemoryType.EPISODIC,
                        importance=importance,
                        related_characters=[p for p in all_participants if p != char_id],
                        event_id=event.id
                    )
        
        # 清空本章结果
        chapter_results = self.results.copy()
        self.results.clear()
        return chapter_results
    
    def _build_context(self, event: Event, character_id: str) -> str:
        """为角色构建事件上下文"""
        parts = []
        
        if event.location_id and event.location_id in self.world_state.locations:
            loc = self.world_state.locations[event.location_id]
            parts.append(f"地点：{loc.name}")
        
        if event.time_description:
            parts.append(f"时间：{event.time_description}")
        
        return "\n".join(parts)
    
    def _determine_importance(self, event: Event):
        """确定记忆重要性"""
        if event.type.value in ["encounter", "world_change"]:
            return MemoryImportance.SIGNIFICANT
        elif event.type.value == "discovery":
            return MemoryImportance.SIGNIFICANT
        return MemoryImportance.NORMAL
    
    def get_completed_events(self) -> List[Event]:
        """获取已完成事件"""
        return self.event_queue.get_history()
