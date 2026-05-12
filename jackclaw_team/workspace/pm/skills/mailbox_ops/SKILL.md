---
name: mailbox_ops
description: "团队邮箱操作（读自己 inbox 或给其他角色发邮件）。**必须通过 sandbox_execute_bash 工具调用 CLI**，不要使用 sandbox_file_operations 手写 json"
type: task
---

# mailbox_ops — 团队邮箱操作

## ⚠️ 执行方式（强约束）

**你必须使用 `sandbox_execute_bash` 工具**调用下列 CLI，**不要**用 `sandbox_file_operations` 手动改 json 文件（后者会破坏并发锁 + 格式约定）。

## 可用子命令

### 1. 发邮件给其他角色（`send`）

```
sandbox_execute_bash cmd="python3 /workspace/manager/skills/mailbox_ops/scripts/mailbox_cli.py send --workspace /workspace --project-id PROJECT_ID_HERE --from manager --to pm --type task_assign --subject 'SUBJECT_HERE' --content 'CONTENT_HERE'"
```

字段说明：
- `--workspace /workspace`：沙盒内 workspace 固定路径
- `--project-id` ：当前项目 id（调用方提供）
- `--from / --to`：角色枚举 `manager | pm | rd | qa` (from 还允许 `human | feishu_bridge`)
- `--type`：枚举之一：`task_assign | task_done | review_request | review_done | retro_trigger | retro_report | retro_approved | retro_rejected | retro_applied | retro_apply_failed | clarification_request | clarification_answer | error_alert`
- `--subject / --content`：字符串，含单引号时用 `'\''` 转义

### 2. 读自己的 inbox（`read-inbox`）

```
sandbox_execute_bash cmd="python3 /workspace/manager/skills/mailbox_ops/scripts/mailbox_cli.py read-inbox --workspace /workspace --project-id PROJECT_ID_HERE --role manager"
```

返回所有 unread 邮件（并自动将其标记为 in_progress）。

### 3. 标记邮件处理完成（`mark-done`）

```
sandbox_execute_bash cmd="python3 /workspace/manager/skills/mailbox_ops/scripts/mailbox_cli.py mark-done --workspace /workspace --project-id PROJECT_ID_HERE --role manager --msg-id msg-xxxxxxxx"
```

## CLI 输出格式

所有子命令都输出标准 JSON 到 stdout：

```json
{"errcode": 0, "errmsg": "success", "data": {"msg_id": "msg-a1b2c3d4"}}
```

- `errcode=0` 表示成功；非 0 失败，`errmsg` 含具体错误
- `data` 里是子命令特定数据（`msg_id` / `messages` 数组 / 等）

## 典型流程

**Manager 派任务给 PM**：
1. `sandbox_execute_bash` 调 `send` 子命令，from=manager to=pm type=task_assign
2. 读取 stdout，解析 JSON，确认 `errcode == 0`
3. 把 `data.msg_id` 记在心里（后续如果要 mark_done 会用）
4. 结束 skill，回主 Agent 继续
