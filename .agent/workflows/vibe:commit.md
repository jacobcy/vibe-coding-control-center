---
name: "vibe:commit"
description: Commit-and-publication workflow that routes commit grouping and PR slicing to the vibe-commit skill.
category: Workflow
tags: [workflow, vibe, git, commit, orchestration]
---

# vibe:commit

**Input**: 运行 `/vibe-commit`，检查当前改动并准备提交或发 PR。

## Steps

1. 回复用户：`我会先检查工作区与当前 flow，运行 pre-commit 验证格式，再委托 vibe-commit skill 处理提交分组和 PR 切片。`
2. 读取当前工作区和 flow 基本事实；若工作区脏或分支语义复杂，继续委托 `skills/vibe-commit/SKILL.md`。
3. **Pre-commit 强制验证**（硬规定，不可跳过）：
   - 运行 `uv run black src tests/vibe3` 格式化代码
   - 运行 `uv run ruff check --fix src tests/vibe3` 修复 lint 问题
   - 若有格式化修改，提交临时 commit → soft reset → 保留修改在工作区
   - 运行 `pre-commit run --all-files` 确保所有检查通过
   - 不允许使用 `--no-verify` 跳过
   - 任何错误（mypy、shellcheck、LOC 超限等）必须修复后才能继续
   - 格式化修改将分散到后续各功能 commit 中，不保留单独的格式化 commit
4. 在任何 commit 分组前，先做最小 metadata preflight：
   - 读取 `vibe flow show --json`
   - 若存在 `current_task`，继续读取 `vibe task show <task-id> --json`
   - 若 `current_task` 缺失、无法解析，或 `runtime_branch` 与当前 flow branch 不一致，则 hard block
   - 若缺少 `issue_refs`、`roadmap_item_ids`、`spec_standard/spec_ref`，则至少报告 warning
5. 由 `vibe-commit` skill 负责：
   - 改动分类
   - commit 分组
   - 串行多 PR 判断
   - 何时使用 `vibe flow new <name> --branch <ref>`
   - 何时调用 `vibe flow pr --base <ref>`
6. PR 发出后，当前 workflow 只负责把结果交回用户，并提示下一步先去 `/vibe-integrate` 收集或确认 review evidence。
7. 只有当 review evidence 已存在，且 PR 已可 merge 或已 merged 时，才提示进入 `/vibe-done` / `vibe flow done` 收口。

## Boundary

- workflow 不重写 `vibe-commit` skill 的业务逻辑。
- workflow 只负责编排，不承载复杂业务逻辑；review evidence 的判定与 `vibe flow done` 的 merge gate 由 skill / shell 真源负责。
- 若当前 flow 已有 PR 且用户要开始新目标，默认在当前目录创建新的逻辑 flow，不得自行新建物理 worktree。
- `vibe flow pr` 是 shell 发布入口；`gh pr create` 不是 workflow 真源。
