"""
JackClaw — 飞书本地工作助手

基于 XiaoPaw 重写的 MVP 版本，通过分阶段迭代实现核心功能。

架构分层：
- 接入层: feishu/listener.py, feishu/sender.py
- 调度层: runner.py, session/manager.py
- 执行层: agents/main_agent.py, llm/aliyun_llm.py
- 工具层: tools/skill_loader.py, skills/
- 基础层: sandbox/, cron/, cleanup/, observability/
"""

__version__ = "0.1.0"
