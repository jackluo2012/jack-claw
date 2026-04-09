# JackClaw

飞书本地工作助手（MVP 重写版）

基于 JackClaw 重写，通过 6 个阶段迭代实现核心功能。

## 特性

- 飞书全场景接入：单聊、群聊、话题群
- 消息串行处理：per-routing_key 队列
- Agent 调度：通义千问 LLM
- Skills 生态：PDF/Word/Excel 处理
- 定时任务：at/every/cron 三种模式
- 可观测性：日志 + Prometheus 指标

## 快速开始

```bash
pip install -e .
cp config.yaml.template config.yaml
# 编辑 config.yaml，设置飞书凭证
jackclaw
```
