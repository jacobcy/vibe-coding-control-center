---
document_type: plan
title: GitHub Project Semantics Readiness Audit Plan
status: draft
scope: standards
author: Codex GPT-5
created: 2026-03-10
last_updated: 2026-03-10
related_docs:
  - docs/standards/data-model-standard.md
  - docs/standards/registry-json-standard.md
  - docs/standards/roadmap-json-standard.md
  - docs/standards/command-standard.md
  - docs/standards/skill-standard.md
  - docs/standards/git-workflow-standard.md
  - docs/references/github_project.md
---

# GitHub Project Semantics Readiness Audit Plan

**Goal:** 以 GitHub Project 官方对象模型为上位约束，审计并修订本项目的数据结构标准、命令标准与 Git workflow 标准，判断项目是否已经具备“全面介入 GitHub Project 标准语义”的标准层前置条件。

**Non-Goals:**
- 本计划不直接修改 `lib/`、`bin/`、`skills/` 的实现。
- 本计划不接入 GitHub Projects API。
- 本计划不处理 PR `#89`、`#90`、`#91`、`#92` 之外的具体 shell 行为修复。
- 本计划不在本轮决定最终迁移脚本或数据迁移顺序。

**Tech Stack:** Markdown standards, shared-state JSON schema design, Zsh CLI semantics, Git workflow rules, GitHub Project domain model

---

## Current Assessment

当前标准层已经完成第一轮 GitHub-first 文本纠偏，但还没有完成 readiness audit。现状有三个明显断层：

1. **数据结构断层**
   - `roadmap.json` 已被解释为 mirrored GitHub Project item，但字段还没有完整表达 GitHub Project item / milestone / repo issue 的稳定映射。
   - `registry.json` 已被解释为 execution record，但与 GitHub `type=task` item 的桥接方式仍不明确。
   - `worktrees.json` 在 `data-model-standard.md` 中只被高层引用，缺少与 GitHub-first flow 语义直接对齐的明确约束。

2. **命令语义断层**
   - `command-standard.md` 已声明 `roadmap sync` 应对齐 GitHub Project item，但标准仍保留较多 issue-first / 本地-first 兼容语义。
   - `skill-standard.md` 仍主要讨论 skills / workflow 注册边界，尚未吸收 GitHub-first 语义下的 slash / workflow 入口分层。

3. **workflow 断层**
   - `git-workflow-standard.md` 当前核心链路仍是 `roadmap -> task -> flow -> PR`。
   - 若目标是 GitHub Project 标准语义，workflow 入口应显式提升为 `repo issue -> roadmap item -> task -> flow -> PR`。

## Target Decision

本计划要产出的不是代码，而是一组标准层决策：

1. `roadmap.json` 是否要引入更明确的 GitHub Project / milestone / issue 映射字段。
2. `registry.json` 应如何表达 execution record 与 GitHub `type=task` 的关系，而不混淆成同一个对象。
3. `command-standard.md` 是否要把 `roadmap sync`、`task add/update`、`flow new/bind` 的 GitHub-first 语义进一步硬化。
4. `skill-standard.md` 是否要新增 “slash / workflow 只做调度入口，不定义 GitHub 规划对象” 的统一约束。
5. `git-workflow-standard.md` 是否要把 GitHub 标准对象链路提升为默认 happy path。

## Files To Modify

- Modify: `docs/standards/data-model-standard.md`
- Modify: `docs/standards/registry-json-standard.md`
- Modify: `docs/standards/roadmap-json-standard.md`
- Modify: `docs/standards/command-standard.md`
- Modify: `docs/standards/skill-standard.md`
- Modify: `docs/standards/git-workflow-standard.md`

## Task 1: 审计共享状态对象模型

**Files:**
- Modify: `docs/standards/data-model-standard.md`
- Modify: `docs/standards/registry-json-standard.md`
- Modify: `docs/standards/roadmap-json-standard.md`

**Step tasks:**

1. 重新列出 GitHub 标准对象与本地对象的最小映射表：
   - `repo issue`
   - `GitHub Project item`
   - `milestone`
   - `roadmap item`
   - `task execution record`
   - `flow`
2. 明确哪些对象是一一映射，哪些对象只是关联关系。
3. 在 `data-model-standard.md` 中修订跨文件关系约束，明确：
   - `repo issue <-> roadmap item`
   - `roadmap item <-> task`
   - `task <-> flow`
   - `milestone -> roadmap window`
4. 在 `roadmap-json-standard.md` 中决定：
   - 是否保留 `milestone` 根字段
   - 是否需要更显式的 GitHub Project item / issue 来源字段说明
   - `type=feature|task|bug` 是否足以表达当前规划层需求
5. 在 `registry-json-standard.md` 中明确：
   - 本地 task 是 execution record，而非 GitHub task item 本体
   - `issue_refs`、`roadmap_item_ids`、`pr_ref` 的桥接边界
   - 是否需要补充 execution record 特有字段说明

**Expected Result:**
- 三份数据结构标准对 GitHub Project 对象映射给出一致定义。
- 不再让 `task` 与 `type=task` 处于语义悬空状态。

## Task 2: 审计 Shell / Slash 命令标准

**Files:**
- Modify: `docs/standards/command-standard.md`
- Modify: `docs/standards/skill-standard.md`

**Step tasks:**

1. 在 `command-standard.md` 中收紧 `vibe roadmap` 语义：
   - `status/list/show/add/sync/classify/version`
   - 明确哪些动作是 GitHub Project 规划层动作，哪些只是兼容字段操作。
2. 明确 `vibe task` 只面向 execution record：
   - 允许哪些原子关系写入
   - 不允许承担哪些 GitHub Project 规划职责
3. 明确 `vibe flow` 只属于执行现场：
   - `new` 不定义 feature
   - `bind` 只绑定 execution record
4. 在 `skill-standard.md` 中补一节 slash / workflow 边界：
   - `/vibe-new-feature`
   - `/vibe-new-flow`
   - `/vibe-issue`
   - `/vibe-task`
   - `/vibe-save`
5. 统一规定：slash / workflow 只能调度现有 GitHub 对象与本地 execution record，不得在入口文案中重新发明对象层级。

**Expected Result:**
- `command-standard.md` 和 `skill-standard.md` 共同形成 “Shell 提供原子能力，slash/workflow 只调度，不重定义 GitHub 对象” 的统一约束。

## Task 3: 审计 Git workflow 标准

**Files:**
- Modify: `docs/standards/git-workflow-standard.md`

**Step tasks:**

1. 将核心链路从 `roadmap -> task -> flow -> PR` 升级为：
   - `repo issue -> roadmap item -> task -> flow -> PR`
2. 在 happy path 中明确：
   - `roadmap item type=feature` 对应主 branch / 主 PR
   - `task execution record` 是 execution layer，不替代规划对象
3. 在 exception / recovery 章节中明确：
   - open PR follow-up 与下一个规划目标的切换边界
   - `flow` 永远不回退为规划入口
4. 明确 `milestone` 在 workflow 中的定位：
   - 它属于规划窗口锚点，而不是 runtime 切换条件

**Expected Result:**
- `git-workflow-standard.md` 与新的数据结构标准、命令标准形成闭环。

## Task 4: 交叉一致性审查

**Files:**
- Modify: `docs/standards/data-model-standard.md`
- Modify: `docs/standards/registry-json-standard.md`
- Modify: `docs/standards/roadmap-json-standard.md`
- Modify: `docs/standards/command-standard.md`
- Modify: `docs/standards/skill-standard.md`
- Modify: `docs/standards/git-workflow-standard.md`

**Step tasks:**

1. 逐文件检查下列高风险混用是否仍存在：
   - `issue` vs `repo issue`
   - `task` vs `type=task`
   - `roadmap item` vs local feature draft
   - `flow` vs planning entry
2. 确保 6 份标准文件对以下句子口径一致：
   - `roadmap item` 是 mirrored `GitHub Project item`
   - `task` 是 execution record
   - `milestone` 是规划窗口锚点
   - `flow` 只属于执行层
3. 修正文档之间的引用关系，避免一份标准回退到旧语义。

**Expected Result:**
- 六份标准文件不再互相打架。

## Test Command

```bash
rg -n "repo issue|GitHub Project item|milestone|execution record|type=task|flow.*执行层|repo issue -> roadmap item -> task -> flow -> PR" \
  docs/standards/data-model-standard.md \
  docs/standards/registry-json-standard.md \
  docs/standards/roadmap-json-standard.md \
  docs/standards/command-standard.md \
  docs/standards/skill-standard.md \
  docs/standards/git-workflow-standard.md
```

## Expected Result

- 数据结构标准能自洽地表达 GitHub Project 对象与本地 execution record 的关系。
- 命令标准与 skill/slash 标准不会重复定义对象模型。
- Git workflow 标准明确以 GitHub-first 语义作为默认路径。
- 项目能够回答“当前标准层是否已具备全面介入 GitHub Project 标准语义的前置条件”。

## Estimated Change Summary

- Modified: 6 files
- Added: ~80-140 lines
- Removed: ~40-90 lines
- Risk: 中等
- Main risk:
  - 继续保留过多兼容性表述，导致标准层口径再次分裂
  - 在 `task` / `type=task` 上定义不严，后续实现仍会误绑定
