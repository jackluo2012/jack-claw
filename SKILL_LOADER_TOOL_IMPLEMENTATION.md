# SkillLoaderTool 实现文档

## 问题回顾

**原问题：** `used_skills` 始终为空，技能无法被调用

**根因：** `SkillLoaderTool` 类从未被实现，导致：
- `main_crew.py` 导入失败，`SkillLoaderTool = None`
- Agent 没有这个工具，无法调用任何技能
- 18 个已配置的技能（pdf, xlsx, search_memory 等）全部不可用

## 解决方案

### 新增文件

1. **`jackclaw/tools/skill_loader_tool.py`** - `SkillLoaderTool` 实现
   - 继承 `BaseTool`，成为 CrewAI 可用工具
   - 支持 `reference` 类型：返回 SKILL.md 内容
   - 支持 `task` 类型：启动 Sub-Crew 在沙盒中执行
   - 返回结构化 JSON 结果（errcode/errmsg/data）

2. **`tests/test_skill_loader_tool.py`** - 单元测试
   - 9 个测试用例覆盖核心功能
   - 测试配置加载、路径解析、参数验证等

### 修改文件

1. **`jackclaw/agents/main_crew.py`**
   - 更新导入路径：`jackclaw.tools.skill_loader_tool`
   - 修改工具初始化逻辑，传入完整参数

2. **`jackclaw/tools/__init__.py`**
   - 添加 `SkillLoaderTool` 导出

## 技术细节

### SkillLoaderTool 类结构

```python
class SkillLoaderTool(BaseTool):
    name: str = "SkillLoaderTool"
    description: str = "加载和执行 JackClaw 的专业技能"
    args_schema: type[BaseModel] = SkillLoaderToolSchema

    def __init__(
        skills_config_path: Path,    # load_skills.yaml 路径
        session_id: str,              # 当前会话 ID
        routing_key: str = "",        # 用户路由键
        history_all: list = [],       # 对话历史
        sandbox_url: str = "",        # 沙盒 MCP URL
    )

    def _run(
        skill_name: str,              # 技能名称
        task_context: str = "",       # 任务上下文
    ) -> str:                        # 返回结果
```

### 工作流程

```
用户请求 → Agent 调用 SkillLoaderTool
                           ↓
         读取 load_skills.yaml 获取技能配置
                           ↓
         ┌─────────────────┴─────────────────┐
         ↓                                   ↓
    reference 类型                      task 类型
         ↓                                   ↓
    返回 SKILL.md 内容                  构建 Sub-Crew
    （供 Agent 参考）                        ↓
                                        在沙盒中执行
                                              ↓
                                      返回结构化结果
```

### 返回格式

**reference 类型：**
```
【{skill_name} Skill 操作规范】

# 技能标题

技能说明内容...
```

**task 类型：**
```json
{
  "errcode": 0,           // 0=成功，-1=失败
  "errmsg": "success",    // 成功时固定，失败时含错误原因
  "data": {...}          // 任务执行结果（按 task_context 定义的 schema）
}
```

## 验证结果

### 测试覆盖
- ✓ 单元测试：9/9 通过
- ✓ 集成测试：42/42 通过
- ✓ 导入测试：通过
- ✓ 功能测试：18 个技能全部可加载

### 技能列表
已加载 18 个启用技能：
- 文件处理：pdf, docx, pptx, xlsx
- 飞书操作：feishu_ops
- 定时任务：scheduler_mgr
- 搜索：baidu_search, web_browse, search_memory
- 记忆：memory-save, skill-creator, memory-governance
- 历史记录：history_reader
- 投资相关：daily-summary, investment-report, investment-review, investment-consult, hk-investment-morning-report

## 使用示例

### Agent 调用 reference 类型
```python
result = SkillLoaderTool._run(skill_name="history_reader")
# 返回 SKILL.md 内容，供 Agent 阅读操作规范
```

### Agent 调用 task 类型
```python
result = SkillLoaderTool._run(
    skill_name="pdf",
    task_context="""
    将上传的 PDF 文件转换为 Word 格式。
    输入文件：{session_dir}/uploads/document.pdf
    输出路径：{session_dir}/outputs/document.docx
    期望返回格式：{"errcode": 0, "errmsg": "success", "data": {"output_file": "..."}}
    """
)
# 返回 JSON：{"errcode": 0, "errmsg": "success", "data": {...}}
```

## 注意事项

1. **参数验证**：task 类型技能必须提供 `task_context`，否则返回错误
2. **路径解析**：支持 `path` 字段自定义路径，默认使用 `skills/{skill_name}/`
3. **事件循环**：task 类型需要 asyncio 事件循环，会自动处理
4. **错误处理**：所有错误都返回统一格式 JSON，便于 Agent 处理

## 后续优化建议

1. **性能优化**：添加技能配置变更监听，避免重复读取文件
2. **缓存机制**：对 reference 类型技能内容进行缓存
3. **异步支持**：实现 `_arun` 方法支持原生异步调用
4. **监控日志**：添加更详细的执行日志和性能指标
5. **错误恢复**：实现 Sub-Crew 执行失败的重试机制

---

**实现日期**：2025-04-23
**测试状态**：✅ 全部通过
**向后兼容**：✅ 不影响现有功能
