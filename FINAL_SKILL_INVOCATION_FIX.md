# 最终修复：让 Agent 主动调用技能

## 问题

即使 `SkillLoaderTool` 已实现，Agent 仍然不调用技能：
```json
{
  "reply": "抱歉，我暂时无法直接查询实时股价 😅 建议您打开股票软件...",
  "used_skills": []
}
```

## 根本原因

虽然 Agent 有 `SkillLoaderTool` 工具和技能列表，但：
1. **工具描述不够明确**：Agent 不知道何时应该调用工具
2. **缺少调用示例**：Agent 不知道如何正确调用
3. **没有强制要求**：Agent 可以选择"不调用"并直接回复

## 最终修复

### 修改 1：强化工具描述

**文件：** `jackclaw/tools/skill_loader_tool.py`

**修改前：**
```python
description: str = (
    "加载和执行 JackClaw 的专业技能。"
    "支持两种类型：reference 和 task"
)
```

**修改后：**
```python
description: str = (
    "加载和执行 JackClaw 的专业技能。这是你完成大多数任务的主要工具。"
    ""
    "【何时使用】"
    "- 用户查询实时信息（股票、天气、新闻）→ skill_name='baidu_search'"
    "- 用户需要处理文件（PDF、Excel、PPT）→ skill_name='pdf'/'xlsx'/'pptx'"
    "- 用户需要访问网页内容 → skill_name='web_browse'"
    "- 用户询问历史对话 → skill_name='search_memory' 或 'history_reader'"
    ""
    "【重要】"
    "不要直接说'我无法做'或'建议您...'，必须先尝试调用相关技能！"
    "调用后必须在 used_skills 字段中记录使用的技能名称。"
)
```

### 修改 2：添加调用示例到参数

**文件：** `jackclaw/tools/skill_loader_tool.py`

```python
skill_name: str = Field(
    ...,
    description=(
        "要调用的 Skill 名称..."
        "【常见技能】baidu_search(搜索)、web_browse(网页)、"
        "pdf/xlsx/docx/pptx(文件处理)、search_memory(搜索历史)"
    ),
)
task_context: str = Field(
    default="",
    description=(
        "任务上下文描述..."
        "示例: task_context='查询美团股票价格' 或 '将上传的PDF转换为Word'"
    ),
)
```

### 修改 3：强化 Agent 背景故事

**文件：** `jackclaw/agents/config/agents.yaml`

**添加明确的指示和示例：**
```yaml
backstory: |
  你是 JackClaw（小爪子）...

  💡【重要】你必须主动使用 SkillLoaderTool 调用技能，
  而不是直接说"我无法做"或"建议您..."。
  在回复"我无法..."之前，先检查是否有相关技能可以帮助完成任务。

  工作流程：
  1. 仔细理解用户需求，判断是否需要调用 Skill
  2. 查看可用技能列表，找到相关技能
  3. 调用 SkillLoaderTool 执行技能
  4. 根据技能返回结果，给用户回复
  5. 在最终回复的 used_skills 字段中记录使用的技能名称

  行为边界：
  - 禁止直接说"我暂时无法..."，必须先尝试调用相关技能

  常见场景示例：
  1. 用户查询实时信息（股票、天气、新闻）→ 调用 baidu_search Skill
  2. 用户需要处理文件（PDF、Excel、PPT） → 调用对应技能
  3. 用户需要访问网页 → 调用 web_browse Skill
  4. 用户问历史对话 → 调用 search_memory 或 history_reader Skill

  调用示例：
  SkillLoaderTool(skill_name="baidu_search", task_context="查询美团(03690.HK)的最新股价")
  返回结果后，在 used_skills 中记录 ["baidu_search"]
```

## 修改效果

### 工具描述对比

**修改前：**
```
"加载和执行 JackClaw 的专业技能。支持两种类型..."
```

**修改后：**
```
"加载和执行 JackClaw 的专业技能。这是你完成大多数任务的主要工具。

【何时使用】
- 用户查询实时信息（股票、天气、新闻）→ skill_name='baidu_search'
- 用户需要处理文件（PDF、Excel、PPT）→ skill_name='pdf'/'xlsx'/'pptx'
...

【重要】
不要直接说'我无法做'或'建议您...'，必须先尝试调用相关技能！
调用后必须在 used_skills 字段中记录使用的技能名称。"
```

### Agent 指示对比

**修改前：**
```
工作流程：
1. 仔细理解用户需求，判断是否需要调用 Skill
2. 若有 reference 类型的 Skill 与任务相关，先加载获取操作规范
...
```

**修改后：**
```
💡【重要】你必须主动使用 SkillLoaderTool 调用技能，
而不是直接说"我无法做"或"建议您..."。

行为边界：
- 禁止直接说"我暂时无法..."，必须先尝试调用相关技能

常见场景示例：
1. 用户查询实时信息 → 调用 baidu_search Skill
2. 用户需要处理文件 → 调用对应技能
...
```

## 验证

### 工具描述检查
```bash
✓ 包含 'baidu_search': True
✓ 包含 '何时使用': True
✓ 包含 '不要直接说': True
✓ 包含 'used_skills': True
```

### Backstory 检查
```bash
✓ 包含 '必须主动使用': True
✓ 包含 'baidu_search': True
✓ 包含 '调用示例': True
✓ 包含 '禁止直接说': True
```

### 测试结果
```bash
✅ 46 个测试全部通过
✅ 工具描述已更新
✅ Backstory 已更新
✅ 参数说明已增强
```

## 预期效果

修复后，当用户问 "帮我查一下美团股票" 时：

**修改前：**
```json
{
  "reply": "抱歉，我暂时无法直接查询实时股价 😅 建议您打开股票软件...",
  "used_skills": []
}
```

**修改后（预期）：**
```json
{
  "reply": "我帮你查询了美团股票信息...\n\n[查询结果]",
  "used_skills": ["baidu_search"]
}
```

Agent 应该会：
1. 看到工具描述中的"何时使用"部分
2. 识别"用户查询实时信息"匹配 `skill_name='baidu_search'`
3. 看到"禁止直接说'我暂时无法...'"的指示
4. 主动调用 `SkillLoaderTool(skill_name="baidu_search", task_context="查询美团股票价格")`
5. 在 `used_skills` 中记录 `["baidu_search"]`

## 关键改进点

| 改进点 | 修改前 | 修改后 |
|-------|--------|--------|
| 工具描述 | 简单说明功能 | 详细说明何时使用 + 强制要求 |
| 参数说明 | 基本描述 | 包含常见技能列表 + 使用示例 |
| Agent 指示 | 建议性措辞 | 强制性要求 + 明确示例 |
| 行为边界 | 没有限制 | 明确禁止"我无法"式回复 |

## 部署

无需额外配置，重启服务即可生效：

```bash
# 重启 JackClaw
python3 -m jackclaw.main
```

---

**修复日期**：2025-04-23
**测试状态**：✅ 46/46 通过
**向后兼容**：✅ 完全兼容
**预期效果**：Agent 应该主动调用技能，used_skills 不再为空
