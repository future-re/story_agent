"""
角色智能体

每个主要角色是一个独立的 Agent，拥有人格 Prompt、记忆和状态。
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, TYPE_CHECKING
from enum import Enum

from simulation.memory import MemoryBank, Memory, MemoryType, MemoryImportance
from schema.story import Character, CharacterRole

if TYPE_CHECKING:
    from simulation.event import Event


class EmotionState(Enum):
    """情绪状态"""
    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    FEARFUL = "fearful"
    SURPRISED = "surprised"
    DISGUSTED = "disgusted"
    ANXIOUS = "anxious"
    HOPEFUL = "hopeful"
    DETERMINED = "determined"


@dataclass
class CharacterState:
    """角色当前状态"""
    emotion: EmotionState = EmotionState.NEUTRAL
    emotion_intensity: float = 0.5
    current_goal: str = ""
    current_location: str = ""
    health: float = 1.0
    energy: float = 1.0
    active_traits: List[str] = field(default_factory=list)


@dataclass
class Relationship:
    """与其他角色的关系"""
    target_id: str
    type: str = "neutral"
    affection: float = 0.0
    trust: float = 0.0
    familiarity: float = 0.0
    notes: List[str] = field(default_factory=list)


class CharacterAgent:
    """角色智能体"""
    
    def __init__(self, character: Character, ai_client=None):
        self.character = character
        self.memory = MemoryBank()
        self.state = CharacterState()
        self.relationships: Dict[str, Relationship] = {}
        
        if ai_client is None:
            from models import get_client
            ai_client = get_client()
        self.ai = ai_client
    
    @property
    def id(self) -> str:
        return self.character.name
    
    @property
    def name(self) -> str:
        return self.character.name
    
    def get_personality_prompt(self) -> str:
        """生成人格系统提示词"""
        char = self.character
        
        prompt_parts = [
            f"你现在扮演角色「{char.name}」。",
            f"\n【性格特征】{char.personality}" if char.personality else "",
            f"\n【内心渴望】{char.desire}" if char.desire else "",
            f"\n【面临障碍】{char.obstacle}" if char.obstacle else "",
            f"\n【身世背景】{char.background}" if char.background else "",
        ]
        
        state = self.state
        prompt_parts.append(f"\n\n【当前状态】")
        prompt_parts.append(f"- 情绪：{state.emotion.value}（强度：{state.emotion_intensity:.1f}）")
        if state.current_goal:
            prompt_parts.append(f"- 当前目标：{state.current_goal}")
        
        memory_context = self.memory.to_context_string(limit=6)
        if memory_context:
            prompt_parts.append(f"\n\n{memory_context}")
        
        prompt_parts.append(f"\n\n【行为准则】")
        prompt_parts.append(f"- 你的一切言行必须符合上述性格特征")
        prompt_parts.append(f"- 根据你的渴望和障碍来决定行动")
        
        return "".join(prompt_parts)
    
    def decide(self, event_description: str, context: str = "") -> str:
        """面对事件做出决策"""
        system_prompt = self.get_personality_prompt()
        
        user_prompt = f"【当前情境】\n{event_description}"
        if context:
            user_prompt += f"\n\n【背景信息】\n{context}"
        user_prompt += f"\n\n请以「{self.name}」的身份，描述你会如何反应或行动。"
        
        response = self.ai.chat(user_prompt, system_prompt=system_prompt)
        return response if isinstance(response, str) else str(response)
    
    def update_emotion(self, emotion: EmotionState, intensity: float = 0.5):
        self.state.emotion = emotion
        self.state.emotion_intensity = max(0, min(1, intensity))
    
    def update_relationship(self, target_id: str, affection_delta: float = 0, trust_delta: float = 0):
        if target_id not in self.relationships:
            self.relationships[target_id] = Relationship(target_id=target_id)
        
        rel = self.relationships[target_id]
        rel.affection = max(-1, min(1, rel.affection + affection_delta))
        rel.trust = max(-1, min(1, rel.trust + trust_delta))
        rel.familiarity = min(1, rel.familiarity + 0.1)
    
    def add_memory(self, content: str, memory_type: MemoryType = MemoryType.EPISODIC,
                   importance: MemoryImportance = MemoryImportance.NORMAL,
                   related_characters: List[str] = None, event_id: str = None):
        memory = Memory(
            id=f"mem_{len(self.memory.short_term) + len(self.memory.long_term)}",
            content=content,
            type=memory_type,
            importance=importance,
            related_characters=related_characters or [],
            related_events=[event_id] if event_id else []
        )
        self.memory.add_memory(memory)
    
    def get_relationship_context(self, target_id: str) -> str:
        if target_id not in self.relationships:
            return f"你不认识{target_id}。"
        
        rel = self.relationships[target_id]
        memories = self.memory.recall_about(target_id, limit=3)
        
        context = f"关系：{rel.type}，好感：{rel.affection:.1f}，信任：{rel.trust:.1f}"
        if memories:
            context += " | 记忆：" + "; ".join(m.content[:30] for m in memories)
        
        return context
