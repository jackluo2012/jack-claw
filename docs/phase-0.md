# Phase 0: 项目骨架

## 目标

搭建最小可运行的项目骨架，验证配置加载和模块结构。

## 交付物

| 文件 | 状态 | 说明 |
|------|------|------|
| `jackclaw/__init__.py` | ✅ | 包初始化 |
| `jackclaw/config.py` | ✅ | 配置加载，支持环境变量替换 |
| `jackclaw/main.py` | ✅ | 入口点（Phase 0 版本仅打印日志） |
| `jackclaw/models.py` | ✅ | 数据模型定义 |
| `tests/test_config.py` | ✅ | 配置模块测试 |

## 验证方式

```bash
git checkout feature/phase-0-skeleton
pytest tests/ -v
```

## 当前状态

**已完成** ✓

- 项目骨架搭建完成
- 配置模块支持 `${ENV_VAR}` 格式的环境变量替换
- 基础测试通过（4 tests）
