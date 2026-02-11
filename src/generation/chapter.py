"""
章节生成器

自动续写模式：
- 获取最新章节，不到 3k 字继续追加
- 超过 3k 字自动新建下一章
"""

import json
import os
from typing import Any, Dict, Generator, List, Optional, Tuple

try:
    from json_repair import repair_json
except ImportError:
    repair_json = None

from config import config
from generation.services import ChapterPreparationService, ChapterWritingService, WorldStateUpdateService
from storage import StorageManager
from tools import resolve_thinking_mode
from utils.word_count import count_chinese_words


class ChapterGenerator:
    """章节生成器 - 自动续写模式。"""

    MIN_CHAPTER_LENGTH = 3000
    OUTLINE_MAX_CHARS = 12000
    GENERATION_SYSTEM_PROMPT = """你是资深网络小说作家。写作风格：
- 文笔流畅，节奏紧凑
- 人物对话有特色
- 善于制造悬念和钩子
请直接输出内容。如果有剧情规划，请严格按照规划写作。"""

    def __init__(self, project_name: str, ai_client=None, storage: StorageManager = None, thinking_engine=None):
        self.project_name = project_name

        if ai_client is None:
            from models import get_client

            ai_client = get_client()
        self.ai = ai_client
        self.storage = storage or StorageManager()

        self.thinking_engine = thinking_engine
        if self.thinking_engine is None and config.enable_plot_thinking:
            from generation.thinking import PlotThinkingEngine

            try:
                self.thinking_engine = PlotThinkingEngine()
            except Exception:
                # 无法初始化推理模型时自动降级，避免影响基础生成功能。
                self.thinking_engine = None

        self.world_data = self.storage.load_world_state(project_name) or {}
        self._preparation_service = ChapterPreparationService()
        self._writing_service = ChapterWritingService()
        self._world_state_service = WorldStateUpdateService()

    def _get_latest_chapter(self) -> Tuple[int, str, str, int]:
        """获取最新章节信息：(章节号, 标题, 内容, 字数)。"""
        chapters = self.storage.list_chapters(self.project_name)
        if not chapters:
            return (0, "", "", 0)

        latest = chapters[-1]
        try:
            ch_num = int(latest.split("_")[0])
            title = latest.split("_", 1)[1].replace(".txt", "")
        except (IndexError, ValueError):
            ch_num = len(chapters)
            title = "未命名"

        ch_path = os.path.join(self.storage.get_project_dir(self.project_name), "chapters", latest)
        try:
            with open(ch_path, "r", encoding="utf-8") as f:
                content = f.read()
            return (ch_num, title, content, count_chinese_words(content))
        except OSError:
            return (ch_num, title, "", 0)

    @staticmethod
    def _to_text_list(values: Any, limit: int = 0) -> List[str]:
        """将任意输入规整为字符串列表。"""
        if not isinstance(values, list):
            return []
        normalized: List[str] = []
        for item in values:
            text = str(item).strip()
            if not text:
                continue
            normalized.append(text)
            if limit > 0 and len(normalized) >= limit:
                break
        return normalized

    @staticmethod
    def _format_action_history_entry(entry: Any) -> str:
        """将行动历史项规整为可注入 prompt 的简短文本。"""
        if isinstance(entry, dict):
            chapter = str(entry.get("chapter", "")).strip()
            action = str(entry.get("action", "")).strip()
            reason = str(entry.get("reason", "")).strip()
            outcome = str(entry.get("outcome", "")).strip()
            impact = str(entry.get("impact", "")).strip()

            if not action:
                fallback = str(entry.get("summary", "")).strip()
                if fallback:
                    action = fallback
                elif not reason and not outcome and not impact:
                    return ""

            parts = []
            if action:
                parts.append(action)
            if reason:
                parts.append(f"动机:{reason}")
            if outcome:
                parts.append(f"结果:{outcome}")
            if impact:
                parts.append(f"影响:{impact}")
            body = "；".join(parts).strip()
            if not body:
                return ""
            if chapter:
                return f"第{chapter}章:{body}"
            return body

        plain = str(entry).strip()
        return plain

    def _build_character_memory_lines(self, char: Dict[str, Any]) -> List[str]:
        """构建角色的状态与记忆上下文（用于生成前注入）。"""
        lines: List[str] = []

        current_goal = str(char.get("current_goal", "")).strip()
        if current_goal:
            lines.append(f"  · 当前目标: {current_goal}")

        physical_state = str(char.get("physical_state", "")).strip()
        mental_state = str(char.get("mental_state", "")).strip()
        if physical_state or mental_state:
            lines.append(f"  · 身心状态: 体={physical_state or '未知'}; 心={mental_state or '未知'}")

        status_tail = self._to_text_list(char.get("current_status", []), limit=2)
        if status_tail:
            lines.append(f"  · 近期状态: {'；'.join(status_tail)}")

        action_tail: List[str] = []
        raw_actions = char.get("action_history", [])
        if isinstance(raw_actions, list):
            for item in raw_actions[-3:]:
                action_text = self._format_action_history_entry(item)
                if action_text:
                    action_tail.append(action_text)
        if action_tail:
            lines.append(f"  · 行动历史: {' | '.join(action_tail)}")

        memory_short = self._to_text_list(char.get("memory_short_term", []), limit=2)
        if memory_short:
            lines.append(f"  · 近期记忆: {'；'.join(memory_short)}")

        memory_long = self._to_text_list(char.get("memory_long_term", []), limit=2)
        if memory_long:
            lines.append(f"  · 长期记忆: {'；'.join(memory_long)}")

        return lines

    def _build_context(self) -> str:
        """构建世界模型上下文。"""
        context_parts = []

        if "characters" in self.world_data:
            context_parts.append("【登场角色】")
            for char in self.world_data["characters"][:8]:
                role_tag = f"[{char.get('role', '配角')}]"
                personality = char.get("personality", "")
                try:
                    level = char.get("level", "凡人")
                    abilities = ", ".join(char.get("abilities", []))
                    items = ", ".join(char.get("items", []))

                    char_desc = f"- {char.get('name', '?')} {role_tag}: {personality} | 境界: {level}"
                    if abilities:
                        char_desc += f" | 功法: {abilities}"
                    if items:
                        char_desc += f" | 法宝: {items}"

                    if char.get("relationships"):
                        rels = []
                        for rel in char.get("relationships", []):
                            if isinstance(rel, dict):
                                rel_str = f"{rel.get('relation_type')}->{rel.get('target')}"
                                if rel.get("description"):
                                    rel_str += f"({rel.get('description')})"
                                rels.append(rel_str)
                        if rels:
                            char_desc += f" | 关系: {', '.join(rels)}"

                    context_parts.append(char_desc)
                    context_parts.extend(self._build_character_memory_lines(char))
                except Exception:
                    context_parts.append(f"- {char.get('name', '?')} {role_tag}: {personality}")

        if "world" in self.world_data:
            world = self.world_data["world"]
            context_parts.append("\n【世界设定】")
            if world.get("cultivation_systems"):
                context_parts.append(self._get_cultivation_info_str())
            elif world.get("power_system"):
                ps = world.get("power_system")
                if isinstance(ps, str):
                    context_parts.append(f"- 力量体系: {ps[:200]}")
                elif isinstance(ps, dict):
                    context_parts.append(f"- 力量体系: {str(ps)[:300]}")

            if world.get("known_methods"):
                context_parts.append(f"- 知名功法: {', '.join(world.get('known_methods', [])[:5])}")
            if world.get("known_artifacts"):
                context_parts.append(f"- 知名法宝: {', '.join(world.get('known_artifacts', [])[:5])}")

            if isinstance(world.get("environment"), str):
                context_parts.append(f"- 环境: {world['environment'][:100]}")

        progression_rules = self._get_world_breakthrough_rules_str()
        if progression_rules:
            context_parts.append("\n【境界晋升硬规则】")
            context_parts.append(progression_rules)

        return "\n".join(context_parts)

    def _get_cultivation_info_str(self) -> str:
        """获取结构化修炼体系描述。"""
        if not self.world_data or "world" not in self.world_data:
            return ""

        world = self.world_data["world"]
        if not world.get("cultivation_systems"):
            return ""

        parts = ["【修炼体系详情】"]
        for system in world.get("cultivation_systems", []):
            desc = system.get("description", "")
            parts.append(f"  * {system.get('name')}: {desc}")
            ranks = sorted(system.get("ranks", []), key=lambda x: x.get("level_index", 0))
            rank_str = " -> ".join([f"{rank.get('name')}" for rank in ranks])
            parts.append(f"    等级序列: {rank_str}")
            for rank in ranks:
                if rank.get("abilities"):
                    parts.append(f"    - {rank.get('name')}特征: {', '.join(rank.get('abilities'))}")
        return "\n".join(parts)

    def _get_level_format_guide_str(self) -> str:
        """提供境界输出格式约束，避免出现“道士/人类”这类过粗标签。"""
        world = self.world_data.get("world", {}) if isinstance(self.world_data, dict) else {}
        systems = world.get("cultivation_systems", []) if isinstance(world, dict) else []
        examples = []
        for system in systems:
            if not isinstance(system, dict):
                continue
            system_name = str(system.get("name", "")).strip()
            ranks = system.get("ranks", [])
            if not system_name or not isinstance(ranks, list) or not ranks:
                continue
            first_rank = str(ranks[0].get("name", "")).strip() if isinstance(ranks[0], dict) else ""
            if first_rank:
                examples.append(f"{system_name}·{first_rank}·初期")
        if not examples:
            examples = ["鬼道·怨灵境·后期", "人道·灵台境·中期", "武道·百战境·后期"]
        return (
            "【境界输出格式要求】\n"
            "1. level_update 必须使用“体系·大境界·小阶段”格式，例如："
            + "；".join(examples[:3])
            + "\n"
            "2. 禁止使用“人类/道士/武夫/将军/修士/鬼物/未知”等粗粒度标签作为最终境界。"
        )

    def _get_world_breakthrough_rules_str(self) -> str:
        """从 world_state 提取境界突破硬规则与主角当前任务。"""
        world = self.world_data.get("world", {}) if isinstance(self.world_data, dict) else {}
        if not isinstance(world, dict):
            return ""

        parts: List[str] = []
        rules = world.get("realm_upgrade_rules", {})
        if isinstance(rules, dict):
            hard_constraints = rules.get("hard_constraints", [])
            if isinstance(hard_constraints, list) and hard_constraints:
                parts.append("硬规则: " + "；".join(str(item).strip() for item in hard_constraints[:4] if str(item).strip()))

            systems = rules.get("systems", [])
            if isinstance(systems, list):
                for system in systems[:3]:
                    if not isinstance(system, dict):
                        continue
                    name = str(system.get("name", "")).strip()
                    transitions = system.get("transitions", [])
                    if not name or not isinstance(transitions, list) or not transitions:
                        continue
                    first_transition = transitions[0] if isinstance(transitions[0], dict) else {}
                    sample = ""
                    if first_transition:
                        sample = (
                            f"{first_transition.get('from_level', '?')}→{first_transition.get('to_level', '?')}"
                        )
                    parts.append(f"{name}突破链: 共{len(transitions)}阶，示例 {sample}")

        progression = world.get("protagonist_progression", {})
        if isinstance(progression, dict):
            current_level = str(progression.get("current_level", "")).strip()
            next_level = str(progression.get("next_level", "")).strip()
            active = self._get_active_transition(progression)
            if current_level:
                line = f"主角当前境界: {current_level}"
                if next_level:
                    line += f" | 下一目标: {next_level}"
                parts.append(line)
            if isinstance(active, dict):
                missing = self._collect_missing_requirements(active)
                if missing:
                    parts.append("主角当前卡点: " + "；".join(missing[:4]))

        return "\n".join(f"- {line}" for line in parts if line)

    @staticmethod
    def _extract_outline_section(outline_text: str, heading_keyword: str) -> str:
        """按二级标题关键字抽取大纲片段。"""
        if not outline_text or not heading_keyword:
            return ""

        lines = outline_text.splitlines()
        start_idx = -1
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("##") and heading_keyword in stripped:
                start_idx = idx
                break

        if start_idx < 0:
            return ""

        end_idx = len(lines)
        for idx in range(start_idx + 1, len(lines)):
            stripped = lines[idx].strip()
            if stripped.startswith("## "):
                end_idx = idx
                break
        return "\n".join(lines[start_idx:end_idx]).strip()

    def _build_realm_rules_context(self, outline_full: str) -> str:
        """组合大纲与 world_state 中的境界规则，供 prompt 强约束。"""
        parts: List[str] = []
        outline_rules = self._extract_outline_section(outline_full, "境界晋升总纲")
        if outline_rules:
            parts.append(f"【大纲-境界晋升总纲】\n{outline_rules[:3000]}")
        world_rules = self._get_world_breakthrough_rules_str()
        if world_rules:
            parts.append(f"【世界模型-境界规则】\n{world_rules}")
        return "\n\n".join(parts)

    def _load_outline(self) -> str:
        """加载大纲。"""
        try:
            outline_path = os.path.join(self.storage.get_project_dir(self.project_name), "大纲.txt")
            if os.path.exists(outline_path):
                with open(outline_path, "r", encoding="utf-8") as f:
                    return f.read()[: self.OUTLINE_MAX_CHARS]
        except OSError:
            pass
        return ""

    def _load_style_ref(self) -> str:
        """加载风格参考文本。"""
        try:
            ref_path = os.path.join(self.storage.base_dir, "reference.txt")
            if os.path.exists(ref_path):
                with open(ref_path, "r", encoding="utf-8") as f:
                    return f.read()[:2000]
        except OSError:
            pass
        return ""

    @staticmethod
    def _build_style_prompt(style_ref: str) -> str:
        if not style_ref:
            return ""
        return f"\n【风格参考】\n请严格模仿以下文本的句式节奏、段落长度和描写风格：\n{style_ref}\n"

    def _resolve_generation_target(
        self, ch_num: int, ch_title: str, ch_content: str, ch_len: int, outline_full: str
    ) -> Dict[str, Any]:
        if ch_len < self.MIN_CHAPTER_LENGTH and ch_num > 0:
            mode = "append"
            target_chapter = ch_num
            target_words = self.MIN_CHAPTER_LENGTH - ch_len + 500
        else:
            mode = "new"
            target_chapter = ch_num + 1
            target_words = config.default_chapter_words + 500

        return {
            "mode": mode,
            "chapter_num": target_chapter,
            "chapter_title": ch_title,
            "chapter_content": ch_content,
            "chapter_len": ch_len,
            "target_words": target_words,
            "outline_info": self._parse_outline_for_chapter(outline_full, target_chapter),
        }

    @staticmethod
    def _extract_title_from_output(full_content: str, chapter_num: int) -> str:
        for line in full_content.split("\n")[:5]:
            if "章" in line and "：" in line:
                return line.split("：", 1)[-1].strip() or f"第{chapter_num}章"
            if "章" in line and ":" in line:
                return line.split(":", 1)[-1].strip() or f"第{chapter_num}章"
        return f"第{chapter_num}章"

    def _run_thinking(
        self,
        chapter_num: int,
        outline_info: Dict[str, str],
        world_context: str,
        previous_content: str,
        is_append: bool,
    ) -> Generator[Any, None, None]:
        """Run plot thinking with auto mode selection and stream outputs."""
        if not self.thinking_engine:
            return

        thinking_mode, reason = resolve_thinking_mode(
            config.thinking_mode,
            is_append=is_append,
            chapter_num=chapter_num,
            previous_content=previous_content,
        )
        yield f"⚙️ 思考模式: {thinking_mode}（{reason}）\n"
        for output in self.thinking_engine.analyze_chapter(
            chapter_num=chapter_num,
            outline_info=outline_info,
            world_context=world_context,
            previous_content=previous_content,
            is_append=is_append,
            thinking_mode=thinking_mode,
        ):
            yield output

    def _select_characters_for_action_graph(self, limit: int = 6) -> List[Dict[str, Any]]:
        characters = self.world_data.get("characters", [])
        if not isinstance(characters, list):
            return []

        scored: List[Tuple[Tuple[int, int, int], Dict[str, Any]]] = []
        for index, char in enumerate(characters):
            if not isinstance(char, dict):
                continue
            role = str(char.get("role", "")).strip().lower()
            role_score = 0 if role in {"主角", "protagonist"} else 1
            has_dynamic_state = 0
            if self._to_text_list(char.get("current_status", []), limit=1):
                has_dynamic_state += 1
            if isinstance(char.get("action_history"), list) and char.get("action_history"):
                has_dynamic_state += 1
            if isinstance(char.get("relationships"), list) and char.get("relationships"):
                has_dynamic_state += 1
            # 按角色重要性 + 动态信息量排序，索引用于保持稳定顺序。
            score = (role_score, -has_dynamic_state, index)
            scored.append((score, char))

        scored.sort(key=lambda item: item[0])
        return [item[1] for item in scored[:limit]]

    def _summarize_storyboard_seed(self, thinking_plan: Optional[Dict[str, Any]]) -> str:
        if not isinstance(thinking_plan, dict):
            return ""
        blueprint = thinking_plan.get("chapter_blueprint", thinking_plan.get("chapter_plan", {}))
        if not isinstance(blueprint, dict):
            return ""
        storyboard = blueprint.get("storyboard", blueprint.get("scenes", []))
        if not isinstance(storyboard, list):
            return ""

        lines: List[str] = []
        for shot in storyboard[:3]:
            if not isinstance(shot, dict):
                continue
            loc = str(shot.get("location", "未知场景")).strip()
            purpose = str(shot.get("purpose", "")).strip()
            action = ""
            action_beats = shot.get("action_beats", [])
            if isinstance(action_beats, list):
                for beat in action_beats:
                    if isinstance(beat, dict):
                        action = str(beat.get("action", "")).strip()
                        if action:
                            break
            line = f"- {loc}"
            if purpose:
                line += f" | 目的: {purpose}"
            if action:
                line += f" | 核心动作: {action}"
            lines.append(line)
        return "\n".join(lines)

    def _build_character_action_prompt(
        self,
        chapter_num: int,
        outline_info: Dict[str, str],
        previous_content: str,
        thinking_plan: Optional[Dict[str, Any]],
        candidates: List[Dict[str, Any]],
    ) -> str:
        char_blocks: List[str] = []
        for char in candidates:
            name = str(char.get("name", "?")).strip() or "?"
            role = str(char.get("role", "配角")).strip()
            personality = str(char.get("personality", "")).strip()
            desire = str(char.get("desire", "")).strip()
            goal = str(char.get("current_goal", "")).strip()
            level = str(char.get("level", "凡人")).strip()
            physical = str(char.get("physical_state", "")).strip()
            mental = str(char.get("mental_state", "")).strip()
            status_tail = self._to_text_list(char.get("current_status", []), limit=2)
            action_tail: List[str] = []
            if isinstance(char.get("action_history"), list):
                for action in char.get("action_history", [])[-3:]:
                    formatted = self._format_action_history_entry(action)
                    if formatted:
                        action_tail.append(formatted)
            rels = []
            for rel in char.get("relationships", [])[:3]:
                if not isinstance(rel, dict):
                    continue
                rel_type = str(rel.get("relation_type", "未知")).strip()
                target = str(rel.get("target", "?")).strip()
                if target:
                    rels.append(f"{rel_type}->{target}")

            block = (
                f"- {name} [{role}] | 性格:{personality or '未知'} | 渴望:{desire or '未知'} | "
                f"当前目标:{goal or '未设定'} | 境界:{level or '未知'}"
            )
            if physical or mental:
                block += f"\n  状态: 体={physical or '未知'}; 心={mental or '未知'}"
            if status_tail:
                block += f"\n  近期状态: {'；'.join(status_tail)}"
            if action_tail:
                block += f"\n  行动历史: {' | '.join(action_tail)}"
            if rels:
                block += f"\n  关系网: {', '.join(rels)}"
            char_blocks.append(block)

        storyboard_seed = self._summarize_storyboard_seed(thinking_plan)
        previous_tail = previous_content[-1500:] if previous_content else "（故事开头）"

        return f"""你现在要做“角色行动图推演”，思路参考 LangGraph 的节点流：
1) 读取每个角色的人格+记忆+当前状态；
2) 先做角色私有决策，再合成整体场景行动顺序；
3) 输出可直接用于写作的结构化 JSON。

【章节】第{chapter_num}章
【本卷目标】{outline_info.get('volume', '')}
【当前阶段】{outline_info.get('phase', '')}
【本章目标】{outline_info.get('specific_goal', '')}

【前文结尾】
{previous_tail}

【剧情分镜种子】
{storyboard_seed or '（无分镜，按本章目标推演）'}

【候选角色（按优先级）】
{chr(10).join(char_blocks)}

请输出 JSON（不要解释）：
{{
  "scene_overview": "本章场景驱动力（50字内）",
  "character_plans": [
    {{
      "name": "角色名",
      "personality_anchor": "本章最影响其决策的性格锚点",
      "current_goal": "该角色本章短期目标",
      "internal_thought": "该角色的内心判断",
      "action_choice": "最终行动选择",
      "interaction_targets": ["优先交互对象"],
      "risk_assessment": "该选择的主要风险",
      "expected_change": "行动后可能发生的状态变化",
      "memory_implication": {{
        "short_term": ["应进入短期记忆的事实"],
        "long_term": ["可能进入长期记忆的事件"],
        "action_log": "建议写入行动历史的一句话"
      }}
    }}
  ],
  "scene_action_order": [
    {{
      "step": 1,
      "actor": "角色名",
      "action": "动作",
      "reason": "为什么这么做"
    }}
  ]
}}

约束：
1. `character_plans` 需覆盖至少 3 名角色（若候选不足则全覆盖）。
2. 行动必须符合角色性格与既有关系，不得 OOC。
3. scene_action_order 至少 3 步，且与 character_plans 一致。
4. 严格只输出 JSON。"""

    def _build_default_character_action_plan(
        self,
        candidates: List[Dict[str, Any]],
        outline_info: Dict[str, str],
    ) -> Dict[str, Any]:
        plans: List[Dict[str, Any]] = []
        order: List[Dict[str, Any]] = []
        for idx, char in enumerate(candidates[:6], 1):
            if not isinstance(char, dict):
                continue
            name = str(char.get("name", "")).strip()
            if not name:
                continue
            goal = str(char.get("current_goal") or char.get("desire") or "").strip()
            if not goal:
                goal = "维持当前生存与优势"
            personality = str(char.get("personality", "")).strip()
            action_choice = f"围绕“{goal}”谨慎推进并观察局势变化"
            plans.append(
                {
                    "name": name,
                    "personality_anchor": personality or "谨慎",
                    "current_goal": goal,
                    "internal_thought": f"先确保自身安全，再寻找推进“{goal}”的机会",
                    "action_choice": action_choice,
                    "interaction_targets": [],
                    "risk_assessment": "信息不足导致判断偏差",
                    "expected_change": "状态小幅波动",
                    "memory_implication": {
                        "short_term": [f"{name}在本章尝试推进目标：{goal}"],
                        "long_term": [],
                        "action_log": action_choice,
                    },
                }
            )
            order.append({"step": idx, "actor": name, "action": action_choice, "reason": "目标驱动"})

        scene_goal = str(outline_info.get("specific_goal", "")).strip()
        return {
            "scene_overview": scene_goal[:60] if scene_goal else "角色围绕当前矛盾推进行动",
            "character_plans": plans,
            "scene_action_order": order,
        }

    def _normalize_character_action_plan(
        self,
        raw_plan: Optional[Dict[str, Any]],
        candidates: List[Dict[str, Any]],
        outline_info: Dict[str, str],
    ) -> Dict[str, Any]:
        if not isinstance(raw_plan, dict):
            return self._build_default_character_action_plan(candidates, outline_info)

        normalized: Dict[str, Any] = {
            "scene_overview": str(raw_plan.get("scene_overview", "")).strip(),
            "character_plans": [],
            "scene_action_order": [],
        }
        candidate_names = {
            str(char.get("name", "")).strip() for char in candidates if isinstance(char, dict) and str(char.get("name", "")).strip()
        }

        raw_character_plans = raw_plan.get("character_plans", [])
        if isinstance(raw_character_plans, list):
            for item in raw_character_plans:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name", "")).strip()
                if not name:
                    continue
                # 限制在候选集合内，避免模型扩散出无关角色。
                if candidate_names and name not in candidate_names:
                    continue
                memory_implication = item.get("memory_implication", {})
                memory_implication = memory_implication if isinstance(memory_implication, dict) else {}
                normalized["character_plans"].append(
                    {
                        "name": name,
                        "personality_anchor": str(item.get("personality_anchor", "")).strip(),
                        "current_goal": str(item.get("current_goal", "")).strip(),
                        "internal_thought": str(item.get("internal_thought", "")).strip(),
                        "action_choice": str(item.get("action_choice", "")).strip(),
                        "interaction_targets": self._to_text_list(item.get("interaction_targets", []), limit=3),
                        "risk_assessment": str(item.get("risk_assessment", "")).strip(),
                        "expected_change": str(item.get("expected_change", "")).strip(),
                        "memory_implication": {
                            "short_term": self._to_text_list(memory_implication.get("short_term", []), limit=2),
                            "long_term": self._to_text_list(memory_implication.get("long_term", []), limit=2),
                            "action_log": str(memory_implication.get("action_log", "")).strip(),
                        },
                    }
                )
                if len(normalized["character_plans"]) >= 6:
                    break

        raw_action_order = raw_plan.get("scene_action_order", [])
        if isinstance(raw_action_order, list):
            for item in raw_action_order:
                if not isinstance(item, dict):
                    continue
                actor = str(item.get("actor", "")).strip()
                action = str(item.get("action", "")).strip()
                reason = str(item.get("reason", "")).strip()
                if not actor or not action:
                    continue
                if candidate_names and actor not in candidate_names:
                    continue
                step_val = item.get("step")
                step = step_val if isinstance(step_val, int) and step_val > 0 else len(normalized["scene_action_order"]) + 1
                normalized["scene_action_order"].append(
                    {"step": step, "actor": actor, "action": action, "reason": reason}
                )
                if len(normalized["scene_action_order"]) >= 8:
                    break

        if not normalized["character_plans"]:
            return self._build_default_character_action_plan(candidates, outline_info)

        if not normalized["scene_overview"]:
            scene_goal = str(outline_info.get("specific_goal", "")).strip()
            normalized["scene_overview"] = scene_goal[:60] if scene_goal else "角色围绕冲突推进"

        if not normalized["scene_action_order"]:
            normalized["scene_action_order"] = [
                {
                    "step": index + 1,
                    "actor": item.get("name", ""),
                    "action": item.get("action_choice", ""),
                    "reason": item.get("current_goal", ""),
                }
                for index, item in enumerate(normalized["character_plans"][:5])
                if item.get("name") and item.get("action_choice")
            ]

        return normalized

    @staticmethod
    def _format_character_action_summary(plan: Dict[str, Any]) -> str:
        scene = str(plan.get("scene_overview", "")).strip()
        plans = plan.get("character_plans", [])
        if not isinstance(plans, list):
            plans = []
        names = [str(item.get("name", "")).strip() for item in plans if isinstance(item, dict) and str(item.get("name", "")).strip()]
        name_text = "、".join(names[:4]) if names else "无"
        scene_order = plan.get("scene_action_order", [])
        order_count = len(scene_order) if isinstance(scene_order, list) else 0
        if scene:
            return f"🎭 角色行动推演完成: {len(names)}人（{name_text}） | 场景:{scene[:30]} | 动作链:{order_count}步"
        return f"🎭 角色行动推演完成: {len(names)}人（{name_text}） | 动作链:{order_count}步"

    def _format_character_action_for_generation(self, plan: Optional[Dict[str, Any]]) -> str:
        if not isinstance(plan, dict):
            return ""
        lines: List[str] = ["【角色行动决策（场景级推演）】"]
        overview = str(plan.get("scene_overview", "")).strip()
        if overview:
            lines.append(f"场景驱动力：{overview}")

        character_plans = plan.get("character_plans", [])
        if isinstance(character_plans, list):
            for item in character_plans[:6]:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name", "")).strip()
                action_choice = str(item.get("action_choice", "")).strip()
                if not name or not action_choice:
                    continue
                personality_anchor = str(item.get("personality_anchor", "")).strip()
                goal = str(item.get("current_goal", "")).strip()
                thought = str(item.get("internal_thought", "")).strip()
                risk = str(item.get("risk_assessment", "")).strip()
                line = f"- {name}: 行动={action_choice}"
                if goal:
                    line += f" | 目标={goal}"
                if personality_anchor:
                    line += f" | 性格锚点={personality_anchor}"
                lines.append(line)
                if thought:
                    lines.append(f"  内心判断: {thought}")
                if risk:
                    lines.append(f"  主要风险: {risk}")

        scene_order = plan.get("scene_action_order", [])
        if isinstance(scene_order, list) and scene_order:
            lines.append("行动顺序（写作时尽量遵循）:")
            for item in scene_order[:6]:
                if not isinstance(item, dict):
                    continue
                actor = str(item.get("actor", "")).strip()
                action = str(item.get("action", "")).strip()
                reason = str(item.get("reason", "")).strip()
                if not actor or not action:
                    continue
                step = item.get("step")
                step_label = step if isinstance(step, int) else "?"
                line = f"{step_label}. {actor} -> {action}"
                if reason:
                    line += f"（因: {reason}）"
                lines.append(line)
        return "\n".join(lines)

    def _run_character_action_graph(
        self,
        chapter_num: int,
        outline_info: Dict[str, str],
        previous_content: str,
        thinking_plan: Optional[Dict[str, Any]],
    ) -> Generator[Any, None, None]:
        candidates = self._select_characters_for_action_graph(limit=6)
        if not candidates:
            yield {"scene_overview": "", "character_plans": [], "scene_action_order": []}
            return

        plan_ai, source = self._get_state_update_ai()
        yield f"🎭 正在推演角色行动（{source}）...\n"
        prompt = self._build_character_action_prompt(
            chapter_num=chapter_num,
            outline_info=outline_info,
            previous_content=previous_content,
            thinking_plan=thinking_plan,
            candidates=candidates,
        )
        response_text = ""
        request_kwargs: Dict[str, Any] = {}
        if self._is_glm_model(plan_ai):
            request_kwargs["thinking"] = {"type": "enabled"}
        for chunk in plan_ai.stream_chat(
            prompt,
            system_prompt="你是角色行为模拟器。按角色性格与记忆推演本章行动，只输出JSON。",
            **request_kwargs,
        ):
            response_text += chunk

        parsed = self._extract_json_dict(response_text)
        plan = self._normalize_character_action_plan(parsed, candidates, outline_info)
        yield self._format_character_action_summary(plan) + "\n"
        yield plan

    def _build_generation_prompt(
        self,
        mode: str,
        chapter_num: int,
        chapter_title: str,
        chapter_content: str,
        chapter_len: int,
        target_words: int,
        world_context: str,
        style_prompt: str,
        outline_info: Dict[str, str],
        thinking_context: str,
        character_action_context: str,
        realm_rules_context: str,
        strict_continuity: bool,
    ) -> str:
        rules_block = ""
        if realm_rules_context:
            rules_block = (
                f"\n【境界晋升约束（必须遵守）】\n{realm_rules_context}\n"
                "硬性要求：主角若未满足下一境突破条件，不得直接突破，只能描写筹备、受阻或失败。\n"
            )

        if mode == "append":
            return f"""请继续续写以下章节内容，直到本章达到3000字以上。

{world_context}
{style_prompt}
【本卷进度】{outline_info.get('volume', '')}
【当前阶段】{outline_info.get('phase', '')}
【本章指引】{outline_info.get('specific_goal', '')}

{thinking_context}
{character_action_context}
{rules_block}

【当前章节】第{chapter_num}章《{chapter_title}》
【当前字数】{chapter_len}字
【还需】约{target_words}字

【已有内容】
{chapter_content[-2000:]}

请直接续写（不要重复已有内容）：
"""

        if strict_continuity:
            previous_context_block = f"""【前一章结尾 - 本章必须紧接此处续写】
------
{chapter_content[-3000:] if chapter_content else '（故事开头，请按大纲创作第1章）'}
------

⚠️ 重要：本章内容必须自然衔接上面的前章结尾，不要重复前章内容，直接从新场景/新时间开始。"""
            writing_requirements = """【写作要求】
1. 字数：3000-4000字
2. 角色行为符合性格设定和分镜剧本规划
3. 节奏：按分镜剧本的紧张度曲线写
4. 对话要有个性，按剧本中的台词和语气来写
5. 请先给本章起一个标题"""
            planning_line = "（请严格按照上述分镜剧本来写作，确保剧情推进符合规划）"
        else:
            previous_context_block = f"""【前情提要】
{chapter_content[-1500:] if chapter_content else '故事开始'}"""
            writing_requirements = """【写作要求】
1. 字数：3000-4000字
2. 角色行为符合性格设定和上述规划
3. 节奏：铺垫→冲突→小高潮→钩子
4. 对话要有个性
5. 请先给本章起一个标题"""
            planning_line = "（请严格按照上述剧情规划来构思，确保剧情推进符合大纲节奏）"

        return f"""请创作小说第{chapter_num}章的完整内容（3000-4000字）。

{world_context}
{style_prompt}
【剧情指引-严禁偏离】
1. 本卷目标：{outline_info.get('volume', '')}
2. 当前阶段：{outline_info.get('phase', '')}
3. 本章具体情节：
{outline_info.get('specific_goal', '')}

{thinking_context}
{character_action_context}
{rules_block}

{planning_line}

{previous_context_block}

{writing_requirements}

请按格式输出：
## 第{chapter_num}章：[标题]

[正文内容]
"""

    def _build_generation_result(
        self, mode: str, chapter_num: int, chapter_title: str, previous_content: str, generated_content: str
    ) -> Dict[str, Any]:
        if mode == "append":
            full_text = previous_content + "\n\n" + generated_content
            title = chapter_title
        else:
            full_text = generated_content
            title = self._extract_title_from_output(generated_content, chapter_num)

        return {
            "mode": mode,
            "chapter": chapter_num,
            "title": title,
            "added_words": count_chinese_words(generated_content),
            "total_words": count_chinese_words(full_text),
            "new_content": generated_content,
            "full_text": full_text,
            "updating_world": False,
        }

    def _parse_outline_for_chapter(self, outline_text: str, chapter_num: int) -> Dict[str, str]:
        """解析大纲，获取指定章节的卷、阶段和具体目标。"""
        import re

        result = {"volume": "", "phase": "", "specific_goal": ""}
        lines = outline_text.split("\n")
        current_volume = ""
        current_phase = ""

        vol_pattern = re.compile(r"^##\s+(.+?)(?:（第(\d+)-(\d+)章）)?$")
        phase_pattern = re.compile(r"^###\s+(.+?)(?:（第(\d+)-(\d+)章）)?$")
        item_pattern = re.compile(r"^\s*-\s*\*\*(?:第)?(\d+)(?:-(\d+))?章\*\*[:：](.+)$")

        for line_idx, raw_line in enumerate(lines):
            line = raw_line.strip()
            if not line:
                continue

            vol_match = vol_pattern.match(line)
            if vol_match:
                title = vol_match.group(1)
                start_ch = int(vol_match.group(2)) if vol_match.group(2) else 0
                end_ch = int(vol_match.group(3)) if vol_match.group(3) else 9999
                if start_ch <= chapter_num <= end_ch:
                    current_volume = title
                    current_phase = ""
                continue

            phase_match = phase_pattern.match(line)
            if phase_match:
                title = phase_match.group(1)
                start_ch = int(phase_match.group(2)) if phase_match.group(2) else 0
                end_ch = int(phase_match.group(3)) if phase_match.group(3) else 9999
                if start_ch <= chapter_num <= end_ch:
                    current_phase = title
                continue

            item_match = item_pattern.match(line)
            if not item_match:
                continue

            start_ch = int(item_match.group(1))
            end_ch = int(item_match.group(2)) if item_match.group(2) else start_ch
            if not (start_ch <= chapter_num <= end_ch):
                continue

            result["specific_goal"] = item_match.group(3).strip()
            idx = line_idx + 1
            details = []
            while idx < len(lines):
                next_line = lines[idx].strip()
                if not next_line:
                    idx += 1
                    continue
                if next_line.startswith("#") or next_line.startswith("- **"):
                    break
                if next_line.startswith("-") or next_line.startswith("*"):
                    details.append(next_line.lstrip("-* "))
                else:
                    details.append(next_line)
                idx += 1

            if details:
                result["specific_goal"] += "\n详情：" + "\n".join(details)
            result["volume"] = current_volume
            result["phase"] = current_phase
            return result

        result["volume"] = current_volume
        result["phase"] = current_phase
        return result

    def continue_writing(self) -> Generator[str, None, Dict[str, Any]]:
        """自动续写入口（委托到写作服务）。"""
        return self._writing_service.continue_writing(self)

    def prepare_writing(self) -> Generator[str, None, Dict[str, Any]]:
        """准备阶段入口（委托到准备服务）。"""
        return self._preparation_service.prepare(self)

    def generate_from_plan(self, preparation: Dict[str, Any]) -> Generator[str, None, Dict[str, Any]]:
        """生成阶段入口（委托到写作服务）。"""
        return self._writing_service.generate_from_plan(self, preparation)

    def update_world_state(self, new_content: str) -> Generator[str, None, dict]:
        """世界状态更新入口（委托到状态服务）。"""
        return self._world_state_service.update(self, new_content)

    def _get_state_update_ai(self) -> Tuple[Any, str]:
        """状态更新优先使用思考模型。"""
        if self.thinking_engine and getattr(self.thinking_engine, "ai", None):
            return self.thinking_engine.ai, "think"
        return self.ai, "chat"

    @staticmethod
    def _is_glm_model(ai_client: Any) -> bool:
        model_name = str(getattr(ai_client, "model_name", "")).lower()
        return "glm" in model_name

    @staticmethod
    def _extract_json_dict(response_text: str) -> Optional[Dict[str, Any]]:
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            first_newline = cleaned.find("\n")
            if first_newline > 0:
                cleaned = cleaned[first_newline + 1:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3].strip()

        json_start = cleaned.find("{")
        json_end = cleaned.rfind("}") + 1
        if json_start < 0 or json_end <= json_start:
            return None

        json_str = cleaned[json_start:json_end]
        try:
            parsed = json.loads(json_str)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            if repair_json is None:
                return None
            repaired = repair_json(json_str, return_objects=True)
            return repaired if isinstance(repaired, dict) else None

    @staticmethod
    def _dedupe_keep_order(values: List[str]) -> List[str]:
        result: List[str] = []
        seen = set()
        for value in values:
            if not isinstance(value, str):
                continue
            normalized = value.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
        return result

    @staticmethod
    def _dedupe_action_history(entries: List[Any], limit: int = 40) -> List[Dict[str, Any]]:
        """去重并裁剪行动历史。"""
        normalized_entries: List[Dict[str, Any]] = []
        seen = set()
        for raw in entries:
            if isinstance(raw, dict):
                chapter = raw.get("chapter", "")
                action = str(raw.get("action", "")).strip()
                reason = str(raw.get("reason", "")).strip()
                outcome = str(raw.get("outcome", "")).strip()
                impact = str(raw.get("impact", "")).strip()
                location = str(raw.get("location", "")).strip()
                target = str(raw.get("target", "")).strip()
                tags = raw.get("tags", [])
                if not action:
                    continue
                if isinstance(tags, list):
                    tags = [str(tag).strip() for tag in tags if str(tag).strip()][:4]
                else:
                    tags = []
                key = (str(chapter).strip(), action, reason, outcome, impact, location, target, tuple(tags))
                if key in seen:
                    continue
                seen.add(key)
                item = {"chapter": chapter, "action": action}
                if reason:
                    item["reason"] = reason
                if outcome:
                    item["outcome"] = outcome
                if impact:
                    item["impact"] = impact
                if location:
                    item["location"] = location
                if target:
                    item["target"] = target
                if tags:
                    item["tags"] = tags
                normalized_entries.append(item)
                continue

            text_entry = str(raw).strip()
            if not text_entry:
                continue
            key = ("", text_entry)
            if key in seen:
                continue
            seen.add(key)
            normalized_entries.append({"action": text_entry})

        if limit > 0:
            return normalized_entries[-limit:]
        return normalized_entries

    @staticmethod
    def _is_granular_level(level_text: str) -> bool:
        if not level_text:
            return False
        normalized = level_text.strip()
        if "·" in normalized:
            return True
        if "境" in normalized and len(normalized) >= 4:
            return True
        blocked = {"人类", "道士", "武夫", "将军", "修士", "鬼物", "未知", "凡人"}
        return normalized not in blocked

    @staticmethod
    def _normalize_level_key(level_text: str) -> str:
        """归一化境界字符串，便于比较。"""
        normalized = str(level_text or "").strip()
        if not normalized:
            return ""
        for sep in ("（", "("):
            if sep in normalized:
                normalized = normalized.split(sep, 1)[0].strip()
        parts = [part.strip() for part in normalized.split("·") if part.strip()]
        if len(parts) >= 3:
            return "·".join(parts[:3])
        if len(parts) >= 2:
            return "·".join(parts[:2])
        return normalized

    @staticmethod
    def _is_requirement_done(status_value: str) -> bool:
        normalized = str(status_value or "").strip().lower()
        if not normalized:
            return False
        done_tokens = {
            "done",
            "completed",
            "acquired",
            "fulfilled",
            "已完成",
            "完成",
            "达成",
            "已获取",
            "获取",
            "获得",
            "acquire",
        }
        return normalized in done_tokens

    def _get_protagonist_progression(self) -> Dict[str, Any]:
        world = self.world_data.get("world", {}) if isinstance(self.world_data, dict) else {}
        if not isinstance(world, dict):
            return {}
        progression = world.get("protagonist_progression", {})
        return progression if isinstance(progression, dict) else {}

    @staticmethod
    def _get_active_transition(progression: Dict[str, Any]) -> Dict[str, Any]:
        """获取主角当前生效的突破节点。"""
        if not isinstance(progression, dict):
            return {}

        direct = progression.get("active_transition")
        if isinstance(direct, dict):
            return direct

        transitions = progression.get("transitions", [])
        if not isinstance(transitions, list) or not transitions:
            return {}

        idx = progression.get("active_transition_index")
        if isinstance(idx, int) and 0 <= idx < len(transitions):
            transition = transitions[idx]
            return transition if isinstance(transition, dict) else {}

        for idx, transition in enumerate(transitions):
            if not isinstance(transition, dict):
                continue
            if not transition.get("completed"):
                progression["active_transition_index"] = idx
                return transition
        return {}

    def _mark_transition_progress(
        self,
        progression: Dict[str, Any],
        transition: Dict[str, Any],
        update: Dict[str, Any],
        new_content: str,
    ) -> List[str]:
        """根据本章更新信息推进主角突破任务进度。"""
        logs: List[str] = []

        progress = update.get("breakthrough_progress", {})
        progress = progress if isinstance(progress, dict) else {}
        explicit_resources = set()
        explicit_conditions = set()

        for item in progress.get("resources_acquired", []):
            token = str(item).strip()
            if token:
                explicit_resources.add(token)
        for item in progress.get("conditions_completed", []):
            token = str(item).strip()
            if token:
                explicit_conditions.add(token)

        for item in update.get("new_items", []):
            token = str(item).strip()
            if token:
                explicit_resources.add(token)

        status_entries: List[str] = []
        if update.get("status_change"):
            status_entries.append(str(update.get("status_change")).strip())
        if isinstance(update.get("status_entries"), list):
            status_entries.extend(str(item).strip() for item in update.get("status_entries", []) if str(item).strip())
        for item in status_entries:
            explicit_conditions.add(item)

        combined_text = " ".join(
            list(explicit_resources)
            + list(explicit_conditions)
            + [str(update.get("mental_state", "")).strip(), str(update.get("physical_state", "")).strip(), new_content[:1500]]
        )

        inventory = progression.get("resource_inventory", [])
        if not isinstance(inventory, list):
            inventory = []
            progression["resource_inventory"] = inventory
        for resource_name in explicit_resources:
            if resource_name not in inventory:
                inventory.append(resource_name)
                logs.append(f"主角资源入库: {resource_name}")

        resources = transition.get("required_resources", [])
        if isinstance(resources, list):
            for requirement in resources:
                if not isinstance(requirement, dict):
                    continue
                req_name = str(requirement.get("name", "")).strip()
                if not req_name or self._is_requirement_done(requirement.get("status")):
                    continue
                keywords = requirement.get("keywords", [])
                keyword_hit = isinstance(keywords, list) and any(
                    str(keyword).strip() and str(keyword).strip() in combined_text for keyword in keywords
                )
                if req_name in explicit_resources or req_name in combined_text or keyword_hit:
                    requirement["status"] = "acquired"
                    logs.append(f"主角突破资源达成: {req_name}")

        conditions = transition.get("required_conditions", [])
        if isinstance(conditions, list):
            for condition in conditions:
                if not isinstance(condition, dict):
                    continue
                cond_name = str(condition.get("name", "")).strip()
                if not cond_name or self._is_requirement_done(condition.get("status")):
                    continue
                keywords = condition.get("keywords", [])
                keyword_hit = isinstance(keywords, list) and any(
                    str(keyword).strip() and str(keyword).strip() in combined_text for keyword in keywords
                )
                if cond_name in explicit_conditions or cond_name in combined_text or keyword_hit:
                    condition["status"] = "done"
                    logs.append(f"主角突破条件达成: {cond_name}")

        return logs

    def _collect_missing_requirements(self, transition: Dict[str, Any]) -> List[str]:
        missing: List[str] = []
        resources = transition.get("required_resources", [])
        if isinstance(resources, list):
            for requirement in resources:
                if not isinstance(requirement, dict):
                    continue
                req_name = str(requirement.get("name", "")).strip()
                if req_name and not self._is_requirement_done(requirement.get("status")):
                    missing.append(f"资源:{req_name}")

        conditions = transition.get("required_conditions", [])
        if isinstance(conditions, list):
            for condition in conditions:
                if not isinstance(condition, dict):
                    continue
                cond_name = str(condition.get("name", "")).strip()
                if cond_name and not self._is_requirement_done(condition.get("status")):
                    missing.append(f"条件:{cond_name}")
        return missing

    @staticmethod
    def _find_transition_index(transitions: List[Dict[str, Any]], transition: Dict[str, Any]) -> Optional[int]:
        for idx, item in enumerate(transitions):
            if not isinstance(item, dict):
                continue
            if item is transition:
                return idx
            if (
                item.get("from_level") == transition.get("from_level")
                and item.get("to_level") == transition.get("to_level")
            ):
                return idx
        return None

    def _complete_transition(self, progression: Dict[str, Any], transition: Dict[str, Any], level_update: str):
        transition["completed"] = True
        progression["current_level"] = level_update
        history = progression.get("history", [])
        if not isinstance(history, list):
            history = []
            progression["history"] = history
        history.append(f"突破成功: {transition.get('from_level', '?')} -> {transition.get('to_level', level_update)}")
        progression["history"] = history[-20:]

        transitions = progression.get("transitions", [])
        if not isinstance(transitions, list):
            progression["next_level"] = ""
            progression["active_transition_index"] = None
            return

        idx = self._find_transition_index(transitions, transition)
        if idx is None:
            progression["next_level"] = ""
            progression["active_transition_index"] = None
            return

        next_idx = idx + 1
        while next_idx < len(transitions):
            next_transition = transitions[next_idx]
            if isinstance(next_transition, dict) and not next_transition.get("completed"):
                progression["active_transition_index"] = next_idx
                progression["next_level"] = next_transition.get("to_level", "")
                return
            next_idx += 1
        progression["active_transition_index"] = None
        progression["next_level"] = ""

    def _handle_protagonist_level_update(
        self,
        char: Dict[str, Any],
        update: Dict[str, Any],
        new_content: str,
        level_update: str,
    ) -> Tuple[bool, str, List[str]]:
        """校验主角升级是否满足资源门槛。"""
        progression = self._get_protagonist_progression()
        if not progression:
            return True, "", []

        protagonist_name = str(progression.get("name", "")).strip()
        if protagonist_name and char.get("name") != protagonist_name:
            return True, "", []

        transition = self._get_active_transition(progression)
        if not transition:
            progression["current_level"] = level_update
            return True, "", [f"主角境界同步: {level_update}"]

        logs = self._mark_transition_progress(
            progression=progression,
            transition=transition,
            update=update,
            new_content=new_content,
        )

        expected_level = self._normalize_level_key(str(transition.get("to_level", "")).strip())
        requested_level = self._normalize_level_key(level_update)
        current_level = self._normalize_level_key(str(progression.get("current_level") or char.get("level", "")).strip())

        if requested_level == current_level:
            return True, "", logs

        if expected_level and requested_level != expected_level:
            return False, f"主角升级路径固定，下一境应为 {transition.get('to_level', expected_level)}", logs

        missing = self._collect_missing_requirements(transition)
        if missing:
            return False, "主角突破条件未满足：" + "；".join(missing[:4]), logs

        self._complete_transition(progression, transition, level_update)
        logs.append(f"主角突破成功: {transition.get('from_level', '?')} -> {transition.get('to_level', level_update)}")
        return True, "", logs

    def _apply_relationship_updates(self, char: Dict[str, Any], relationship_updates: List[Dict[str, Any]]):
        char.setdefault("relationships", [])
        if not isinstance(char["relationships"], list):
            char["relationships"] = []

        for update in relationship_updates:
            if not isinstance(update, dict):
                continue
            target = str(update.get("target", "")).strip()
            if not target:
                continue
            relation_type = str(update.get("relation_type") or update.get("type") or "").strip()
            description = str(update.get("description", "")).strip()

            existing = next(
                (item for item in char["relationships"] if isinstance(item, dict) and item.get("target") == target),
                None,
            )
            if existing is None:
                char["relationships"].append(
                    {
                        "target": target,
                        "relation_type": relation_type or "未知",
                        "description": description,
                    }
                )
            else:
                if relation_type:
                    existing["relation_type"] = relation_type
                if description:
                    existing["description"] = description

    @staticmethod
    def _build_world_update_summary_lines(updates: Dict[str, Any]) -> List[str]:
        lines: List[str] = []

        character_updates = updates.get("character_updates", [])
        if not isinstance(character_updates, list):
            character_updates = []
        character_names = []
        relationship_change_count = 0
        status_change_count = 0
        goal_change_count = 0
        action_history_count = 0
        memory_change_count = 0
        for update in character_updates:
            if not isinstance(update, dict):
                continue
            name = str(update.get("name", "")).strip()
            if name:
                character_names.append(name)
            if update.get("status_change"):
                status_change_count += 1
            if isinstance(update.get("status_entries"), list):
                status_change_count += len([x for x in update["status_entries"] if str(x).strip()])
            if update.get("current_goal"):
                goal_change_count += 1
            if isinstance(update.get("action_history_entries"), list):
                action_history_count += len([x for x in update["action_history_entries"] if str(x).strip()])
            memory_updates = update.get("memory_updates", {})
            if isinstance(memory_updates, dict):
                if isinstance(memory_updates.get("short_term"), list):
                    memory_change_count += len([x for x in memory_updates["short_term"] if str(x).strip()])
                if isinstance(memory_updates.get("long_term"), list):
                    memory_change_count += len([x for x in memory_updates["long_term"] if str(x).strip()])
                if isinstance(memory_updates.get("beliefs"), list):
                    memory_change_count += len([x for x in memory_updates["beliefs"] if str(x).strip()])
            if isinstance(update.get("relationship_updates"), list):
                relationship_change_count += len(
                    [x for x in update["relationship_updates"] if isinstance(x, dict) and str(x.get("target", "")).strip()]
                )
            if isinstance(update.get("relationship_changes"), list):
                relationship_change_count += len([x for x in update["relationship_changes"] if str(x).strip()])

        world_updates = updates.get("world_updates", {})
        if not isinstance(world_updates, dict):
            world_updates = {}
        new_locations = world_updates.get("new_locations", [])
        new_methods = world_updates.get("new_methods", [])
        new_artifacts = world_updates.get("new_artifacts", [])
        new_factions = world_updates.get("new_factions", [])
        faction_changes = world_updates.get("faction_changes", [])
        world_notes = world_updates.get("world_state_notes", [])
        time_advance = str(world_updates.get("time_advance", "")).strip()
        meta = updates.get("_meta", {})
        if not isinstance(meta, dict):
            meta = {}
        protagonist_progress_logs = meta.get("protagonist_progress_logs", [])
        if not isinstance(protagonist_progress_logs, list):
            protagonist_progress_logs = []

        lines.append("\n📌 更新摘要：")
        if character_names:
            lines.append(f"\n- 角色更新: {len(character_names)}人（{', '.join(character_names[:5])}）")
        else:
            lines.append("\n- 角色更新: 0人")

        lines.append(f"\n- 人物状态变更: {status_change_count}条")
        lines.append(f"\n- 人物关系变更: {relationship_change_count}条")
        lines.append(f"\n- 人物目标更新: {goal_change_count}条")
        lines.append(f"\n- 行动历史新增: {action_history_count}条")
        lines.append(f"\n- 记忆条目新增: {memory_change_count}条")
        lines.append(
            f"\n- 世界新增: 地点{len(new_locations) if isinstance(new_locations, list) else 0} "
            f"功法{len(new_methods) if isinstance(new_methods, list) else 0} "
            f"法宝{len(new_artifacts) if isinstance(new_artifacts, list) else 0} "
            f"势力{len(new_factions) if isinstance(new_factions, list) else 0}"
        )
        if isinstance(faction_changes, list) and faction_changes:
            lines.append(f"\n- 势力动态: {len(faction_changes)}条")
        if isinstance(world_notes, list) and world_notes:
            lines.append(f"\n- 世界备注: {len(world_notes)}条")
        if time_advance:
            lines.append(f"\n- 时间推进: {time_advance}")
        if protagonist_progress_logs:
            lines.append(f"\n- 主角晋升进度: {len(protagonist_progress_logs)}条")
            lines.append(f"\n  · {protagonist_progress_logs[0]}")
            if len(protagonist_progress_logs) > 1:
                lines.append(f"\n  · {protagonist_progress_logs[1]}")

        return lines

    def stream_generate(self, chapter_index: int, title: str, chapter_goal: str = "") -> Generator[str, None, str]:
        """流式生成（兼容旧接口）。"""
        full_text = ""
        for chunk in self.continue_writing():
            if isinstance(chunk, str):
                full_text += chunk
                yield chunk
            elif isinstance(chunk, dict):
                full_text = chunk.get("full_text", full_text)
        return full_text

    def generate_full(self, chapter_index: int, title: str, context: str, previous_summary: str = "") -> str:
        """完整生成（兼容旧接口）。"""
        content = ""
        for chunk in self.continue_writing():
            if isinstance(chunk, str):
                content += chunk
            elif isinstance(chunk, dict):
                return chunk.get("full_text", content)
        return content
