"""Skill document registry for local SKILL.md files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class SkillDocument:
    """In-memory representation of a skill markdown file."""

    name: str
    description: str
    body: str
    path: str


def _split_frontmatter(text: str) -> Tuple[Dict[str, str], str]:
    content = str(text or "")
    if not content.startswith("---\n"):
        return {}, content

    end_marker = "\n---\n"
    end_idx = content.find(end_marker, 4)
    if end_idx < 0:
        return {}, content

    raw_meta = content[4:end_idx]
    body = content[end_idx + len(end_marker) :]
    meta: Dict[str, str] = {}
    for line in raw_meta.splitlines():
        stripped = line.strip()
        if not stripped or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        meta[key.strip()] = value.strip().strip('"').strip("'")
    return meta, body


class SkillRegistry:
    """Load and cache skills from local repository paths."""

    def __init__(self, skills_dir: str):
        self.skills_dir = Path(skills_dir)
        self._cache: Dict[str, Optional[SkillDocument]] = {}

    @classmethod
    def default(cls) -> "SkillRegistry":
        repo_root = Path(__file__).resolve().parents[2]
        return cls(str(repo_root / "skills"))

    def load(self, skill_name: str) -> Optional[SkillDocument]:
        normalized = str(skill_name or "").strip()
        if not normalized:
            return None
        if normalized in self._cache:
            return self._cache[normalized]

        skill_path = self.skills_dir / normalized / "SKILL.md"
        if not skill_path.exists():
            self._cache[normalized] = None
            return None

        raw = skill_path.read_text(encoding="utf-8")
        meta, body = _split_frontmatter(raw)
        document = SkillDocument(
            name=meta.get("name", normalized),
            description=meta.get("description", ""),
            body=body.strip(),
            path=str(skill_path),
        )
        self._cache[normalized] = document
        return document
