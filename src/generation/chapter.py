"""
章节生成器

自动续写模式：
- 获取最新章节，不到 3k 字继续追加
- 超过 3k 字自动新建下一章
"""

import json
import os
from typing import Any, Dict, Generator, Tuple

from config import config
from storage import StorageManager
from tools import resolve_thinking_mode
from utils.word_count import count_chinese_words


class ChapterGenerator:
    """章节生成器 - 自动续写模式。"""

    MIN_CHAPTER_LENGTH = 3000
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

    def _load_outline(self) -> str:
        """加载大纲。"""
        try:
            outline_path = os.path.join(self.storage.get_project_dir(self.project_name), "大纲.txt")
            if os.path.exists(outline_path):
                with open(outline_path, "r", encoding="utf-8") as f:
                    return f.read()[:4000]
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
        strict_continuity: bool,
    ) -> str:
        if mode == "append":
            return f"""请继续续写以下章节内容，直到本章达到3000字以上。

{world_context}
{style_prompt}
【本卷进度】{outline_info.get('volume', '')}
【当前阶段】{outline_info.get('phase', '')}
【本章指引】{outline_info.get('specific_goal', '')}

{thinking_context}

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
        """
        自动续写（双模型架构）：
        1. 先用 thinking 模型分析剧情
        2. 再用 chat 模型生成内容
        """
        ch_num, ch_title, ch_content, ch_len = self._get_latest_chapter()

        world_context = self._build_context()
        outline_full = self._load_outline()
        style_ref = self._load_style_ref()
        style_prompt = self._build_style_prompt(style_ref)

        target_meta = self._resolve_generation_target(ch_num, ch_title, ch_content, ch_len, outline_full)
        mode = target_meta["mode"]
        ch_num = target_meta["chapter_num"]
        outline_info = target_meta["outline_info"]
        target_words = target_meta["target_words"]

        thinking_plan = None
        thinking_context = ""
        if self.thinking_engine:
            for output in self._run_thinking(
                chapter_num=ch_num,
                outline_info=outline_info,
                world_context=world_context,
                previous_content=ch_content,
                is_append=(mode == "append"),
            ):
                if isinstance(output, dict):
                    thinking_plan = output
                else:
                    yield output
            if thinking_plan:
                thinking_context = self.thinking_engine.format_for_generation(thinking_plan)

        prompt = self._build_generation_prompt(
            mode=mode,
            chapter_num=ch_num,
            chapter_title=ch_title,
            chapter_content=ch_content,
            chapter_len=ch_len,
            target_words=target_words,
            world_context=world_context,
            style_prompt=style_prompt,
            outline_info=outline_info,
            thinking_context=thinking_context,
            strict_continuity=False,
        )

        full_content = ""
        for chunk in self.ai.stream_chat(prompt, system_prompt=self.GENERATION_SYSTEM_PROMPT):
            yield chunk
            full_content += chunk

        yield self._build_generation_result(
            mode=mode,
            chapter_num=ch_num,
            chapter_title=ch_title,
            previous_content=ch_content,
            generated_content=full_content,
        )

    def prepare_writing(self) -> Generator[str, None, Dict[str, Any]]:
        """准备阶段：收集上下文并进行剧情思考。"""
        ch_num, ch_title, ch_content, ch_len = self._get_latest_chapter()

        world_context = self._build_context()
        outline_full = self._load_outline()
        style_ref = self._load_style_ref()

        target_meta = self._resolve_generation_target(ch_num, ch_title, ch_content, ch_len, outline_full)
        mode = target_meta["mode"]
        ch_num = target_meta["chapter_num"]
        outline_info = target_meta["outline_info"]

        thinking_plan = None
        if self.thinking_engine:
            for output in self._run_thinking(
                chapter_num=ch_num,
                outline_info=outline_info,
                world_context=world_context,
                previous_content=ch_content,
                is_append=(mode == "append"),
            ):
                if isinstance(output, dict):
                    thinking_plan = output
                else:
                    yield output

        yield {
            "mode": mode,
            "chapter_num": ch_num,
            "chapter_title": ch_title,
            "chapter_content": ch_content,
            "chapter_len": ch_len,
            "target_words": target_meta["target_words"],
            "world_context": world_context,
            "outline_info": target_meta["outline_info"],
            "style_ref": style_ref,
            "thinking_plan": thinking_plan,
        }

    def generate_from_plan(self, preparation: Dict[str, Any]) -> Generator[str, None, Dict[str, Any]]:
        """生成阶段：根据准备结果生成内容。"""
        mode = preparation["mode"]
        ch_num = preparation["chapter_num"]
        ch_title = preparation["chapter_title"]
        ch_content = preparation["chapter_content"]
        ch_len = preparation["chapter_len"]
        target_words = preparation["target_words"]
        world_context = preparation["world_context"]
        outline_info = preparation["outline_info"]
        style_ref = preparation["style_ref"]
        thinking_plan = preparation["thinking_plan"]

        style_prompt = self._build_style_prompt(style_ref)
        thinking_context = ""
        if thinking_plan and self.thinking_engine:
            thinking_context = self.thinking_engine.format_for_generation(thinking_plan)

        prompt = self._build_generation_prompt(
            mode=mode,
            chapter_num=ch_num,
            chapter_title=ch_title,
            chapter_content=ch_content,
            chapter_len=ch_len,
            target_words=target_words,
            world_context=world_context,
            style_prompt=style_prompt,
            outline_info=outline_info,
            thinking_context=thinking_context,
            strict_continuity=True,
        )

        full_content = ""
        for chunk in self.ai.stream_chat(prompt, system_prompt=self.GENERATION_SYSTEM_PROMPT):
            yield chunk
            full_content += chunk

        yield self._build_generation_result(
            mode=mode,
            chapter_num=ch_num,
            chapter_title=ch_title,
            previous_content=ch_content,
            generated_content=full_content,
        )

    def update_world_state(self, new_content: str) -> Generator[str, None, dict]:
        """根据新章节内容更新世界状态。"""
        if not self.world_data:
            return {"updated": False, "reason": "no_world_data"}

        current_chars = self.world_data.get("characters", [])
        prompt = f"""请分析以下新章节内容，更新角色和世界状态。

【当前角色列表】
{chr(10).join([f"- {c.get('name')}: {c.get('level', '凡人')} | {c.get('personality', '')[:30]}" for c in current_chars[:8]])}

【修炼体系参考】
{self._get_cultivation_info_str()}

【新章节内容】
{new_content[:3000]}

请输出 JSON 格式的状态更新：
{{
  "character_updates": [
    {{
      "name": "角色名",
      "status_change": "状态变化描述",
      "level_update": "新境界(可选)",
      "new_abilities": ["新学会的功法/技能"],
      "new_items": ["新获得的法宝/物品"],
      "relationship_changes": ["关系变化"]
    }}
  ],
  "world_updates": {{
    "new_locations": ["新发现的地点"],
    "new_methods": ["新出现的功法"],
    "new_artifacts": ["新出现的法宝"],
    "plot_progress": "剧情进展摘要",
    "new_factions": ["新势力"],
    "time_advance": "时间推进描述"
  }},
  "chapter_summary": "本章概要（50字内）"
}}
"""

        yield "\n\n📊 正在更新世界状态..."

        response_text = ""
        for chunk in self.ai.stream_chat(prompt, system_prompt="你是一个精准的状态分析器，只输出JSON。"):
            response_text += chunk

        try:
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            if json_start < 0 or json_end <= json_start:
                return {"updated": False, "error": "no_json"}

            updates = json.loads(response_text[json_start:json_end])

            if "character_updates" in updates:
                for update in updates["character_updates"]:
                    for char in self.world_data.get("characters", []):
                        if char.get("name") != update.get("name"):
                            continue
                        if "current_status" not in char:
                            char["current_status"] = []
                        char["current_status"].append(update.get("status_change", ""))
                        char["current_status"] = char["current_status"][-5:]

                        if update.get("level_update"):
                            char["level"] = update["level_update"]
                        if update.get("new_abilities"):
                            char.setdefault("abilities", [])
                            char["abilities"].extend(update["new_abilities"])
                            char["abilities"] = list(set(char["abilities"]))
                        if update.get("new_items"):
                            char.setdefault("items", [])
                            char["items"].extend(update["new_items"])
                            char["items"] = list(set(char["items"]))

            if "world_updates" in updates:
                world_updates = updates["world_updates"]
                if "plot_progress" in world_updates:
                    self.world_data.setdefault("plot_history", [])
                    self.world_data["plot_history"].append(world_updates["plot_progress"])
                    self.world_data["plot_history"] = self.world_data["plot_history"][-10:]

                if world_updates.get("new_locations"):
                    self.world_data.setdefault("locations", [])
                    for loc in world_updates["new_locations"]:
                        if not any(item.get("name") == loc for item in self.world_data["locations"]):
                            self.world_data["locations"].append({"name": loc, "description": ""})

                if world_updates.get("new_methods"):
                    self.world_data.setdefault("world", {})
                    self.world_data["world"].setdefault("known_methods", [])
                    self.world_data["world"]["known_methods"].extend(world_updates["new_methods"])
                    self.world_data["world"]["known_methods"] = list(
                        set(self.world_data["world"]["known_methods"])
                    )

                if world_updates.get("new_artifacts"):
                    self.world_data.setdefault("world", {})
                    self.world_data["world"].setdefault("known_artifacts", [])
                    self.world_data["world"]["known_artifacts"].extend(world_updates["new_artifacts"])
                    self.world_data["world"]["known_artifacts"] = list(
                        set(self.world_data["world"]["known_artifacts"])
                    )

            self.storage.save_world_state(self.project_name, self.world_data)
            yield "\n✅ 状态已更新"
            if "chapter_summary" in updates:
                yield f" | 本章: {updates['chapter_summary']}"
            return {"updated": True, "updates": updates}
        except Exception as exc:
            yield f"\n⚠️ 状态更新失败: {exc}"
            return {"updated": False, "error": str(exc)}

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
