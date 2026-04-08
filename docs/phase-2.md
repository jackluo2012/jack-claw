# Phase 2: Agent 集成

## 目标

集成 LLM（通义千问），实现对话能力。

## 交付物

| 文件 | 状态 | 说明 |
|------|------|------|
| `jackclaw/llm/aliyun_llm.py` | ✅ | 通义千问 API 适配器 |
| `jackclaw/agents/main_agent.py` | ✅ | 主 Agent 实现 |

## 依赖

- Phase 1 所有模块
- `QWEN_API_KEY` 环境变量

## 关键特性

- **异步调用**：使用 DashScope 异步 API
- **历史上下文**：自动加载对话历史
- **错误重试**：网络错误自动重试

## 验证方式

```bash
git checkout feature/phase-2-agent
pytest tests/ -v

# 设置环境变量
export QWEN_API_KEY=sk_xxx

python -m jackclaw.main
```

## 当前状态

**已完成** ✓

- AliyunLLM 适配器实现
- MainAgent 调度逻辑
- 历史消息管理
