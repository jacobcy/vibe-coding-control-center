---
name: "Vibe: Issue"
description: 启动 Issue 创建与预旋工作流
---

# Vibe Issue Workflow

**指令**：运行 `/vibe-issue` 开启治理引导。

## 运行步骤

1. **调用技能**
   - 触发 `vibe-issue` 技能。
   
2. **遵循 Gate 约束**
   - **Template Gate**: 必须匹配 `.github/ISSUE_TEMPLATE`。
   - **Duplication Gate**: 必须通过 `gh issue list` 查重。
   - **Roadmap Gate**: 必须运行 `vibe roadmap list` 检查对齐。

3. **物理执行**
   - 技能编排 `gh issue create` 命令并执行。

4. **完成**
   - 输出 Issue 链接。
