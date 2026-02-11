import json
import os
import sys
from typing import List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from generation.outline import OutlineGenerator
from storage import StorageManager


class MockAI:
    def __init__(self, responses: List[str]):
        self.responses = responses
        self.calls = 0

    def chat(self, *args, **kwargs):
        if self.calls >= len(self.responses):
            raise RuntimeError("mock responses exhausted")
        response = self.responses[self.calls]
        self.calls += 1
        return response


def test_build_story_pipeline_saves_all_artifacts(tmp_path):
    blueprint_payload = json.dumps(
        {
            "title_candidate": "幽狱志",
            "genre": "玄幻",
            "target_audience": "男频",
            "character_setup": [
                {
                    "name": "沈焱笙",
                    "gender": "男",
                    "identity": "井底鬼修",
                    "age": "18",
                    "appearance": "瘦削冷白",
                    "personality_temperament": "冷静克制",
                    "desire": "复仇",
                    "short_term_goal": "先活下来",
                },
                {
                    "name": "将军鬼物",
                    "gender": "男",
                    "identity": "旧军残魂",
                    "age": "未知",
                    "appearance": "甲胄残破",
                    "personality_temperament": "强硬偏执",
                    "desire": "守住地盘",
                    "short_term_goal": "压制外来者",
                },
            ],
            "core_event": {
                "event_goal": "主角借阴井势力复仇",
                "meaning": "重塑命运",
                "difficulties": ["资源不足", "势力追杀"],
            },
            "conflicts": [
                {
                    "conflict": "主角与幽冥宗敌对",
                    "phase_result": "阶段性失利",
                    "resolution_path": "伪装潜伏并反查",
                }
            ],
            "plot_development": {
                "cause": "主角被投入阴井",
                "development": "结盟与反查并行",
                "twist": "盟友身份反转",
                "climax": "井口大战",
                "ending": "主角暂胜并埋下新敌",
            },
            "scene_formula": [
                {
                    "location": "凛阴岗古井",
                    "characters": ["沈焱笙", "将军鬼物"],
                    "event": "试探结盟",
                    "result": "形成短期同盟",
                }
            ],
        },
        ensure_ascii=False,
    )

    detailed_payload = json.dumps(
        {
            "summary": "卷一围绕井底求生与反查布局展开。",
            "volumes": [
                {
                    "title": "卷1：井下破局",
                    "start_chapter": 1,
                    "end_chapter": 4,
                    "phase": "开局试探",
                    "volume_goal": "建立主角生存优势",
                    "chapter_beats": [
                        {
                            "chapter": 1,
                            "title": "井底醒来",
                            "goal": "确认局势并避免被吞噬",
                            "conflict": "主角与井底鬼物互相试探",
                            "hook": "井壁出现旧阵纹",
                            "scene_formula": [
                                {
                                    "location": "井底",
                                    "characters": ["沈焱笙"],
                                    "event": "探查阴井",
                                    "result": "发现阵纹线索",
                                }
                            ],
                        }
                    ],
                }
            ],
            "outline_markdown": "## 卷1：井下破局（第1-4章）\n### 开局试探（第1-4章）\n- **第1章**: 确认局势并避免被吞噬\n  - 冲突：主角与井底鬼物互相试探\n  - 钩子：井壁出现旧阵纹\n",
        },
        ensure_ascii=False,
    )

    world_payload = json.dumps(
        {
            "characters": [
                {
                    "name": "沈焱笙",
                    "role": "主角",
                    "appeared": True,
                    "personality": "冷静克制",
                    "level": "鬼道·怨灵境·后期",
                    "abilities": ["阴符凝火"],
                    "items": ["残魂玉"],
                    "current_goal": "反查幽冥宗",
                    "action_tendency": "先观察再出手",
                    "relationships": [
                        {"target": "将军鬼物", "relation_type": "盟友", "description": "互利合作"}
                    ],
                    "current_status": [],
                    "action_history": [],
                    "memory_short_term": [],
                    "memory_long_term": [],
                }
            ],
            "world": {
                "environment": "阴井与鬼域交叠",
                "power_system": "鬼道修行",
                "factions": ["幽冥宗"],
                "known_methods": ["阴符凝火"],
                "known_artifacts": ["残魂玉"],
                "scene_rules": ["井口白日封禁"],
            },
            "locations": [{"name": "凛阴岗古井", "description": "阴气汇聚之地"}],
            "plot_history": [],
            "timeline": [],
            "faction_history": [],
            "world_state_notes": [],
        },
        ensure_ascii=False,
    )

    ai = MockAI([blueprint_payload, detailed_payload, world_payload])
    storage = StorageManager(str(tmp_path))
    gen = OutlineGenerator(ai_client=ai, storage=storage)

    result = gen.build_story_pipeline(
        idea="被投入阴井的少年鬼修要在势力夹缝中求生复仇",
        project_name="幽狱志",
        chapter_count=4,
    )

    assert ai.calls == 3
    assert "blueprint" in result
    assert "detailed_outline" in result
    assert "world_state" in result
    assert result["world_state"]["characters"][0]["name"] == "沈焱笙"

    project_dir = storage.get_project_dir("幽狱志")
    assert os.path.exists(os.path.join(project_dir, "story_blueprint.json"))
    assert os.path.exists(os.path.join(project_dir, "detailed_outline.json"))
    assert os.path.exists(os.path.join(project_dir, "world_state.json"))
    assert os.path.exists(os.path.join(project_dir, "大纲.txt"))

    with open(os.path.join(project_dir, "大纲.txt"), "r", encoding="utf-8") as f:
        outline_text = f.read()
    assert "## 卷1：井下破局（第1-4章）" in outline_text
    assert "- **第1章**: 确认局势并避免被吞噬" in outline_text


def test_generate_detailed_outline_renders_markdown_when_missing(tmp_path):
    payload = json.dumps(
        {
            "summary": "测试细纲",
            "volumes": [
                {
                    "title": "卷一：测试卷",
                    "start_chapter": 1,
                    "end_chapter": 2,
                    "phase": "开局",
                    "volume_goal": "建立冲突",
                    "chapter_beats": [
                        {
                            "chapter": 1,
                            "title": "测试章",
                            "goal": "推进冲突",
                            "conflict": "双方对峙",
                            "hook": "出现新线索",
                            "scene_formula": [
                                {
                                    "location": "古井",
                                    "characters": ["主角"],
                                    "event": "试探",
                                    "result": "发现异常",
                                }
                            ],
                        }
                    ],
                }
            ],
        },
        ensure_ascii=False,
    )
    ai = MockAI([payload])
    storage = StorageManager(str(tmp_path))
    gen = OutlineGenerator(ai_client=ai, storage=storage)

    blueprint = {
        "title_candidate": "测试",
        "genre": "玄幻",
        "target_audience": "网文读者",
        "character_setup": [],
        "core_event": {},
        "conflicts": [],
        "plot_development": {},
        "scene_formula": [],
    }
    detailed = gen.generate_detailed_outline(blueprint=blueprint, chapter_count=2, save_to="测试项目")

    assert detailed["outline_markdown"]
    assert "## 卷一：测试卷（第1-2章）" in detailed["outline_markdown"]
    assert "- **第1章**: 推进冲突" in detailed["outline_markdown"]

