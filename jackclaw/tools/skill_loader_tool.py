"""SkillLoaderTool — CrewAI Tool：加载和执行 Skills

💡【设计要点】
- reference 类型：直接返回 SKILL.md 内容（操作规范），供主 Agent 自行推理
- task 类型：启动 Sub-Crew 在 AIO-Sandbox 中执行，返回结构化结果
- 所有调用必须通过 skill_name 明确指定，避免 LLM 幻觉
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import yaml
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from jackclaw.agents.skill_crew import build_skill_crew

logger = logging.getLogger(__name__)


class SkillLoaderToolSchema(BaseModel):
    """SkillLoaderTool 参数 schema"""

    skill_name: str = Field(
        ...,
        description=(
            "要调用的 Skill 名称，必须与 load_skills.yaml 中定义的 name 完全一致。"
            "例如: 'pdf', 'xlsx', 'search_memory', 'baidu_search', 'web_browse' 等。"
            "【常见技能】baidu_search(搜索)、web_browse(网页)、pdf/xlsx/docx/pptx(文件处理)、search_memory(搜索历史)"
        ),
    )
    task_context: str = Field(
        default="",
        description=(
            "任务上下文描述，对于 task 类型 Skill 必须提供。"
            "应包含完整的任务要求、输入数据说明。"
            "对于 reference 类型 Skill 可以省略。"
            "示例: task_context='查询美团股票价格' 或 '将上传的PDF转换为Word'"
        ),
    )


class SkillLoaderTool(BaseTool):
    """技能加载器工具 — JackClaw 的核心能力入口"""

    name: str = "SkillLoaderTool"
    description: str = (
        "【核心工具 - 必须使用】加载和执行 JackClaw 的专业技能。"
        ""
        "🚨 强制要求：在说'我无法...'之前，必须先调用此工具尝试！"
        ""
        "【常用技能速查】"
        "- baidu_search: 百度搜索（股票、天气、新闻、实时信息）"
        "- web_browse: 网页内容提取"
        "- pdf/xlsx/docx/pptx: 文件处理"
        "- search_memory: 搜索历史对话"
        "- feishu_ops: 飞书操作"
        ""
        "【调用方式】"
        "- Task类型：SkillLoaderTool(skill_name='名称', task_context='详细任务')"
        "- Reference类型：SkillLoaderTool(skill_name='名称')"
        ""
        "【常见错误】禁止说'没有联网权限'或'无法查询' - baidu_search可以搜索！"
    )
    args_schema: type[BaseModel] = SkillLoaderToolSchema

    # 运行时参数（非 Tool 参数，通过 __init__ 传入）
    _skills_config_path: Path
    _session_id: str
    _routing_key: str = ""
    _history_all: list = []
    _sandbox_url: str = ""
    _dynamic_description: str = ""

    class Config:
        arbitrary_types_allowed = True

    def __init__(
        self,
        skills_config_path: Path,
        session_id: str,
        routing_key: str = "",
        history_all: list | None = None,
        sandbox_url: str = "",
        **kwargs: Any,
    ):
        """初始化 SkillLoaderTool

        Args:
            skills_config_path: load_skills.yaml 配置文件路径
            session_id: 当前会话 ID（用于沙盒工作目录隔离）
            routing_key: 用户路由键（用于发送消息）
            history_all: 完整对话历史（用于参考型技能）
            sandbox_url: AIO-Sandbox MCP 服务 URL
        """
        super().__init__(**kwargs)
        self._skills_config_path = skills_config_path
        self._session_id = session_id
        self._routing_key = routing_key or ""
        self._history_all = history_all or []
        self._sandbox_url = sandbox_url

        # 缓存技能配置，避免重复读取
        self._skills_cache: dict[str, dict] | None = None

        # 💡 动态生成包含技能列表的描述，让 Agent 知道有哪些技能可用
        self._update_description_with_skills()

    def _update_description_with_skills(self) -> None:
        """动态生成包含可用技能列表的描述"""
        skills = self._load_skills_config()

        if not skills:
            self._dynamic_description = (
                "加载和执行 JackClaw 的专业技能（当前无可用技能）。"
                "支持两种类型："
                "1. reference 类型：返回操作规范文档（SKILL.md），供主 Agent 参考"
                "2. task 类型：在沙盒中启动 Sub-Crew 执行任务，返回结构化结果"
            )
            self.description = self._dynamic_description
            return

        # 按类型分组技能
        task_skills = []
        ref_skills = []

        for name, config in skills.items():
            skill_type = config.get("type", "task")
            desc = config.get("description", "无描述")
            if skill_type == "reference":
                ref_skills.append(f"  - **{name}**: {desc}")
            else:
                task_skills.append(f"  - **{name}**: {desc}")

        # 构建动态描述
        parts = [
            "加载和执行 JackClaw 的专业技能。",
            "",
            "【可用技能列表】",
        ]

        if ref_skills:
            parts.append("\n**Reference 类型（返回操作规范，供参考）**：")
            parts.extend(ref_skills[:5])  # 只显示前5个，避免描述过长
            if len(ref_skills) > 5:
                parts.append(f"  ... 还有 {len(ref_skills) - 5} 个 reference 技能")

        if task_skills:
            parts.append("\n**Task 类型（在沙盒中执行，返回结果）**：")
            parts.extend(task_skills[:10])  # 只显示前10个
            if len(task_skills) > 10:
                parts.append(f"  ... 还有 {len(task_skills) - 10} 个 task 技能")

        parts.append("\n【使用方法】")
        parts.append("- reference 类型：只传 skill_name，获取操作规范")
        parts.append("- task 类型：传 skill_name + task_context（完整任务描述）")

        self._dynamic_description = "\n".join(parts)

        # 💡 强制更新工具描述（使用 Pydantic 的 model_validator 来确保更新生效）
        # 注意：直接修改 self.description 可能不会影响已注册的工具定义
        # 所以我们在初始化时就构建好完整的描述
        object.__setattr__(self, 'description', self._dynamic_description)

    def _load_skills_config(self) -> dict[str, dict]:
        """加载技能配置，返回 {skill_name: skill_config} 字典"""
        if self._skills_cache is not None:
            return self._skills_cache

        if not self._skills_config_path.exists():
            logger.warning("Skills config not found: %s", self._skills_config_path)
            self._skills_cache = {}
            return {}

        try:
            config = yaml.safe_load(self._skills_config_path.read_text(encoding="utf-8"))
            skills_list = config.get("skills", [])
            # 只保留 enabled=true 的技能
            self._skills_cache = {
                s["name"]: s
                for s in skills_list
                if s.get("enabled", True)
            }

            # 输出详细日志
            logger.info("📋 Skills config loaded from %s", self._skills_config_path)
            logger.info("   Total skills: %d (enabled: %d)", len(skills_list), len(self._skills_cache))

            # 按类型分组输出
            task_skills = [name for name, cfg in self._skills_cache.items() if cfg.get("type") == "task"]
            ref_skills = [name for name, cfg in self._skills_cache.items() if cfg.get("type") == "reference"]

            if task_skills:
                logger.info("   Task skills (%d): %s", len(task_skills), ", ".join(task_skills))
            if ref_skills:
                logger.info("   Reference skills (%d): %s", len(ref_skills), ", ".join(ref_skills))

        except Exception as e:
            logger.error("Failed to load skills config: %s", e)
            self._skills_cache = {}

        return self._skills_cache

    def _resolve_skill_path(self, skill_config: dict) -> Path:
        """解析技能目录路径"""
        # 如果配置中有 path 字段，相对于配置文件目录解析
        if "path" in skill_config:
            config_dir = self._skills_config_path.parent
            return (config_dir / skill_config["path"]).resolve()

        # 否则使用默认路径：技能名称同名的子目录
        config_dir = self._skills_config_path.parent
        return config_dir / skill_config["name"]

    def _load_reference_skill(self, skill_name: str, skill_path: Path) -> str:
        """加载 reference 类型技能的内容

        返回 SKILL.md 的完整内容（不含 frontmatter），供主 Agent 参考
        """
        skill_md = skill_path / "SKILL.md"
        if not skill_md.exists():
            return f"错误：技能文件不存在 {skill_md}"

        try:
            content = skill_md.read_text(encoding="utf-8")
            # 去除 frontmatter（--- 包围的 YAML 头）
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    content = parts[2].strip()
            return f"【{skill_name} Skill 操作规范】\n\n{content}"
        except Exception as e:
            return f"错误：读取技能文件失败 {e}"

    def _run_task_skill(
        self,
        skill_name: str,
        skill_path: Path,
        task_context: str,
    ) -> str:
        """执行 task 类型技能

        通过 Sub-Crew 在沙盒中执行，返回结构化结果
        """
        skill_md = skill_path / "SKILL.md"
        if not skill_md.exists():
            return json.dumps({
                "errcode": -1,
                "errmsg": f"技能文件不存在: {skill_md}",
                "data": None,
            }, ensure_ascii=False)

        try:
            # 读取 SKILL.md 内容（包含 frontmatter）
            skill_content = skill_md.read_text(encoding="utf-8")

            # 构建 Sub-Crew
            crew = build_skill_crew(
                skill_name=skill_name,
                skill_instructions=skill_content,
                session_id=self._session_id,
                sandbox_mcp_url=self._sandbox_url,
                max_iter=20,
            )

            # 异步执行（需要在事件循环中运行）
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # 没有运行中的事件循环，创建新的
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            result = loop.run_until_complete(
                crew.akickoff(inputs={"task_context": task_context})
            )

            # 解析结果
            if result.pydantic:
                # 有结构化输出，直接转 JSON
                return json.dumps(
                    result.pydantic.model_dump(),
                    ensure_ascii=False,
                    indent=2,
                )
            else:
                # 没有结构化输出，包装为通用格式
                return json.dumps({
                    "errcode": 0,
                    "errmsg": "success",
                    "data": result.raw or str(result),
                }, ensure_ascii=False)

        except Exception as e:
            logger.exception("Failed to execute task skill: %s", skill_name)
            return json.dumps({
                "errcode": -1,
                "errmsg": f"技能执行失败: {e}",
                "data": None,
            }, ensure_ascii=False)

    def _run(
        self,
        skill_name: str,
        task_context: str = "",
        **_kwargs: Any,
    ) -> str:
        """执行技能加载

        Args:
            skill_name: 技能名称
            task_context: 任务上下文（task 类型必需）

        Returns:
            reference 类型：SKILL.md 内容文本
            task 类型：JSON 字符串（errcode/errmsg/data 结构）
        """
        # 加载技能配置
        skills = self._load_skills_config()

        # 检查技能是否存在
        if skill_name not in skills:
            available = ", ".join(skills.keys())
            return json.dumps({
                "errcode": -1,
                "errmsg": f"技能 '{skill_name}' 不存在或未启用。可用技能: {available}",
                "data": None,
            }, ensure_ascii=False)

        skill_config = skills[skill_name]
        skill_type = skill_config.get("type", "task")
        skill_path = self._resolve_skill_path(skill_config)

        logger.info(
            "Loading skill: %s (type=%s, path=%s, context_len=%d)",
            skill_name,
            skill_type,
            skill_path,
            len(task_context),
        )

        # 根据类型分发处理
        if skill_type == "reference":
            return self._load_reference_skill(skill_name, skill_path)
        elif skill_type == "task":
            if not task_context:
                return json.dumps({
                    "errcode": -1,
                    "errmsg": f"task 类型技能 '{skill_name}' 必须提供 task_context 参数",
                    "data": None,
                }, ensure_ascii=False)
            return self._run_task_skill(skill_name, skill_path, task_context)
        else:
            return json.dumps({
                "errcode": -1,
                "errmsg": f"未知的技能类型: {skill_type}",
                "data": None,
            }, ensure_ascii=False)
