# Vibe New / Task / Flow Convergence Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 收敛 `vibe new`、`vibe task`、`vibe flow` 的职责边界，让 `/vibe-new` 成为唯一智能入口，并支持“当前目录开新任务”与“新目录开新任务”两种模式。

**Architecture:** Shell 负责确定性状态修改与 Git/registry 脏活，Slash 只负责交互与编排。`vibe task` 负责任务配置与绑定，`vibe flow` 负责流程推进，`vibe new` 负责入口整合和模式选择。实现上优先复用现有 `lib/task.sh`、`lib/flow.sh`、`scripts/rotate.sh`，避免新增独立命令或 Slash。

**Tech Stack:** Zsh, jq, git, bats, GitHub CLI (`gh`)

---

## Goal

- 为 `vibe task` 增加最小必要的 `list / add / update / remove` 能力。
- 让 `/vibe-new` 底层可通过 shell 支持：
  - 当前目录原地开新任务
  - 新目录创建并开新任务
- 将 agent 对应的 `git config user.name/user.email` 统一下沉到 shell 流程。
- 停止继续引入新的顶层命令或独立 Slash（如 `/vibe-rotate`）。

## Non-Goals

- 不在本期实现完整的 task schema 重构。
- 不实现过度通用的 task CRUD 字段集合。
- 不引入新的数据库、缓存层或复杂配置系统。
- 不重写整个 `vibe-orchestrator` 或 skills 体系。
- 不实现 GPG/SSH commit signing。

## Tech Stack

- CLI: `bin/vibe`
- Shell modules: `lib/task.sh`, `lib/flow.sh`, `lib/config.sh`, `lib/utils.sh`
- Existing helper: `scripts/rotate.sh`
- Tests: `tests/test_task.bats`, `tests/test_flow.bats`, 新增或扩展 `tests/test_vibe.bats`

## Task 1: 定义 `vibe task` 的最小子命令边界

**Files:**
- Modify: `docs/tasks/2026-03-02-rotate-alignment/plan-v1.md`
- Modify: `docs/tasks/2026-03-02-rotate-alignment/README.md`
- Modify: `docs/tasks/2026-03-02-command-slash-alignment/README.md`

**Step 1: 对齐任务文档**

明确：
- `vibe task` 负责配置与绑定
- `vibe flow` 负责流程推进
- `/vibe-new` 负责入口编排

**Step 2: 写明当前最小子命令集合**

仅定义：
- `vibe task list`
- `vibe task add`
- `vibe task update`
- `vibe task remove`

`update` 当前仅覆盖：
- `--status`
- `--agent`
- `--worktree`
- `--branch`
- `--bind-current`
- `--next-step`

**Step 3: 验证文档收敛**

Run:
```bash
rg -n "vibe task (list|add|update|remove)|/vibe-new|不新增独立的 /vibe-rotate|task.*配置|flow.*流程" \
  docs/tasks/2026-03-02-rotate-alignment/README.md \
  docs/tasks/2026-03-02-rotate-alignment/plan-v1.md \
  docs/tasks/2026-03-02-command-slash-alignment/README.md
```

Expected:
- 文档只保留一套一致的职责模型
- 不再把 `/vibe-rotate` 当成目标方案

## Task 2: 为 `vibe task` 增加子命令解析骨架

**Files:**
- Modify: `lib/task.sh`
- Modify: `bin/vibe`
- Test: `tests/test_task.bats`

**Step 1: 写失败测试**

新增测试覆盖：
- `vibe task list` 复用当前 overview 输出
- `vibe task add --help`
- `vibe task update --help`
- `vibe task remove --help`
- `vibe task update` 在缺少必填参数时返回错误

**Step 2: 运行测试确认 RED**

Run:
```bash
bats tests/test_task.bats
```

Expected:
- 新增的子命令测试失败
- 现有 overview 测试仍可运行

**Step 3: 写最小实现**

在 `lib/task.sh` 中：
- 增加 `list/add/update/remove` dispatcher
- 保留当前裸 `vibe task` 等价于 `vibe task list`
- 为 `add/update/remove` 先提供参数校验与帮助输出

**Step 4: 运行测试确认 GREEN**

Run:
```bash
bats tests/test_task.bats
```

Expected:
- 所有 task 相关测试通过

## Task 3: 实现 `vibe task update` 的最小写入能力

**Files:**
- Modify: `lib/task.sh`
- Modify: `lib/utils.sh` (仅当需要复用 JSON/agent helper)
- Test: `tests/test_task.bats`

**Step 1: 写失败测试**

覆盖以下场景：
- 更新 registry 中 task 的 `status`
- 更新 task 的 `next_step`
- `--bind-current` 时同步当前 worktree 绑定
- 更新 worktree 的 `branch`
- 更新/设置 agent
- 非白名单 agent 默认拒绝
- `-f` 允许强制写入，并将 email slug 化

**Step 2: 运行测试确认 RED**

Run:
```bash
bats tests/test_task.bats --filter "update"
```

Expected:
- 新增 update 行为测试失败

**Step 3: 写最小实现**

实现原则：
- 所有 JSON 修改都通过 `jq`
- 只写 `.git/vibe/registry.json`、`.git/vibe/worktrees.json` 和本地 `.vibe/*` 缓存
- agent 白名单固定为：
  - `codex`
  - `antigravity`
  - `trae`
  - `claude`
  - `opencode`
  - `kiro`
- `git config` 规则：
  - 默认：`user.name=<agent>` `user.email=<agent>@vibe.coding`
  - `-f`：`user.name=<raw-agent>` `user.email=<slug>@vibe.coding`

**Step 4: 运行测试确认 GREEN**

Run:
```bash
bats tests/test_task.bats
```

Expected:
- `update` 的 JSON 写入与 agent 校验行为全绿

## Task 4: 让 `vibe flow start` 支持基于已有 task 启动

**Files:**
- Modify: `lib/flow.sh`
- Modify: `tests/test_flow.bats`

**Step 1: 写失败测试**

覆盖：
- `vibe flow start --task <task-id>` 在当前目录模式下读取 task metadata
- `vibe flow start --task <task-id> --agent <agent>` 生成 `<agent>/<task-id>` 分支名
- 缺少 task 时报错

**Step 2: 运行测试确认 RED**

Run:
```bash
bats tests/test_flow.bats
```

Expected:
- 新增 start 语义测试失败

**Step 3: 写最小实现**

实现原则：
- 尽量兼容现有 `vibe flow start <feature>`
- 新增 `--task` 模式，不立即删除旧接口
- 不再依赖目录名作为 task 真源
- 当前目录模式下可复用 `scripts/rotate.sh` 的“对齐主干 + 重建分支”逻辑，但由 `flow` 统一编排

**Step 4: 运行测试确认 GREEN**

Run:
```bash
bats tests/test_flow.bats
```

Expected:
- 旧 `flow` 测试通过
- 新增 task-aware start 测试通过

## Task 5: 让 `/vibe-new` 复用 shell 能力，而不是自行改状态文件

**Files:**
- Modify: `.agent/workflows/vibe-new.md`
- Modify: `skills/vibe-orchestrator/SKILL.md`
- Modify: `skills/vibe-new/SKILL.md` (若存在相关入口说明)

**Step 1: 对齐文档与 skill 说明**

明确：
- `/vibe-new` 只做意图判断与最少交互
- shell 命令负责真正写 registry/worktree/.vibe
- 支持两种模式：
  - 当前目录开新任务
  - 新目录开新任务

**Step 2: 文档验证**

Run:
```bash
rg -n "当前目录开新任务|新目录开新任务|Shell 负责脏活|不得直接修改 registry|vibe task update|vibe flow start" \
  .agent/workflows/vibe-new.md skills/vibe-orchestrator/SKILL.md skills/vibe-new/SKILL.md 2>/dev/null
```

Expected:
- `/vibe-new` 的职责与 shell 边界一致

## Task 6: 补齐端到端命令帮助与回归验证

**Files:**
- Modify: `bin/vibe`
- Modify: `lib/task.sh`
- Modify: `lib/flow.sh`
- Test: `tests/test_vibe.bats`

**Step 1: 写失败测试**

覆盖：
- `vibe help` 中出现 `task add/update/remove`
- `vibe task --help`
- `vibe flow start --task --help`

**Step 2: 运行测试确认 RED**

Run:
```bash
bats tests/test_vibe.bats
```

Expected:
- 新增帮助文案测试失败

**Step 3: 写最小实现**

只更新帮助和 usage 文案，不做额外抽象。

**Step 4: 运行完整验证**

Run:
```bash
bats tests/test_task.bats
bats tests/test_flow.bats
bats tests/test_vibe.bats
bash scripts/lint.sh
```

Expected:
- 所有相关 bats 测试通过
- shell lint `0 errors`

## Files To Modify

- `bin/vibe`
- `lib/task.sh`
- `lib/flow.sh`
- `lib/utils.sh`（仅在需要共享 helper 时）
- `.agent/workflows/vibe-new.md`
- `skills/vibe-orchestrator/SKILL.md`
- `skills/vibe-new/SKILL.md`（若存在）
- `tests/test_task.bats`
- `tests/test_flow.bats`
- `tests/test_vibe.bats`
- `docs/tasks/2026-03-02-rotate-alignment/README.md`
- `docs/tasks/2026-03-02-rotate-alignment/plan-v1.md`
- `docs/tasks/2026-03-02-command-slash-alignment/README.md`

## Test Command

```bash
bats tests/test_task.bats
bats tests/test_flow.bats
bats tests/test_vibe.bats
bash scripts/lint.sh
```

## Expected Result

- `vibe task` 拥有最小 `list/add/update/remove` 能力
- `vibe flow start` 能基于 task 启动
- `/vibe-new` 不再承担复杂文件修改逻辑
- 当前目录开任务与新目录开任务都走统一 shell 路径
- agent 对应的 git identity 写入规则生效
- 没有新增独立顶层命令或新的 Slash 心智模型

## Change Summary

- 新增：约 `120-220` 行
- 修改：约 `120-200` 行
- 删除：约 `20-60` 行
- 主要集中在 `lib/task.sh`、`lib/flow.sh`、相关 tests 与 `/vibe-new` 文档契约
