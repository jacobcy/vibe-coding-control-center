# Vibe Skills 规范标准 (SKILL_STANDARD.md)

所有技能必须遵循统一的 Vibe Skills 治理体系标准：

## 1. 文件结构
```
skills/<name>/
  SKILL.md          # 技能定义（必须）
  README.md         # 使用说明（可选）
  examples/         # 示例（可选）
```

## 2. SKILL.md Frontmatter 必须包含

在文件顶部的 YAML frontmatter 区域，必须提供以下元数据：

```yaml
---
name: <skill-name>
description: <one-line description>
category: process | guardian | audit
trigger: manual | auto | mixed
enforcement: hard | tiered | advisory
phase: exploration | convergence | both
---
```

## 3. 必须包含的章节

每个 `SKILL.md` 必须包含以下 Markdown 标题和内容：

- **System Role**: 技能人格和需要绝对遵守的硬规则
- **Overview**: 用一段话清晰描述该技能的核心目的
- **When to Use**: 触发条件列表（何时该用此技能）
- **Execution Steps**: 具体的执行步骤指南
- **Output Format**: 输出的格式模板（如合规报告模板）
- **What This Skill Does NOT Do**: 边界声明（明确不做的事情，防止范围蔓延）
