---
document_type: plan
title: Changelog Message Cache Plan
status: proposed
author: GPT-5 Codex
created: 2026-03-12
last_updated: 2026-03-12
related_docs:
  - lib/flow_pr.sh
  - scripts/bump.sh
  - lib/flow_help.sh
  - skills/vibe-commit/SKILL.md
  - docs/standards/v2/git-workflow-standard.md
related_issues: []
---

# Changelog Message Cache Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复 `vibe flow pr` 在未显式提供 changelog message 时把 `...` 或默认占位文本写入 `CHANGELOG.md` 的问题，并让 agent 在同一 branch / flow 上只需提供一次可用 `--msg`，后续重复执行 `vibe flow pr` 时自动复用。

**Architecture:** 使用共享 git common-dir 下的 branch-keyed 本地缓存目录 `.git/vibe/changelog-msg/` 作为最小状态层。message 的语义属于当前 branch / flow 的发布说明，而不是版本号对象；因此不按 version 建模，不改 task / flow JSON schema，不把临时状态塞进 handoff。

**Tech Stack:** Zsh, Git, jq, Bats, Markdown

---

## Goal / Non-goals

**Goal**
- `vibe flow pr` 首次 bump / 写 changelog 时，若没有显式 `--msg` 且当前 branch 没有已确认缓存，直接报错阻断
- 一旦 agent 显式提供过一次可用 `--msg`，后续同一 branch / flow 再执行 `vibe flow pr` 时自动复用，不再反复提醒
- 禁止 `...`、空字符串、默认占位文本进入 `CHANGELOG.md`
- 让 help / skill 文案明确“首次必须提供可用 changelog message，之后 branch 级缓存自动复用”

**Non-goals**
- 本轮不引入按版本号命名的共享状态文件
- 本轮不修改 task / flow / worktrees 的 JSON schema
- 本轮不做跨 branch 的 changelog message 共享
- 本轮不处理 CHANGELOG 历史占位条目的回填修复

## Problem Statement

当前实现里：

- `lib/flow_pr.sh` 若未传 `--msg`，会从 commit message 推导 `version_msg`
- 推导逻辑会自动拼出 `...`
- `scripts/bump.sh` 再把该字符串直接写进 `CHANGELOG.md`

这导致两个问题：

1. agent 没有显式提供 release note 时，shell 仍然会产出占位式 changelog
2. 同一 branch 若因为 review follow-up 重新跑 `vibe flow pr`，即使之前已经给过一次可用 message，也没有稳定复用机制

用户目标不是“每次都强制再问一次”，而是：

- 第一次必须给出可用 changelog message
- 给过之后，在同一 branch / flow 上不再重复提醒

## Design Decision To Validate

首选方案：

- 把 changelog message 缓存在 `.git/vibe/changelog-msg/<branch-key>.txt`
- key 使用 branch / flow，而不是 version
- `vibe flow pr` 的 message 获取顺序固定为：
  1. 显式 `--msg`
  2. branch-keyed 缓存
  3. 若前两者都没有，则报错阻断
- 若显式 `--msg` 存在，则校验非空、非 `...`、非默认占位文本，并写入 branch 缓存
- 若从缓存命中，则直接复用，不再报错

不采用的方案：

- 按版本号在共享目录下缓存 message
  - 缺点：多 worktree 并发时可能同时计算到同一版本号，语义与并发控制都更复杂
- 把 changelog message 写入 handoff
  - 缺点：handoff 不是共享真源，且它更偏会话记录
- 在当前 worktree `temp/` 下放一次性文件
  - 缺点：不能跨 worktree / 跨会话稳定复用
- 继续允许 `vibe flow pr` 自动回退到占位式 message

## Files To Modify

- `lib/flow_pr.sh`
- `scripts/bump.sh`
- `lib/flow_help.sh`
- `skills/vibe-commit/SKILL.md`
- `tests/flow/test_flow_pr_review.bats`

如需补充共享目录 helper，可优先放在 `lib/flow_pr.sh` 内部，避免无关扩面。

## Tasks

### Task 1: 先把 changelog message gate 收敛成可测试需求

**Files**
- Modify: `tests/flow/test_flow_pr_review.bats`

**Steps**
1. 新增失败测试，覆盖首次 bump 时未传 `--msg` 且无 branch 缓存时必须阻断。
2. 新增测试，覆盖显式 `--msg` 写入 branch-keyed 缓存后，后续同一 branch 可直接复用。
3. 新增测试，覆盖 `...`、空字符串、默认占位文本被拒绝。
4. 新增测试，覆盖缓存按 branch 隔离，不因别的 worktree / branch 的 message 串用。

**Run command**

```bash
bats tests/flow/test_flow_pr_review.bats
```

**Expected Result**

- 改实现前至少有一条“无 message 仍继续 bump”的用例失败

### Task 2: 在 shell 层加入 branch-keyed changelog message 缓存

**Files**
- Modify: `lib/flow_pr.sh`
- Modify: `scripts/bump.sh`

**Steps**
1. 在 `lib/flow_pr.sh` 中增加 branch -> cache file 的解析 helper，目录固定为 `.git/vibe/changelog-msg/`。
2. 增加 changelog message 校验 helper，拒绝空值、`...` 和默认占位文本。
3. 调整 `vibe flow pr` 的 message 解析顺序：显式 `--msg` 优先，其次 branch 缓存，否则阻断。
4. 当显式 `--msg` 通过校验时，写入 branch 缓存；缓存命中时直接复用。
5. 移除当前自动拼接 `...` 的逻辑，确保 shell 不再生成占位 changelog。
6. 让 `scripts/bump.sh` 只负责根据已提供的 message 写 CHANGELOG，不再默许默认占位文案参与正常发布。

**Run command**

```bash
bats tests/flow/test_flow_pr_review.bats
```

**Expected Result**

- 首次缺 message 会硬阻断
- 同一 branch 第二次执行可自动复用已确认 message
- CHANGELOG 不再出现新的 `...` 占位条目

### Task 3: 同步 help 与 skill 语义

**Files**
- Modify: `lib/flow_help.sh`
- Modify: `skills/vibe-commit/SKILL.md`

**Steps**
1. 把 `--msg` 的 help 从“默认首条 commit...”改成“首次必须给可用 changelog message；之后同 branch 自动复用已确认值”。
2. 在 `vibe-commit` skill 里明确：
   - 首次发布若无已确认 message，agent 必须提供 `--msg`
   - 不允许用占位文本糊弄过关
   - 同一 branch 若已有缓存，不必反复询问

**Run command**

```bash
rg -n -- "--msg|changelog message|CHANGELOG" lib/flow_help.sh skills/vibe-commit/SKILL.md
```

**Expected Result**

- help 与 skill 不再暗示 `--msg` 可以安全省略到 shell 自动兜底

### Task 4: 做最小端到端复核

**Files**
- Modify: 如前述文件；不新增实现范围外文件

**Steps**
1. 跑 `flow pr` 相关 bats 用例。
2. 在最小 shell 场景中验证：
   - 第一次无 `--msg` 时阻断
   - 提供一次 `--msg` 后，再次执行可复用
3. 记录若后续需要在 `vibe flow done` 清理 branch cache，可作为后续小任务，不在本轮扩张。

**Run command**

```bash
bats tests/flow/test_flow_pr_review.bats
git status --short
```

**Expected Result**

- tests 通过
- 共享缓存目录只在 branch 级别写入 message，不影响无关 branch

## Risks

### Risk 1: 共享缓存 key 设计错误，导致多 branch 串用
- **Impact:** 错误的 changelog message 被写入别的 PR
- **Mitigation:** key 直接基于当前 branch 规范化后的文件名生成，不使用版本号
- **Stop Condition:** 若测试无法稳定证明 branch 隔离，停止实现并先收缩到只支持当前 branch 的显式缓存

### Risk 2: 默认占位文本识别不全
- **Impact:** 仍有 `...` 或默认文案漏进 CHANGELOG
- **Mitigation:** 明确拒绝空字符串、`...`、`Automated version bump and updates.` 等已知占位文本
- **Stop Condition:** 若需要复杂 NLP 识别“低质量文案”，则收缩到只处理明确列举的坏值

### Risk 3: help / skill 仍保留旧默认语义
- **Impact:** agent 继续误以为不传 `--msg` 没问题
- **Mitigation:** 同步修改 shell help 与 `vibe-commit` skill
- **Stop Condition:** 若文案开始扩写成完整发布流程手册，则回退为最小提醒

## Test Command

- `bats tests/flow/test_flow_pr_review.bats`
- `rg -n -- "--msg|changelog message|CHANGELOG" lib/flow_help.sh skills/vibe-commit/SKILL.md`
- `git status --short`

## Expected Result

- `vibe flow pr` 首次缺少 changelog message 时会阻断，而不是写入占位文本
- 同一 branch / flow 只需提供一次可用 `--msg`
- branch-keyed 共享缓存可被多 worktree 复用，且不会因为版本号碰撞而串用
- help 与 skill 都会提醒 agent：首次必须给可用 changelog message

## Change Summary Estimate

- Files to modify: 4 到 5 个
- Approx line changes: 60 到 120 行
- 类型分布：
  - 代码：25 到 50 行
  - 测试：20 到 45 行
  - 文档：10 到 25 行
