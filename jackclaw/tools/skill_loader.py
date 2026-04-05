"""
Skill 加载器
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


@dataclass
class SkillMeta:
    """Skill 元数据"""
    name: str
    description: str
    type: str
    version: str
    path: Path

    @classmethod
    def from_md(cls, path: Path) -> "SkillMeta":
        """从 SKILL.md 解析"""
        content = path.read_text(encoding="utf-8")
        if not content.startswith("---"):
            raise ValueError(f"Invalid SKILL.md: {path}")
        parts = content.split("---", 2)
        if len(parts) < 3:
            raise ValueError(f"Invalid SKILL.md: {path}")
        frontmatter = yaml.safe_load(parts[1])
        return cls(
            name=frontmatter.get("name", ""),
            description=frontmatter.get("description", ""),
            type=frontmatter.get("type", "task"),
            version=frontmatter.get("version", "0.1.0"),
            path=path.parent,
        )


class SkillLoader:
    """Skill 加载器"""

    def __init__(self, skills_dir: Path):
        self._skills_dir = skills_dir
        self._skills: dict[str, SkillMeta] = {}
        self._load_skills()

    def _load_skills(self) -> None:
        """加载所有 Skill"""
        if not self._skills_dir.exists():
            logger.warning("Skills dir not found: %s", self._skills_dir)
            return
        for skill_dir in self._skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            try:
                meta = SkillMeta.from_md(skill_md)
                self._skills[meta.name] = meta
                logger.info("Loaded skill: %s", meta.name)
            except Exception:
                logger.warning("Failed to load skill: %s", skill_dir)

    def list_skills(self) -> list[SkillMeta]:
        """列出所有 Skill"""
        return list(self._skills.values())

    def get_skill(self, name: str) -> SkillMeta | None:
        """获取 Skill"""
        return self._skills.get(name)

    def get_all_descriptions(self) -> str:
        """获取所有 Skill 描述"""
        if not self._skills:
            return "暂无可用 Skill"
        lines = ["可用 Skill：\n"]
        for skill in self._skills.values():
            lines.append(f"- **{skill.name}**: {skill.description}")
        return "\n".join(lines)
