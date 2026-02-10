"""
记忆系统

管理角色的短期记忆和长期记忆。
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum


class MemoryType(Enum):
    """记忆类型"""
    EPISODIC = "episodic"       # 情节记忆（事件经历）
    SEMANTIC = "semantic"       # 语义记忆（知识、信息）
    EMOTIONAL = "emotional"     # 情感记忆（情绪体验）
    RELATIONAL = "relational"   # 关系记忆（与他人的互动）


class MemoryImportance(Enum):
    """记忆重要性"""
    TRIVIAL = 1         # 琐碎
    NORMAL = 2          # 普通
    SIGNIFICANT = 3     # 重要
    CRITICAL = 4        # 关键
    CORE = 5            # 核心（人生转折点）


@dataclass
class Memory:
    """单条记忆"""
    id: str                                 # 唯一标识
    content: str                            # 记忆内容
    type: MemoryType = MemoryType.EPISODIC
    importance: MemoryImportance = MemoryImportance.NORMAL
    
    # 时空标记
    chapter: int = 0                        # 发生章节
    location: str = ""                      # 发生地点
    
    # 关联
    related_characters: List[str] = field(default_factory=list)  # 相关角色ID
    related_events: List[str] = field(default_factory=list)      # 相关事件ID
    
    # 情感色彩
    emotion: str = ""                       # 情绪标签
    
    # 元数据
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    access_count: int = 0                   # 访问次数（用于遗忘机制）
    
    def access(self):
        """访问记忆（强化）"""
        self.access_count += 1


@dataclass
class MemoryBank:
    """记忆库"""
    
    # 短期记忆（最近几章的事件）
    short_term: List[Memory] = field(default_factory=list)
    short_term_limit: int = 20              # 短期记忆容量
    
    # 长期记忆（重要事件、核心经历）
    long_term: List[Memory] = field(default_factory=list)
    
    # 关系记忆（与其他角色的互动历史）
    relationships: Dict[str, List[Memory]] = field(default_factory=dict)
    
    def add_memory(self, memory: Memory):
        """添加记忆"""
        # 根据重要性决定存储位置
        if memory.importance.value >= MemoryImportance.SIGNIFICANT.value:
            self.long_term.append(memory)
        else:
            self.short_term.append(memory)
            self._manage_short_term()
        
        # 如果涉及其他角色，同时存入关系记忆
        for char_id in memory.related_characters:
            if char_id not in self.relationships:
                self.relationships[char_id] = []
            self.relationships[char_id].append(memory)
    
    def _manage_short_term(self):
        """管理短期记忆容量（遗忘机制）"""
        while len(self.short_term) > self.short_term_limit:
            # 移除访问最少的普通记忆
            self.short_term.sort(key=lambda m: (m.importance.value, m.access_count))
            forgotten = self.short_term.pop(0)
            # 如果被遗忘的记忆足够重要，转入长期
            if forgotten.importance.value >= MemoryImportance.NORMAL.value and forgotten.access_count > 3:
                self.long_term.append(forgotten)
    
    def recall_recent(self, limit: int = 5) -> List[Memory]:
        """回忆最近的记忆"""
        return self.short_term[-limit:]
    
    def recall_about(self, character_id: str, limit: int = 5) -> List[Memory]:
        """回忆与某角色相关的记忆"""
        if character_id not in self.relationships:
            return []
        memories = self.relationships[character_id][-limit:]
        for m in memories:
            m.access()
        return memories
    
    def recall_important(self, limit: int = 10) -> List[Memory]:
        """回忆重要记忆"""
        sorted_memories = sorted(self.long_term, key=lambda m: m.importance.value, reverse=True)
        return sorted_memories[:limit]
    
    def search(self, keyword: str, limit: int = 5) -> List[Memory]:
        """搜索记忆（简单关键词匹配）"""
        all_memories = self.short_term + self.long_term
        matched = [m for m in all_memories if keyword in m.content]
        for m in matched[:limit]:
            m.access()
        return matched[:limit]
    
    def to_context_string(self, limit: int = 10) -> str:
        """将记忆转换为上下文字符串（用于注入 Prompt）"""
        recent = self.recall_recent(limit // 2)
        important = self.recall_important(limit // 2)
        
        lines = ["[近期经历]"]
        for m in recent:
            lines.append(f"- {m.content}")
        
        lines.append("\n[重要记忆]")
        for m in important:
            lines.append(f"- {m.content}")
        
        return "\n".join(lines)
