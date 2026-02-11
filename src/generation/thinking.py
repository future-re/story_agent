"""
剧情思考引擎 - 使用推理模型分析剧情后再生成内容
"""
from collections import OrderedDict
import copy
from typing import Dict, Any, Optional, Generator, List
import json
try:
    from json_repair import repair_json
except ImportError:
    repair_json = None

from config import config
from tools import build_thinking_cache_key, clip_tail, normalize_thinking_mode


class PlotThinkingEngine:
    """
    剧情思考引擎
    
    使用 DeepSeek R1 等推理模型深度分析当前剧情，
    输出结构化的章节规划供生成模型使用。
    """
    
    def __init__(self, ai_client=None, debug: bool = False, cache_size: Optional[int] = None):
        """
        初始化思考引擎
        
        :param ai_client: 推理模型客户端 (应为 deepseek-reasoner)
        """
        if ai_client is None:
            from models import get_thinking_client
            ai_client = get_thinking_client()
        self.ai = ai_client
        self.debug = debug
        self.cache_size = max(1, cache_size or config.thinking_cache_size)
        self.previous_context_chars = max(500, config.thinking_previous_context_chars)
        self.world_context_chars = max(500, config.thinking_world_context_chars)
        self.quality_retry_count = max(0, config.thinking_quality_retry)
        self.deep_min_storyboard_shots = max(2, config.thinking_deep_min_storyboard_shots)
        self.fast_min_storyboard_shots = max(1, config.thinking_fast_min_storyboard_shots)
        self._plan_cache: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()

    def _debug(self, message: str):
        if self.debug:
            print(f"[DEBUG] {message}")

    def _get_cached_plan(self, cache_key: str) -> Optional[Dict[str, Any]]:
        cached = self._plan_cache.get(cache_key)
        if cached is None:
            return None
        self._plan_cache.move_to_end(cache_key)
        return copy.deepcopy(cached)

    def _save_cached_plan(self, cache_key: str, plan: Dict[str, Any]):
        self._plan_cache[cache_key] = copy.deepcopy(plan)
        self._plan_cache.move_to_end(cache_key)
        while len(self._plan_cache) > self.cache_size:
            self._plan_cache.popitem(last=False)

    def _stream_collect_response(self, prompt: str, system_prompt: str) -> str:
        """Collect full response text from stream API."""
        response_text = ""
        for chunk in self.ai.stream_chat(prompt, system_prompt=system_prompt):
            response_text += chunk
        return response_text

    @staticmethod
    def _extract_blueprint(plan: Dict[str, Any]) -> Dict[str, Any]:
        return plan.get("chapter_blueprint", plan.get("chapter_plan", {}))

    @staticmethod
    def _extract_storyboard(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        blueprint = plan.get("chapter_blueprint", plan.get("chapter_plan", {}))
        storyboard = blueprint.get("storyboard", blueprint.get("scenes", []))
        return storyboard if isinstance(storyboard, list) else []

    @staticmethod
    def _extract_conflicts(blueprint: Dict[str, Any]) -> List[Dict[str, Any]]:
        conflicts = blueprint.get("conflict_escalation", blueprint.get("conflicts", []))
        return conflicts if isinstance(conflicts, list) else []

    def _validate_plan_quality(self, plan: Dict[str, Any], thinking_mode: str) -> List[str]:
        """Return quality issues; empty means pass."""
        issues: List[str] = []
        blueprint = self._extract_blueprint(plan)
        storyboard = self._extract_storyboard(plan)
        min_shots = self.fast_min_storyboard_shots if thinking_mode == "fast" else self.deep_min_storyboard_shots

        if len(storyboard) < min_shots:
            issues.append(f"分镜数量不足：当前{len(storyboard)}，至少{min_shots}")

        weak_shots: List[str] = []
        for idx, shot in enumerate(storyboard, 1):
            action_beats = shot.get("action_beats", [])
            dialogue_script = shot.get("dialogue_script", [])
            key_actions = shot.get("key_actions", [])
            if not action_beats and not dialogue_script and not key_actions:
                weak_shots.append(f"{idx}(无动作/对白)")
            if not shot.get("purpose"):
                weak_shots.append(f"{idx}(无叙事目的)")
        if weak_shots:
            issues.append("分镜可执行性不足：" + "、".join(weak_shots[:6]))

        plot_analysis = plan.get("plot_analysis", {})
        pre_context = plot_analysis.get("pre_chapter_context", {})
        if not pre_context.get("immediate_consequences"):
            issues.append("缺少前文结尾的立刻后果")

        if thinking_mode == "deep":
            conflicts = self._extract_conflicts(blueprint)
            key_moments = blueprint.get("key_moments", [])
            if not isinstance(key_moments, list):
                key_moments = []
            if len(conflicts) < 2:
                issues.append("deep 模式冲突层级不足（至少2条）")
            if len(key_moments) < 2:
                issues.append("deep 模式关键时刻不足（至少2条）")

        return issues

    def _repair_plan_for_quality(
        self,
        plan: Dict[str, Any],
        issues: List[str],
        chapter_num: int,
        thinking_mode: str,
    ) -> Optional[Dict[str, Any]]:
        """Ask model to fix low-quality plan and return parsed JSON."""
        min_shots = self.fast_min_storyboard_shots if thinking_mode == "fast" else self.deep_min_storyboard_shots
        prompt = f"""当前章节规划质量不达标，请按问题清单修复并输出完整 JSON。

【章节】第{chapter_num}章
【模式】{thinking_mode}
【问题清单】
{chr(10).join(f"- {item}" for item in issues)}

【硬性约束】
1. storyboard 至少 {min_shots} 个镜头，必须编号连续。
2. 每个镜头必须包含：location、purpose、action_beats 或 dialogue_script。
3. 开篇必须响应前文 immediate_consequences。
4. deep 模式下至少 2 条 conflict_escalation 和 2 条 key_moments。
5. 只输出合法 JSON，不要附加解释。

【当前规划】
```json
{json.dumps(plan, ensure_ascii=False, indent=2)}
```
"""
        system = "你是剧情结构修复器。只输出修复后的完整 JSON。"
        try:
            response = self._stream_collect_response(prompt, system)
        except Exception:
            return None
        return self._parse_result(response)
    
    def analyze_chapter(
        self, 
        chapter_num: int,
        outline_info: Dict[str, str],
        world_context: str,
        previous_content: str,
        is_append: bool = False,
        thinking_mode: str = "auto",
    ) -> Generator[str, None, Dict[str, Any]]:
        """
        分析并规划本章内容
        
        :param chapter_num: 章节号
        :param outline_info: 大纲信息 (volume, phase, specific_goal)
        :param world_context: 世界和角色上下文
        :param previous_content: 前文内容
        :param is_append: 是否为续写模式
        
        :yields: 思考过程的流式输出
        :returns: 结构化的章节规划
        """
        resolved_mode = normalize_thinking_mode(thinking_mode)
        if resolved_mode == "auto":
            resolved_mode = "fast" if is_append else "deep"
        clipped_world_context = clip_tail(world_context, self.world_context_chars)
        clipped_previous_content = clip_tail(previous_content, self.previous_context_chars)

        cache_key = build_thinking_cache_key(
            chapter_num=chapter_num,
            thinking_mode=resolved_mode,
            outline_info=outline_info,
            world_context=clipped_world_context,
            previous_content=clipped_previous_content,
        )
        cached_plan = self._get_cached_plan(cache_key)
        if cached_plan is not None:
            yield f"⚡ 使用缓存剧情规划（{resolved_mode}）\n"
            yield self._format_summary(cached_plan)
            yield "\n"
            yield cached_plan
            return

        prompt = self._build_prompt(
            chapter_num=chapter_num,
            outline_info=outline_info,
            world_context=clipped_world_context,
            previous_content=clipped_previous_content,
            thinking_mode=resolved_mode,
        )
        system = self._build_system_prompt(resolved_mode)

        yield f"🧠 正在分析剧情（{resolved_mode}）...\n"
        
        try:
            response_text = self._stream_collect_response(prompt, system)
        except Exception as e:
            yield f"❌ API 调用失败: {str(e)}\n"
            fallback = self._get_default_plan(chapter_num, outline_info)
            fallback.setdefault("_meta", {})["thinking_mode"] = resolved_mode
            yield fallback
            return
        
        # 调试：输出原始响应（前500字符）
        # yield f"\n[DEBUG] 响应长度: {len(response_text)} 字符\n"
        # yield f"[DEBUG] 响应前500字: {response_text[:500]}\n\n"
        
        # 解析 JSON 结果
        result = self._parse_result(response_text)
        
        if result:
            quality_issues = self._validate_plan_quality(result, resolved_mode)
            for attempt in range(self.quality_retry_count):
                if not quality_issues:
                    break
                yield f"⚠️ 规划质量不足，正在自动强化（{attempt + 1}/{self.quality_retry_count}）...\n"
                repaired = self._repair_plan_for_quality(
                    plan=result,
                    issues=quality_issues,
                    chapter_num=chapter_num,
                    thinking_mode=resolved_mode,
                )
                if not repaired:
                    continue
                result = repaired
                quality_issues = self._validate_plan_quality(result, resolved_mode)

            result.setdefault("_meta", {})["thinking_mode"] = resolved_mode
            if quality_issues:
                result.setdefault("_meta", {})["quality_warnings"] = quality_issues
                yield "⚠️ 规划仍有缺口：" + "；".join(quality_issues[:3]) + "\n"
            else:
                self._save_cached_plan(cache_key, result)

            yield self._format_summary(result)
            yield "\n"
            yield result
        else:
            yield "⚠️ 思考结果解析失败\n"
            # 输出调试信息
            yield f"📝 响应长度: {len(response_text)} 字符\n"
            if len(response_text) > 0:
                yield f"📝 响应开头: {response_text[:200]}...\n"
            else:
                yield "📝 响应为空\n"
            yield "使用默认模式\n"
            fallback = self._get_default_plan(chapter_num, outline_info)
            fallback.setdefault("_meta", {})["thinking_mode"] = resolved_mode
            yield fallback

    def _build_system_prompt(self, thinking_mode: str) -> str:
        if thinking_mode == "fast":
            return """你是一位资深网文编辑，请快速给出可执行剧情规划。
要求：优先连贯性和人物关系逻辑，只输出有效 JSON，不要解释。"""
        return """你是一位资深影视编剧。你的特长是处理剧情连贯性和人物关系逻辑。
请创建详细分镜剧本，不得给出空泛总结，必须提供可执行镜头信息。
确保输出为有效 JSON。"""

    def _build_prompt(
        self,
        chapter_num: int,
        outline_info: Dict[str, str],
        world_context: str,
        previous_content: str,
        thinking_mode: str,
    ) -> str:
        if thinking_mode == "fast":
            return self._build_fast_prompt(chapter_num, outline_info, world_context, previous_content)
        return self._build_deep_prompt(chapter_num, outline_info, world_context, previous_content)

    def _build_fast_prompt(
        self,
        chapter_num: int,
        outline_info: Dict[str, str],
        world_context: str,
        previous_content: str,
    ) -> str:
        return f"""你是一位资深网文编剧，请为第{chapter_num}章做“快速剧情规划”。

目标：在最少 token 内给出可直接写作的结构化计划，重点保证连续性和人物逻辑。

【世界与角色状态】
{world_context}

【大纲指引】
- 本卷目标：{outline_info.get('volume', '未知')}
- 当前阶段：{outline_info.get('phase', '未知')}
- 本章具体情节：{outline_info.get('specific_goal', '未指定')}

【前文结尾（必须衔接）】
{previous_content if previous_content else '（故事开始）'}

请输出 JSON：
```json
{{
  "plot_analysis": {{
    "pre_chapter_context": {{
      "previous_ending": "前文结尾",
      "immediate_consequences": "本章开头必须处理",
      "character_emotional_carryover": "情绪延续"
    }},
    "interaction_logic_check": [
      {{
        "characters": ["角色A", "角色B"],
        "relation_status": "初识/熟识/敌对/未知",
        "interaction_guidance": "交互建议"
      }}
    ],
    "current_situation": "局势"
  }},
  "chapter_blueprint": {{
    "title_suggestion": "标题",
    "theme": "核心主题",
    "opening_hook": "开篇钩子",
    "storyboard": [
      {{
        "shot_number": 1,
        "location": "场景",
        "action_beats": [
          {{"beat": 1, "actor": "角色", "action": "动作", "reaction": "反应"}}
        ],
        "dialogue_script": [
          {{"speaker": "说话人", "line": "台词", "tone": "语气"}}
        ],
        "purpose": "叙事目的",
        "word_count": 400
      }}
    ],
    "key_moments": [
      {{"moment_type": "高光", "description": "关键场面", "impact": "作用"}}
    ],
    "cliffhanger": {{
      "type": "钩子类型",
      "final_line": "最后一句",
      "reader_hook": "读者疑问"
    }},
    "writing_guidance": {{
      "tone": "基调",
      "pacing": "节奏",
      "highlight": ["要写重点"],
      "avoid": ["避免事项"]
    }}
  }}
}}
```

约束：
1. `storyboard` 至少 {self.fast_min_storyboard_shots} 个镜头，建议 3-5 个，强调可执行性。
2. 严格遵守“初识角色不能熟络对话”。
3. 每个镜头都要有 `purpose` 与动作/对白。
4. 只输出 JSON。"""

    def _build_deep_prompt(
        self,
        chapter_num: int,
        outline_info: Dict[str, str],
        world_context: str,
        previous_content: str,
    ) -> str:
        return f"""你是一位资深网文编剧，请为第{chapter_num}章创建详细的【分镜剧本】。

⚠️ **核心要求**：
1. **必须紧接上文**：仔细分析前文结尾，新章节第一幕必须直接承接上文的最后一幕，或者处理其直接后果。严禁跳跃或忽略前文结尾的悬念。
2. **人物一致性**：角色的行动和对话必须符合其既定性格和当前情绪状态。
3. **信息差管理**：
   - 仔细检查主角是否认识本章出场的其他角色。
   - 如果是**初遇**，必须描写外貌观察、试探、自我介绍等过程，严禁出现熟络的对话。
   - 主角不知道的信息（如配角的秘密计划），在主角视角下必须是未知的。
4. **分镜详细**：像电影分镜一样规划每个场景。

【世界与角色状态】
{world_context}

【大纲指引】
- 本卷目标：{outline_info.get('volume', '未知')}
- 当前阶段：{outline_info.get('phase', '未知')}
- 本章具体情节：{outline_info.get('specific_goal', '未指定')}

【前文内容（重点关注结尾及主角人际关系）】
{previous_content if previous_content else '（故事开始）'}

---

请输出 JSON 规划：

```json
{{
  "plot_analysis": {{
    "pre_chapter_context": {{
      "previous_ending": "前文结尾发生了什么",
      "immediate_consequences": "根据结尾，现在必须立刻发生什么",
      "character_emotional_carryover": "主角情绪延续"
    }},
    "interaction_logic_check": [
      {{
        "characters": ["角色A", "角色B"],
        "relation_status": "初识/熟识/敌对/未知",
        "interaction_guidance": "如果是初识，通过外貌/动作/试探来建立关系；如果是熟识，依据过往经历互动。"
      }}
    ],
    "current_situation": "局势分析",
    "unresolved_threads": ["待解决的伏笔"]
  }},
  "chapter_blueprint": {{
    "title_suggestion": "章节标题",
    "theme": "核心主题",
    "opening_hook": "开篇必须直接响应前文结尾",
    "total_word_target": 3500,
    "storyboard": [
      {{
        "shot_number": 1,
        "shot_type": "镜头类型",
        "location": "场景地点",
        "time": "时间（紧接上文）",
        "atmosphere": "氛围",
        "characters_on_screen": [
          {{
            "name": "角色名",
            "position": "位置",
            "posture": "姿态",
            "expression": "表情",
            "emotion": "内心情绪",
            "inner_thought": "内心独白"
          }}
        ],
        "action_beats": [
          {{
            "beat": 1,
            "actor": "动作执行者",
            "action": "具体动作",
            "reaction": "反应"
          }}
        ],
        "dialogue_script": [
          {{
            "speaker": "说话人",
            "line": "台词",
            "tone": "语气",
            "subtext": "潜台词",
            "action_during": "动作"
          }}
        ],
        "sensory_details": {{
          "visual": "视觉",
          "audio": "听觉",
          "smell": "嗅觉"
        }},
        "tension_level": 7,
        "word_count": 500,
        "purpose": "叙事目的"
      }}
    ],
    "character_journey": {{
      "主角名": {{
        "start_state": "起点",
        "trigger_event": "触发",
        "internal_conflict": "内心冲突",
        "decision": "决定",
        "end_state": "终点",
        "growth_delta": "成长"
      }}
    }},
    "conflict_escalation": [
      {{
        "stage": "阶段",
        "conflict_type": "类型",
        "parties": ["方1", "方2"],
        "stakes": "赌注",
        "beat_description": "表现"
      }}
    ],
    "key_moments": [
      {{
        "moment_type": "类型",
        "description": "描述",
        "impact": "影响"
      }}
    ],
    "foreshadowing": [
      {{
        "hint": "伏笔",
        "how_to_plant": "植入",
        "payoff_chapter": "回收"
      }}
    ],
    "cliffhanger": {{
      "type": "类型",
      "final_line": "最后一句",
      "reader_hook": "疑问"
    }},
    "writing_guidance": {{
      "tone": "基调",
      "pacing": "节奏",
      "style_notes": "风格",
      "highlight": ["重点"],
      "avoid": ["避免"]
    }}
  }}
}}
```

⚠️ 重要：
1. 逻辑自洽：重点检查人物关系，不要出现主角初见反派却像老朋友聊天。
2. 连贯性：开头无缝衔接。
3. 细节决定成败：通过微表情和潜台词体现人物关系。
4. **硬性数量要求**：
   - `storyboard` 至少 {self.deep_min_storyboard_shots} 个镜头（建议 5-7）。
   - 每个镜头必须给出 `purpose`，并包含动作或对白（不可只有环境描写）。
   - `conflict_escalation` 至少 2 条。
   - `key_moments` 至少 2 条。
5. 输出必须是可解析 JSON，禁止附加解释文本。

请输出 JSON："""
    
    def _parse_result(self, response: str) -> Optional[Dict[str, Any]]:
        """解析模型输出的 JSON，支持自动修复损坏的 JSON"""
        try:
            # 1. 先尝试去除 markdown 代码块标记
            cleaned = response.strip()
            
            # 检查是否有 ```json 或 ``` 标记
            if cleaned.startswith('```'):
                # 找到第一个换行符（代码块开始）
                first_newline = cleaned.find('\n')
                if first_newline > 0:
                    cleaned = cleaned[first_newline + 1:]
                
                # 去除末尾的 ```
                if cleaned.endswith('```'):
                    cleaned = cleaned[:-3].strip()
            
            # 2. 查找 JSON 块的起止位置
            json_start = cleaned.find('{')
            json_end = cleaned.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = cleaned[json_start:json_end]
                
                # 3. 先尝试标准解析
                try:
                    result = json.loads(json_str)
                    return result
                except json.JSONDecodeError:
                    # 4. 标准解析失败，使用 json_repair 修复
                    self._debug("标准 JSON 解析失败，尝试自动修复...")
                    if repair_json is None:
                        self._debug("json_repair 不可用，跳过修复")
                        return None
                    repaired = repair_json(json_str, return_objects=True)
                    if isinstance(repaired, dict):
                        self._debug("JSON 修复成功")
                        return repaired
                    self._debug(f"修复后不是字典类型: {type(repaired)}")
                    return None
                
        except Exception as e:
            self._debug(f"解析错误: {e}")
        
        return None
    
    def _format_summary(self, plan: Dict[str, Any]) -> str:
        """格式化思考结果摘要"""
        lines = ["📋 分镜剧本生成完成："]
        thinking_mode = plan.get("_meta", {}).get("thinking_mode")
        if thinking_mode:
            lines.append(f"   模式: {thinking_mode}")
        quality_warnings = plan.get("_meta", {}).get("quality_warnings", [])
        if quality_warnings:
            lines.append(f"   质检: {len(quality_warnings)}个问题")
        
        blueprint = plan.get('chapter_blueprint', plan.get('chapter_plan', {}))
        
        if blueprint.get('title_suggestion'):
            lines.append(f"   标题: {blueprint['title_suggestion']}")
        if blueprint.get('theme'):
            lines.append(f"   主题: {blueprint['theme']}")
        
        # 前文衔接检查
        plot_analysis = plan.get('plot_analysis', {})
        pre_context = plot_analysis.get('pre_chapter_context', {})
        if pre_context:
            if pre_context.get('immediate_consequences'):
                lines.append(f"   承接: {pre_context['immediate_consequences'][:20]}...")
        
        # 统计分镜数量
        storyboard = blueprint.get('storyboard', blueprint.get('scenes', []))
        if storyboard:
            lines.append(f"   镜头: {len(storyboard)}个")
            # 统计总对话数和动作数
            dialogue_count = sum(len(s.get('dialogue_script', [])) for s in storyboard)
            action_count = sum(len(s.get('action_beats', [])) for s in storyboard)
            if dialogue_count > 0:
                lines.append(f"   对话: {dialogue_count}段")
            if action_count > 0:
                lines.append(f"   动作: {action_count}节拍")
        
        # 冲突类型
        conflicts = blueprint.get('conflict_escalation', blueprint.get('conflicts', []))
        if conflicts:
            types = [c.get('conflict_type', c.get('type', '?')) for c in conflicts[:2]]
            lines.append(f"   冲突: {', '.join(types)}")
        
        # 关键时刻
        moments = blueprint.get('key_moments', [])
        if moments:
            lines.append(f"   高光: {len(moments)}个")
        
        return "\n".join(lines)
    
    def _get_default_plan(self, chapter_num: int, outline_info: Dict[str, str]) -> Dict[str, Any]:
        """默认规划（降级方案）"""
        return {
            "chapter_plan": {
                "theme": outline_info.get('specific_goal', f'第{chapter_num}章'),
                "scenes": [],
                "conflicts": [],
                "cliffhanger": ""
            },
            "writing_notes": {
                "tone": "按大纲推进",
                "pacing": "正常节奏",
                "focus": "剧情推进"
            }
        }
    
    def format_for_generation(self, plan: Dict[str, Any]) -> str:
        """
        将思考结果格式化为生成 prompt 的一部分
        传递详细分镜剧本上下文给 chat 模型
        """
        if not plan:
            return ""
        if plan.get("_meta", {}).get("thinking_mode") == "fast":
            return self._format_fast_generation(plan)
        
        lines = ["【分镜剧本 - 严格按此执行写作】"]
        
        blueprint = plan.get('chapter_blueprint', plan.get('chapter_plan', {}))
        
        # 前文衔接要求 (高优先级)
        plot_analysis = plan.get('plot_analysis', {})
        pre_context = plot_analysis.get('pre_chapter_context', {})
        if pre_context:
            lines.append("\n⚠️【前文衔接要求 - 必须执行】")
            if pre_context.get('previous_ending'):
                lines.append(f"• 前文结尾：{pre_context['previous_ending']}")
            if pre_context.get('immediate_consequences'):
                lines.append(f"• 必须立刻发生：{pre_context['immediate_consequences']}")
            if pre_context.get('character_emotional_carryover'):
                lines.append(f"• 情绪延续：{pre_context['character_emotional_carryover']}")
            lines.append("（请确保开篇第一幕直接响应上述要求，严禁忽略前文结尾）")

        # 人物交互逻辑 (高优先级)
        interactions = plot_analysis.get('interaction_logic_check', [])
        if interactions:
            lines.append("\n⚠️【人物交互逻辑 - 严格遵守】")
            for inter in interactions:
                chars = " & ".join(inter.get('characters', []))
                status = inter.get('relation_status', '?')
                guidance = inter.get('interaction_guidance', '')
                lines.append(f"• {chars} ({status}): {guidance}")
            lines.append("（严禁出现'初识'角色之间的熟络对话，必须描写相识过程）")

        # 章节基本信息
        if blueprint.get('title_suggestion'):
            lines.append(f"\n章节标题：{blueprint['title_suggestion']}")
        if blueprint.get('theme'):
            lines.append(f"核心主题：{blueprint['theme']}")
        if blueprint.get('opening_hook'):
            lines.append(f"开篇钩子：{blueprint['opening_hook']}")
        
        # ===== 分镜剧本 =====
        storyboard = blueprint.get('storyboard', blueprint.get('scenes', []))
        if storyboard:
            lines.append("\n" + "=" * 40)
            lines.append("📽️ 【分镜剧本】请按以下镜头顺序写作")
            lines.append("=" * 40)
            
            for shot in storyboard:
                shot_num = shot.get('shot_number', shot.get('scene_number', '?'))
                shot_type = shot.get('shot_type', '')
                location = shot.get('location', '未知')
                atmosphere = shot.get('atmosphere', shot.get('weather_mood', ''))
                
                lines.append(f"\n🎬 镜头 {shot_num}：【{location}】")
                if shot_type:
                    lines.append(f"   类型：{shot_type}")
                if shot.get('time'):
                    lines.append(f"   时间：{shot.get('time')} | 氛围：{atmosphere}")
                
                # 人物站位
                chars_on_screen = shot.get('characters_on_screen', [])
                if chars_on_screen:
                    lines.append("   👥 人物站位：")
                    for char in chars_on_screen:
                        if isinstance(char, dict):
                            name = char.get('name', '?')
                            pos = char.get('position', '')
                            posture = char.get('posture', '')
                            expr = char.get('expression', '')
                            emotion = char.get('emotion', '')
                            lines.append(f"      - {name}：{pos} {posture}")
                            if expr or emotion:
                                lines.append(f"        表情：{expr} | 内心：{emotion}")
                            if char.get('inner_thought'):
                                lines.append(f"        内心独白：「{char['inner_thought']}」")
                        else:
                            lines.append(f"      - {char}")
                elif shot.get('characters'):
                    lines.append(f"   人物：{', '.join(shot['characters'])}")
                
                # 动作节拍
                action_beats = shot.get('action_beats', [])
                if action_beats:
                    lines.append("   🎯 动作分解：")
                    for beat in action_beats:
                        if isinstance(beat, dict):
                            actor = beat.get('actor', '?')
                            action = beat.get('action', '')
                            reaction = beat.get('reaction', '')
                            lines.append(f"      [{beat.get('beat', '?')}] {actor}：{action}")
                            if reaction:
                                lines.append(f"          → 反应：{reaction}")
                        else:
                            lines.append(f"      - {beat}")
                elif shot.get('key_actions'):
                    lines.append(f"   动作：{'; '.join(shot['key_actions'])}")
                
                # 对话剧本
                dialogue_script = shot.get('dialogue_script', [])
                if dialogue_script:
                    lines.append("   💬 对话剧本：")
                    for dial in dialogue_script:
                        if isinstance(dial, dict):
                            speaker = dial.get('speaker', '?')
                            line = dial.get('line', '')
                            tone = dial.get('tone', '')
                            subtext = dial.get('subtext', '')
                            action_during = dial.get('action_during', '')
                            lines.append(f"      {speaker}（{tone}）：「{line}」")
                            if subtext:
                                lines.append(f"        潜台词：{subtext}")
                            if action_during:
                                lines.append(f"        动作：{action_during}")
                
                # 感官描写
                sensory = shot.get('sensory_details', {})
                if sensory and isinstance(sensory, dict):
                    sens_parts = []
                    if sensory.get('visual'): sens_parts.append(f"视觉：{sensory['visual']}")
                    if sensory.get('audio'): sens_parts.append(f"听觉：{sensory['audio']}")
                    if sensory.get('smell'): sens_parts.append(f"嗅觉：{sensory['smell']}")
                    if sens_parts:
                        lines.append(f"   🎨 感官描写：{' | '.join(sens_parts)}")
                elif sensory:
                    lines.append(f"   感官描写：{sensory}")
                
                # 其他信息
                if shot.get('tension_level'):
                    lines.append(f"   紧张度：{shot['tension_level']}/10 | 目标字数：~{shot.get('word_count', shot.get('word_count_target', 500))}字")
                if shot.get('purpose'):
                    lines.append(f"   叙事目的：{shot['purpose']}")
        
        # ===== 角色旅程 =====
        journey = blueprint.get('character_journey', blueprint.get('character_arcs', {}))
        if journey:
            lines.append("\n【角色旅程】")
            for name, arc in journey.items():
                if isinstance(arc, dict):
                    lines.append(f"  {name}：")
                    if arc.get('start_state'): lines.append(f"    起点：{arc['start_state']}")
                    if arc.get('trigger_event'): lines.append(f"    触发：{arc['trigger_event']}")
                    if arc.get('internal_conflict'): lines.append(f"    内心冲突：{arc['internal_conflict']}")
                    if arc.get('decision'): lines.append(f"    决定：{arc['decision']}")
                    if arc.get('end_state'): lines.append(f"    终点：{arc['end_state']}")
                    if arc.get('growth_delta'): lines.append(f"    成长：{arc['growth_delta']}")
                    # 兼容旧格式
                    if arc.get('goal'): lines.append(f"    目标：{arc['goal']}")
                    if arc.get('obstacle'): lines.append(f"    阻碍：{arc['obstacle']}")
                else:
                    lines.append(f"  {name}: {arc}")
        
        # ===== 冲突升级 =====
        conflicts = blueprint.get('conflict_escalation', blueprint.get('conflicts', []))
        if conflicts:
            lines.append("\n【冲突升级】")
            for c in conflicts:
                stage = c.get('stage', c.get('intensity', ''))
                ctype = c.get('conflict_type', c.get('type', ''))
                parties = ' vs '.join(c.get('parties', []))
                lines.append(f"  [{stage}] {ctype}：{parties}")
                if c.get('stakes'): lines.append(f"    赌注：{c['stakes']}")
                if c.get('beat_description'): lines.append(f"    表现：{c['beat_description']}")
        
        # ===== 关键时刻 =====
        key_moments = blueprint.get('key_moments', [])
        if key_moments:
            lines.append("\n【关键时刻】务必写出以下高光点：")
            for m in key_moments:
                if isinstance(m, dict):
                    lines.append(f"  - [{m.get('moment_type', '?')}] {m.get('description', '')}")
                    if m.get('impact'): lines.append(f"    影响：{m['impact']}")
        
        # ===== 伏笔 =====
        if blueprint.get('foreshadowing'):
            lines.append("\n【埋下伏笔】")
            for f in blueprint['foreshadowing']:
                if isinstance(f, dict):
                    lines.append(f"  - {f.get('hint', '')}")
                    if f.get('how_to_plant'): lines.append(f"    植入方式：{f['how_to_plant']}")
                else:
                    lines.append(f"  - {f}")
        
        # ===== 章末钩子 =====
        cliffhanger = blueprint.get('cliffhanger', {})
        if cliffhanger:
            lines.append("\n【章末钩子】")
            if isinstance(cliffhanger, dict):
                if cliffhanger.get('type'): lines.append(f"  类型：{cliffhanger['type']}")
                if cliffhanger.get('final_line'): lines.append(f"  最后一句：「{cliffhanger['final_line']}」")
                if cliffhanger.get('content'): lines.append(f"  设计：{cliffhanger['content']}")
                if cliffhanger.get('reader_hook') or cliffhanger.get('reader_question'):
                    lines.append(f"  读者会问：{cliffhanger.get('reader_hook', cliffhanger.get('reader_question', ''))}")
            else:
                lines.append(f"  {cliffhanger}")
        
        # ===== 写作指导 =====
        guidance = plan.get('writing_guidance', plan.get('writing_notes', {}))
        if guidance:
            lines.append("\n【写作指导】")
            parts = []
            if guidance.get('tone'): parts.append(f"基调：{guidance['tone']}")
            pacing = guidance.get('pacing', '')
            if isinstance(pacing, dict):
                if pacing.get('overall'): parts.append(f"节奏：{pacing['overall']}")
            elif pacing:
                parts.append(f"节奏：{pacing}")
            if parts:
                lines.append(f"  {' | '.join(parts)}")
            if guidance.get('style_notes'):
                lines.append(f"  风格：{guidance['style_notes']}")
            if guidance.get('highlight'):
                lines.append(f"  重点：{', '.join(guidance['highlight'])}")
            if guidance.get('avoid'):
                lines.append(f"  ⚠️避免：{', '.join(guidance['avoid'])}")
        
        return "\n".join(lines)

    def _format_fast_generation(self, plan: Dict[str, Any]) -> str:
        """Fast thinking mode uses a compact prompt block to reduce token pressure."""
        lines = ["【快速剧情规划 - 严格执行】"]

        analysis = plan.get("plot_analysis", {})
        pre = analysis.get("pre_chapter_context", {})
        if pre:
            lines.append(f"前文结尾：{pre.get('previous_ending', '')}")
            lines.append(f"开篇必须处理：{pre.get('immediate_consequences', '')}")
            if pre.get("character_emotional_carryover"):
                lines.append(f"情绪延续：{pre['character_emotional_carryover']}")

        interactions = analysis.get("interaction_logic_check", [])
        if interactions:
            lines.append("人物交互逻辑：")
            for inter in interactions[:3]:
                chars = " & ".join(inter.get("characters", []))
                status = inter.get("relation_status", "?")
                guidance = inter.get("interaction_guidance", "")
                lines.append(f"- {chars}({status}): {guidance}")

        blueprint = plan.get("chapter_blueprint", plan.get("chapter_plan", {}))
        if blueprint.get("title_suggestion"):
            lines.append(f"标题建议：{blueprint['title_suggestion']}")
        if blueprint.get("theme"):
            lines.append(f"主题：{blueprint['theme']}")
        if blueprint.get("opening_hook"):
            lines.append(f"开篇钩子：{blueprint['opening_hook']}")

        storyboard = blueprint.get("storyboard", blueprint.get("scenes", []))
        if storyboard:
            lines.append("镜头安排：")
            for shot in storyboard[:5]:
                num = shot.get("shot_number", shot.get("scene_number", "?"))
                loc = shot.get("location", "未知场景")
                purpose = shot.get("purpose", "")
                lines.append(f"- 镜头{num} @ {loc}: {purpose}")
                for beat in shot.get("action_beats", [])[:2]:
                    if isinstance(beat, dict):
                        lines.append(
                            f"  动作[{beat.get('beat', '?')}] {beat.get('actor', '?')}: {beat.get('action', '')}"
                        )
                for dial in shot.get("dialogue_script", [])[:2]:
                    if isinstance(dial, dict):
                        lines.append(
                            f"  对话 {dial.get('speaker', '?')}({dial.get('tone', '')}): {dial.get('line', '')}"
                        )

        moments = blueprint.get("key_moments", [])
        if moments:
            lines.append("关键时刻：")
            for moment in moments[:3]:
                if isinstance(moment, dict):
                    lines.append(f"- {moment.get('description', '')}")

        cliff = blueprint.get("cliffhanger", {})
        if isinstance(cliff, dict) and cliff.get("reader_hook"):
            lines.append(f"章末悬念：{cliff['reader_hook']}")

        guidance = plan.get("writing_guidance", blueprint.get("writing_guidance", plan.get("writing_notes", {})))
        if guidance:
            tone = guidance.get("tone", "")
            pacing = guidance.get("pacing", "")
            if tone or pacing:
                lines.append(f"写作基调：{tone} | 节奏：{pacing}")
            if guidance.get("highlight"):
                lines.append(f"重点：{', '.join(guidance['highlight'])}")
            if guidance.get("avoid"):
                lines.append(f"避免：{', '.join(guidance['avoid'])}")

        return "\n".join(lines)
    
    def format_full_plan_display(self, plan: Dict[str, Any]) -> str:
        """
        格式化完整的规划展示（供用户审核）
        """
        if not plan:
            return "（无规划）"
        
        lines = []
        
        # 剧情分析
        analysis = plan.get('plot_analysis', {})
        if analysis:
            lines.append("=" * 50)
            lines.append("📊 【剧情分析】")
            lines.append("=" * 50)
            
            # 前文衔接分析
            pre_context = analysis.get('pre_chapter_context', {})
            if pre_context:
                lines.append("🔗 前文衔接:")
                if pre_context.get('previous_ending'):
                    lines.append(f"  - 结尾回顾: {pre_context['previous_ending']}")
                if pre_context.get('immediate_consequences'):
                    lines.append(f"  - 必须发生: {pre_context['immediate_consequences']}")
                if pre_context.get('character_emotional_carryover'):
                    lines.append(f"  - 情绪延续: {pre_context['character_emotional_carryover']}")
                lines.append("-" * 30)

            # 人物交互逻辑检查
            interactions = analysis.get('interaction_logic_check', [])
            if interactions:
                lines.append("👥 人物交互逻辑:")
                for inter in interactions:
                    chars = " & ".join(inter.get('characters', []))
                    status = inter.get('relation_status', '?')
                    guidance = inter.get('interaction_guidance', '')[:30]
                    lines.append(f"  - [{status}] {chars}")
                    if guidance:
                        lines.append(f"    指导: {guidance}...")
                lines.append("-" * 30)

            if analysis.get('current_situation'):
                lines.append(f"当前局势: {analysis['current_situation']}")
            if analysis.get('emotional_state'):
                lines.append(f"情感基调: {analysis['emotional_state']}")
            if analysis.get('unresolved_threads'):
                lines.append(f"未解悬念: {', '.join(analysis['unresolved_threads'])}")
            if analysis.get('character_positions'):
                lines.append("角色位置:")
                for name, pos in analysis['character_positions'].items():
                    lines.append(f"  - {name}: {pos}")
        
        # 章节蓝图
        blueprint = plan.get('chapter_blueprint', plan.get('chapter_plan', {}))
        if blueprint:
            lines.append("")
            lines.append("=" * 50)
            lines.append("📝 【分镜剧本】")
            lines.append("=" * 50)
            
            if blueprint.get('title_suggestion'):
                lines.append(f"章节标题: {blueprint['title_suggestion']}")
            if blueprint.get('theme'):
                lines.append(f"核心主题: {blueprint['theme']}")
            if blueprint.get('opening_hook'):
                lines.append(f"开篇钩子: {blueprint['opening_hook']}")
            
            # 分镜剧本
            storyboard = blueprint.get('storyboard', blueprint.get('scenes', []))
            if storyboard:
                lines.append("\n🎬 分镜序列:")
                for shot in storyboard:
                    num = shot.get('shot_number', shot.get('scene_number', '?'))
                    loc = shot.get('location', '?')
                    shot_type = shot.get('shot_type', '')
                    
                    lines.append(f"\n  【镜头 {num}】{loc}")
                    if shot_type:
                        lines.append(f"    类型: {shot_type}")
                    if shot.get('time'):
                        lines.append(f"    时间: {shot.get('time')} | 氛围: {shot.get('atmosphere', shot.get('weather_mood', ''))}")
                    
                    # 人物站位
                    chars = shot.get('characters_on_screen', [])
                    if chars:
                        lines.append("    👥 人物:")
                        for c in chars[:3]:  # 限制显示数量
                            if isinstance(c, dict):
                                lines.append(f"      - {c.get('name', '?')}: {c.get('posture', '')} | {c.get('expression', '')} | {c.get('emotion', '')}")
                            else:
                                lines.append(f"      - {c}")
                    elif shot.get('characters'):
                        lines.append(f"    人物: {', '.join(shot['characters'])}")
                    
                    # 动作节拍
                    beats = shot.get('action_beats', [])
                    if beats:
                        lines.append("    🎯 动作:")
                        for b in beats[:3]:
                            if isinstance(b, dict):
                                lines.append(f"      [{b.get('beat', '?')}] {b.get('actor', '?')}: {b.get('action', '')}")
                    elif shot.get('key_actions'):
                        lines.append(f"    动作: {'; '.join(shot['key_actions'][:2])}")
                    
                    # 对话
                    dialogue = shot.get('dialogue_script', [])
                    if dialogue:
                        lines.append("    💬 对话:")
                        for d in dialogue[:2]:
                            if isinstance(d, dict):
                                lines.append(f"      {d.get('speaker', '?')}({d.get('tone', '')}): 「{d.get('line', '')[:30]}...」")
                    
                    if shot.get('tension_level'):
                        lines.append(f"    紧张度: {shot['tension_level']}/10 | ~{shot.get('word_count', 500)}字")
            
            # 角色旅程
            journey = blueprint.get('character_journey', blueprint.get('character_arcs', {}))
            if journey:
                lines.append("\n🎭 角色旅程:")
                for name, arc in journey.items():
                    if isinstance(arc, dict):
                        lines.append(f"  {name}:")
                        if arc.get('start_state'): lines.append(f"    起点: {arc['start_state'][:50]}...")
                        if arc.get('decision'): lines.append(f"    决定: {arc['decision'][:50]}...")
                        if arc.get('end_state'): lines.append(f"    终点: {arc['end_state'][:50]}...")
                        # 兼容旧格式
                        if arc.get('goal'): lines.append(f"    目标: {arc['goal']}")
                    else:
                        lines.append(f"  - {name}: {arc}")
            
            # 冲突升级
            conflicts = blueprint.get('conflict_escalation', blueprint.get('conflicts', []))
            if conflicts:
                lines.append("\n⚔️ 冲突升级:")
                for c in conflicts:
                    stage = c.get('stage', c.get('intensity', ''))
                    ctype = c.get('conflict_type', c.get('type', ''))
                    parties = ' vs '.join(c.get('parties', []))
                    lines.append(f"  [{stage}] {ctype}: {parties}")
            
            # 关键时刻
            moments = blueprint.get('key_moments', [])
            if moments:
                lines.append("\n⭐ 关键时刻:")
                for m in moments:
                    if isinstance(m, dict):
                        lines.append(f"  - [{m.get('moment_type', '?')}] {m.get('description', '')[:50]}...")
            
            # 伏笔
            if blueprint.get('foreshadowing'):
                lines.append("\n🔮 埋下伏笔:")
                for f in blueprint['foreshadowing'][:3]:
                    if isinstance(f, dict):
                        lines.append(f"  - {f.get('hint', '')} (第{f.get('payoff_chapter', '?')}章回收)")
                    else:
                        lines.append(f"  - {f}")
            
            # 章末钩子
            cliffhanger = blueprint.get('cliffhanger', {})
            if cliffhanger:
                lines.append("\n🪝 章末钩子:")
                if isinstance(cliffhanger, dict):
                    if cliffhanger.get('type'): lines.append(f"  类型: {cliffhanger['type']}")
                    if cliffhanger.get('final_line'): lines.append(f"  最后一句: 「{cliffhanger['final_line']}」")
                    if cliffhanger.get('content'): lines.append(f"  设计: {cliffhanger['content'][:60]}...")
                    if cliffhanger.get('reader_hook') or cliffhanger.get('reader_question'):
                        lines.append(f"  悬念: {cliffhanger.get('reader_hook', cliffhanger.get('reader_question', ''))[:50]}...")
                else:
                    lines.append(f"  {cliffhanger}")
        
        # 写作指导
        guidance = plan.get('writing_guidance', plan.get('writing_notes', {}))
        if guidance:
            lines.append("")
            lines.append("=" * 50)
            lines.append("✍️ 【写作指导】")
            lines.append("=" * 50)
            parts = []
            if guidance.get('tone'): parts.append(f"基调: {guidance['tone']}")
            pacing = guidance.get('pacing', '')
            if isinstance(pacing, dict):
                if pacing.get('overall'): parts.append(f"节奏: {pacing['overall']}")
            elif pacing:
                parts.append(f"节奏: {pacing}")
            if parts:
                lines.append(' | '.join(parts))
            if guidance.get('style_notes'):
                lines.append(f"风格: {guidance['style_notes']}")
            if guidance.get('highlight'):
                lines.append(f"重点: {', '.join(guidance['highlight'])}")
            if guidance.get('avoid'):
                lines.append(f"⚠️避免: {', '.join(guidance['avoid'])}")
        
        lines.append("=" * 50)
        return "\n".join(lines)
    
    def refine_plan(self, current_plan: Dict[str, Any], user_feedback: str) -> Generator[str, None, Dict[str, Any]]:
        """
        根据用户反馈修改剧情规划
        
        :param current_plan: 当前的规划
        :param user_feedback: 用户的修改意见
        :yields: 思考过程
        :returns: 修改后的规划
        """
        prompt = f"""当前的章节规划如下：

```json
{json.dumps(current_plan, ensure_ascii=False, indent=2)}
```

用户对此规划有以下修改意见：
{user_feedback}

请根据用户意见调整规划，输出修改后的完整 JSON 规划。保持原有 JSON 结构不变。"""

        system = """你是一位资深小说编剧。请根据用户的反馈修改章节规划。
保持 JSON 格式不变，只修改需要调整的内容。输出必须是有效的 JSON。"""

        yield "🔄 正在调整规划...\n"
        
        response_text = ""
        for chunk in self.ai.stream_chat(prompt, system_prompt=system):
            response_text += chunk
        
        result = self._parse_result(response_text)
        
        if result:
            yield "✅ 规划已调整\n"
            yield result
        else:
            yield "⚠️ 调整失败，保持原规划\n"
            yield current_plan
    
    def refine_chapter(
        self,
        chapter_content: str,
        world_context: str,
        style_ref: str = "",
        focus: str = "风格优化"
    ) -> Generator[str, None, str]:
        """
        润色已生成的章节内容
        
        :param chapter_content: 待润色的章节内容
        :param world_context: 世界和角色上下文
        :param style_ref: 风格参考文本
        :param focus: 润色重点（风格优化/节奏优化/对话润色等）
        :yields: 润色过程
        :returns: 润色后的完整内容
        """
        
        style_hint = ""
        if style_ref:
            style_hint = f"""
【风格参考】
请模仿以下文本的写作风格：
{style_ref[:1000]}
"""
        
        prompt = f"""请对以下小说章节进行润色优化。

【润色重点】{focus}

【世界与角色设定】
{world_context}
{style_hint}
【待润色章节】
{chapter_content}

---

请根据以下要点进行润色：
1. **风格统一**：确保文风一致，语言流畅
2. **节奏优化**：调整段落长度，增强节奏感
3. **对话打磨**：让人物对话更有特色和个性
4. **描写增强**：适当增加细节描写，但不要过于冗长
5. **情感深化**：加强情感表达的层次感
6. **伏笔呼应**：确保前后呼应，逻辑自洽

⚠️ 注意：
- 保持原有剧情走向不变
- 保持字数基本一致（可略有增加）
- 不要改变人物性格和设定

请直接输出润色后的完整章节内容："""

        system = """你是一位资深小说编辑和文学润色专家。
你的任务是在保持原有剧情的基础上，提升文字的质量和可读性。
做到：精炼表达、增强画面感、让对话更生动、节奏更紧凑。
直接输出润色后的内容，不要添加解释或评论。"""

        yield "✨ 正在润色章节...\n"
        
        refined_content = ""
        for chunk in self.ai.stream_chat(prompt, system_prompt=system):
            refined_content += chunk
            yield chunk  # 流式输出润色内容
        
        yield refined_content
