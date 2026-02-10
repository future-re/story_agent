import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from generation.thinking import PlotThinkingEngine
from tools.thinking_tools import build_thinking_cache_key, clip_tail, resolve_thinking_mode


class MockThinkingAI:
    def __init__(self):
        self.calls = 0

    def stream_chat(self, *args, **kwargs):
        self.calls += 1
        yield """{
  "plot_analysis": {
    "pre_chapter_context": {
      "previous_ending": "主角跌入密道",
      "immediate_consequences": "先确认伤势和出口",
      "character_emotional_carryover": "紧张戒备"
    },
    "interaction_logic_check": [],
    "current_situation": "密道危机"
  },
  "chapter_blueprint": {
    "title_suggestion": "密道惊魂",
    "theme": "危机中的冷静",
    "opening_hook": "脚步声逼近",
    "storyboard": [
      {
        "shot_number": 1,
        "location": "密道入口",
        "action_beats": [{"beat": 1, "actor": "主角", "action": "贴墙潜行", "reaction": "听到追兵"}],
        "dialogue_script": [],
        "purpose": "立刻承接前文"
      }
    ],
    "cliffhanger": {"type": "危机", "final_line": "火光映出陌生人影", "reader_hook": "那人是谁？"},
    "writing_guidance": {"tone": "紧张", "pacing": "快"}
  }
}"""


def test_clip_tail():
    assert clip_tail("abcdef", 3) == "def"
    assert clip_tail("abc", 10) == "abc"
    assert clip_tail("", 5) == ""


def test_resolve_thinking_mode():
    mode, reason = resolve_thinking_mode("auto", is_append=True, chapter_num=8, previous_content="x" * 100)
    assert mode == "fast"
    assert reason

    mode, _ = resolve_thinking_mode("deep", is_append=True, chapter_num=8, previous_content="x" * 100)
    assert mode == "deep"


def test_build_cache_key_is_stable():
    key1 = build_thinking_cache_key(
        chapter_num=2,
        thinking_mode="fast",
        outline_info={"volume": "卷一", "phase": "前中期"},
        world_context="world",
        previous_content="prev",
    )
    key2 = build_thinking_cache_key(
        chapter_num=2,
        thinking_mode="fast",
        outline_info={"phase": "前中期", "volume": "卷一"},
        world_context="world",
        previous_content="prev",
    )
    key3 = build_thinking_cache_key(
        chapter_num=2,
        thinking_mode="deep",
        outline_info={"phase": "前中期", "volume": "卷一"},
        world_context="world",
        previous_content="prev",
    )
    assert key1 == key2
    assert key1 != key3


def test_thinking_engine_cache_hit():
    ai = MockThinkingAI()
    engine = PlotThinkingEngine(ai_client=ai, cache_size=4)

    params = dict(
        chapter_num=5,
        outline_info={"volume": "卷一", "phase": "中段", "specific_goal": "逃离追捕"},
        world_context="角色状态",
        previous_content="上一章结尾",
        is_append=True,
        thinking_mode="fast",
    )

    outputs_1 = list(engine.analyze_chapter(**params))
    outputs_2 = list(engine.analyze_chapter(**params))

    assert ai.calls == 1
    assert any(isinstance(item, dict) for item in outputs_1)
    assert any(isinstance(item, dict) for item in outputs_2)
    assert any("使用缓存剧情规划" in item for item in outputs_2 if isinstance(item, str))
