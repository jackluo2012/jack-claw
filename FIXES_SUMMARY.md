# JackClaw 问题修复总结

## 修复的问题

### 1. ✅ 技能无法调用 (`used_skills` 为空)

**问题描述：**
- 用户配置了 18 个技能，但 `used_skills` 始终为空数组
- Agent 无法调用任何技能（pdf, xlsx, search_memory 等）

**根本原因：**
- `SkillLoaderTool` 类从未被实现
- `main_crew.py` 导入失败，`SkillLoaderTool = None`
- Agent 的工具列表中没有这个工具

**解决方案：**
- 实现 `SkillLoaderTool` 类（继承 `BaseTool`）
- 支持 reference 和 task 两种技能类型
- 更新 `main_crew.py` 导入路径和初始化逻辑

**相关文件：**
- 新增：`jackclaw/tools/skill_loader_tool.py`
- 新增：`tests/test_skill_loader_tool.py`
- 修改：`jackclaw/agents/main_crew.py`
- 修改：`jackclaw/tools/__init__.py`

**验证结果：**
- 18 个技能全部可加载
- 9 个单元测试通过
- 42 个集成测试通过

---

### 2. ✅ 异步上下文 LLM 调用冲突

**问题描述：**
```
RuntimeError: asyncio.run() cannot be called from a running event loop
RuntimeWarning: coroutine 'AliyunLLM.acall' was never awaited
```

**根本原因：**
- `@before_llm_call` hook 在异步上下文中执行
- `_summarize_chunk` 调用 `summary_llm.call()`
- `call()` 使用 `asyncio.run()` 创建新事件循环，与现有循环冲突

**解决方案：**
- 修改 `AliyunLLM.call()` 方法，智能检测运行环境
- 有事件循环时，在新线程中创建独立的事件循环
- 保持同步 API 接口不变，向后兼容

**相关文件：**
- 修改：`jackclaw/llm/aliyun_llm.py`
- 新增：`tests/test_async_llm_call.py`

**验证结果：**
- 4 个异步测试通过
- 46 个总测试通过
- 上下文压缩功能正常工作

---

## 技术亮点

### SkillLoaderTool 设计

```python
class SkillLoaderTool(BaseTool):
    """JackClaw 的核心能力入口"""

    def _run(skill_name: str, task_context: str) -> str:
        if skill_type == "reference":
            # 返回 SKILL.md 内容，供 Agent 参考
            return load_skill_content(skill_name)
        elif skill_type == "task":
            # 启动 Sub-Crew 在沙盒中执行
            return execute_skill_crew(skill_name, task_context)
```

**特点：**
- 统一的技能调用接口
- 结构化返回格式（errcode/errmsg/data）
- 支持参数验证和错误处理

### 异步兼容 LLM 调用

```python
def call(self, ...) -> str | Any:
    try:
        asyncio.get_running_loop()  # 检测异步上下文

        # 在新线程中运行，避免事件循环冲突
        thread = threading.Thread(target=run_in_new_loop, daemon=True)
        thread.start()
        thread.join(timeout=30)
        return result

    except RuntimeError:
        # 同步上下文，直接使用 asyncio.run()
        return asyncio.run(self.acall(...))
```

**特点：**
- 智能检测运行环境
- 线程隔离，避免事件循环冲突
- 超时保护（30秒）
- 向后兼容

---

## 测试覆盖

### 新增测试

| 测试文件 | 测试用例数 | 覆盖内容 |
|---------|----------|---------|
| `test_skill_loader_tool.py` | 9 | SkillLoaderTool 功能 |
| `test_async_llm_call.py` | 4 | 异步上下文 LLM 调用 |

### 测试结果

```bash
$ python3 -m pytest tests/ -v

============================== 46 passed in 2.63s ===============================
```

---

## 文档

新增详细文档：
- `SKILL_LOADER_TOOL_IMPLEMENTATION.md` - SkillLoaderTool 实现文档
- `ASYNC_LLM_CALL_FIX.md` - 异步 LLM 调用修复文档

---

## 使用示例

### Agent 调用技能

```python
# reference 类型 - 获取操作规范
result = SkillLoaderTool._run(skill_name="history_reader")

# task 类型 - 执行具体任务
result = SkillLoaderTool._run(
    skill_name="pdf",
    task_context="将上传的 PDF 转换为 Word 格式"
)
# 返回：{"errcode": 0, "errmsg": "success", "data": {...}}
```

### 异步上下文中调用 LLM

```python
# @before_llm_call hook 中
def before_llm_hook(context):
    # 现在可以安全地调用 LLM，即使在异步上下文中
    maybe_compress(context.messages, context)
```

---

## 性能影响

- **SkillLoaderTool**: 可忽略，仅在需要时加载
- **异步 LLM 调用**: 轻微，仅压缩场景使用（低频）
- **测试执行时间**: 2.63 秒（46 个测试）

---

## 向后兼容性

✅ 所有修改都保持向后兼容：
- 现有 API 接口不变
- 同步调用仍然使用 `asyncio.run()`
- 仅在检测到异步上下文时使用新逻辑

---

## 后续建议

### 短期优化
1. 监控跨线程 LLM 调用的性能
2. 收集实际使用中的错误日志
3. 优化技能加载的缓存策略

### 长期优化
1. 考虑将 `maybe_compress` 改为异步函数
2. 实现技能的预热加载
3. 添加更详细的性能指标和日志

---

**修复完成时间**：2025-04-23
**测试状态**：✅ 全部通过
**向后兼容**：✅ 完全兼容
**生产就绪**：✅ 可以部署
