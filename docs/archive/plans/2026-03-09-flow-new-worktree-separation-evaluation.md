---
document_type: plan
title: Flow New / Worktree Separation Evaluation
status: proposed
author: Codex GPT-5
created: 2026-03-09
last_updated: 2026-03-09
related_docs:
  - docs/standards/v2/git-workflow-standard.md
  - docs/standards/v2/worktree-lifecycle-standard.md
  - docs/standards/v2/command-standard.md
  - docs/standards/v2/shell-capability-design.md
  - lib/flow.sh
  - scripts/rotate.sh
  - alias/worktree.sh
---

# Flow New / Worktree Separation Evaluation

## Goal

评估 `vibe flow new` 与 `worktree` 创建能力应如何分离，满足以下目标：

- 保持 `flow`、`branch`、`worktree` 概念分离
- 支持当前目录串行切换下一个交付 `flow`
- 覆盖 dirty worktree、已提交 PR 后续切片、多 PR 拆分等边缘情况
- 避免让 Shell 隐藏 workflow 编排

## Non-Goals

- 本文不直接修改 `lib/flow.sh`
- 本文不重写 `wtnew` / `vnew` 的并行 worktree 能力
- 本文不决定具体实现细节和迁移步骤顺序

## Tech Stack

- Zsh CLI
- Git / git worktree
- GitHub CLI
- `bin/vibe` -> `lib/*.sh`

## Current Facts

1. 标准已经明确：
   - `flow` 是交付切片，不等于 `worktree`，也不等于 `branch`
   - 新 `flow` 不强制要求新 `worktree`
   - 并行交付才优先需要独立 `worktree`
2. 当前实现不一致：
   - `vibe flow new` 直接走 `_flow_new_worktree`
   - 物理效果是“创建 sibling worktree + 新 branch”
   - 这让 `flow new` 实际上更像 `worktree new`
3. 现有能力已经分裂：
   - `wtnew` / `vnew` 负责物理 worktree 创建
   - `scripts/rotate.sh` 负责当前目录串行切 branch，并可带入 stash
4. 现有审计已经指出：
   - `flow new` 不应越权承载完整 workflow
   - Shell 应提供原子能力，而不是把“交付切换 + 物理现场创建”混成一个命令

## Option A

### 定义

将 `vibe flow new` 改造成“当前目录创建新 flow / 新 branch”，并吸收 `rotate.sh` 的 stash 逻辑，例如：

```bash
vibe flow new <name> --branch <base-ref> [--save-stash]
```

物理 worktree 创建继续留给 `wtnew` / `vnew`。

### 优点

- 最符合 `command-standard` 中 `flow new = 创建现场` 的语义
- 最符合 `git-workflow-standard` 中“新 flow 不强制新建 worktree”
- 最符合 `worktree-lifecycle-standard` 中“允许复用当前目录承载新的 flow”
- 避免 `flow new` 与 `wtnew` 重复造同类能力

### 风险

- 是一个明显的命令语义变更
- 现有文档、workflow、skill 中所有“`flow new` = 新 worktree”表述都要跟着修
- 旧用户心智会断裂，迁移成本最高

## Option B

### 定义

保留 `vibe flow new` 继续创建新 worktree；新增：

```bash
vibe flow switch <name> --branch <base-ref> [--save-stash]
```

`flow switch` 负责当前目录串行切换到新的 `flow` / `branch`，可吸收 `rotate.sh` 逻辑。

### 优点

- 迁移风险最低
- 不会立刻破坏现有 `flow new` 使用方式
- 可以尽快把“当前目录串行切 flow”收敛成正式能力

### 风险

- 标准语义会继续分叉：`flow new` 仍然名不副实
- `flow new` 与 `flow switch` 都在做 flow 级动作，但一个夹带 worktree，一个不夹带
- 长期看需要再次收敛，否则文档和 skill 会持续出现歧义

## Option C

### 定义

让 `vibe flow new` 双模：

```bash
vibe flow new <name> --worktree
vibe flow new <name> --reuse-current [--save-stash]
```

### 结论

不推荐。

### 原因

- 一个命令同时表达两类现场创建方式，语义过重
- 会把“是否复用当前目录”这种编排选择塞回一个命令里
- 违反 `shell-capability-design` 的原子能力倾向

## Recommendation

推荐 **Option A 作为目标模型**，理由如下：

1. 它与现行标准最一致。
2. 并行能力已经有 `wtnew` / `vnew` 承载，不需要 `flow new` 重复承担。
3. 串行交付正是当前最缺、且与你现在的 PR 切片场景最匹配的能力。
4. `rotate.sh` 的能力本质是“复用当前 worktree 承载新 flow”，应该上收为正式 Shell 能力，而不是继续作为游离脚本。

但从迁移风险看，建议采用 **两阶段落地**：

- Phase 1：先新增 `vibe flow switch`，把 `rotate.sh` 能力正式化
- Phase 2：再把 `vibe flow new` 退回到标准语义，或明确废弃其“创建 worktree”含义

也就是说：

- **最终模型**：Option A
- **低风险迁移路径**：先落 Option B，再收敛到 Option A

## Edge Cases That Must Be Covered

无论最后选 A 还是 B，实现都必须覆盖以下边缘情况：

1. dirty worktree
   - 默认拒绝切换
   - 只有显式 `--save-stash` 才允许带入未提交改动
2. 当前分支是 `main/master`
   - 默认拒绝直接旋转保护分支
3. 当前 PR 已提交，但本地改动属于下一个交付目标
   - 必须切到新 `flow` / `branch`
4. 当前 PR 已提交，但改动只是 review follow-up
   - 不应切 flow
5. 一个 flow 已混入多个交付目标
   - 必须先拆组，再进入新的 `flow`
6. 目标 branch 已存在
   - 必须明确定义是切换、失败、还是要求显式确认
7. stash pop 冲突
   - 必须把失败暴露出来，不能静默吞掉
8. worktree dashboard / flow runtime 绑定
   - 必须更新到新的 branch/flow 语义，不能只切 Git 不切运行时事实

## Files To Modify

若进入实现，预计涉及：

- `lib/flow.sh`
- `lib/flow_help.sh`
- `tests/test_flow.bats`
- `scripts/rotate.sh` 或其逻辑迁移目标
- `docs/standards/v2/command-standard.md` 或相关帮助/计划文档
- `skills/vibe-commit/SKILL.md` 及引用它的 workflow 文档

## Test Commands

本次为讨论文档，未执行实现测试。

实现阶段至少应验证：

- `bats tests/test_flow.bats`
- `bin/vibe flow help`
- `bin/vibe flow new --help`
- `bin/vibe flow switch --help`（若采用过渡方案）

## Expected Result

评估结论应明确：

- 并行 PR 继续由独立 worktree 能力承载
- 串行 PR 切片需要正式 flow 切换能力
- `rotate.sh` 的逻辑应该被收敛为受标准约束的 Shell 能力
- 长期目标是让 `flow` 与 `worktree` 彻底分离

## Change Summary

- Added: 1 plan document
- Modified: 0 source files
- Removed: 0 files
