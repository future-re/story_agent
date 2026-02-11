"""Chapter workflow services: preparation, writing, world-state update."""

from typing import Any, Dict, Generator, List


class ChapterPreparationService:
    """准备阶段：统一收集上下文与行动推演。"""

    def prepare(self, gen: Any) -> Generator[str, None, Dict[str, Any]]:
        ch_num, ch_title, ch_content, ch_len = gen._get_latest_chapter()

        world_context = gen._build_context()
        outline_full = gen._load_outline()
        style_ref = gen._load_style_ref()
        realm_rules_context = gen._build_realm_rules_context(outline_full)

        target_meta = gen._resolve_generation_target(ch_num, ch_title, ch_content, ch_len, outline_full)
        mode = target_meta["mode"]
        ch_num = target_meta["chapter_num"]
        outline_info = target_meta["outline_info"]

        thinking_plan = None
        if gen.thinking_engine:
            for output in gen._run_thinking(
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

        character_action_plan = None
        character_action_context = ""
        for output in gen._run_character_action_graph(
            chapter_num=ch_num,
            outline_info=outline_info,
            previous_content=ch_content,
            thinking_plan=thinking_plan,
        ):
            if isinstance(output, dict):
                character_action_plan = output
            else:
                yield output
        if character_action_plan:
            character_action_context = gen._format_character_action_for_generation(character_action_plan)

        result = {
            "mode": mode,
            "chapter_num": ch_num,
            "chapter_title": ch_title,
            "chapter_content": ch_content,
            "chapter_len": ch_len,
            "target_words": target_meta["target_words"],
            "world_context": world_context,
            "outline_info": target_meta["outline_info"],
            "style_ref": style_ref,
            "realm_rules_context": realm_rules_context,
            "thinking_plan": thinking_plan,
            "character_action_plan": character_action_plan,
            "character_action_context": character_action_context,
        }
        yield result
        return result


class ChapterWritingService:
    """写作阶段：支持自动续写与基于准备结果生成。"""

    def continue_writing(self, gen: Any) -> Generator[str, None, Dict[str, Any]]:
        ch_num, ch_title, ch_content, ch_len = gen._get_latest_chapter()

        world_context = gen._build_context()
        outline_full = gen._load_outline()
        style_ref = gen._load_style_ref()
        style_prompt = gen._build_style_prompt(style_ref)
        realm_rules_context = gen._build_realm_rules_context(outline_full)

        target_meta = gen._resolve_generation_target(ch_num, ch_title, ch_content, ch_len, outline_full)
        mode = target_meta["mode"]
        ch_num = target_meta["chapter_num"]
        outline_info = target_meta["outline_info"]
        target_words = target_meta["target_words"]

        thinking_plan = None
        thinking_context = ""
        if gen.thinking_engine:
            for output in gen._run_thinking(
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
                thinking_context = gen.thinking_engine.format_for_generation(thinking_plan)

        character_action_plan = None
        character_action_context = ""
        for output in gen._run_character_action_graph(
            chapter_num=ch_num,
            outline_info=outline_info,
            previous_content=ch_content,
            thinking_plan=thinking_plan,
        ):
            if isinstance(output, dict):
                character_action_plan = output
            else:
                yield output
        if character_action_plan:
            character_action_context = gen._format_character_action_for_generation(character_action_plan)

        prompt = gen._build_generation_prompt(
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
            character_action_context=character_action_context,
            realm_rules_context=realm_rules_context,
            strict_continuity=False,
        )

        full_content = ""
        for chunk in gen.ai.stream_chat(prompt, system_prompt=gen.get_generation_system_prompt(mode)):
            yield chunk
            full_content += chunk

        yield gen._build_generation_result(
            mode=mode,
            chapter_num=ch_num,
            chapter_title=ch_title,
            previous_content=ch_content,
            generated_content=full_content,
        )

    def generate_from_plan(self, gen: Any, preparation: Dict[str, Any]) -> Generator[str, None, Dict[str, Any]]:
        mode = preparation["mode"]
        ch_num = preparation["chapter_num"]
        ch_title = preparation["chapter_title"]
        ch_content = preparation["chapter_content"]
        ch_len = preparation["chapter_len"]
        target_words = preparation["target_words"]
        world_context = preparation["world_context"]
        outline_info = preparation["outline_info"]
        style_ref = preparation["style_ref"]
        realm_rules_context = preparation.get("realm_rules_context", "")
        thinking_plan = preparation["thinking_plan"]
        character_action_plan = preparation.get("character_action_plan")
        character_action_context = str(preparation.get("character_action_context", "")).strip()

        style_prompt = gen._build_style_prompt(style_ref)
        thinking_context = ""
        if thinking_plan and gen.thinking_engine:
            thinking_context = gen.thinking_engine.format_for_generation(thinking_plan)
        if not character_action_context and character_action_plan:
            character_action_context = gen._format_character_action_for_generation(character_action_plan)

        prompt = gen._build_generation_prompt(
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
            character_action_context=character_action_context,
            realm_rules_context=realm_rules_context,
            strict_continuity=True,
        )

        full_content = ""
        for chunk in gen.ai.stream_chat(prompt, system_prompt=gen.get_generation_system_prompt(mode)):
            yield chunk
            full_content += chunk

        yield gen._build_generation_result(
            mode=mode,
            chapter_num=ch_num,
            chapter_title=ch_title,
            previous_content=ch_content,
            generated_content=full_content,
        )


class WorldStateUpdateService:
    """章节后处理：根据新内容更新 world_state。"""

    def update(self, gen: Any, new_content: str) -> Generator[str, None, dict]:
        if not gen.world_data:
            return {"updated": False, "reason": "no_world_data"}

        latest_chapter_num, _, _, _ = gen._get_latest_chapter()
        current_chars = gen.world_data.get("characters", [])
        character_lines = []
        for char in current_chars[:12]:
            relations = []
            for rel in char.get("relationships", []):
                if not isinstance(rel, dict):
                    continue
                rel_type = rel.get("relation_type", "未知关系")
                target = rel.get("target", "?")
                relations.append(f"{rel_type}->{target}")
            status_tail = char.get("current_status", [])[-2:] if isinstance(char.get("current_status"), list) else []
            action_tail = ""
            if isinstance(char.get("action_history"), list) and char.get("action_history"):
                action_tail = gen._format_action_history_entry(char["action_history"][-1])
            character_lines.append(
                f"- {char.get('name', '?')}: 境界={char.get('level', '凡人')} | "
                f"状态={'; '.join(status_tail) or '无'} | "
                f"目标={str(char.get('current_goal', '')).strip() or '无'} | "
                f"关系={', '.join(relations) or '无'} | "
                f"最近行动={action_tail or '无'}"
            )
        realm_rules_context = gen._build_realm_rules_context(gen._load_outline())

        prompt = f"""请分析以下新章节内容，更新角色和世界状态。

【当前角色列表】
{chr(10).join(character_lines)}

【修炼体系参考】
{gen._get_cultivation_info_str()}
{gen._get_level_format_guide_str()}
{realm_rules_context}

【新章节内容】
{new_content[:3000]}

额外约束：
1. 主角境界必须遵守“资源门槛与突破条件”，资源未满足时禁止给 level_update。
2. 若主角本章仅获取了部分资源，请写入 breakthrough_progress，而不是直接升级。

请输出 JSON 格式的状态更新：
{{
  "character_updates": [
    {{
      "name": "角色名",
      "status_change": "状态变化描述",
      "status_entries": ["状态记录1", "状态记录2"],
      "status_tags": ["受伤", "警惕"],
      "physical_state": "身体状态",
      "mental_state": "心理状态",
      "current_goal": "该角色下一步短期目标",
      "level_update": "新境界(可选，格式: 体系·大境界·小阶段)",
      "breakthrough_progress": {{
        "resources_acquired": ["本章已获取资源（仅主角）"],
        "conditions_completed": ["本章达成的突破条件（仅主角）"]
      }},
      "action_history_entries": [
        {{
          "action": "做了什么",
          "reason": "为什么这么做",
          "outcome": "结果如何",
          "impact": "对后续剧情/关系的影响"
        }}
      ],
      "memory_updates": {{
        "short_term": ["应进入近期记忆的内容"],
        "long_term": ["应沉淀为长期记忆的事件"],
        "beliefs": ["价值观/判断变化（可选）"]
      }},
      "new_abilities": ["新学会的功法/技能"],
      "new_items": ["新获得的法宝/物品"],
      "relationship_updates": [
        {{
          "target": "目标角色",
          "relation_type": "盟友/敌对/师徒/亲属/陌生",
          "description": "关系变化说明",
          "change": "new/update"
        }}
      ],
      "relationship_changes": ["关系变化（兼容旧格式）"]
    }}
  ],
  "world_updates": {{
    "new_locations": ["新发现的地点"],
    "new_methods": ["新出现的功法"],
    "new_artifacts": ["新出现的法宝"],
    "plot_progress": "剧情进展摘要",
    "new_factions": ["新势力"],
    "time_advance": "时间推进描述",
    "faction_changes": ["势力变化"],
    "world_state_notes": ["世界状态补充说明"]
  }},
  "chapter_summary": "本章概要（50字内）"
}}
"""

        state_ai, state_source = gen._get_state_update_ai()
        yield f"\n\n📊 正在更新世界状态（{state_source}）..."

        response_text = ""
        request_kwargs: Dict[str, Any] = {}
        if gen._is_glm_model(state_ai):
            request_kwargs["thinking"] = {"type": "enabled"}
        for chunk in state_ai.stream_chat(
            prompt,
            system_prompt="你是一个精准的状态分析器，擅长人物关系与状态追踪，只输出JSON。",
            **request_kwargs,
        ):
            response_text += chunk

        try:
            updates = gen._extract_json_dict(response_text)
            if not updates:
                return {"updated": False, "error": "no_json"}

            protagonist_progress_logs: List[str] = []
            if "character_updates" in updates:
                for update in updates["character_updates"]:
                    if not isinstance(update, dict):
                        continue
                    for char in gen.world_data.get("characters", []):
                        if char.get("name") != update.get("name"):
                            continue
                        status_entries: List[str] = []
                        if update.get("status_change"):
                            status_entries.append(str(update.get("status_change")).strip())
                        if isinstance(update.get("status_entries"), list):
                            status_entries.extend(
                                str(item).strip() for item in update.get("status_entries", []) if str(item).strip()
                            )
                        if status_entries:
                            char.setdefault("current_status", [])
                            char["current_status"].extend(status_entries)
                            char["current_status"] = char["current_status"][-10:]

                        if update.get("physical_state"):
                            char["physical_state"] = str(update["physical_state"]).strip()
                        if update.get("mental_state"):
                            char["mental_state"] = str(update["mental_state"]).strip()
                        if update.get("current_goal"):
                            char["current_goal"] = str(update["current_goal"]).strip()
                        if isinstance(update.get("status_tags"), list):
                            existing_tags = char.get("status_tags", [])
                            if not isinstance(existing_tags, list):
                                existing_tags = []
                            existing_tags.extend(
                                str(tag).strip() for tag in update.get("status_tags", []) if str(tag).strip()
                            )
                            char["status_tags"] = gen._dedupe_keep_order(existing_tags)

                        if update.get("breakthrough_progress") and not update.get("level_update"):
                            progression = gen._get_protagonist_progression()
                            protagonist_name = str(progression.get("name", "")).strip() if progression else ""
                            if progression and (not protagonist_name or protagonist_name == char.get("name")):
                                transition = gen._get_active_transition(progression)
                                if transition:
                                    protagonist_progress_logs.extend(
                                        gen._mark_transition_progress(
                                            progression=progression,
                                            transition=transition,
                                            update=update,
                                            new_content=new_content,
                                        )
                                    )

                        if update.get("level_update"):
                            level_update = str(update.get("level_update")).strip()
                            if gen._is_granular_level(level_update):
                                is_allowed, block_reason, level_logs = gen._handle_protagonist_level_update(
                                    char=char,
                                    update=update,
                                    new_content=new_content,
                                    level_update=level_update,
                                )
                                protagonist_progress_logs.extend(level_logs)
                                if is_allowed:
                                    char["level"] = level_update
                                elif block_reason:
                                    char.setdefault("current_status", [])
                                    char["current_status"].append(f"境界更新被拦截: {block_reason}")
                                    char["current_status"] = char["current_status"][-10:]
                            else:
                                char.setdefault("current_status", [])
                                char["current_status"].append(f"境界更新被忽略（过粗）: {level_update}")
                                char["current_status"] = char["current_status"][-10:]

                        action_entries: List[Dict[str, Any]] = []
                        raw_action_entries = update.get("action_history_entries", [])
                        if isinstance(raw_action_entries, list):
                            for raw_entry in raw_action_entries:
                                if isinstance(raw_entry, dict):
                                    action_text = str(raw_entry.get("action", "")).strip()
                                    if not action_text:
                                        action_text = str(raw_entry.get("summary", "")).strip()
                                    if not action_text:
                                        continue
                                    reason = str(raw_entry.get("reason", "")).strip()
                                    outcome = str(raw_entry.get("outcome", "")).strip()
                                    impact = str(raw_entry.get("impact", "")).strip()
                                    location = str(raw_entry.get("location", "")).strip()
                                    target = str(raw_entry.get("target", "")).strip()
                                    tags = gen._to_text_list(raw_entry.get("tags", []), limit=3)
                                    action_entries.append(
                                        {
                                            "chapter": latest_chapter_num,
                                            "action": action_text,
                                            "reason": reason,
                                            "outcome": outcome,
                                            "impact": impact,
                                            "location": location,
                                            "target": target,
                                            "tags": tags,
                                        }
                                    )
                                else:
                                    text_entry = str(raw_entry).strip()
                                    if text_entry:
                                        action_entries.append({"chapter": latest_chapter_num, "action": text_entry})

                        memory_updates = update.get("memory_updates", {})
                        memory_updates = memory_updates if isinstance(memory_updates, dict) else {}
                        short_memories = gen._to_text_list(memory_updates.get("short_term", []), limit=6)
                        long_memories = gen._to_text_list(memory_updates.get("long_term", []), limit=6)
                        belief_memories = gen._to_text_list(memory_updates.get("beliefs", []), limit=4)
                        if status_entries:
                            short_memories.extend(status_entries[-2:])
                        for item in action_entries:
                            action_log = gen._format_action_history_entry(item)
                            if action_log:
                                short_memories.append(action_log)
                                break

                        if action_entries:
                            char.setdefault("action_history", [])
                            if not isinstance(char.get("action_history"), list):
                                char["action_history"] = []
                            char["action_history"].extend(action_entries)
                            char["action_history"] = gen._dedupe_action_history(char["action_history"], limit=40)

                        if short_memories:
                            char.setdefault("memory_short_term", [])
                            if not isinstance(char.get("memory_short_term"), list):
                                char["memory_short_term"] = []
                            char["memory_short_term"].extend(short_memories)
                            char["memory_short_term"] = gen._dedupe_keep_order(char["memory_short_term"])[-30:]

                        if long_memories:
                            char.setdefault("memory_long_term", [])
                            if not isinstance(char.get("memory_long_term"), list):
                                char["memory_long_term"] = []
                            char["memory_long_term"].extend(long_memories)
                            char["memory_long_term"] = gen._dedupe_keep_order(char["memory_long_term"])[-40:]

                        if belief_memories:
                            char.setdefault("memory_beliefs", [])
                            if not isinstance(char.get("memory_beliefs"), list):
                                char["memory_beliefs"] = []
                            char["memory_beliefs"].extend(belief_memories)
                            char["memory_beliefs"] = gen._dedupe_keep_order(char["memory_beliefs"])[-20:]

                        if update.get("new_abilities"):
                            char.setdefault("abilities", [])
                            char["abilities"].extend(
                                str(item).strip() for item in update["new_abilities"] if str(item).strip()
                            )
                            char["abilities"] = gen._dedupe_keep_order(char["abilities"])
                        if update.get("new_items"):
                            char.setdefault("items", [])
                            char["items"].extend(str(item).strip() for item in update["new_items"] if str(item).strip())
                            char["items"] = gen._dedupe_keep_order(char["items"])
                        if isinstance(update.get("relationship_updates"), list):
                            gen._apply_relationship_updates(char, update["relationship_updates"])
                        if isinstance(update.get("relationship_changes"), list):
                            char.setdefault("relationship_history", [])
                            char["relationship_history"].extend(
                                str(item).strip()
                                for item in update.get("relationship_changes", [])
                                if str(item).strip()
                            )
                            char["relationship_history"] = char["relationship_history"][-20:]
            if protagonist_progress_logs:
                updates.setdefault("_meta", {})
                updates["_meta"]["protagonist_progress_logs"] = gen._dedupe_keep_order(protagonist_progress_logs)

            if "world_updates" in updates:
                world_updates = updates["world_updates"] if isinstance(updates["world_updates"], dict) else {}
                if "plot_progress" in world_updates:
                    gen.world_data.setdefault("plot_history", [])
                    gen.world_data["plot_history"].append(world_updates["plot_progress"])
                    gen.world_data["plot_history"] = gen.world_data["plot_history"][-10:]

                if world_updates.get("new_locations"):
                    gen.world_data.setdefault("locations", [])
                    for loc in world_updates["new_locations"]:
                        if isinstance(loc, dict):
                            loc_name = str(loc.get("name", "")).strip()
                            loc_desc = str(loc.get("description", "")).strip()
                        else:
                            loc_name = str(loc).strip()
                            loc_desc = ""
                        if not loc_name:
                            continue
                        existing_loc = next(
                            (item for item in gen.world_data["locations"] if item.get("name") == loc_name),
                            None,
                        )
                        if existing_loc:
                            if loc_desc:
                                existing_loc["description"] = loc_desc
                        else:
                            gen.world_data["locations"].append({"name": loc_name, "description": loc_desc})

                if world_updates.get("new_methods"):
                    gen.world_data.setdefault("world", {})
                    gen.world_data["world"].setdefault("known_methods", [])
                    gen.world_data["world"]["known_methods"].extend(
                        str(item).strip() for item in world_updates["new_methods"] if str(item).strip()
                    )
                    gen.world_data["world"]["known_methods"] = gen._dedupe_keep_order(
                        gen.world_data["world"]["known_methods"]
                    )

                if world_updates.get("new_artifacts"):
                    gen.world_data.setdefault("world", {})
                    gen.world_data["world"].setdefault("known_artifacts", [])
                    gen.world_data["world"]["known_artifacts"].extend(
                        str(item).strip() for item in world_updates["new_artifacts"] if str(item).strip()
                    )
                    gen.world_data["world"]["known_artifacts"] = gen._dedupe_keep_order(
                        gen.world_data["world"]["known_artifacts"]
                    )

                if world_updates.get("new_factions"):
                    gen.world_data.setdefault("world", {})
                    gen.world_data["world"].setdefault("factions", [])
                    gen.world_data["world"]["factions"].extend(
                        str(item).strip() for item in world_updates["new_factions"] if str(item).strip()
                    )
                    gen.world_data["world"]["factions"] = gen._dedupe_keep_order(
                        gen.world_data["world"]["factions"]
                    )

                if world_updates.get("time_advance"):
                    gen.world_data.setdefault("timeline", [])
                    gen.world_data["timeline"].append(str(world_updates["time_advance"]).strip())
                    gen.world_data["timeline"] = gen.world_data["timeline"][-20:]

                if isinstance(world_updates.get("faction_changes"), list):
                    gen.world_data.setdefault("faction_history", [])
                    gen.world_data["faction_history"].extend(
                        str(item).strip() for item in world_updates["faction_changes"] if str(item).strip()
                    )
                    gen.world_data["faction_history"] = gen.world_data["faction_history"][-30:]

                if isinstance(world_updates.get("world_state_notes"), list):
                    gen.world_data.setdefault("world_state_notes", [])
                    gen.world_data["world_state_notes"].extend(
                        str(item).strip() for item in world_updates["world_state_notes"] if str(item).strip()
                    )
                    gen.world_data["world_state_notes"] = gen.world_data["world_state_notes"][-30:]

            gen.edit_tools.save_world_state(gen.project_name, gen.world_data)
            yield "\n✅ 状态已更新"
            for line in gen._build_world_update_summary_lines(updates):
                yield line
            if "chapter_summary" in updates:
                yield f" | 本章: {updates['chapter_summary']}"
            return {"updated": True, "updates": updates}
        except Exception as exc:
            yield f"\n⚠️ 状态更新失败: {exc}"
            return {"updated": False, "error": str(exc)}
