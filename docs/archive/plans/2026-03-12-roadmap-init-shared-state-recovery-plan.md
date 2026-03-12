# Roadmap Init Shared State Recovery Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 增加 `vibe roadmap init [--force]`，用于安全重建 `.git/vibe` 共享真源骨架，并修复会污染真实 shared state 的相关测试隔离。

**Architecture:** 保持 `scripts/init.sh` 继续承担环境/skills/worktree setup，不混入 shared state 重建语义。新增一个窄的 `roadmap init` shell 子命令，只负责创建或强制重建 `roadmap.json`、`registry.json`、`worktrees.json` 及必要目录；恢复远端 mirror 继续通过 `vibe roadmap sync` 单独执行。测试侧优先修正 `git-common-dir` 隔离，避免 fixture 再写入真实 `.git/vibe`。

**Tech Stack:** Zsh shell (`bin/vibe`, `lib/roadmap*.sh`), shared state JSON under `$(git rev-parse --git-common-dir)/vibe`, `jq`, Bats

---

## Goal

- 增加 `vibe roadmap init`：在 shared state 缺失时创建最小骨架。
- 增加 `vibe roadmap init --force`：强制清空并重建 shared state 骨架。
- 明确 `vibe roadmap init` 不负责远端同步、不负责 task 历史恢复。
- 修复高风险测试隔离，避免 fixture 污染真实 `.git/vibe`。

## Non-Goals

- 本计划不自动恢复历史 task 数据。
- 本计划不把 shared state 重建塞进 `scripts/init.sh`。
- 本计划不实现一体化的顶层 `vibe init`。
- 本计划不自动执行 `vibe roadmap sync`。
- 本计划不处理历史 `.bak` 文件的自动回放或 merge。

## Current Decision To Encode

1. `vibe roadmap init` 挂在 roadmap shell 层级下，而不是新增顶层 `vibe init`。
2. `vibe roadmap init` 只创建共享真源骨架：
   - `roadmap.json`
   - `registry.json`
   - `worktrees.json`
   - 必要目录，例如 `tasks/`、`pending-tasks/`
3. `vibe roadmap init --force` 允许强制重建共享真源，但不自动 sync。
4. 远端恢复路径固定为：
   - `vibe roadmap init --force`
   - `vibe roadmap sync`
   - task 数据人工补录
5. `scripts/init.sh` 继续只做环境/worktree setup，不承担 shared state 恢复。
6. 测试必须把 `git rev-parse --git-common-dir` 指向 fixture；任何会碰 shared state 的测试都不能落到真实 `.git/vibe`。

## Files To Modify

- Modify: `bin/vibe`
- Modify: `lib/roadmap.sh`
- Modify: `lib/roadmap_init.sh` or existing roadmap module split point
- Modify: `lib/roadmap_project_sync.sh` or shared roadmap bootstrap helper if needed for schema reuse
- Modify: `scripts/init.sh` (help text only if needed to clarify non-responsibility; do not change behavior unless necessary)
- Modify: `tests/roadmap/*`
- Modify: `tests/flow/*` or `tests/task/*` affected by shared-state pollution risk
- Modify: `tests/helpers/*`
- Modify: `docs/standards/command-standard.md`
- Modify: `skills/vibe-roadmap/SKILL.md`

## Step Tasks

### Task 1: Freeze command semantics and write failing tests

**Files:**
- Modify: `tests/roadmap/test_roadmap_*.bats`
- Modify: `tests/helpers/roadmap_common.bash`
- Modify: `docs/standards/command-standard.md`

**Steps:**
1. Write a failing Bats test for `vibe roadmap init` creating missing shared state files and directories.
2. Write a failing Bats test for `vibe roadmap init --force` replacing existing corrupted shared state with empty skeleton data.
3. Write a failing doc-regression assertion that `roadmap init` does not imply `roadmap sync` or task recovery.
4. Run the focused roadmap tests and confirm they fail on the missing command/old wording.
5. Commit.

### Task 2: Implement `vibe roadmap init`

**Files:**
- Modify: `bin/vibe`
- Modify: `lib/roadmap.sh`
- Create or Modify: `lib/roadmap_init.sh`

**Steps:**
1. Add `init` subcommand parsing under `vibe roadmap`.
2. Implement a helper that resolves `git-common-dir`, ensures `vibe/` exists, and creates the minimal shared-state files/directories when missing.
3. Define empty skeleton payloads for:
   - `roadmap.json`
   - `registry.json`
   - `worktrees.json`
4. Make non-`--force` mode idempotent: existing files remain untouched.
5. Run focused roadmap tests and confirm the new command passes.
6. Commit.

### Task 3: Implement `--force` rebuild semantics

**Files:**
- Modify: `lib/roadmap_init.sh`
- Test: `tests/roadmap/test_roadmap_*.bats`

**Steps:**
1. Extend `roadmap init` with `--force`.
2. In force mode, replace corrupted or stale shared-state files with fresh skeleton data.
3. Preserve the command boundary: no automatic `roadmap sync`, no task rehydration.
4. Run the focused `--force` test and confirm it passes.
5. Commit.

### Task 4: Repair test isolation around shared state

**Files:**
- Modify: `tests/helpers/flow_common.bash`
- Modify: `tests/helpers/roadmap_common.bash`
- Modify: `tests/task/test_task_helper.zsh`
- Modify: targeted `tests/flow/*.bats`, `tests/task/*.bats`, `tests/roadmap/*.bats`

**Steps:**
1. Audit the tests that touch `registry.json` / `worktrees.json` and identify any path that can fall through to the real `git-common-dir`.
2. Add or tighten helper mocks so every such test redirects `git rev-parse --git-common-dir` into a fixture path.
3. Remove any implicit dependency on the real `.git/vibe` state.
4. Run the affected flow/task/roadmap tests and confirm they pass without mutating real shared state.
5. Commit.

### Task 5: Align docs and roadmap skill wording

**Files:**
- Modify: `docs/standards/command-standard.md`
- Modify: `skills/vibe-roadmap/SKILL.md`
- Test: `tests/skills/test_skills.bats`

**Steps:**
1. Document `vibe roadmap init [--force]` as shared-state skeleton initialization only.
2. State explicitly that remote recovery remains a separate `vibe roadmap sync` step.
3. State explicitly that task history/task registry recovery is manual follow-up, not part of `roadmap init`.
4. Add or refine skill/doc tests to lock this wording.
5. Run the skill/doc regression tests and confirm they pass.
6. Commit.

### Task 6: Full regression and smoke validation

**Files:**
- Test: `tests/roadmap/*.bats`
- Test: `tests/flow/*.bats`
- Test: `tests/task/*.bats`
- Test: `tests/skills/test_skills.bats`

**Steps:**
1. Run the focused roadmap, flow, task, and skill test suites relevant to the touched files.
2. In a fixture-backed environment, verify this recovery sequence:
   - `vibe roadmap init --force`
   - `vibe roadmap sync`
3. Confirm the result is:
   - shared-state files recreated
   - roadmap mirror restorable by sync
   - task data still absent unless manually re-added
4. If contradictions remain, fix the authoritative command/help/doc file first.
5. Commit the final reconciliation change if needed.

## Test Command

```bash
bats tests/roadmap/*.bats
bats tests/flow/*.bats
bats tests/task/*.bats
bats tests/skills/test_skills.bats
```

## Expected Result

- `vibe roadmap init` can create missing `.git/vibe` shared-state skeleton safely.
- `vibe roadmap init --force` can reset corrupted shared-state files to empty skeleton data.
- `vibe roadmap init` does not auto-run `roadmap sync`.
- `scripts/init.sh` remains an environment/setup script, not a shared-state recovery command.
- tests no longer mutate the real shared-state files when using fixtures.
- shared-state recovery path becomes:
  - `vibe roadmap init --force`
  - `vibe roadmap sync`
  - manual task re-registration

## Change Summary

- Modified: 8-12 files
- Added: 0-1 files depending on whether `lib/roadmap_init.sh` is split out
- Approximate lines: 180-320
