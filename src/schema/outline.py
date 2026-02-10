"""
Story Agent 数据模型 - 大纲结构

定义大纲相关的数据结构：粗纲、细纲、章节大纲。
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class RoughOutline:
    """粗纲 - 一句话描述核心冲突"""
    idea: str = ""              # 用户原始点子
    logline: str = ""           # 提炼后的一句话粗纲
    protagonist: str = ""       # 主角是谁
    core_conflict: str = ""     # 核心冲突/困境
    hook: str = ""              # 吸引读者的钩子


@dataclass
class ChapterOutline:
    """章节细纲 - 基于"渴望/障碍/冲突/爽点"模型"""
    chapter_index: int = 0
    
    # 细纲核心要素（来自用户提供的方法论）
    desire: str = ""            # 角色渴望：主角想要达到什么目的
    obstacle: str = ""          # 遇到障碍：遇到了什么阻碍
    conflict: str = ""          # 核心冲突：谁与谁的对碰
    
    action_covert: str = ""     # 暗中行动
    action_overt: str = ""      # 明面行动
    
    emotion: str = ""           # 情感基调
    payoff: str = ""            # 爽点：如何给读者正向反馈
    
    # 展示要素
    reveal: str = ""            # 本章展示：主角的什么特质/能力


@dataclass
class VolumeOutline:
    """分卷大纲"""
    volume_index: int = 1
    title: str = ""
    word_count_target: int = 100000     # 目标字数
    summary: str = ""                   # 一两百字概述
    start_level: str = ""               # 主角起始等级/状态
    end_level: str = ""                 # 主角结束等级/状态
    chapters: List[ChapterOutline] = field(default_factory=list)


@dataclass
class DetailedOutline:
    """完整细纲 - 包含所有设定和规划"""
    # 基础信息
    genre: str = ""                     # 题材
    selling_points: List[str] = field(default_factory=list)  # 卖点
    target_audience: str = ""           # 读者定位
    
    # 设定
    world_setting: str = ""             # 环境设定
    power_system: str = ""              # 等级体系
    levels: List[str] = field(default_factory=list)
    cheat_code: str = ""                # 金手指
    
    # 人物
    protagonist_summary: str = ""       # 主角概述
    antagonist_summary: str = ""        # 反派概述
    
    # 主线
    main_plot: str = ""                 # 故事主线描述
    volumes: List[VolumeOutline] = field(default_factory=list)
