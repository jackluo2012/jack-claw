"""SkillLoaderTool 单元测试"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from jackclaw.tools.skill_loader_tool import SkillLoaderTool


class TestSkillLoaderTool:
    """测试 SkillLoaderTool 的基本功能"""

    def test_init(self, tmp_path):
        """测试初始化"""
        config_path = tmp_path / "load_skills.yaml"
        config_path.write_text("skills: []", encoding="utf-8")

        tool = SkillLoaderTool(
            skills_config_path=config_path,
            session_id="test-session",
            routing_key="test-user",
        )

        assert tool.name == "SkillLoaderTool"
        assert tool._session_id == "test-session"
        assert tool._routing_key == "test-user"

    def test_load_skills_config_empty(self, tmp_path):
        """测试加载空的技能配置"""
        config_path = tmp_path / "load_skills.yaml"
        config_path.write_text("skills: []\n", encoding="utf-8")

        tool = SkillLoaderTool(
            skills_config_path=config_path,
            session_id="test",
        )

        skills = tool._load_skills_config()
        assert skills == {}

    def test_load_skills_config_with_enabled_skills(self, tmp_path):
        """测试加载包含启用技能的配置"""
        config_path = tmp_path / "load_skills.yaml"
        config_path.write_text("""
skills:
  - name: pdf
    type: task
    enabled: true
  - name: disabled_skill
    type: task
    enabled: false
  - name: xlsx
    type: task
    enabled: true
""", encoding="utf-8")

        tool = SkillLoaderTool(
            skills_config_path=config_path,
            session_id="test",
        )

        skills = tool._load_skills_config()
        assert len(skills) == 2
        assert "pdf" in skills
        assert "xlsx" in skills
        assert "disabled_skill" not in skills

    def test_run_reference_skill(self, tmp_path):
        """测试执行 reference 类型技能"""
        # 创建技能配置
        config_path = tmp_path / "load_skills.yaml"
        config_path.write_text("""
skills:
  - name: test_ref
    type: reference
    enabled: true
""", encoding="utf-8")

        # 创建技能文件
        skill_dir = tmp_path / "test_ref"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
name: test_ref
description: 测试参考技能
type: reference
---

# 测试技能说明

这是测试技能的内容。
""", encoding="utf-8")

        tool = SkillLoaderTool(
            skills_config_path=config_path,
            session_id="test",
        )

        result = tool._run(skill_name="test_ref")

        assert "测试技能说明" in result
        assert "这是测试技能的内容" in result
        assert "---" not in result  # frontmatter 应该被去除

    def test_run_nonexistent_skill(self, tmp_path):
        """测试调用不存在的技能"""
        config_path = tmp_path / "load_skills.yaml"
        config_path.write_text("skills: []\n", encoding="utf-8")

        tool = SkillLoaderTool(
            skills_config_path=config_path,
            session_id="test",
        )

        result = tool._run(skill_name="nonexistent")
        data = json.loads(result)

        assert data["errcode"] == -1
        assert "不存在" in data["errmsg"]

    def test_run_task_skill_without_context(self, tmp_path):
        """测试 task 类型技能缺少 task_context 参数"""
        config_path = tmp_path / "load_skills.yaml"
        config_path.write_text("""
skills:
  - name: test_task
    type: task
    enabled: true
""", encoding="utf-8")

        skill_dir = tmp_path / "test_task"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: test_task\n---\n# Test\n", encoding="utf-8")

        tool = SkillLoaderTool(
            skills_config_path=config_path,
            session_id="test",
        )

        result = tool._run(skill_name="test_task", task_context="")
        data = json.loads(result)

        assert data["errcode"] == -1
        assert "task_context" in data["errmsg"]

    def test_resolve_skill_path_with_path_field(self, tmp_path):
        """测试解析带 path 字段的技能配置"""
        config_path = tmp_path / "load_skills.yaml"
        config_path.write_text("""
skills:
  - name: custom_skill
    path: ./custom/path
    type: task
    enabled: true
""", encoding="utf-8")

        tool = SkillLoaderTool(
            skills_config_path=config_path,
            session_id="test",
        )

        skill_config = tool._load_skills_config()["custom_skill"]
        resolved_path = tool._resolve_skill_path(skill_config)

        # 应该解析为相对于配置文件目录的路径
        assert resolved_path == tmp_path / "custom" / "path"

    def test_resolve_skill_path_without_path_field(self, tmp_path):
        """测试解析不带 path 字段的技能配置（使用默认名称）"""
        config_path = tmp_path / "load_skills.yaml"
        config_path.write_text("""
skills:
  - name: pdf
    type: task
    enabled: true
""", encoding="utf-8")

        tool = SkillLoaderTool(
            skills_config_path=config_path,
            session_id="test",
        )

        skill_config = tool._load_skills_config()["pdf"]
        resolved_path = tool._resolve_skill_path(skill_config)

        # 应该使用技能名称作为子目录
        assert resolved_path == tmp_path / "pdf"


class TestSkillLoaderToolIntegration:
    """集成测试（需要完整的 skill 目录结构）"""

    def test_list_available_skills(self, tmp_path, sample_skills_dir):
        """测试列出可用的技能"""
        config_path = tmp_path / "load_skills.yaml"
        config_path.write_text(f"""
skills:
  - name: pdf
    type: task
    enabled: true
  - name: xlsx
    type: task
    enabled: true
""", encoding="utf-8")

        tool = SkillLoaderTool(
            skills_config_path=config_path,
            session_id="test",
        )

        skills = tool._load_skills_config()
        skill_names = list(skills.keys())

        assert "pdf" in skill_names
        assert "xlsx" in skill_names


@pytest.fixture
def sample_skills_dir(tmp_path):
    """创建示例技能目录结构"""
    pdf_dir = tmp_path / "pdf"
    pdf_dir.mkdir()
    (pdf_dir / "SKILL.md").write_text("""---
name: pdf
description: PDF 处理
type: task
---""")
    return tmp_path
