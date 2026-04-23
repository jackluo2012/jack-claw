# JackClaw 执行流程文档

## 📋 目录

1. [系统架构概述](#系统架构概述)
2. [完整执行流程](#完整执行流程)
3. [核心组件详解](#核心组件详解)
4. [关键数据流转](#关键数据流转)
5. [潜在问题与解决方案](#潜在问题与解决方案)
6. [配置说明](#配置说明)

---

## 系统架构概述

JackClaw 是一个基于飞书的多智能体系统，采用 **主从式多 Agent 架构**：

```
┌─────────────────────────────────────────────────────────────┐
│                         用户层                               │
│                    飞书客户端（用户）                         │
└──────────────────────┬──────────────────────────────────────┘
                       │ 消息事件
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    接入层                                    │
│              FeishuListener (WebSocket)                      │
│         - 监听飞书消息事件                                    │
│         - 转换为 InboundMessage                              │
└──────────────────────┬──────────────────────────────────────┘
                       │ dispatch()
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   调度层                                     │
│                    Runner                                    │
│         - Per-routing-key 串行队列                           │
│         - Session 管理                                       │
│         - Slash Command 处理                                │
└──────────────────────┬──────────────────────────────────────┘
                       │ agent_fn()
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   Agent 层 (主 Crew)                         │
│              MemoryAwareCrew                                 │
│         - orchestrator agent (主 Agent)                      │
│         - Tools: SkillLoaderTool, IntermediateTool          │
│         - @before_llm_call hook (记忆管理)                   │
└──────────────────────┬──────────────────────────────────────┘
                       │ SkillLoaderTool._run()
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  技能执行层 (Sub-Crew)                        │
│              build_skill_crew()                              │
│         - skill_agent (技能执行专家)                         │
│         - MCP Tools (沙盒工具集)                             │
│         - AIO-Sandbox 执行环境                               │
└──────────────────────┬──────────────────────────────────────┘
                       │ 执行结果
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   响应层                                     │
│                  FeishuSender                                │
│         - 发送回复到飞书                                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 完整执行流程

### 阶段 1: 消息接收 (FeishuListener)

**触发条件**: 用户在飞书中发送消息

```python
# 文件: jackclaw/feishu/listener.py
# 1. 建立 WebSocket 长连接
listener = FeishuListener(
    app_id=app_id,
    app_secret=app_secret,
    on_message=runner.dispatch,  # 回调函数
    allowed_chats=allowed_chats,  # 白名单过滤
)
listener.start()

# 2. 接收消息事件
def on_message(event: P2ImMessageReceiveV1):
    # 解析消息内容
    content = event.event.message.content
    msg_id = event.event.message.message_id
    chat_id = event.event.message.chat_id
    root_id = event.event.message.root_id or msg_id

    # 构建 InboundMessage
    inbound = InboundMessage(
        content=content,
        msg_id=msg_id,
        chat_id=chat_id,
        root_id=root_id,
        routing_key=build_routing_key(chat_id),  # "user:{chat_id}"
        attachment=None,  # 如果有文件附件
    )

    # 回调到 Runner.dispatch()
    self._on_message(inbound)
```

**关键点**:
- WebSocket 运行在独立线程中
- 通过 `call_soon_threadsafe` 线程安全地投递到主事件循环
- 支持 `allowed_chats` 白名单过滤

---

### 阶段 2: 消息调度 (Runner)

**文件**: `jackclaw/runner.py`

```python
# 步骤 1: 消息入队 (Per-routing-key 串行)
async def dispatch(self, inbound: InboundMessage):
    key = inbound.routing_key  # 例如: "user:oc_xxx"

    async with self._dispatch_lock:
        if key not in self._queues:
            # 为新的 routing_key 创建队列和 worker
            self._queues[key] = asyncio.Queue()
            self._workers[key] = asyncio.create_task(self._worker(key))

    # 消息入队（同一用户的消息串行处理）
    await self._queues[key].put(inbound)

# 步骤 2: Worker 消费队列
async def _worker(self, key: str):
    while True:
        try:
            inbound = await asyncio.wait_for(
                queue.get(), timeout=self._idle_timeout  # 默认 300s
            )
        except asyncio.TimeoutError:
            # 空闲超时，退出 worker 释放资源
            return

        await self._handle(inbound)
        queue.task_done()
```

**关键设计**:
- **串行保证**: 同一用户的消息串行处理，避免并发冲突
- **并行优化**: 不同用户的消息并行处理
- **空闲超时**: 300秒无消息后自动退出 worker

---

### 阶段 3: 消息处理 (Runner._handle)

```python
async def _handle(self, inbound: InboundMessage):
    # 1. Slash Command 拦截
    slash_reply = await self._handle_slash(inbound)
    if slash_reply is not None:
        await self._sender.send_text(key, slash_reply, inbound.root_id)
        return  # 不进入 Agent，不写历史

    # 2. 获取或创建 Session
    session = await self._session_mgr.get_or_create(key)
    # Session.id: "s-{uuid}"
    # Session.verbose: 是否显示推理过程

    # 3. 附件下载（如果有）
    if inbound.attachment and self._downloader:
        local_path = await self._downloader.download(
            inbound.msg_id, inbound.attachment, session.id
        )
        # 下载成功后，修改用户消息
        user_content = f"用户发来了文件，已自动保存至沙盒路径：`{sandbox_path}`"

    # 4. 加载对话历史
    history = await self._session_mgr.load_history(session.id)
    # 返回 List[MessageEntry]

    # 5. 发送 Loading 卡片
    card_msg_id = await self._sender.send_thinking(key, inbound.root_id)

    # 6. 执行 Agent (核心步骤)
    reply = await self._agent_fn(
        user_content,      # 用户消息
        history,           # 历史对话
        session.id,        # Session ID
        inbound.routing_key,
        inbound.root_id,
        session.verbose,   # 是否显示推理过程
    )

    # 7. 写入 Session 历史
    await self._session_mgr.append(
        session.id,
        user=user_content,
        feishu_msg_id=inbound.msg_id,
        assistant=reply,
    )

    # 8. 发送回复
    await self._sender.delete_message(card_msg_id)  # 删除 Loading 卡片
    await self._sender.send(key, reply, inbound.root_id)
```

**关键点**:
- Slash Command 优先处理，不进入 Agent
- Session 管理保证多轮对话的上下文连续性
- 历史记录加载后注入到 Agent 的 backstory 中

---

### 阶段 4: Agent 执行 (MemoryAwareCrew)

**文件**: `jackclaw/agents/main_crew.py`

```python
# 1. 构建 Agent
def orchestrator(self) -> Agent:
    # 加载 YAML 配置
    cfg = load_yaml("agents.yaml")["orchestrator"]

    # 动态构建 backstory (三层叠加)
    # Layer 1: Bootstrap (workspace 文件注入)
    bootstrap_backstory = build_bootstrap_prompt(self._workspace_dir)

    # Layer 2: 技能列表注入
    skills_list = _load_available_skills(skills_config_path)
    skills_section = f"\n\n【可用技能列表】\n{skills_list}\n"

    # Layer 3: 原始 backstory (来自 YAML)
    cfg["backstory"] = f"{bootstrap_backstory}\n\n{cfg['backstory']}{skills_section}"

    # 2. 准备 Tools
    tools = []

    # Tool 1: SkillLoaderTool (技能加载器)
    if SkillLoaderTool is not None:
        skill_loader = SkillLoaderTool(
            skills_config_path=skills_config_path,
            session_id=self.session_id,
            routing_key=self.routing_key,
            history_all=self._history_all,
            sandbox_url=self._sandbox_url,
        )
        tools.append(skill_loader)

    # Tool 2: IntermediateTool (中间结果保存)
    tools.append(IntermediateTool())

    # 3. 创建 Agent
    return Agent(
        **cfg,
        llm=LLMFactory.create_for_role("assistant"),
        tools=tools,
        max_iter=3,  # 最多3次迭代
        verbose=True,
    )

# 4. 执行 Crew
async def run_and_index(self) -> str:
    result = await self.crew().akickoff(
        inputs={
            "user_message": self.user_message,
            "history": _format_history(self._history_all),
        }
    )

    # 提取回复
    assistant_reply = result.raw or str(result)
    if result.pydantic and hasattr(result.pydantic, "reply"):
        assistant_reply = str(result.pydantic.reply)

    return assistant_reply
```

**关键设计**:
- **三层 backstory**: Bootstrap + 技能列表 + 原始配置
- **两个工具**: SkillLoaderTool + IntermediateTool
- **最大迭代**: 3次（防止无限循环）

---

### 阶段 5: 工具调用 (SkillLoaderTool)

**文件**: `jackclaw/tools/skill_loader_tool.py`

```python
# Agent 调用 SkillLoaderTool 的执行流程
def _run(self, skill_name: str, task_context: str = "") -> str:
    # 1. 加载技能配置
    skills = self._load_skills_config()
    # 返回: {"baidu_search": {"type": "task", ...}, ...}

    # 2. 检查技能是否存在
    if skill_name not in skills:
        return json.dumps({
            "errcode": -1,
            "errmsg": f"技能 '{skill_name}' 不存在或未启用",
            "data": None,
        })

    skill_config = skills[skill_name]
    skill_type = skill_config.get("type", "task")

    # 3. 根据类型分发处理
    if skill_type == "reference":
        # Reference 类型: 直接返回 SKILL.md 内容
        return self._load_reference_skill(skill_name, skill_path)

    elif skill_type == "task":
        # Task 类型: 启动 Sub-Crew 执行
        return self._run_task_skill(skill_name, skill_path, task_context)
```

**Reference 类型执行流程**:
```python
def _load_reference_skill(self, skill_name: str, skill_path: Path) -> str:
    skill_md = skill_path / "SKILL.md"
    content = skill_md.read_text(encoding="utf-8")

    # 去除 frontmatter (--- 包围的 YAML 头)
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            content = parts[2].strip()

    return f"【{skill_name} Skill 操作规范】\n\n{content}"
```

**Task 类型执行流程**:
```python
def _run_task_skill(
    self,
    skill_name: str,
    skill_path: Path,
    task_context: str,
) -> str:
    # 1. 读取 SKILL.md 内容（包含 frontmatter）
    skill_content = (skill_path / "SKILL.md").read_text(encoding="utf-8")

    # 2. 构建 Sub-Crew
    crew = build_skill_crew(
        skill_name=skill_name,
        skill_instructions=skill_content,
        session_id=self._session_id,
        sandbox_mcp_url=self._sandbox_url,
        max_iter=20,
    )

    # 3. 异步执行
    loop = asyncio.get_running_loop()
    result = loop.run_until_complete(
        crew.akickoff(inputs={"task_context": task_context})
    )

    # 4. 解析结果
    if result.pydantic:
        return json.dumps(result.pydantic.model_dump(), ensure_ascii=False)
    else:
        return json.dumps({
            "errcode": 0,
            "errmsg": "success",
            "data": result.raw or str(result),
        }, ensure_ascii=False)
```

---

### 阶段 6: Sub-Crew 执行 (build_skill_crew)

**文件**: `jackclaw/agents/skill_crew.py`

```python
def build_skill_crew(
    skill_name: str,
    skill_instructions: str,
    session_id: str,
    sandbox_mcp_url: str,
    max_iter: int = 20,
) -> Crew:
    # 1. 创建 MCP 连接 (连接到 AIO-Sandbox)
    sandbox_mcp = MCPServerHTTP(url=sandbox_mcp_url)

    # 2. 创建 LLM (使用 sub_agent 角色配置)
    skill_llm = LLMFactory.create_for_role("sub_agent")
    # 模型: qwen3-max-2025-09-23, 温度: 0.7

    # 3. 构建 skill_agent 配置
    session_dir = f"/workspace/sessions/{session_id}"
    agent_fmt_vars = dict(
        skill_name=skill_name,
        skill_name_upper=skill_name.upper(),
        session_dir=session_dir,
        skill_instructions=skill_instructions,
    )

    # 从 YAML 加载配置并格式化
    skill_agent_cfg = _format_cfg(
        agents_cfg["skill_agent"],
        **agent_fmt_vars
    )
    skill_agent_cfg["max_iter"] = max_iter

    # 4. 创建 Agent
    skill_agent = Agent(
        **skill_agent_cfg,
        llm=skill_llm,
        mcps=[sandbox_mcp],  # 注入 MCP 工具
        verbose=True,
    )

    # 5. 创建 Task
    skill_task = Task(
        **tasks_cfg["skill_task"],
        agent=skill_agent,
    )

    # 6. 创建并返回 Crew
    return Crew(
        agents=[skill_agent],
        tasks=[skill_task],
        process=Process.sequential,
        verbose=True,
    )
```

**关键设计**:
- **MCP 连接**: Sub-Crew 通过 MCP 连接到 AIO-Sandbox
- **沙盒路径**: `/workspace/sessions/{session_id}/`
- **最大迭代**: 20次（技能任务可能需要多次尝试）

---

### 阶段 7: 沙盒执行 (AIO-Sandbox)

Sub-Crew 中的 skill_agent 可以使用以下 MCP 工具：

| 工具名称 | 功能 | 使用场景 |
|---------|------|---------|
| `sandbox_execute_bash` | 执行 Shell 命令 | 文件操作、系统命令 |
| `sandbox_execute_code` | 执行 Python 代码 | 数据处理、计算 |
| `sandbox_file_operations` | 文件读写 | 保存结果、读取配置 |
| `sandbox_str_replace_editor` | 编辑文件 | 修改文件内容 |
| `sandbox_convert_to_markdown` | URL 转 Markdown | 网页内容提取 |
| `browser_*` | 浏览器自动化 | 网页交互、截图 |

**沙盒目录结构**:
```
/workspace/sessions/{session_id}/
├── uploads/      # 用户上传的文件
├── outputs/      # 任务输出文件
└── tmp/          # 临时工作区
```

**执行示例** (baidu_search Skill):
```python
# skill_agent 的思考过程
# 1. 理解任务: "查询美团股票价格"
# 2. 决定使用 bash 调用搜索脚本
thought = "使用 bash 调用 baidu_search 脚本查询美团股价"

# 3. 执行命令
action = sandbox_execute_bash
action_input = {
    "command": "cd /workspace/sessions/xxx && python3 scripts/search.py \"美团股票价格\""
}

# 4. 获取结果
observation = {
    "stdout": '{"price": "123.45 HKD", "change": "+2.3%"}',
    "stderr": "",
    "exit_code": 0
}

# 5. 返回最终答案
final_answer = {
    "errcode": 0,
    "errmsg": "success",
    "data": {"price": "123.45 HKD", "change": "+2.3%"}
}
```

---

### 阶段 8: 结果返回

```python
# 1. Sub-Crew 返回结果
# SkillLoaderTool._run_task_skill() 接收到 JSON 结果
result_json = {
    "errcode": 0,
    "errmsg": "success",
    "data": {"price": "123.45 HKD"}
}

# 2. 主 Agent 接收到工具返回
# Agent 的 Observation 阶段
observation = result_json

# 3. Agent 给出最终回复
final_answer = """根据查询结果，美团(03690.HK)的最新股价为：
- 价格：123.45 HKD
- 涨跌：+2.3%

used_skills: ["baidu_search"]"""

# 4. 返回给 Runner
reply = final_answer

# 5. Runner 发送到飞书
await sender.send(routing_key, reply, root_id)
```

---

## 核心组件详解

### 1. FeishuListener (消息监听器)

**职责**: 监听飞书消息事件，转换为标准化的 InboundMessage

**关键特性**:
- WebSocket 长连接
- 线程安全的事件回调
- 白名单过滤

**配置**: `config.yaml` 中的 `feishu` 部分

---

### 2. Runner (执行引擎)

**职责**: 消息调度、Session 管理、Agent 执行编排

**关键特性**:
- Per-routing-key 串行队列
- 空闲超时自动清理
- Slash Command 处理

**配置**: `config.yaml` 中的 `runner` 部分

---

### 3. SessionManager (会话管理器)

**职责**: 管理多轮对话的上下文

**存储结构**:
```
data/sessions/
├── index.json              # Session 索引
└── {session_id}/
    ├── raw.jsonl           # 原始对话记录
    └── ctx.json            # 压缩后的上下文 (供 LLM 使用)
```

**关键方法**:
- `get_or_create()`: 获取或创建 Session
- `load_history()`: 加载对话历史
- `append()`: 追加新的对话

---

### 4. MemoryAwareCrew (主 Crew)

**职责**: 主 Agent，负责理解用户意图、调用技能、组织回复

**关键特性**:
- 三层 backstory (Bootstrap + 技能列表 + 原始配置)
- @before_llm_call hook (记忆管理)
- 两个工具: SkillLoaderTool + IntermediateTool

**配置**:
- `jackclaw/agents/config/agents.yaml`: Agent 配置
- `jackclaw/agents/config/tasks.yaml`: Task 配置

---

### 5. SkillLoaderTool (技能加载器)

**职责**: 加载和执行 Skills

**技能类型**:
- **Reference**: 返回 SKILL.md 内容（操作规范）
- **Task**: 启动 Sub-Crew 在沙盒中执行

**配置**: `jackclaw/skills/load_skills.yaml`

---

### 6. build_skill_crew (Sub-Crew 工厂)

**职责**: 为 Task 类型技能构建独立的执行 Crew

**关键特性**:
- 独立的 LLM 实例（sub_agent 角色）
- MCP 连接到 AIO-Sandbox
- 完全隔离的执行环境

**配置**:
- `jackclaw/agents/config/agents.yaml`: skill_agent 配置
- `jackclaw/agents/config/tasks.yaml`: skill_task 配置

---

### 7. AIO-Sandbox (沙盒执行环境)

**职责**: 提供安全的代码执行环境

**可用工具**:
- `sandbox_execute_bash`: 执行 Shell 命令
- `sandbox_execute_code`: 执行 Python 代码
- `sandbox_file_operations`: 文件读写
- `sandbox_str_replace_editor`: 编辑文件
- `sandbox_convert_to_markdown`: URL 转 Markdown
- `browser_*`: 浏览器自动化

**配置**: `config.yaml` 中的 `sandbox` 部分

---

## 关键数据流转

### 1. 用户消息流转

```
用户输入 (飞书)
    ↓
FeishuListener 接收
    ↓
InboundMessage {
    content: "查询美团股价",
    msg_id: "om_xxx",
    chat_id: "oc_xxx",
    root_id: "om_xxx",
    routing_key: "user:oc_xxx",
    attachment: None,
}
    ↓
Runner.dispatch() 入队
    ↓
Runner._handle() 处理
    ↓
SessionManager.get_or_create()
    ↓
agent_fn() 执行
    ↓
MemoryAwareCrew.run_and_index()
    ↓
返回 reply
    ↓
FeishuSender.send() 发送到飞书
```

---

### 2. Session 数据流转

```
SessionManager
    ↓
index.json {
    "user:oc_xxx": {
        "active_session_id": "s-uuid-1",
        "sessions": [
            {
                "id": "s-uuid-1",
                "created_at": "2026-04-23T11:00:00",
                "verbose": false,
                "message_count": 5
            }
        ]
    }
}
    ↓
s-uuid-1/raw.jsonl [
    {"role": "user", "content": "...", "ts": 123456, "feishu_msg_id": "om_xxx"},
    {"role": "assistant", "content": "...", "ts": 123457, "feishu_msg_id": ""},
]
    ↓
s-uuid-1/ctx.json [
    {"role": "system", "content": "Bootstrap backstory..."},
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."},
    ...
]
    ↓
注入到 Agent 的 context.messages
```

---

### 3. 技能调用流转

```
Agent 决定调用技能
    ↓
SkillLoaderTool._run(
    skill_name="baidu_search",
    task_context="查询美团股价"
)
    ↓
加载技能配置
load_skills.yaml → {"baidu_search": {"type": "task", ...}}
    ↓
判断类型: task
    ↓
读取 SKILL.md
jackclaw/skills/baidu_search/SKILL.md
    ↓
构建 Sub-Crew
build_skill_crew(
    skill_name="baidu_search",
    skill_instructions=skill_content,
    session_id="s-uuid-1",
    sandbox_mcp_url="http://localhost:8022/mcp"
)
    ↓
创建 MCP 连接
MCPServerHTTP("http://localhost:8022/mcp")
    ↓
创建 skill_agent
Agent(
    role="BAIDU_SEARCH SKILL 执行专家",
    goal="严格按照 baidu_search Skill 的操作规范...",
    llm=AliyunLLM("qwen3-max-2025-09-23"),
    mcps=[sandbox_mcp],
)
    ↓
执行 Crew
crew.akickoff(inputs={"task_context": "查询美团股价"})
    ↓
skill_agent 在沙盒中执行
sandbox_execute_bash("python3 scripts/search.py ...")
    ↓
返回结果
{"errcode": 0, "errmsg": "success", "data": {...}}
    ↓
主 Agent 接收结果
    ↓
组织最终回复
"根据查询结果，美团股价为..."
```

---

## 潜在问题与解决方案

### 问题 1: Agent 无限循环

**现象**: Agent 不断重复相同的工具调用，不返回最终答案

**原因**:
1. 没有设置 `max_iter` 限制
2. Agent 的 backstory 没有明确的停止条件
3. Agent 没有理解何时应该返回答案

**解决方案**:
```yaml
# agents.yaml
orchestrator:
  max_iter: 3  # 设置最大迭代次数
  backstory: |
    🎯【完成标准】执行任务后，你必须返回最终答案给用户，而不是继续循环：
    1. 技能执行成功 → 根据返回结果给用户一个清晰、有用的回复
    2. 技能执行失败 → 告诉用户具体错误，并建议可能的解决方案

    ⚠️【停止条件】以下情况下立即停止并返回答案：
    - 已经获得了足够的信息来回答用户的问题
    - 技能返回了有用的结果
    - 技能执行失败，你已经告诉用户错误原因
```

---

### 问题 2: Agent 说"没有工具"

**现象**: Agent 回复"我无法..."、"我没有权限..."

**原因**:
1. SkillLoaderTool 没有正确注入到 Agent
2. Agent 的 backstory 没有强制要求使用工具
3. Tool 的 description 不够清晰

**解决方案**:
```yaml
# agents.yaml
orchestrator:
  backstory: |
    🚨【最重要的规则】你必须拥有 SkillLoaderTool 工具！
    如果你自己为没有工具，那是错误的！

    💡【强制要求】在说以下任何一句话之前，你必须先尝试调用 SkillLoaderTool：
    - "我无法..."
    - "我没有权限..."
    - "我暂时无法..."
```

```python
# skill_loader_tool.py
class SkillLoaderTool(BaseTool):
    name: str = "SkillLoaderTool"
    description: str = (
        "【核心工具 - 必须使用】加载和执行 JackClaw 的专业技能。"
        ""
        "🚨 强制要求：在说'我无法...'之前，必须先调用此工具尝试！"
        ""
        "【常用技能速查】"
        "- baidu_search: 百度搜索（股票、天气、新闻、实时信息）"
        ...
    )
```

---

### 问题 3: 模型配置错误

**现象**: `ValueError: 模型 'qwen3-max' 不在允许使用的模型列表中`

**原因**:
- 代码中硬编码的模型名与配置文件不一致

**解决方案**:
```python
# skill_crew.py
def build_skill_crew(
    skill_name: str,
    skill_instructions: str,
    sub_agent_model: str | None = None,  # 改为可选参数
    ...
):
    # 如果没有指定模型，使用配置文件中的 sub_agent 角色
    if sub_agent_model is None:
        skill_llm = LLMFactory.create_for_role("sub_agent")
    else:
        skill_llm = AliyunLLM(model=sub_agent_model, temperature=0.3)
```

---

### 问题 4: Sub-Crew 执行失败

**现象**: SkillLoaderTool 返回 `{"errcode": -1, "errmsg": "技能执行失败: ..."}`

**可能原因**:
1. AIO-Sandbox 未启动或连接失败
2. SKILL.md 文件不存在
3. 沙盒中的脚本执行错误

**调试步骤**:
1. 检查 AIO-Sandbox 是否运行: `docker ps | grep aio-sandbox`
2. 检查 MCP 连接: `curl http://localhost:8022/mcp`
3. 查看沙盒日志: `docker logs aio-sandbox`
4. 检查 Skill 文件: `ls -la jackclaw/skills/{skill_name}/`

---

### 问题 5: Session 历史丢失

**现象**: Agent 不记得之前的对话内容

**原因**:
1. `ctx.json` 文件损坏或丢失
2. @before_llm_call hook 没有正确恢复历史
3. `prune_keep_turns` 设置太小

**解决方案**:
```python
# main_crew.py
crew_instance = MemoryAwareCrew(
    ...
    prune_keep_turns=10,  # 保留最近10轮对话
)
```

检查 `ctx.json` 文件:
```bash
ls -la data/sessions/*/ctx.json
cat data/sessions/{session_id}/ctx.json | jq .
```

---

## 配置说明

### 1. 主配置文件: `config.yaml`

```yaml
# 飞书配置
feishu:
  app_id: "cli_xxx"
  app_secret: "xxx"
  allowed_chats:
    - "oc_xxx"  # 白名单

# Agent 配置
agent:
  model: "qwen-plus"

# 技能配置
skills:
  local_dir: "./skills"

# 沙盒配置
sandbox:
  url: "http://localhost:8022/mcp"
  timeout_s: 60

# Session 配置
session:
  max_history_turns: 20

# Runner 配置
runner:
  queue_idle_timeout_s: 300

# 可观测性配置
observability:
  enable_metrics: false
  metrics_port: 9091
```

---

### 2. Agent 配置: `jackclaw/agents/config/agents.yaml`

```yaml
orchestrator:
  role: JackClaw 工作助手
  goal: 理解用户的工作需求，通过合理使用 Skills 完成任务
  max_iter: 3  # 最多3次迭代
  backstory: |
    你是 JackClaw（小爪子），部署在飞书的本地工作助手...
```

---

### 3. 技能配置: `jackclaw/skills/load_skills.yaml`

```yaml
skills:
  - name: baidu_search
    type: task
    enabled: true

  - name: pdf
    type: task
    enabled: true

  - name: history_reader
    type: reference
    enabled: true
```

---

### 4. LLM 配置: `jackclaw/llm/llm_config.yaml`

```yaml
# 默认模型
default:
  provider: aliyun
  text_model: qwen-max
  temperature: 0.7

# 角色模型映射
models:
  assistant:
    model: qwen3-max-preview
    temperature: 0.7

  sub_agent:
    model: qwen3-max-2025-09-23
    temperature: 0.7
```

---

## 执行流程图总结

```
┌──────────────────────────────────────────────────────────────┐
│                      用户发送消息                             │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│              FeishuListener (WebSocket)                       │
│         接收事件 → 构建 InboundMessage                        │
└────────────────────┬─────────────────────────────────────────┘
                     │ dispatch()
                     ▼
┌──────────────────────────────────────────────────────────────┐
│                    Runner                                     │
│    Per-routing-key 队列 → Worker 消费 → _handle()            │
└────────────────────┬─────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        ▼            ▼             ▼
   Slash Command  Session    附件下载
      拦截         管理          (可选)
        │            │             │
        └────────────┼─────────────┘
                     ▼
              agent_fn() 调用
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│              MemoryAwareCrew                                 │
│    orchestrator agent + SkillLoaderTool + IntermediateTool   │
└────────────────────┬─────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        ▼            ▼             ▼
    Bootstrap    技能列表      原始backstory
      注入        注入           (YAML)
        │            │             │
        └────────────┼─────────────┘
                     ▼
              @before_llm_call hook
              (历史恢复 + prune + compress)
                     │
                     ▼
              Crew.akickoff()
                     │
        ┌────────────┼────────────┐
        ▼            ▼             ▼
   Thought 1    Action 1     Observation 1
        │            │             │
        ▼            ▼             ▼
   Thought 2    Action 2     Observation 2
        │            │             │
        ▼            ▼             ▼
   Thought 3    Final Answer
                     │
                     ▼
              提取 reply
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│                    SkillLoaderTool                           │
│         _run(skill_name, task_context)                       │
└────────────────────┬─────────────────────────────────────────┘
                     │
           ┌─────────┴─────────┐
           ▼                   ▼
    reference 类型        task 类型
           │                   │
           ▼                   ▼
    返回 SKILL.md       build_skill_crew()
      内容                   │
                           ▼
                   MCPServerHTTP 连接
                           │
                           ▼
                   skill_agent 创建
                           │
                           ▼
                   在沙盒中执行
                   (MCP 工具调用)
                           │
                           ▼
                   返回 JSON 结果
                     │
                     ▼
              Agent 组织回复
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│                   FeishuSender                                │
│              发送回复到飞书                                    │
└──────────────────────────────────────────────────────────────┘
```

---

## 总结

JackClaw 的执行流程可以概括为以下核心步骤：

1. **消息接收**: FeishuListener 监听飞书消息
2. **消息调度**: Runner 串行处理同一用户的消息
3. **Session 管理**: 加载历史对话，维护上下文
4. **Agent 执行**: MemoryAwareCrew 理解意图、调用技能
5. **技能执行**: SkillLoaderTool 加载技能、构建 Sub-Crew
6. **沙盒执行**: skill_agent 在 AIO-Sandbox 中执行任务
7. **结果返回**: Sub-Crew → 主 Agent → Runner → 飞书

每个环节都有明确的职责和边界，通过标准化的数据结构（InboundMessage、MessageEntry 等）进行通信，形成了一个清晰、可维护的多智能体系统。
