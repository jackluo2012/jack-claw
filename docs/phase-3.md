# Phase 3: Skills 系统

## 目标

实现 Skill 加载机制，支持动态加载技能定义。

## 交付物

| 文件 | 状态 | 说明 |
|------|------|------|
| `jackclaw/tools/skill_loader.py` | ✅ | Skill 加载器 |
| `jackclaw/skills/*/SKILL.md` | ✅ | Skill 定义文件 |

## Skill 目录结构

```
jackclaw/skills/
├── pdf/
│   └── SKILL.md
├── xlsx/
│   └── SKILL.md
└── docx/
    └── SKILL.md
```

## SKILL.md 格式

```yaml
---
name: pdf
description: PDF 文件处理
type: task
version: 1.0.0
---

# PDF Skill

详细说明...
```

## 关键特性

- **自动发现**：扫描 skills 目录加载所有 SKILL.md
- **元数据解析**：从 YAML Front Matter 提取 name/description/type/version
- **系统提示注入**：Skill 描述自动注入 Agent 系统提示

## 验证方式

```bash
git checkout feature/phase-3-skills  # 仅远程分支
git checkout remotes/origin/feature/phase-3-skills

pytest tests/ -v
python -m jackclaw.main
```

## 当前状态

**已完成** ✓

- SkillLoader 实现
- 3 个示例 Skill（pdf/xlsx/docx）
- 系统提示自动注入 Skill 描述
