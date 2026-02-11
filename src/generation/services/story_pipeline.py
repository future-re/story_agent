"""Story pipeline service: structured blueprint -> detailed outline -> world state."""

import json
import os
from typing import Any, Dict, List, Optional

try:
    from json_repair import repair_json
except ImportError:
    repair_json = None

from storage import StorageManager
from ..prompts import (
    PROMPT_DETAILED_OUTLINE_FROM_BLUEPRINT,
    PROMPT_STRUCTURED_BLUEPRINT,
    PROMPT_WORLD_STATE_FROM_OUTLINE,
)


class StoryPipelineService:
    """封装五阶段流程中的结构化阶段（1-4）。"""

    def __init__(self, ai_client: Any, storage: StorageManager):
        self.ai = ai_client
        self.storage = storage

    @staticmethod
    def _extract_json_dict(response_text: str) -> Optional[Dict[str, Any]]:
        cleaned = str(response_text or "").strip()
        if not cleaned:
            return None

        if cleaned.startswith("```"):
            first_newline = cleaned.find("\n")
            if first_newline > 0:
                cleaned = cleaned[first_newline + 1 :]
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
    def _to_text_list(values: Any, limit: int = 0) -> List[str]:
        if not isinstance(values, list):
            return []
        result: List[str] = []
        for item in values:
            text = str(item).strip()
            if not text:
                continue
            result.append(text)
            if limit > 0 and len(result) >= limit:
                break
        return result

    def _normalize_story_blueprint(self, blueprint: Optional[Dict[str, Any]], idea: str) -> Dict[str, Any]:
        data = blueprint if isinstance(blueprint, dict) else {}
        character_setup = data.get("character_setup", [])
        if not isinstance(character_setup, list):
            character_setup = []

        normalized_chars: List[Dict[str, Any]] = []
        for item in character_setup[:12]:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            normalized_chars.append(
                {
                    "name": name,
                    "gender": str(item.get("gender", "未知")).strip() or "未知",
                    "identity": str(item.get("identity", "未知身份")).strip() or "未知身份",
                    "age": str(item.get("age", "未知")).strip() or "未知",
                    "appearance": str(item.get("appearance", "外貌待补充")).strip() or "外貌待补充",
                    "personality_temperament": str(
                        item.get("personality_temperament", item.get("personality", "性格待补充"))
                    ).strip()
                    or "性格待补充",
                    "desire": str(item.get("desire", "达成核心目标")).strip() or "达成核心目标",
                    "short_term_goal": str(item.get("short_term_goal", "推进当前主线")).strip() or "推进当前主线",
                }
            )

        core_event = data.get("core_event", {})
        if not isinstance(core_event, dict):
            core_event = {}
        conflicts = data.get("conflicts", [])
        if not isinstance(conflicts, list):
            conflicts = []
        plot_development = data.get("plot_development", {})
        if not isinstance(plot_development, dict):
            plot_development = {}
        scene_formula = data.get("scene_formula", [])
        if not isinstance(scene_formula, list):
            scene_formula = []

        normalized_scene_formula: List[Dict[str, Any]] = []
        for scene in scene_formula[:12]:
            if not isinstance(scene, dict):
                continue
            normalized_scene_formula.append(
                {
                    "location": str(scene.get("location", "未知地点")).strip() or "未知地点",
                    "characters": self._to_text_list(scene.get("characters", []), limit=6),
                    "event": str(scene.get("event", "事件待补充")).strip() or "事件待补充",
                    "result": str(scene.get("result", "结果待补充")).strip() or "结果待补充",
                }
            )

        return {
            "title_candidate": str(data.get("title_candidate", "未命名故事")).strip() or "未命名故事",
            "genre": str(data.get("genre", "未分类")).strip() or "未分类",
            "target_audience": str(data.get("target_audience", "网络小说读者")).strip() or "网络小说读者",
            "idea": str(idea).strip(),
            "character_setup": normalized_chars,
            "core_event": {
                "event_goal": str(core_event.get("event_goal", "推进主角核心目标")).strip() or "推进主角核心目标",
                "meaning": str(core_event.get("meaning", "决定主角命运")).strip() or "决定主角命运",
                "difficulties": self._to_text_list(core_event.get("difficulties", []), limit=8),
            },
            "conflicts": [
                {
                    "conflict": str(item.get("conflict", "冲突待补充")).strip() if isinstance(item, dict) else "冲突待补充",
                    "phase_result": str(item.get("phase_result", "阶段结果待补充")).strip()
                    if isinstance(item, dict)
                    else "阶段结果待补充",
                    "resolution_path": str(item.get("resolution_path", "解决路径待补充")).strip()
                    if isinstance(item, dict)
                    else "解决路径待补充",
                }
                for item in conflicts[:12]
            ],
            "plot_development": {
                "cause": str(plot_development.get("cause", "起因待补充")).strip() or "起因待补充",
                "development": str(plot_development.get("development", "发展待补充")).strip() or "发展待补充",
                "twist": str(plot_development.get("twist", "转折待补充")).strip() or "转折待补充",
                "climax": str(plot_development.get("climax", "高潮待补充")).strip() or "高潮待补充",
                "ending": str(plot_development.get("ending", "结局待补充")).strip() or "结局待补充",
            },
            "scene_formula": normalized_scene_formula,
        }

    def _render_outline_markdown_from_detailed(self, detailed_outline: Dict[str, Any]) -> str:
        lines: List[str] = []
        summary = str(detailed_outline.get("summary", "")).strip()
        if summary:
            lines.append("## 细纲摘要")
            lines.append(summary)
            lines.append("")

        volumes = detailed_outline.get("volumes", [])
        if not isinstance(volumes, list):
            volumes = []

        for idx, volume in enumerate(volumes, 1):
            if not isinstance(volume, dict):
                continue
            title = str(volume.get("title", f"卷{idx}")).strip() or f"卷{idx}"
            start_chapter = int(volume.get("start_chapter", 1) or 1)
            end_chapter = int(volume.get("end_chapter", start_chapter) or start_chapter)
            phase = str(volume.get("phase", "阶段")).strip() or "阶段"
            volume_goal = str(volume.get("volume_goal", "")).strip()
            lines.append(f"## {title}（第{start_chapter}-{end_chapter}章）")
            lines.append(f"### {phase}（第{start_chapter}-{end_chapter}章）")
            if volume_goal:
                lines.append(f"- 本卷目标：{volume_goal}")

            beats = volume.get("chapter_beats", [])
            if not isinstance(beats, list):
                beats = []
            for beat in beats:
                if not isinstance(beat, dict):
                    continue
                chapter = int(beat.get("chapter", start_chapter) or start_chapter)
                goal = str(beat.get("goal", "")).strip()
                title_text = str(beat.get("title", "")).strip()
                main_line = goal or title_text or "推进主线"
                lines.append(f"- **第{chapter}章**: {main_line}")
                conflict = str(beat.get("conflict", "")).strip()
                hook = str(beat.get("hook", "")).strip()
                if conflict:
                    lines.append(f"  - 冲突：{conflict}")
                if hook:
                    lines.append(f"  - 钩子：{hook}")
            lines.append("")

        return "\n".join(lines).strip()

    def _normalize_detailed_outline(self, detailed: Optional[Dict[str, Any]], chapter_count: int) -> Dict[str, Any]:
        data = detailed if isinstance(detailed, dict) else {}
        volumes_raw = data.get("volumes", [])
        if not isinstance(volumes_raw, list):
            volumes_raw = []

        volumes: List[Dict[str, Any]] = []
        for idx, volume in enumerate(volumes_raw[:8], 1):
            if not isinstance(volume, dict):
                continue
            start_chapter = int(volume.get("start_chapter", 1) or 1)
            end_chapter = int(volume.get("end_chapter", start_chapter) or start_chapter)
            chapter_beats_raw = volume.get("chapter_beats", [])
            if not isinstance(chapter_beats_raw, list):
                chapter_beats_raw = []
            chapter_beats: List[Dict[str, Any]] = []
            for beat in chapter_beats_raw[:200]:
                if not isinstance(beat, dict):
                    continue
                chapter_no = int(beat.get("chapter", start_chapter) or start_chapter)
                scene_formula = beat.get("scene_formula", [])
                if not isinstance(scene_formula, list):
                    scene_formula = []
                chapter_beats.append(
                    {
                        "chapter": chapter_no,
                        "title": str(beat.get("title", f"第{chapter_no}章")).strip() or f"第{chapter_no}章",
                        "goal": str(beat.get("goal", "推进主线")).strip() or "推进主线",
                        "conflict": str(beat.get("conflict", "")).strip(),
                        "hook": str(beat.get("hook", "")).strip(),
                        "scene_formula": [
                            {
                                "location": str(scene.get("location", "未知地点")).strip() if isinstance(scene, dict) else "未知地点",
                                "characters": self._to_text_list(scene.get("characters", []), limit=6)
                                if isinstance(scene, dict)
                                else [],
                                "event": str(scene.get("event", "事件待补充")).strip() if isinstance(scene, dict) else "事件待补充",
                                "result": str(scene.get("result", "结果待补充")).strip() if isinstance(scene, dict) else "结果待补充",
                            }
                            for scene in scene_formula[:6]
                        ],
                    }
                )
            volumes.append(
                {
                    "title": str(volume.get("title", f"卷{idx}")).strip() or f"卷{idx}",
                    "start_chapter": start_chapter,
                    "end_chapter": end_chapter,
                    "phase": str(volume.get("phase", "阶段")).strip() or "阶段",
                    "volume_goal": str(volume.get("volume_goal", "")).strip(),
                    "chapter_beats": chapter_beats,
                }
            )

        if not volumes:
            volumes = [
                {
                    "title": "卷一：开局",
                    "start_chapter": 1,
                    "end_chapter": max(1, chapter_count),
                    "phase": "开局",
                    "volume_goal": "建立主线冲突",
                    "chapter_beats": [
                        {
                            "chapter": 1,
                            "title": "第一章",
                            "goal": "主角卷入核心事件",
                            "conflict": "与外部规则产生正面碰撞",
                            "hook": "发现更大阴谋",
                            "scene_formula": [
                                {
                                    "location": "起始场景",
                                    "characters": ["主角"],
                                    "event": "触发主线事件",
                                    "result": "被迫进入主线",
                                }
                            ],
                        }
                    ],
                }
            ]

        normalized = {
            "summary": str(data.get("summary", "细纲已生成")).strip() or "细纲已生成",
            "volumes": volumes,
            "outline_markdown": str(data.get("outline_markdown", "")).strip(),
        }
        if not normalized["outline_markdown"]:
            normalized["outline_markdown"] = self._render_outline_markdown_from_detailed(normalized)
        return normalized

    def _normalize_world_state(
        self,
        world_state: Optional[Dict[str, Any]],
        blueprint: Dict[str, Any],
    ) -> Dict[str, Any]:
        raw = world_state if isinstance(world_state, dict) else {}
        characters_raw = raw.get("characters", [])
        if not isinstance(characters_raw, list):
            characters_raw = []

        normalized_characters: List[Dict[str, Any]] = []
        known_names = set()
        for char in characters_raw[:20]:
            if not isinstance(char, dict):
                continue
            name = str(char.get("name", "")).strip()
            if not name:
                continue
            known_names.add(name)
            normalized_characters.append(
                {
                    "name": name,
                    "role": str(char.get("role", "配角")).strip() or "配角",
                    "appeared": bool(char.get("appeared", False)),
                    "personality": str(char.get("personality", "待补充")).strip() or "待补充",
                    "level": str(char.get("level", "凡人")).strip() or "凡人",
                    "abilities": self._to_text_list(char.get("abilities", []), limit=20),
                    "items": self._to_text_list(char.get("items", []), limit=20),
                    "current_goal": str(char.get("current_goal", "推进主线")).strip() or "推进主线",
                    "action_tendency": str(char.get("action_tendency", "按性格谨慎行动")).strip() or "按性格谨慎行动",
                    "relationships": [
                        {
                            "target": str(rel.get("target", "")).strip(),
                            "relation_type": str(rel.get("relation_type", "未知")).strip() or "未知",
                            "description": str(rel.get("description", "")).strip(),
                        }
                        for rel in char.get("relationships", [])
                        if isinstance(rel, dict) and str(rel.get("target", "")).strip()
                    ],
                    "current_status": self._to_text_list(char.get("current_status", []), limit=30),
                    "action_history": char.get("action_history", []) if isinstance(char.get("action_history"), list) else [],
                    "memory_short_term": self._to_text_list(char.get("memory_short_term", []), limit=30),
                    "memory_long_term": self._to_text_list(char.get("memory_long_term", []), limit=40),
                }
            )

        for base_char in blueprint.get("character_setup", []):
            if not isinstance(base_char, dict):
                continue
            name = str(base_char.get("name", "")).strip()
            if not name or name in known_names:
                continue
            normalized_characters.append(
                {
                    "name": name,
                    "role": "配角",
                    "appeared": False,
                    "personality": str(base_char.get("personality_temperament", "待补充")).strip() or "待补充",
                    "level": "凡人",
                    "abilities": [],
                    "items": [],
                    "current_goal": str(base_char.get("short_term_goal", "推进主线")).strip() or "推进主线",
                    "action_tendency": "按性格行动",
                    "relationships": [],
                    "current_status": [],
                    "action_history": [],
                    "memory_short_term": [],
                    "memory_long_term": [],
                }
            )

        world_raw = raw.get("world", {})
        if not isinstance(world_raw, dict):
            world_raw = {}
        world = {
            "environment": str(world_raw.get("environment", "环境待补充")).strip() or "环境待补充",
            "power_system": world_raw.get("power_system", ""),
            "factions": self._to_text_list(world_raw.get("factions", []), limit=30),
            "known_methods": self._to_text_list(world_raw.get("known_methods", []), limit=30),
            "known_artifacts": self._to_text_list(world_raw.get("known_artifacts", []), limit=30),
            "scene_rules": self._to_text_list(world_raw.get("scene_rules", []), limit=20),
        }

        locations_raw = raw.get("locations", [])
        if not isinstance(locations_raw, list):
            locations_raw = []
        locations: List[Dict[str, str]] = []
        for item in locations_raw[:40]:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            locations.append({"name": name, "description": str(item.get("description", "")).strip()})

        return {
            "characters": normalized_characters,
            "world": world,
            "locations": locations,
            "plot_history": self._to_text_list(raw.get("plot_history", []), limit=30),
            "timeline": self._to_text_list(raw.get("timeline", []), limit=30),
            "faction_history": self._to_text_list(raw.get("faction_history", []), limit=30),
            "world_state_notes": self._to_text_list(raw.get("world_state_notes", []), limit=30),
        }

    def _load_recent_chapter_samples(self, project_name: str, max_chapters: int = 3, max_chars_each: int = 1200) -> str:
        chapters = self.storage.list_chapters(project_name)
        if not chapters:
            return ""

        project_dir = self.storage.get_project_dir(project_name)
        snippets: List[str] = []
        for filename in chapters[-max_chapters:]:
            chapter_path = os.path.join(project_dir, "chapters", filename)
            try:
                with open(chapter_path, "r", encoding="utf-8") as f:
                    text = f.read().strip()
                if text:
                    snippets.append(f"【{filename}】\n{text[:max_chars_each]}")
            except OSError:
                continue
        return "\n\n".join(snippets)

    def generate_structured_blueprint(self, idea: str, save_to: Optional[str] = None) -> Dict[str, Any]:
        prompt = PROMPT_STRUCTURED_BLUEPRINT.format(idea=idea)
        response = self.ai.chat(prompt, system_prompt="你是严谨的故事策划编辑，只输出合法JSON。")
        parsed = self._extract_json_dict(response if isinstance(response, str) else str(response))
        normalized = self._normalize_story_blueprint(parsed, idea=idea)
        if save_to:
            self.storage.save_story_blueprint(save_to, normalized)
        return normalized

    def generate_detailed_outline(
        self,
        blueprint: Dict[str, Any],
        chapter_count: int = 10,
        save_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        prompt = PROMPT_DETAILED_OUTLINE_FROM_BLUEPRINT.format(
            blueprint_json=json.dumps(blueprint, ensure_ascii=False, indent=2),
            chapter_count=chapter_count,
        )
        response = self.ai.chat(prompt, system_prompt="你是小说细纲拆解器，只输出合法JSON。")
        parsed = self._extract_json_dict(response if isinstance(response, str) else str(response))
        normalized = self._normalize_detailed_outline(parsed, chapter_count=chapter_count)

        if save_to:
            self.storage.save_detailed_outline_json(save_to, normalized)
            self.storage.save_outline(save_to, normalized.get("outline_markdown", ""))
        return normalized

    def initialize_world_state(
        self,
        blueprint: Dict[str, Any],
        detailed_outline: Dict[str, Any],
        project_name: str,
        chapter_samples: str = "",
        save: bool = True,
    ) -> Dict[str, Any]:
        prompt = PROMPT_WORLD_STATE_FROM_OUTLINE.format(
            blueprint_json=json.dumps(blueprint, ensure_ascii=False, indent=2),
            detailed_outline_json=json.dumps(detailed_outline, ensure_ascii=False, indent=2),
            chapter_samples=chapter_samples or "（无）",
        )
        response = self.ai.chat(prompt, system_prompt="你是世界状态建模器，只输出合法JSON。")
        parsed = self._extract_json_dict(response if isinstance(response, str) else str(response))
        normalized = self._normalize_world_state(parsed, blueprint=blueprint)

        if save:
            self.storage.save_world_state(project_name, normalized)
            for char in normalized.get("characters", []):
                name = str(char.get("name", "")).strip()
                if name:
                    self.storage.save_character_profile(project_name, name, char)
        return normalized

    def build_story_pipeline(
        self,
        idea: str,
        project_name: str,
        chapter_count: int = 10,
    ) -> Dict[str, Any]:
        blueprint = self.generate_structured_blueprint(idea=idea, save_to=project_name)
        detailed_outline = self.generate_detailed_outline(
            blueprint=blueprint,
            chapter_count=chapter_count,
            save_to=project_name,
        )
        chapter_samples = self._load_recent_chapter_samples(project_name, max_chapters=3, max_chars_each=1200)
        world_state = self.initialize_world_state(
            blueprint=blueprint,
            detailed_outline=detailed_outline,
            project_name=project_name,
            chapter_samples=chapter_samples,
            save=True,
        )
        return {
            "blueprint": blueprint,
            "detailed_outline": detailed_outline,
            "world_state": world_state,
        }

    def initialize_world_from_saved(self, project_name: str, save: bool = True) -> Dict[str, Any]:
        blueprint = self.storage.load_story_blueprint(project_name)
        detailed_outline = self.storage.load_detailed_outline_json(project_name)
        if not blueprint:
            raise FileNotFoundError(f"项目 '{project_name}' 缺少 story_blueprint.json，请先执行 pipeline")
        if not detailed_outline:
            raise FileNotFoundError(f"项目 '{project_name}' 缺少 detailed_outline.json，请先执行 pipeline")

        chapter_samples = self._load_recent_chapter_samples(project_name, max_chapters=3, max_chars_each=1200)
        return self.initialize_world_state(
            blueprint=blueprint,
            detailed_outline=detailed_outline,
            project_name=project_name,
            chapter_samples=chapter_samples,
            save=save,
        )
