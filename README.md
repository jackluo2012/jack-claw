# Phase 3: Skills 系统

> JackClaw MVP 重写 - 第 4 阶段

## 📋 概述

本阶段实现 Skills 生态：
- Skill 元数据加载
- SKILL.md 规范
- Agent 系统提示注入
- 初始 Skills（PDF/DOCX/XLSX）

## 🏗️ 架构

```
┌─────────────────────────────────────────────────────────┐
│                    MainAgent                             │
│  - 构建系统提示                                          │
│  - 调用 LLM                                            │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│                  SkillLoader                             │
│  - 扫描 skills/ 目录                                    │
│  - 解析 SKILL.md                                        │
│  - 注入系统提示                                         │
└─────────────────────────────────────────────────────────┘
```

## 📁 新增文件

```
jack-claw/
├── jackclaw/
│   ├── tools/                    # 工具层 ⭐
│   │   └── skill_loader.py      # Skill 加载器
│   │
│   └── skills/                 # 技能模块 ⭐
│       ├── pdf/
│       │   └── SKILL.md         # PDF 技能
│       ├── docx/
│       │   └── SKILL.md         # Word 技能
│       └── xlsx/
│           └── SKILL.md         # Excel 技能
```

## 🔑 核心组件

### 1. SkillLoader (Skill 加载器)

```python
"""
Skill 加载器

职责：
- 扫描 skills/ 目录
- 解析 SKILL.md frontmatter
- 提供 Skill 列表
"""

@dataclass
class SkillMeta:
    """Skill 元数据"""
    name: str           # 名称
    description: str    # 描述
    type: str           # 类型: task / reference
    version: str        # 版本
    path: Path          # 路径

    @classmethod
    def from_md(cls, path: Path) -> "SkillMeta":
        """从 SKILL.md 解析"""
        # 1. 读取文件
        # 2. 解析 frontmatter
        # 3. 返回 SkillMeta

class SkillLoader:
    """Skill 加载器"""
    
    def __init__(self, skills_dir: Path):
        self._skills_dir = skills_dir
        self._skills: dict[str, SkillMeta] = {}
        self._load_skills()
    
    def list_skills(self) -> list[SkillMeta]:
        """列出所有 Skill"""
        
    def get_skill(self, name: str) -> SkillMeta | None:
        """获取指定 Skill"""
        
    def get_all_descriptions(self) -> str:
        """获取所有描述（注入系统提示）"""
```

### 2. SKILL.md 规范

```markdown
---
name: pdf
description: PDF 文档处理，支持文本提取、格式转换
type: task
version: "0.1.0"
---

# PDF Skill

## 能力

- PDF 文本提取
- PDF 转 Markdown

## 使用示例

```
请提取这个 PDF 的文本内容
```
```

**Frontmatter 字段**：

| 字段 | 必填 | 说明 |
|------|------|------|
| `name` | ✅ | Skill 名称 |
| `description` | ✅ | Skill 描述 |
| `type` | ✅ | 类型：task / reference |
| `version` | ❌ | 版本号，默认 "0.1.0" |

## 📦 内置 Skills

### PDF Skill

```yaml
name: pdf
description: PDF 文档处理，支持文本提取、格式转换
type: task
```

### DOCX Skill

```yaml
name: docx
description: Word 文档处理，支持读取、编辑
type: task
```

### XLSX Skill

```yaml
name: xlsx
description: Excel 表格处理，支持读取、数据分析
type: task
```

## 🔄 Agent 系统提示注入

```
你是 JackClaw，一个飞书工作助手。

## 可用技能

可用 Skill：
- **pdf**: PDF 文档处理，支持文本提取、格式转换
- **docx**: Word 文档处理，支持读取、编辑
- **xlsx**: Excel 表格处理，支持读取、数据分析

## 使用说明

- 用户发送文件时，会自动保存到沙盒路径
- 请根据用户意图选择合适的技能
```

## 📊 设计决策

### D-01: Skill 配置格式

**问题**: 如何定义 Skill？

**方案**: SKILL.md（Markdown + YAML frontmatter）

```
优点：
- 可读性好
- 支持文档
- 易于编辑
```

### D-02: Skill 类型

| 类型 | 说明 | 执行方式 |
|------|------|---------|
| `task` | 任务型 | 启动 Sub-Crew，调用沙盒 |
| `reference` | 参考型 | 返回指令文本，不执行 |

**MVP**: 仅加载元数据，不实现执行

## 🚀 使用

```bash
# 查看加载日志
python -m jackclaw.main
# 输出: Loaded skill: pdf
# 输出: Loaded skill: docx
# 输出: Loaded skill: xlsx

# TestAPI 测试
curl -X POST http://127.0.0.1:9090/api/test/message \
  -d '{"routing_key": "p2p:ou_test", "content": "你能做什么？"}'
# 回复会包含 Skills 列表
```

## ➡️ 下一步

[Phase 4: 沙盒集成](../feature/phase-4-sandbox)
