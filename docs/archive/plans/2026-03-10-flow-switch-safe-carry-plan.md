---
title: "Flow Switch Safe Carry Implementation Plan"
date: "2026-03-10"
status: "draft"
author: "GPT-5.4"
related_docs:
  - docs/plans/2026-03-10-flow-switch-safe-carry-design.md
  - docs/standards/git-workflow-standard.md
  - docs/standards/worktree-lifecycle-standard.md
  - docs/standards/v2/command-standard.md
  - lib/flow.sh
  - lib/flow_runtime.sh
  - lib/flow_help.sh
  - tests/test_flow.bats
  - tests/flow/test_flow_lifecycle.bats
---

# Flow Switch Safe Carry Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让 `vibe flow switch (shell)` 默认安全携带当前未提交改动，并使用精确 stash ref 恢复现场；同时保持 `vibe flow new (shell)` 继续采用显式 `--save-unstash` 的保守语义。

**Architecture:** 先用测试固定 `switch` 的默认 carry 语义与失败回滚要求，再把 `new/switch` 当前重复的 stash 迁移逻辑提取为共享 helper，最后同步 help 与标准文档，确保外部命令语义和内部恢复机制一致。

**Tech Stack:** Zsh CLI (`lib/flow.sh`, `lib/flow_runtime.sh`, `lib/flow_help.sh`), Bats (`tests/test_flow.bats` 或拆分后的 `tests/flow/*.bats`), Markdown。

---

### Task 1: 固定 `flow switch` 的默认安全语义

**Files:**
- Modify: `tests/test_flow.bats` 或 `tests/flow/test_flow_lifecycle.bats`
- Inspect: `lib/flow_runtime.sh`
- Inspect: `lib/flow_help.sh`

**Step 1: 写 dirty switch 默认自动 carry 的失败测试**

覆盖至少以下场景：
- dirty worktree 下执行 `vibe flow switch <name>`，不再要求 `--save-stash`
- 测试应验证：发生 stash 保存、切换目标 branch、更新 runtime、恢复改动

**Step 2: 写干净 switch 不创建 stash 的失败测试**

覆盖：
- `git status --porcelain` 为空时，switch 不应调用 stash 相关命令

**Step 3: 写帮助文案回归测试**

覆盖：
- `vibe flow switch --help` 不再显示 `--save-stash`
- 帮助中明确 dirty worktree 会默认安全带入

**Step 4: 运行测试确认当前实现失败**

Run: `bats tests/test_flow.bats`

Expected:
- 新增 `switch` 默认 carry 用例失败
- help 文案用例失败

### Task 2: 为失败路径补精确恢复测试

**Files:**
- Modify: `tests/test_flow.bats` 或 `tests/flow/test_flow_lifecycle.bats`
- Inspect: `lib/flow_runtime.sh`

**Step 1: 写 checkout 失败时恢复原现场的测试**

覆盖：
- stash 已保存
- 切换目标分支失败
- 原分支现场恢复，不吞 stash

**Step 2: 写 runtime 更新失败时恢复原现场的测试**

覆盖：
- branch 已切过去
- `_flow_update_current_worktree_branch` 失败
- 命令要么切回原分支并恢复改动，要么明确暴露手动恢复信息

**Step 3: 写多 stash 并存时仍恢复本次 stash 的测试**

覆盖：
- 历史 stash 已存在
- 本次操作必须精确定位当前 stash ref
- 不允许恢复错对象

**Step 4: 写 apply 冲突时的失败测试**

覆盖：
- `git stash apply <ref>` 失败
- 输出明确包含恢复失败事实和 stash ref 提示

### Task 3: 提取共享 carry helper

**Files:**
- Modify: `lib/flow_runtime.sh`
- Modify: `lib/flow.sh`

**Step 1: 抽出保存当前 dirty 状态的 helper**

helper 需要完成：
- 判断是否 dirty
- 生成唯一 stash message
- 执行 `git stash push -u -m ...`
- 精确解析并返回本次 stash ref

**Step 2: 抽出恢复 stash ref 的 helper**

helper 需要完成：
- 对精确 ref 执行 `git stash apply <ref>`
- 成功后执行 `git stash drop <ref>`
- 失败时保留 ref 并输出诊断信息

**Step 3: 抽出失败回滚 helper**

helper 需要覆盖：
- 目标切换失败时恢复原 branch
- 结合 stash ref 恢复原现场
- 不做静默吞错

### Task 4: 切换 `flow switch` 到默认 carry 语义

**Files:**
- Modify: `lib/flow_runtime.sh`
- Modify: `lib/flow_help.sh`

**Step 1: 移除 `--save-stash` 参数解析**

要求：
- `switch` 不再读取 `--save-stash`
- dirty worktree 自动进入 carry 流程
- 干净 worktree 直接切换

**Step 2: 保持现有 flow 边界检查不变**

包括：
- `main/master` 保护
- branch 名合法性
- 目标 flow 必须存在
- 已有 PR 历史的 flow 仍拒绝 resume

**Step 3: 更新帮助文案**

要求：
- 删除 `--save-stash`
- 明确 switch 默认安全带入当前未提交改动

### Task 5: 保持 `flow new` 的显式带入语义，但改用共享 helper

**Files:**
- Modify: `lib/flow.sh`
- Modify: `lib/flow_help.sh`

**Step 1: 保留 `--save-unstash` 的外部契约**

要求：
- `new` 默认仍拒绝 dirty worktree
- 只有显式 `--save-unstash` 才进入 carry 流程

**Step 2: 将 `new` 的 stash 保存/恢复逻辑改为复用共享 helper**

要求：
- 不再使用重复的裸 `git stash pop`
- 与 `switch` 共用精确 stash ref 恢复机制

**Step 3: 跑回归测试确认 `new` 旧语义不回归**

Run: `bats tests/test_flow.bats`

Expected:
- `new` 相关旧测试通过
- `switch` 新语义测试通过

### Task 6: 同步文档与标准

**Files:**
- Modify: `docs/standards/git-workflow-standard.md`
- Modify: `docs/standards/worktree-lifecycle-standard.md`
- Modify: `docs/plans/2026-03-10-flow-switch-safe-carry-design.md`

**Step 1: 同步 `switch` 默认安全 carry 的描述**

要求：
- 目录复用场景不再把 dirty worktree 视为默认阻塞
- 文档中要明确这属于 `switch` 的默认能力

**Step 2: 明确 `new` 与 `switch` 的差异**

要求：
- `new` 默认保守
- `switch` 默认安全

### Task 7: 汇总验证

**Files to inspect during execution:**
- `lib/flow.sh`
- `lib/flow_runtime.sh`
- `lib/flow_help.sh`
- `tests/test_flow.bats` 或 `tests/flow/*.bats`

**Step 1: 跑 flow 相关测试**

Run: `bats tests/test_flow.bats`

Expected:
- `new` / `switch` / help 相关用例全部通过

**Step 2: 跑拆分后的 flow 测试集合（若已完成 test suite split）**

Run: `bats tests/flow/*.bats`

Expected:
- lifecycle / PR / help 相关用例通过

**Step 3: 跑帮助校验**

Run:

```bash
bin/vibe flow switch --help
bin/vibe flow new --help
```

Expected:
- `switch` 不再出现 `--save-stash`
- `new` 仍保留 `--save-unstash`

## Expected Result

- `vibe flow switch (shell)` 默认保证安全切换，不再要求用户记住额外参数。
- `vibe flow new (shell)` 仍维持显式带入改动的保守语义。
- `new` 与 `switch` 的共享恢复逻辑变成单一实现，不再依赖裸 `stash pop`。