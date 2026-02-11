import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from skills_runtime import NovelSkillMiner


class MockAI:
    def chat(self, prompt: str, system_prompt: str = "", **kwargs):
        _ = (system_prompt, kwargs)
        if "生成三类技能可直接使用的技巧清单" in prompt:
            return json.dumps(
                {
                    "outline_skill_tips": ["卷级目标先行", "每章必须有冲突节点"],
                    "continuation_skill_tips": ["强承接上章末尾动作", "结尾必须留风险"],
                    "rewrite_skill_tips": ["删解释、留动作", "对白需角色化"],
                    "global_do_not": ["避免设定堆砌"],
                },
                ensure_ascii=False,
            )
        return json.dumps(
            {
                "novel": "样本",
                "hook_patterns": ["3段内入冲突"],
                "pacing_patterns": ["短段推进"],
                "dialogue_patterns": ["角色口吻分离"],
                "scene_transition_patterns": ["目标驱动切场"],
                "cliffhanger_patterns": ["章末新问题"],
                "rewrite_patterns": ["替换抽象句为动作句"],
                "top_reusable_techniques": ["先冲突后解释"],
            },
            ensure_ascii=False,
        )


def test_novel_skill_miner_mines_and_writes_references(tmp_path):
    source = tmp_path / "novels"
    source.mkdir(parents=True, exist_ok=True)

    novel_a = source / "novel_a"
    novel_a.mkdir()
    (novel_a / "001.txt").write_text("第1章 开局\n内容A1", encoding="utf-8")
    (novel_a / "002.txt").write_text("第2章 转折\n内容A2", encoding="utf-8")

    novel_b = source / "novel_b.txt"
    novel_b.write_text(
        "第1章 起\n内容B1\n\n第2章 承\n内容B2\n\n第3章 转\n内容B3",
        encoding="utf-8",
    )

    skills_dir = tmp_path / "skills"
    miner = NovelSkillMiner(ai_client=MockAI(), skills_dir=str(skills_dir))
    report = miner.mine(str(source), max_novels=20, max_chapters=100, chapter_chars=2000)

    assert report["novel_count"] == 2
    assert "aggregate" in report

    paths = miner.write_skill_references(report)
    assert "outline-skill" in paths
    assert "continuation-skill" in paths
    assert "rewrite-skill" in paths

    outline_file = paths["outline-skill"]
    assert os.path.exists(outline_file)
    text = open(outline_file, "r", encoding="utf-8").read()
    assert "卷级目标先行" in text
