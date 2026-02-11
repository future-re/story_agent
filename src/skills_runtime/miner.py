"""Novel corpus miner: learn writing techniques and write skill references."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from json_repair import repair_json
except ImportError:
    repair_json = None


@dataclass
class NovelSample:
    """Parsed sample from one novel."""

    name: str
    chapters: List[str]

    @property
    def chapter_count(self) -> int:
        return len(self.chapters)

    def merged_text(self, max_chars: int = 20000) -> str:
        joined = "\n\n".join(self.chapters)
        if max_chars > 0:
            return joined[:max_chars]
        return joined


class NovelSkillMiner:
    """Analyze multi-novel corpus and generate skill technique references."""

    def __init__(self, ai_client: Any, skills_dir: str):
        self.ai = ai_client
        self.skills_dir = Path(skills_dir)

    def collect_corpus(
        self,
        source_dir: str,
        *,
        max_novels: int = 20,
        max_chapters: int = 100,
        chapter_chars: int = 3000,
    ) -> List[NovelSample]:
        root = Path(source_dir)
        if not root.exists():
            raise FileNotFoundError(f"语料目录不存在: {source_dir}")

        entries = sorted(root.iterdir(), key=lambda p: p.name)
        samples: List[NovelSample] = []
        for entry in entries:
            if len(samples) >= max_novels:
                break
            if entry.is_dir():
                chapters = self._read_chapters_from_novel_dir(entry, max_chapters=max_chapters, chapter_chars=chapter_chars)
            elif entry.is_file() and entry.suffix.lower() in {".txt", ".md"}:
                chapters = self._read_chapters_from_single_file(entry, max_chapters=max_chapters, chapter_chars=chapter_chars)
            else:
                continue

            if not chapters:
                continue
            samples.append(NovelSample(name=entry.stem, chapters=chapters))
        return samples

    def mine(
        self,
        source_dir: str,
        *,
        max_novels: int = 20,
        max_chapters: int = 100,
        chapter_chars: int = 3000,
    ) -> Dict[str, Any]:
        corpus = self.collect_corpus(
            source_dir,
            max_novels=max_novels,
            max_chapters=max_chapters,
            chapter_chars=chapter_chars,
        )
        if not corpus:
            raise ValueError("未读取到有效小说样本，请检查目录结构和文件格式。")

        per_novel = [self._analyze_one(sample) for sample in corpus]
        aggregate = self._aggregate(per_novel)
        report = {
            "source_dir": os.path.abspath(source_dir),
            "novel_count": len(corpus),
            "max_chapters_per_novel": max_chapters,
            "per_novel": per_novel,
            "aggregate": aggregate,
        }
        return report

    def write_skill_references(self, report: Dict[str, Any]) -> Dict[str, str]:
        aggregate = report.get("aggregate", {}) if isinstance(report, dict) else {}
        files: Dict[str, str] = {}
        mapping = {
            "outline-skill": aggregate.get("outline_skill_tips", []),
            "continuation-skill": aggregate.get("continuation_skill_tips", []),
            "rewrite-skill": aggregate.get("rewrite_skill_tips", []),
        }

        for skill_name, tips in mapping.items():
            skill_dir = self.skills_dir / skill_name
            ref_dir = skill_dir / "references"
            ref_dir.mkdir(parents=True, exist_ok=True)
            path = ref_dir / "learned_techniques.md"

            lines = [
                f"# Learned Techniques ({skill_name})",
                "",
                "来源：小说语料前100章自动分析",
                "",
            ]
            if isinstance(tips, list) and tips:
                for idx, tip in enumerate(tips, 1):
                    text = str(tip).strip()
                    if not text:
                        continue
                    lines.append(f"{idx}. {text}")
            else:
                lines.append("暂无可用技巧。")
            path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
            files[skill_name] = str(path)
        return files

    def _analyze_one(self, sample: NovelSample) -> Dict[str, Any]:
        prompt = f"""你是中文网文编辑，请分析以下小说样本（前{sample.chapter_count}章截断文本），提炼“可迁移写作技巧”。

【小说名】{sample.name}
【样本文本】
{sample.merged_text(max_chars=24000)}

请输出 JSON：
{{
  "novel": "{sample.name}",
  "hook_patterns": ["开篇钩子技巧"],
  "pacing_patterns": ["节奏控制技巧"],
  "dialogue_patterns": ["对白技巧"],
  "scene_transition_patterns": ["场景切换技巧"],
  "cliffhanger_patterns": ["章末钩子技巧"],
  "rewrite_patterns": ["语言改写/润色技巧"],
  "top_reusable_techniques": ["最值得迁移的技巧"]
}}
"""
        raw = self.ai.chat(prompt, system_prompt="你是写作技巧分析器，只输出合法JSON。")
        parsed = self._extract_json_dict(raw if isinstance(raw, str) else str(raw))
        if parsed:
            return parsed
        return {
            "novel": sample.name,
            "hook_patterns": [],
            "pacing_patterns": [],
            "dialogue_patterns": [],
            "scene_transition_patterns": [],
            "cliffhanger_patterns": [],
            "rewrite_patterns": [],
            "top_reusable_techniques": [],
        }

    def _aggregate(self, per_novel: List[Dict[str, Any]]) -> Dict[str, Any]:
        payload = json.dumps(per_novel, ensure_ascii=False, indent=2)
        prompt = f"""基于以下多本小说技巧分析结果，生成三类技能可直接使用的技巧清单：
1) outline-skill
2) continuation-skill
3) rewrite-skill

【输入】
{payload}

请输出 JSON：
{{
  "outline_skill_tips": ["..."],
  "continuation_skill_tips": ["..."],
  "rewrite_skill_tips": ["..."],
  "global_do_not": ["应避免的问题"]
}}
"""
        raw = self.ai.chat(prompt, system_prompt="你是技能提炼器，只输出合法JSON。")
        parsed = self._extract_json_dict(raw if isinstance(raw, str) else str(raw))
        if parsed:
            return parsed
        return {
            "outline_skill_tips": [],
            "continuation_skill_tips": [],
            "rewrite_skill_tips": [],
            "global_do_not": [],
        }

    @staticmethod
    def _read_chapters_from_novel_dir(path: Path, *, max_chapters: int, chapter_chars: int) -> List[str]:
        files = [
            file
            for file in sorted(path.iterdir(), key=lambda p: p.name)
            if file.is_file() and file.suffix.lower() in {".txt", ".md"}
        ]
        chapters: List[str] = []
        for file in files[:max_chapters]:
            try:
                text = file.read_text(encoding="utf-8").strip()
            except OSError:
                continue
            if not text:
                continue
            chapters.append(text[:chapter_chars] if chapter_chars > 0 else text)
        return chapters

    @staticmethod
    def _read_chapters_from_single_file(path: Path, *, max_chapters: int, chapter_chars: int) -> List[str]:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return []
        chunks = NovelSkillMiner._split_text_into_chapters(text)
        chapters = chunks[:max_chapters]
        return [chapter[:chapter_chars] if chapter_chars > 0 else chapter for chapter in chapters]

    @staticmethod
    def _split_text_into_chapters(text: str) -> List[str]:
        normalized = str(text or "").replace("\r\n", "\n")
        heading = re.compile(r"(?m)^(第[0-9一二三四五六七八九十百千两零〇]+章[^\n]*|Chapter\s+\d+[^\n]*)$")
        matches = list(heading.finditer(normalized))
        if not matches:
            stripped = normalized.strip()
            return [stripped] if stripped else []

        chapters: List[str] = []
        for idx, match in enumerate(matches):
            start = match.start()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(normalized)
            chunk = normalized[start:end].strip()
            if chunk:
                chapters.append(chunk)
        return chapters

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
