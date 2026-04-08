"""
SkillLoader 模块测试
"""

import pytest
from pathlib import Path

from jackclaw.tools.skill_loader import SkillMeta, SkillLoader


class TestSkillMeta:
    def test_from_md_valid(self, tmp_path):
        skill_dir = tmp_path / "pdf"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("""---
name: pdf
description: PDF 文件处理
type: task
version: 1.0.0
---

# PDF Skill
""")
        meta = SkillMeta.from_md(skill_md)
        assert meta.name == "pdf"
        assert meta.description == "PDF 文件处理"
        assert meta.type == "task"
        assert meta.version == "1.0.0"
        assert meta.path == skill_dir

    def test_from_md_missing_frontmatter(self, tmp_path):
        skill_dir = tmp_path / "test"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("# Test Skill\nContent")
        with pytest.raises(ValueError):
            SkillMeta.from_md(skill_md)

    def test_from_md_invalid_frontmatter(self, tmp_path):
        skill_dir = tmp_path / "test"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("---invalid---")
        # 实际行为：yaml.safe_load 返回字符串，触发 AttributeError
        with pytest.raises(AttributeError):
            SkillMeta.from_md(skill_md)


class TestSkillLoader:
    def test_init_empty_dir(self, tmp_path):
        loader = SkillLoader(tmp_path)
        assert loader.list_skills() == []
        assert loader.get_skill("none") is None

    def test_load_skills(self, tmp_path):
        # 创建测试 skill 目录
        pdf_dir = tmp_path / "pdf"
        pdf_dir.mkdir()
        (pdf_dir / "SKILL.md").write_text("""---
name: pdf
description: PDF 处理
type: task
version: 1.0.0
---
""")
        xlsx_dir = tmp_path / "xlsx"
        xlsx_dir.mkdir()
        (xlsx_dir / "SKILL.md").write_text("""---
name: xlsx
description: Excel 处理
type: task
version: 1.0.0
---
""")
        # 创建一个没有 SKILL.md 的目录
        (tmp_path / "empty").mkdir()

        loader = SkillLoader(tmp_path)
        skills = loader.list_skills()
        assert len(skills) == 2
        assert loader.get_skill("pdf").description == "PDF 处理"
        assert loader.get_skill("xlsx").description == "Excel 处理"

    def test_get_all_descriptions_empty(self, tmp_path):
        loader = SkillLoader(tmp_path)
        desc = loader.get_all_descriptions()
        assert desc == "暂无可用 Skill"

    def test_get_all_descriptions(self, tmp_path):
        pdf_dir = tmp_path / "pdf"
        pdf_dir.mkdir()
        (pdf_dir / "SKILL.md").write_text("""---
name: pdf
description: PDF 处理
type: task
version: 1.0.0
---
""")
        loader = SkillLoader(tmp_path)
        desc = loader.get_all_descriptions()
        assert "pdf" in desc
        assert "PDF 处理" in desc