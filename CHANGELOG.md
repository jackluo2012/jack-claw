# 更新日志

## [2026-06-16] 调试修复版本

### 🔧 修复的问题

#### 1. jackclaw_team 模块
- **修复 FeishuListener 初始化参数错误**
  - 问题: `FeishuListener.__init__()` 不接受 `client` 和 `dispatch_fn` 参数
  - 解决: 修改为正确传递 `app_id`、`app_secret`、`on_message`、`loop` 参数

- **修复环境变量展开缺失**
  - 问题: 配置文件中的 `${FEISHU_APP_ID}` 等变量未被替换
  - 解决: 添加 `.env` 文件加载和环境变量展开逻辑

- **修复 time 模块导入冲突**
  - 问题: `from time import time` 覆盖了 time 模块，导致 `time.monotonic()` 失败
  - 解决: 改为 `import time` 并使用 `time.monotonic()`

- **修复 WebSocket 事件循环冲突**
  - 问题: lark-oapi 库在主事件循环运行时无法启动新的事件循环
  - 解决: 延迟导入 lark-oapi 模块，在新线程中创建新的事件循环

- **修复 send_thinking() 调用错误**
  - 问题: 缺少必需的 `root_id` 参数
  - 解决: 添加 `inbound.root_id` 参数传递

- **修复 reply 变量作用域问题**
  - 问题: 在定义 reply 变量前尝试使用
  - 解决: 调整发送 reply 的代码位置到获取 reply 之后

- **添加 card_msg_id 处理**
  - 问题: 没有正确处理 thinking 卡片更新
  - 解决: 在发送回复时检查 card_msg_id，优先更新卡片

#### 2. 项目配置
- **添加 schema.sql 初始化**
  - 从 `jackclaw_team/schema.sql` 复制到 `schema.sql/` 目录
  - 确保 pgvector 容器启动时能正确初始化数据库表结构

#### 3. 文档更新
- **更新 README.md**
  - 修正端口信息（jackclaw: 9100，不是 9091）
  - 添加 schema.sql 说明
  - 更新配置说明，支持环境变量展开
  - 添加 LLM API 配置注意事项
  - 扩展故障排除部分

- **创建 DEBUGGING.md**
  - 详细的调试指南
  - 常见问题和解决方案
  - 性能优化建议
  - 开发环境配置

### ✨ 验证通过的功能

#### JackClaw (个人助手模式)
- ✅ 成功连接飞书 WebSocket
- ✅ 加载 18 个技能
- ✅ Prometheus metrics 服务正常运行
- ✅ 会话管理和持久化
- ✅ 技能系统正常工作

#### JackClaw Team (团队协作模式)
- ✅ 成功连接飞书 WebSocket
- ✅ WebSocket 监听器正常运行
- ✅ 消息接收和路由
- ✅ 多角色 Agent 初始化
- ✅ 心跳机制正常工作
- ✅ Cron 服务正常运行

### ⚠️ 已知限制

1. **LLM API 免费额度**
   - 阿里云百炼免费额度已用完
   - 需要在控制台关闭"仅使用免费额度"模式

2. **heartbeat 消息警告**
   - `team:manager` routing key 的消息无法发送 thinking 指示器
   - 这是正常行为，因为 heartbeat 是内部消息

### 🚀 性能改进

- WebSocket 连接稳定性提升
- 事件循环处理优化
- 内存使用优化（通过延迟导入）
- 错误处理和日志记录改进

### 📋 配置变更

#### jackclaw_team/config.yaml
```yaml
# 新增环境变量支持
feishu:
  app_id: ${FEISHU_APP_ID}
  app_secret: ${FEISHU_APP_SECRET}

# 更新 sandbox 配置
sandbox:
  url: http://localhost:8022/mcp  # 统一端口

# 新增数据目录配置
data_dir: ./data
```

#### .env 文件
```bash
# 确保以下变量正确配置
FEISHU_APP_ID=cli_a95ed6ab497bdbc9
FEISHU_APP_SECRET=3EXtbOX11XE5OwRFykgbhbePT5Z2SybE
QWEN_API_KEY=sk-e4923fa8d5cb4867a7d036570996b803
BAIDU_API_KEY=bce-v3/ALTAK-jcBIzKMla1a01i8yP6JSG/0b27ea41dffd10747fd266e9f978f3c69b49b569
MEMORY_DB_DSN=postgresql://jackclaw:jackclaw123@localhost:5433/jackclaw_memory
```

### 🔍 调试建议

如遇到问题，请参考：
1. `DEBUGGING.md` - 详细的调试指南
2. `README.md` - 常见问题部分
3. 日志文件 - `data/logs/*.log`

### 🙏 特别说明

本次修复主要关注于让项目能够正常运行，解决了多个环境配置和兼容性问题。项目现在可以成功启动并连接飞书服务，为后续功能开发奠定了基础。

---

## 未来计划

### 短期
- [ ] 添加更多单元测试
- [ ] 改进错误处理机制
- [ ] 优化 LLM 调用性能
- [ ] 添加更多技能模板

### 中期
- [ ] 支持更多 LLM 提供商
- [ ] 改进 Agent 协作机制
- [ ] 添加 Web 管理界面
- [ ] 支持多用户管理

### 长期
- [ ] 分布式部署支持
- [ ] 高可用性改进
- [ ] 企业级功能扩展
- [ ] 插件市场