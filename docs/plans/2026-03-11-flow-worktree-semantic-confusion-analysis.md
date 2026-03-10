---
document_type: plan
title: flow/worktree semantic confusion analysis
status: proposed
author: Codex GPT-5
created: 2026-03-11
related_docs:
  - docs/standards/glossary.md
  - docs/standards/action-verbs.md
  - docs/standards/command-standard.md
  - docs/standards/git-workflow-standard.md
  - docs/standards/worktree-lifecycle-standard.md
  - .agent/workflows/vibe-new.md
  - .agent/workflows/vibe-new-flow.md
  - lib/flow.sh
  - lib/flow_help.sh
---

# Goal

明确回答：为什么 agent 仍反复把 `vibe flow new` 理解成“新开 worktree”，以及这个错觉是由哪一层语义泄漏造成的。

# Non-Goals

- 不修改 `lib/`、`bin/` 或 tests
- 不在本轮决定最终命令重构方案
- 不处理 detached HEAD 本身的恢复流程

# Tech Stack

- Zsh shell CLI
- 文档标准：`docs/standards/*`
- Agent workflow：`.agent/workflows/*`
- Shell 实现：`lib/flow.sh`、`lib/flow_help.sh`

# Findings

## 1. 规范真源其实已经说清楚了

- `glossary.md` 已明确：`flow` 是 task 的运行时容器，`flow` 不等于 `worktree`，也不等于 `branch`。
- `command-standard.md` 已明确：`flow new = 创建现场`，不是创建 planning object。
- `git-workflow-standard.md` 与 `worktree-lifecycle-standard.md` 进一步明确：新 `flow` 不强制要求新 `worktree`，允许复用当前目录承载新的 flow。

结论：标准层不是主因，主因在“引用这些标准的下游文本和残留实现心智”。

## 2. 直接诱发错觉的第一责任层：workflow 文案仍在混用

- `.agent/workflows/vibe-new.md` 第 22 行仍写着：
  - “再调用 `vibe flow new <slug> --agent <agent>` 创建/切换 worktree”
- 同文件第 65 行虽然补充“`vibe flow new` 只创建执行现场”，但紧接着又把它与“shell 中新建 worktree”并列描述。

这会让 agent 形成冲突心智：

1. 上半段把 `flow new` 解释成 worktree 创建器
2. 下半段又说它只是现场创建
3. agent 在不确定时会退回更具体、更可执行的旧表述，也就是“开 worktree”

## 3. 第二责任层：实现文件仍保留旧入口残影

- `lib/flow.sh:80-101` 仍存在 `_flow_new_worktree()` / `_flow_start_worktree()`，而且内部真实执行 `wtnew` 或 `git worktree add -b ...`
- 即使当前 `vibe flow new` 实际入口走的是 `_flow_new()`（`lib/flow.sh:115-187`），代码库里仍保留“flow=start_worktree”的历史实现痕迹
- `lib/flow.sh:162` 也仍输出 `Creating flow branch: ...`，说明现在真实语义已转向“当前目录开 branch”，但旧 worktree helper 没有被彻底退场

结论：这会诱导任何读实现或做模式归纳的 agent 认为：

- `flow` 子系统天然负责 worktree 编排
- `flow new` 与 “new worktree” 至少存在近义关系
- 只是当前某条路径临时换成了 checkout 分支

## 4. 第三责任层：架构文档保留了高强度历史语义

- `docs/standards/vibe-engine-design.md` 第 3 行加了“边界补充”，但正文第 11、21、27、40、137、139 行仍持续把 flow 生命周期与 worktree 隔离/挂载/清理绑定叙述
- 这种写法不是当前命令标准，但它对 agent 的影响更强，因为它给出了完整故事线：
  - 开任务
  - 切环境
  - 在隔离 worktree 里执行
  - 清理 worktree 收尾

结论：当标准文档是“定义”，架构文档是“故事”时，agent 更容易记住故事。

## 5. 动词 `new` 本身也在放大偏差

- `action-verbs.md` 把 `new` 定义为“创建一个新的运行时现场”
- 这个定义本身没错，但“现场”是抽象词，既可被解释为 flow runtime，也可被误解为物理 worktree
- 一旦下游 workflow 同时出现“新目录准备执行现场”“创建/切换 worktree”之类措辞，agent 会把抽象“现场”具体化成 worktree

结论：不是 `new` 定义错，而是它缺少一句反歧义提醒，例如“默认不等于新建物理 worktree”。

# Root Cause Summary

根因不是单一 bug，而是三层叠加：

1. **workflow 直述错误**：把 `vibe flow new` 明写成“创建/切换 worktree”
2. **实现残影未清**：`_flow_new_worktree()` / `_flow_start_worktree()` 仍留在 `lib/flow.sh`
3. **架构叙事惯性**：旧设计文档长期把 flow 生命周期和 worktree 生命周期捆绑叙述

因此 agent 并不是“没听懂”，而是在做代码库内一致性归纳时，读到了相互冲突的信息，并偏向了更老、更具体、出现次数更多的那一组。

# Suggested Tasks

1. 修正 `.agent/workflows/vibe-new.md` 中所有把 `flow new` 说成“创建/切换 worktree”的表述。
2. 审计 `.agent/workflows/`、`skills/`、`docs/standards/` 中所有 `flow new -> worktree` 的残留文案。
3. 为 `action-verbs.md` 或 `command-standard.md` 增加一句反歧义说明：`flow new` 默认不是“新建物理 worktree”。
4. 评估 `lib/flow.sh` 中 `_flow_new_worktree()` / `_flow_start_worktree()` 是否应迁移到纯 worktree/alias 语义层，避免实现层继续污染认知。

# Files To Modify

- `.agent/workflows/vibe-new.md`
- `.agent/workflows/vibe-new-flow.md`
- `docs/standards/action-verbs.md` 或 `docs/standards/command-standard.md`
- `docs/standards/vibe-engine-design.md`
- `lib/flow.sh`（仅在确认要清理历史 helper 时）

# Test Command

```bash
sed -n '1,240p' docs/plans/2026-03-11-flow-worktree-semantic-confusion-analysis.md
```

# Expected Result

- 计划文件存在且可读
- 明确列出错觉来源的责任层
- 后续执行阶段可直接据此做文案清理与实现残影清理

# Change Summary

- Added: 1 file
- Modified: 0 files
- Removed: 0 files
- Approximate lines: +95 / -0
