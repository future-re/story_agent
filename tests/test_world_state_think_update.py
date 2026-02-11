import os
import sys
from typing import Any, Dict, Generator, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from generation.chapter import ChapterGenerator


class MockAI:
    def __init__(self, payload: str):
        self.payload = payload
        self.calls = 0

    def stream_chat(self, *args, **kwargs) -> Generator[str, None, None]:
        self.calls += 1
        yield self.payload


class MockThinkingEngine:
    def __init__(self, ai_client):
        self.ai = ai_client


class MockStorage:
    def __init__(self, initial_world: Dict[str, Any]):
        self.initial_world = initial_world
        self.saved_world: Dict[str, Any] = {}

    def load_world_state(self, project_name: str) -> Dict[str, Any]:
        return self.initial_world

    def save_world_state(self, project_name: str, state_data: Dict[str, Any]) -> str:
        self.saved_world = state_data
        return "/tmp/world_state.json"

    def list_chapters(self, project_name: str) -> List[str]:
        return []

    def get_project_dir(self, project_name: str) -> str:
        return "/tmp"

    @property
    def base_dir(self) -> str:
        return "/tmp"


def _consume_generator_with_return(gen):
    chunks = []
    try:
        while True:
            chunks.append(next(gen))
    except StopIteration as stop:
        return chunks, stop.value


def test_world_state_update_prefers_thinking_model_and_updates_relationships():
    world = {
        "characters": [
            {
                "name": "沈焱笙",
                "level": "怨灵",
                "relationships": [
                    {"target": "将军鬼物", "relation_type": "合作", "description": "暂时联手"}
                ],
            },
            {"name": "将军鬼物", "level": "凶魂"},
        ],
        "world": {"known_methods": [], "known_artifacts": [], "factions": []},
    }

    think_payload = """{
      "character_updates": [
        {
          "name": "沈焱笙",
          "status_change": "魂力亏空但保持警惕",
          "status_tags": ["受伤", "警惕"],
          "physical_state": "魂体虚弱",
          "mental_state": "冷静克制",
          "current_goal": "先稳住魂体，再反查幽冥宗线索",
          "action_history_entries": [
            {
              "action": "借阴井余气压住魂核裂纹",
              "reason": "防止魂力溃散",
              "outcome": "短时稳定",
              "impact": "可继续追查敌踪"
            }
          ],
          "memory_updates": {
            "short_term": ["确认幽冥宗已盯上自己"],
            "long_term": ["将军鬼物可作为阶段盟友"],
            "beliefs": ["先活下来再谈复仇"]
          },
          "relationship_updates": [
            {"target": "将军鬼物", "relation_type": "盟友", "description": "互利同盟升级"},
            {"target": "幽冥宗外门执事", "relation_type": "敌对", "description": "被对方锁定"}
          ],
          "relationship_changes": ["与将军鬼物从合作升级为盟友"],
          "new_abilities": ["阴符凝火"],
          "new_items": ["破损魂玉"]
        }
      ],
      "world_updates": {
        "new_factions": ["幽冥宗"],
        "time_advance": "距离侯府复仇还有两日",
        "faction_changes": ["幽冥宗开始追查将军鬼物"],
        "world_state_notes": ["凛阴岗周边戒备加强"]
      },
      "chapter_summary": "沈焱笙在疗伤中确认了下一步目标。"
    }"""

    chat_ai = MockAI(payload='{"character_updates":[]}')
    think_ai = MockAI(payload=think_payload)
    storage = MockStorage(initial_world=world)
    gen = ChapterGenerator(
        "幽狱志",
        ai_client=chat_ai,
        storage=storage,
        thinking_engine=MockThinkingEngine(think_ai),
    )

    chunks, result = _consume_generator_with_return(gen.update_world_state("测试章节内容"))

    assert result["updated"] is True
    assert think_ai.calls == 1
    assert chat_ai.calls == 0
    assert any("正在更新世界状态（think）" in item for item in chunks if isinstance(item, str))
    assert any("更新摘要" in item for item in chunks if isinstance(item, str))
    assert any("人物关系变更" in item for item in chunks if isinstance(item, str))

    protagonist = next(c for c in gen.world_data["characters"] if c.get("name") == "沈焱笙")
    assert "魂力亏空但保持警惕" in protagonist.get("current_status", [])
    assert protagonist.get("physical_state") == "魂体虚弱"
    assert protagonist.get("mental_state") == "冷静克制"
    assert protagonist.get("current_goal") == "先稳住魂体，再反查幽冥宗线索"
    assert "阴符凝火" in protagonist.get("abilities", [])
    assert "破损魂玉" in protagonist.get("items", [])
    assert "受伤" in protagonist.get("status_tags", [])
    assert protagonist.get("action_history")
    assert protagonist["action_history"][-1]["action"] == "借阴井余气压住魂核裂纹"
    assert "确认幽冥宗已盯上自己" in protagonist.get("memory_short_term", [])
    assert "将军鬼物可作为阶段盟友" in protagonist.get("memory_long_term", [])
    assert "先活下来再谈复仇" in protagonist.get("memory_beliefs", [])

    updated_rels = protagonist.get("relationships", [])
    assert any(rel.get("target") == "将军鬼物" and rel.get("relation_type") == "盟友" for rel in updated_rels)
    assert any(rel.get("target") == "幽冥宗外门执事" and rel.get("relation_type") == "敌对" for rel in updated_rels)
    assert "与将军鬼物从合作升级为盟友" in protagonist.get("relationship_history", [])

    assert "幽冥宗" in gen.world_data.get("world", {}).get("factions", [])
    assert "距离侯府复仇还有两日" in gen.world_data.get("timeline", [])
    assert "幽冥宗开始追查将军鬼物" in gen.world_data.get("faction_history", [])
    assert "凛阴岗周边戒备加强" in gen.world_data.get("world_state_notes", [])
    assert storage.saved_world


def test_prepare_writing_builds_character_action_plan_context():
    world = {
        "characters": [
            {
                "name": "沈焱笙",
                "role": "主角",
                "personality": "冷静果断",
                "desire": "复仇并变强",
                "level": "鬼道·怨灵境·后期",
                "current_goal": "查清幽冥宗追踪线索",
                "current_status": ["魂体受损后恢复"],
                "relationships": [{"target": "将军鬼物", "relation_type": "盟友"}],
            },
            {
                "name": "将军鬼物",
                "role": "配角",
                "personality": "执念深重",
                "desire": "守住地盘",
                "level": "鬼道·凶煞境·中期",
                "current_status": ["潜伏观察"],
            },
        ],
        "world": {"known_methods": [], "known_artifacts": [], "factions": []},
    }

    action_plan_payload = """{
      "scene_overview": "双方在阴井周围进行试探性博弈",
      "character_plans": [
        {
          "name": "沈焱笙",
          "personality_anchor": "冷静果断",
          "current_goal": "查清幽冥宗追踪线索",
          "internal_thought": "先确认追踪源，再决定是否反击",
          "action_choice": "借井壁残阵反向追踪气息",
          "interaction_targets": ["将军鬼物"],
          "risk_assessment": "暴露自身位置",
          "expected_change": "短暂获取敌方情报",
          "memory_implication": {
            "short_term": ["确认追踪源来自幽冥宗外门"],
            "long_term": ["与将军鬼物建立战术互信"],
            "action_log": "反向追踪敌方气息"
          }
        },
        {
          "name": "将军鬼物",
          "personality_anchor": "执念深重",
          "current_goal": "避免领地失控",
          "internal_thought": "可暂借沈焱笙之力清除外敌",
          "action_choice": "压制井口阴煞防止外敌入侵",
          "interaction_targets": ["沈焱笙"],
          "risk_assessment": "被人类修士察觉",
          "expected_change": "与沈焱笙形成短暂协同",
          "memory_implication": {
            "short_term": ["默认与沈焱笙协同防守"],
            "long_term": [],
            "action_log": "封锁井口"
          }
        }
      ],
      "scene_action_order": [
        {"step": 1, "actor": "沈焱笙", "action": "布置反追踪符线", "reason": "确认敌踪来源"},
        {"step": 2, "actor": "将军鬼物", "action": "封锁井口阴煞", "reason": "防止外敌趁隙而入"},
        {"step": 3, "actor": "沈焱笙", "action": "共享敌踪信息", "reason": "争取临时同盟"}
      ]
    }"""

    ai = MockAI(payload=action_plan_payload)
    storage = MockStorage(initial_world=world)
    gen = ChapterGenerator("幽狱志", ai_client=ai, storage=storage, thinking_engine=None)

    chunks, preparation = _consume_generator_with_return(gen.prepare_writing())

    assert any("正在推演角色行动" in item for item in chunks if isinstance(item, str))
    assert preparation["character_action_plan"]["scene_overview"].startswith("双方在阴井周围")
    assert preparation["character_action_plan"]["character_plans"][0]["name"] == "沈焱笙"
    assert "角色行动决策（场景级推演）" in preparation.get("character_action_context", "")
    assert "沈焱笙" in preparation.get("character_action_context", "")


def test_protagonist_level_update_blocked_without_required_resources():
    world = {
        "characters": [
            {
                "name": "沈焱笙",
                "level": "鬼道·怨灵境·后期（井底破封后）",
                "current_status": [],
                "relationships": [],
            }
        ],
        "world": {
            "known_methods": [],
            "known_artifacts": [],
            "factions": [],
            "protagonist_progression": {
                "name": "沈焱笙",
                "current_level": "鬼道·怨灵境·后期（井底破封后）",
                "next_level": "鬼道·怨灵境·圆满（镜域寄生）",
                "active_transition_index": 0,
                "transitions": [
                    {
                        "from_level": "鬼道·怨灵境·后期",
                        "to_level": "鬼道·怨灵境·圆满（镜域寄生）",
                        "required_resources": [
                            {"name": "镜鬼本源碎片", "status": "missing"},
                            {"name": "三夜惊恐香火", "status": "missing"},
                        ],
                        "required_conditions": [
                            {"name": "完成一次镜面猎杀并稳定魂核", "status": "pending"},
                        ],
                        "completed": False,
                    }
                ],
            },
        },
    }

    think_payload = """{
      "character_updates": [
        {
          "name": "沈焱笙",
          "level_update": "鬼道·怨灵境·圆满（镜域寄生）"
        }
      ],
      "world_updates": {},
      "chapter_summary": "主角尝试冲关。"
    }"""

    chat_ai = MockAI(payload='{"character_updates":[]}')
    think_ai = MockAI(payload=think_payload)
    storage = MockStorage(initial_world=world)
    gen = ChapterGenerator(
        "幽狱志",
        ai_client=chat_ai,
        storage=storage,
        thinking_engine=MockThinkingEngine(think_ai),
    )

    _, result = _consume_generator_with_return(gen.update_world_state("沈焱笙尝试突破但资源不足。"))

    assert result["updated"] is True
    protagonist = gen.world_data["characters"][0]
    assert protagonist["level"] == "鬼道·怨灵境·后期（井底破封后）"
    assert any("境界更新被拦截" in entry for entry in protagonist.get("current_status", []))


def test_protagonist_level_update_succeeds_with_resource_progress():
    world = {
        "characters": [
            {
                "name": "沈焱笙",
                "level": "鬼道·怨灵境·后期（井底破封后）",
                "current_status": [],
                "relationships": [],
            }
        ],
        "world": {
            "known_methods": [],
            "known_artifacts": [],
            "factions": [],
            "protagonist_progression": {
                "name": "沈焱笙",
                "current_level": "鬼道·怨灵境·后期（井底破封后）",
                "next_level": "鬼道·怨灵境·圆满（镜域寄生）",
                "active_transition_index": 0,
                "transitions": [
                    {
                        "from_level": "鬼道·怨灵境·后期",
                        "to_level": "鬼道·怨灵境·圆满（镜域寄生）",
                        "required_resources": [
                            {"name": "镜鬼本源碎片", "status": "missing"},
                            {"name": "三夜惊恐香火", "status": "missing"},
                        ],
                        "required_conditions": [
                            {"name": "完成一次镜面猎杀并稳定魂核", "status": "pending"},
                        ],
                        "completed": False,
                    },
                    {
                        "from_level": "鬼道·怨灵境·圆满",
                        "to_level": "鬼道·厉鬼境·初期",
                        "required_resources": [{"name": "厉鬼鬼核", "status": "missing"}],
                        "required_conditions": [{"name": "吞噬同阶强敌", "status": "pending"}],
                        "completed": False,
                    },
                ],
            },
        },
    }

    think_payload = """{
      "character_updates": [
        {
          "name": "沈焱笙",
          "breakthrough_progress": {
            "resources_acquired": ["镜鬼本源碎片", "三夜惊恐香火"],
            "conditions_completed": ["完成一次镜面猎杀并稳定魂核"]
          },
          "level_update": "鬼道·怨灵境·圆满（镜域寄生）"
        }
      ],
      "world_updates": {},
      "chapter_summary": "主角完成镜域合魂，突破成功。"
    }"""

    chat_ai = MockAI(payload='{"character_updates":[]}')
    think_ai = MockAI(payload=think_payload)
    storage = MockStorage(initial_world=world)
    gen = ChapterGenerator(
        "幽狱志",
        ai_client=chat_ai,
        storage=storage,
        thinking_engine=MockThinkingEngine(think_ai),
    )

    chunks, result = _consume_generator_with_return(gen.update_world_state("沈焱笙吞噬镜鬼本源并完成镜域合魂。"))

    assert result["updated"] is True
    protagonist = gen.world_data["characters"][0]
    assert protagonist["level"] == "鬼道·怨灵境·圆满（镜域寄生）"
    progression = gen.world_data["world"]["protagonist_progression"]
    assert progression["current_level"] == "鬼道·怨灵境·圆满（镜域寄生）"
    assert progression["next_level"] == "鬼道·厉鬼境·初期"
    assert progression["active_transition_index"] == 1
    assert any("主角晋升进度" in item for item in chunks if isinstance(item, str))
