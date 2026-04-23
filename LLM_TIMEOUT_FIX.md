# LLM 调用超时问题修复

## 问题描述

遇到 LLM API 调用超时错误：

```
TimeoutError: asyncio.TimeoutError
File "/home/jackluo/my/jack-claw/jackclaw/llm/aliyun_llm.py", line 158, in acall
```

## 修复内容

### 1. 增加超时时间

**修改前：**
```python
timeout=aiohttp.ClientTimeout(total=60)  # 60秒超时
```

**修改后：**
```python
timeout_config = aiohttp.ClientTimeout(
    total=300,      # 总超时 5 分钟
    connect=30,     # 连接超时 30 秒
    sock_read=270   # 读取超时 4.5 分钟
)
```

### 2. 改进错误处理和日志

添加了更详细的错误日志和分类处理：

- **asyncio.TimeoutError**: 专门处理超时错误
- **aiohttp.ClientError**: 处理网络连接错误
- **KeyError**: 处理响应格式错误
- **Exception**: 通用异常捕获

### 3. 添加调用日志

- 调用前记录：模型名称和 max_tokens
- 调用成功记录：响应长度
- 错误时记录：详细的错误信息

## 配置说明

相关的超时配置（按优先级排序）：

### 1. HTTP 请求超时（aliyun_llm.py）
```python
total=300      # 总超时 5 分钟
connect=30     # 连接超时 30 秒
sock_read=270  # 读取超时 4.5 分钟
```

### 2. Agent 超时（config.yaml）
```yaml
agent:
  timeout_s: 300  # 5 分钟
```

### 3. LLM 配置超时（llm_config.yaml）
```yaml
default:
  timeout: 600  # 10 分钟（未使用，预留）
  retry_count: 2  # 重试次数（预留）
```

## 使用建议

### 1. 检查网络连接

```bash
# 测试到阿里云 API 的连接
curl -I https://dashscope.aliyuncs.com
```

### 2. 查看详细日志

启动服务后，观察日志输出：

```
[INFO] 正在调用 LLM API: model=qwen-turbo-1101, max_tokens=2000
[INFO] LLM API 调用成功: model=qwen-turbo-1101, response_length=1234
```

### 3. 如果仍然超时

可能的原因：

1. **模型响应慢**: 某些大模型在处理复杂请求时响应较慢
2. **网络问题**: 检查网络连接质量和防火墙设置
3. **API 限流**: 检查配额是否耗尽或触发了速率限制
4. **请求过大**: 减少 `max_input_tokens` 或 `max_tokens`

### 4. 调整超时时间

如果需要更长的超时时间，编辑 `jackclaw/llm/aliyun_llm.py`:

```python
timeout_config = aiohttp.ClientTimeout(
    total=600,      # 增加到 10 分钟
    connect=60,     # 连接超时 1 分钟
    sock_read=540   # 读取超时 9 分钟
)
```

## 重启服务

应用修复后，重启服务：

```bash
# 停止当前服务（如果在运行）
# 然后重新启动
./start.sh
```

## 监控建议

持续监控以下指标：

1. **调用频率**: 是否触发了 API 速率限制
2. **响应时间**: 正常响应时间范围
3. **错误率**: 超时错误的发生频率
4. **配额使用**: 检查配额是否即将耗尽

如果问题持续，请检查：
- 阿里云 Dashboard 中的 API 调用日志
- 网络连接质量
- 模型状态（是否维护中）
