"""
叙述者智能体

将仿真结果转化为文学化的小说文本。
"""
from typing import List, Dict, Optional, TYPE_CHECKING
from dataclasses import dataclass
from enum import Enum

if TYPE_CHECKING:
    from simulation.runner import SimulationResult


class NarrativeStyle(Enum):
    """叙事风格"""
    FIRST_PERSON = "first_person"
    THIRD_LIMITED = "third_limited"
    THIRD_OMNISCIENT = "third_omniscient"


class NarrativeTone(Enum):
    """叙事基调"""
    SERIOUS = "serious"
    HUMOROUS = "humorous"
    DARK = "dark"
    LIGHT = "light"
    EPIC = "epic"
    INTIMATE = "intimate"


@dataclass
class NarratorConfig:
    """叙述者配置"""
    style: NarrativeStyle = NarrativeStyle.THIRD_LIMITED
    tone: NarrativeTone = NarrativeTone.SERIOUS
    pov_character: Optional[str] = None
    word_count_target: int = 3000


class Narrator:
    """叙述者 - 将仿真结果转化为小说文本"""
    
    def __init__(self, config: NarratorConfig = None, ai_client=None):
        self.config = config or NarratorConfig()
        
        if ai_client is None:
            from models import get_client
            ai_client = get_client()
        self.ai = ai_client
    
    def get_system_prompt(self) -> str:
        style_desc = {
            NarrativeStyle.FIRST_PERSON: "使用第一人称'我'来叙述，以主角的视角和内心感受来描写。",
            NarrativeStyle.THIRD_LIMITED: "使用第三人称叙述，紧跟主要角色的视角。",
            NarrativeStyle.THIRD_OMNISCIENT: "使用第三人称全知视角，可以展示任何角色的内心想法。"
        }
        
        tone_desc = {
            NarrativeTone.SERIOUS: "保持严肃认真的基调。",
            NarrativeTone.HUMOROUS: "加入幽默元素。",
            NarrativeTone.DARK: "营造黑暗压抑的氛围。",
            NarrativeTone.LIGHT: "保持轻松愉快的氛围。",
            NarrativeTone.EPIC: "使用宏大的叙事手法，营造史诗感。",
            NarrativeTone.INTIMATE: "细腻描写情感，让读者产生共鸣。"
        }
        
        return f"""你是一位资深网络小说作家。

【叙事风格】{style_desc.get(self.config.style)}
【叙事基调】{tone_desc.get(self.config.tone)}
【目标字数】约 {self.config.word_count_target} 字

【写作要求】
1. 文笔流畅，善用细节描写
2. 对话符合角色性格
3. 在关键处制造悬念或爽点"""
    
    def narrate_chapter(self, chapter_outline: str, events_material: str) -> str:
        """生成章节正文"""
        user_prompt = f"""请根据以下素材撰写小说正文。

【章节大纲】
{chapter_outline}

【事件素材】
{events_material}

请开始创作："""
        
        response = self.ai.chat(user_prompt, system_prompt=self.get_system_prompt())
        return response if isinstance(response, str) else str(response)
    
    def narrate_scene(self, scene_description: str, character_responses: Dict[str, str]) -> str:
        """生成单个场景"""
        responses_text = "\n".join([f"【{name}】{resp}" for name, resp in character_responses.items()])
        
        user_prompt = f"""请创作这个场景（约500-800字）：

【场景】{scene_description}

【角色反应】
{responses_text}"""
        
        response = self.ai.chat(user_prompt, system_prompt=self.get_system_prompt())
        return response if isinstance(response, str) else str(response)
    
    def polish_text(self, raw_text: str, focus: str = "流畅度") -> str:
        """润色文本"""
        user_prompt = f"请对以下文本进行润色，重点关注「{focus}」。\n\n【原文】\n{raw_text}"
        response = self.ai.chat(user_prompt, system_prompt="你是经验丰富的文字编辑。")
        return response if isinstance(response, str) else str(response)
