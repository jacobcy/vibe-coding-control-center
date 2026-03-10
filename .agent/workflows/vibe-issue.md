---
name: "Vibe: Issue"
description: Handle issue intake for this repo: create, deduplicate, template-check, and label a GitHub issue before roadmap planning.
---

# Vibe Issue Workflow

**指令**：优先运行 `/vibe-issue create "<标题>"` 开启治理引导；若标题未定，可先运行 `/vibe-issue` 进入引导。

`repo issue` 是来源层对象，不是本地执行 task，也不是 flow runtime 的主语。

## 运行步骤

1. **调用技能**
   - 触发 `vibe-issue` 技能。
   
2. **遵循 Gate 约束**
   - **Template Gate**: 必须匹配 `.github/ISSUE_TEMPLATE`。
   - **Duplication Gate**: 必须通过 `gh issue list` 查重。
   - **Roadmap Gate**: 必须先运行 `vibe roadmap list --json`，读取 shell 输出后再检查是否已存在对应的 `GitHub Project item` / `roadmap item` 镜像。

3. **物理执行**
   - 技能编排 `gh issue create` 命令并执行。
   - 创建时必须附带 `vibe-task` label，确保后续 `vibe roadmap sync` 以 GitHub Project 语义进行同步，而不是把 issue 直接偷换成本地 task execution record。

4. **完成**
   - 输出 repo issue 链接。
