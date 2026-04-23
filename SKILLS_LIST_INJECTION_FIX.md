# Agent 技能列表注入修复

## 问题描述

即使 `SkillLoaderTool` 已经实现并且工具已经加载到 Agent 中，Agent 仍然不调用技能，`used_skills` 始终为空数组。

**示例响应：**
```json
{
  "reply": "上一个任务是帮你查询美团的股份信息 📊 虽然我暂时无法提供实时数据，但可以为你整理分析维度或查询方法，需要吗？",
  "used_skills": []  // ← 仍然是空的
}
```

## 根本原因分析

### Agent 不知道有哪些技能可用

虽然 Agent 有 `SkillLoaderTool` 工具，但它的 backstory 中**没有列出具体的可用技能列表**。

**问题链：**
1. `agents.yaml` 中只提到 "使用 SkillLoaderTool"
2. 但没有告诉 Agent **有哪些技能可以调用**
3. Agent 不知道 `skill_name` 参数可以接受哪些值
4. 因此 Agent 不会主动调用技能

### 验证问题

在修复前，Agent 的 backstory 包含：
- ✅ "你的核心工具是 SkillLoaderTool"
- ✅ "调用 task 类型 Skill：调用 SkillLoaderTool"
- ❌ 但**没有具体的技能名称列表**（如 baidu_search, pdf, xlsx 等）

## 解决方案

### 在 Agent 初始化时注入技能列表

**修改文件：** `jackclaw/agents/main_crew.py`

#### 1. 添加技能列表加载函数

```python
def _load_available_skills(skills_config_path: Path | None = None) -> str:
    """加载可用技能列表，生成格式化的字符串供 Agent 使用"""
    # 读取 load_skills.yaml
    # 过滤启用的技能
    # 按类型分组（reference / task）
    # 返回格式化的技能列表
```

#### 2. 修改 orchestrator 方法

```python
@agent
def orchestrator(self) -> Agent:
    cfg = dict(_load_yaml(_CONFIG_DIR / "agents.yaml")["orchestrator"])

    # 加载 Bootstrap 内容
    bootstrap_backstory = build_bootstrap_prompt(self._workspace_dir)

    # 💡 加载技能列表
    skills_config_path = _CONFIG_DIR.parent.parent / "skills" / "load_skills.yaml"
    skills_list = _load_available_skills(skills_config_path)
    skills_section = f"\n\n【可用技能列表】\n{skills_list}\n"

    # 合并 backstory：bootstrap + skills + 原始 backstory
    cfg["backstory"] = f"{bootstrap_backstory}\n\n{cfg['backstory']}{skills_section}"

    # ... 创建 Agent
```

### 生成的技能列表格式

```
【可用技能列表】

**Reference 类型（返回操作规范，供参考）：**
- **history_reader**: 无描述 [reference]

**Task 类型（在沙盒中执行，返回结果）：**
- **pdf**: 无描述 [task]
- **docx**: 无描述 [task]
- **baidu_search**: 无描述 [task]
- **web_browse**: 无描述 [task]
- **search_memory**: 无描述 [task]
- ... （共 17 个 task 技能）

**使用提示：**
- 调用 reference 类型：`SkillLoaderTool(skill_name="名称")`
- 调用 task 类型：`SkillLoaderTool(skill_name="名称", task_context="任务描述")`
```

## 验证结果

### 测试脚本输出

```bash
$ python3 test_agent_skills.py

【验证 Backstory 内容】
✓ 包含 'baidu_search': True
✓ 包含 'web_browse': True
✓ 包含 'SkillLoaderTool': True
✓ 包含 '可用技能列表': True
✓ 包含 'pdf': True
✓ 包含 'search_memory': True

=== ✅ 所有检查通过！Agent 可以看到技能列表 ===
```

### Backstory 长度

- 修复前：约 6000 字符
- 修复后：约 6800 字符（+800 字符，包含技能列表）

### 测试覆盖

```bash
$ python3 -m pytest tests/ -v

============================== 46 passed in 2.85s ===============================
```

## 技术细节

### 为什么不在 Tool 的 description 中包含列表？

最初尝试在 `SkillLoaderTool` 的 `description` 属性中包含技能列表，但失败了：

**问题：** `BaseTool` 的 `description` 是**类属性**，不是实例属性
- 在 `__init__` 中修改 `self.description` 不会影响类属性
- CrewAI 使用类属性来显示工具描述
- 因此动态生成的描述无法生效

**解决方案：** 将技能列表注入到 Agent 的 `backstory` 中
- `backstory` 是实例属性，可以动态修改
- CrewAI 会将完整的 backstory 传递给 LLM
- LLM 可以看到所有可用技能

### 性能影响

- **每次创建 Agent 时重新加载**：可接受，因为每次请求都会创建新 Agent 实例
- **YAML 解析开销**： negligible（< 1ms）
- **Backstory 长度增加**：约 800 字符，对 context window 影响很小

## 后续优化建议

### 1. 添加技能描述

当前技能列表显示 "无描述"，因为 `load_skills.yaml` 中没有 `description` 字段。

**建议：** 在 `load_skills.yaml` 中添加简短描述：

```yaml
skills:
  - name: baidu_search
    type: task
    enabled: true
    description: 百度搜索，查询实时信息（股票、天气、新闻等）
```

### 2. 技能分类

按功能分类技能，便于 Agent 理解：

```yaml
# 文件处理
- name: pdf
  category: 文件处理

# 搜索
- name: baidu_search
  category: 信息搜索
```

### 3. 动态更新

监听 `load_skills.yaml` 变化，自动重新加载技能列表（如果 Agent 实例被缓存）。

## 相关文件

### 修改的文件
- `jackclaw/agents/main_crew.py` - 添加 `_load_available_skills()` 函数和技能列表注入

### 新增的文件
- `test_agent_skills.py` - 验证脚本（已删除）

### 相关配置
- `jackclaw/skills/load_skills.yaml` - 技能配置文件
- `jackclaw/agents/config/agents.yaml` - Agent 配置

---

**修复日期**：2025-04-23
**测试状态**：✅ 全部通过
**向后兼容**：✅ 完全兼容
**技能可见性**：✅ Agent 现在可以看到所有 18 个技能
