---
document_type: plan
title: flow/worktree semantic confusion analysis
status: proposed
author: Codex GPT-5
created: 2026-03-11
related_docs:
  - docs/standards/glossary.md
  - docs/standards/action-verbs.md
  - docs/standards/v2/command-standard.md
  - docs/standards/v2/git-workflow-standard.md
  - docs/standards/v2/worktree-lifecycle-standard.md
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

## 2. 直接诱发错觉的第一责任层：workflow 文案曾经混用

- 在较早版本中，`.agent/workflows/vibe-new.md` 曾把 `vibe flow new <slug> --agent <agent>` 表述为“创建/切换 worktree”。
- 同一时期的文案虽然也补充过“`vibe flow new` 只创建执行现场”，但仍把它与“shell 中新建 worktree”并列描述。
- 本 PR 已将该 workflow 文案更新为：`vibe flow new` 在当前 worktree 内创建/切换 branch 对应的 flow 现场，不再宣称自动创建/切换 worktree。

这会让 agent 形成冲突心智：

1. 上半段把 `flow new` 解释成 worktree 创建器
2. 下半段又说它只是现场创建
3. agent 在不确定时会退回更具体、更可执行的旧表述，也就是“开 worktree”

## 3. 第二责任层：实现文件曾经保留旧入口残影

- 旧版 `lib/flow.sh` 曾包含 `_flow_new_worktree()` / `_flow_start_worktree()` 这类 helper，并在内部执行 `wtnew` 或 `git worktree add -b ...`。
- 本 PR 已删除这些 helper；当前 `vibe flow new` 的入口统一走 `_flow_new()`，实现只在当前目录上创建/切换 branch。
- `lib/flow.sh` 中仍有 `Creating flow branch: ...` 这样的日志文案，说明真实语义已经收敛为“当前目录开 branch”，不再隐式新建 worktree。

结论：这会诱导任何读实现或做模式归纳的 agent 认为：

- `flow` 子系统天然负责或至少曾经负责过 worktree 编排
- `flow new` 与 “new worktree” 至少存在过近义关系
- 当前语义收敛后，历史实现心智仍可能滞留在 workflow / 设计文档中

## 4. 第三责任层：架构文档保留了高强度历史语义

- `docs/standards/v2/vibe-engine-design.md` 第 3 行加了“边界补充”，但正文第 11、21、27、40、137、139 行仍持续把 flow 生命周期与 worktree 隔离/挂载/清理绑定叙述
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

1. **workflow 历史直述错误**：曾把 `vibe flow new` 明写成“创建/切换 worktree”
2. **实现历史残影强化误解**：旧版 `lib/flow.sh` 曾保留 worktree helper，放大了这种联想
3. **架构叙事惯性**：旧设计文档长期把 flow 生命周期和 worktree 生命周期捆绑叙述

因此 agent 并不是“没听懂”，而是在做代码库内一致性归纳时，读到了相互冲突的信息，并偏向了更老、更具体、出现次数更多的那一组。

# Suggested Tasks

1. 审计 `.agent/workflows/`、`skills/`、`docs/standards/` 中所有 `flow new -> worktree` 的残留文案。
2. 为 `action-verbs.md` 或 `command-standard.md` 增加一句反歧义说明：`flow new` 默认不是“新建物理 worktree”。
3. 审阅 `docs/standards/v2/vibe-engine-design.md` 这类叙事性文档，继续降低旧故事线对 agent 的误导。

# Files To Modify

- `.agent/workflows/vibe-new.md`
- `.agent/workflows/vibe-new-flow.md`
- `docs/standards/action-verbs.md` 或 `docs/standards/v2/command-standard.md`
- `docs/standards/v2/vibe-engine-design.md`

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
