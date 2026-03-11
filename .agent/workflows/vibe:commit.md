---
name: "vibe:commit"
description: Commit-and-publication workflow that routes commit grouping and PR slicing to the vibe-commit skill.
category: Workflow
tags: [workflow, vibe, git, commit, orchestration]
---

# vibe:commit

**Input**: 运行 `/vibe-commit`，检查当前改动并准备提交或发 PR。

## Steps

1. 回复用户：`我会先检查工作区与当前 flow，再委托 vibe-commit skill 处理提交分组和 PR 切片。`
2. 读取当前工作区和 flow 基本事实；若工作区脏或分支语义复杂，继续委托 `skills/vibe-commit/SKILL.md`。
3. 由 `vibe-commit` skill 负责：
   - 改动分类
   - commit 分组
   - 串行多 PR 判断
   - 何时使用 `vibe flow new <name> --branch <ref>`
   - 何时调用 `vibe flow pr --base <ref>`
4. 当前 workflow 只负责把结果交回用户，或在 skill 完成后提示下一步去 `/vibe-integrate` / `/vibe-done`。

## Boundary

- workflow 不重写 `vibe-commit` skill 的业务逻辑。
- 若当前 flow 已有 PR 且用户要开始新目标，默认在当前目录创建新的逻辑 flow，不得自行新建物理 worktree。
- `vibe flow pr` 是 shell 发布入口；`gh pr create` 不是 workflow 真源。
