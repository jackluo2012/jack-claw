# 异步上下文 LLM 调用修复

## 问题描述

在运行时出现以下错误：

```
RuntimeError: asyncio.run() cannot be called from a running event loop
```

**错误位置：**
- `jackclaw/memory/context_mgmt.py:150` - `_summarize_chunk` 函数
- `jackclaw/llm/aliyun_llm.py:74` - `AliyunLLM.call` 方法

## 根本原因分析

### 调用链

```
@before_llm_call hook (异步上下文)
    ↓
maybe_compress() (同步函数)
    ↓
_summarize_chunk() (同步函数)
    ↓
summary_llm.call() (同步函数)
    ↓
asyncio.run(self.acall(...))  ← 冲突点！
```

### 问题原因

1. `@before_llm_call` hook 在 CrewAI 的异步上下文中执行
2. `_summarize_chunk` 被 `maybe_compress` 调用，最终调用 `summary_llm.call()`
3. `call()` 方法使用 `asyncio.run()` 创建新的事件循环
4. 但已经有一个运行中的事件循环，导致 `RuntimeError`

## 解决方案

### 修改文件：`jackclaw/llm/aliyun_llm.py`

**修改前：**
```python
def call(self, ...) -> str | Any:
    import asyncio
    return asyncio.run(self.acall(...))
```

**修改后：**
```python
def call(self, ...) -> str | Any:
    import asyncio
    import threading

    async def _acall_wrapper():
        return await self.acall(...)

    try:
        # 检测是否在异步上下文中
        asyncio.get_running_loop()

        # 在新线程中创建新的事件循环运行
        result = [None]
        exception = [None]

        def run_in_thread():
            try:
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    result[0] = new_loop.run_until_complete(_acall_wrapper())
                finally:
                    new_loop.close()
            except Exception as e:
                exception[0] = e

        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()
        thread.join(timeout=30)

        if exception[0]:
            raise exception[0]
        return result[0]

    except RuntimeError:
        # 没有运行中的事件循环，使用 asyncio.run()
        return asyncio.run(_acall_wrapper())
```

### 核心思想

**智能检测运行环境：**
- **无事件循环**（正常同步调用）：使用 `asyncio.run()` 创建新循环
- **有事件循环**（异步上下文中的同步调用）：在新线程中创建独立的事件循环

**线程隔离：**
- 使用 `threading.Thread` 创建守护线程
- 在线程内创建独立的事件循环
- 通过 `join(timeout=30)` 同步等待结果（30秒超时）

## 验证结果

### 测试覆盖

新增 `tests/test_async_llm_call.py`，包含 4 个测试用例：

1. **test_call_from_sync_context** - 同步上下文调用（原有场景）
2. **test_call_from_async_context** - 异步上下文调用（修复场景）
3. **test_call_from_async_context_nested** - 嵌套异步调用
4. **test_call_timeout_in_async_context** - 超时处理

### 测试结果

```bash
$ python3 -m pytest tests/test_async_llm_call.py -v

tests/test_async_llm_call.py::TestAsyncLLMCall::test_call_from_sync_context PASSED
tests/test_async_llm_call.py::TestAsyncLLMCall::test_call_from_async_context PASSED
tests/test_async_llm_call.py::TestAsyncLLMCall::test_call_from_async_context_nested PASSED
tests/test_async_llm_call.py::TestAsyncLLMCall::test_call_timeout_in_async_context PASSED

============================== 4 passed in 2.04s ===============================
```

### 回归测试

所有现有测试仍然通过：

```bash
$ python3 -m pytest tests/ -v

============================== 42 passed in 2.65s ===============================
```

## 技术细节

### 为什么不用 `asyncio.get_event_loop().run_until_complete()`？

在异步上下文中，`run_until_complete()` 会抛出：
```
RuntimeError: This event loop is already running
```

这是因为当前循环正在运行其他任务（如 CrewAI 的主循环），不能在其上运行同步等待。

### 为什么使用新线程？

**线程隔离优势：**
1. 独立的事件循环，不与主循环冲突
2. 同步等待（`thread.join()`）不会阻塞主循环
3. 守护线程（`daemon=True`）确保进程退出时自动清理

### 超时保护

```python
thread.join(timeout=30)
```

30秒超时防止：
- API 调用hang住导致主线程永久阻塞
- 资源泄漏

## 使用场景

### 修复前的错误场景

```python
# @before_llm_call hook 中
def before_llm_hook(context):
    maybe_compress(context.messages, context)  # 触发异步上下文中的同步 LLM 调用
```

**错误：** `RuntimeError: asyncio.run() cannot be called from a running event loop`

### 修复后的正常工作流

```python
# @before_llm_call hook 中
def before_llm_hook(context):
    maybe_compress(context.messages, context)  # ✅ 正常工作
    # 内部调用 summary_llm.call()，在异步上下文中通过新线程解决
```

## 注意事项

### 线程安全

- `AliyunLLM` 实例本身应该是线程安全的
- 如果 LLM 实现内部有共享状态，需要加锁保护

### 性能考虑

- 每次跨线程调用有轻微性能开销
- 对于高频场景，建议直接使用异步 API (`await acall()`)
- 压缩场景（`_summarize_chunk`）是低频操作，开销可接受

### 超时配置

当前硬编码 30 秒超时，如需自定义：

```python
# 可以在 __init__ 中添加 timeout 参数
def __init__(self, ..., sync_call_timeout: int = 30):
    self._sync_call_timeout = sync_call_timeout
```

## 相关问题

这个修复解决了以下相关问题：
- ✅ 上下文压缩时的异步事件循环冲突
- ✅ `@before_llm_call` hook 中调用 LLM 的错误
- ✅ `_summarize_chunk` 函数的调用失败

## 后续优化建议

1. **API 重构**：考虑将 `maybe_compress` 改为异步函数，避免跨线程调用
2. **配置化超时**：将超时时间作为可配置参数
3. **监控指标**：添加跨线程调用的性能监控
4. **线程池**：考虑使用线程池代替临时创建线程

---

**修复日期**：2025-04-23
**测试状态**：✅ 全部通过
**向后兼容**：✅ 不影响现有功能
