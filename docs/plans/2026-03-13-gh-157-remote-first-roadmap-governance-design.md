---
document_type: plan
title: GH-157 Remote-First Roadmap Governance Design
status: proposed
author: GPT-5 Codex
created: 2026-03-13
last_updated: 2026-03-13
related_docs:
  - docs/plans/2026-03-13-gh-157-semantic-cleanup-prerequisite-plan.md
  - docs/plans/2026-03-13-gh-157-worktrees-json-retirement-plan.md
  - docs/standards/data-model-standard.md
  - docs/standards/command-standard.md
  - docs/standards/git-workflow-standard.md
  - docs/standards/handoff-governance-standard.md
related_issues:
  - gh-157
  - gh-158
  - gh-100
  - gh-101
  - gh-105
  - gh-122
  - gh-119
  - gh-152
  - gh-153
  - gh-154
  - gh-155
---

# GH-157 Remote-First Roadmap Governance Design

## Goal

为当前治理 flow 确定一张可执行的总设计图，回答以下问题：

- `repo issue`、`roadmap item`、`task`、`flow` 在 GitHub 原生能力已增强的前提下，应该如何重新分层
- 哪些关系应以 GitHub 为真源，哪些只保留在本地共享状态中
- 本地 `roadmap.json` 应继续承担什么职责，哪些职责应该退出
- 后续实施应如何拆阶段、控依赖、避免一次性重做全栈

## Problem Statement

当前仓库已经把 `roadmap item` 定义为 GitHub Project item mirror，把 `task` 定义为 execution record，并保留桥接链 `repo issue -> roadmap item -> task -> flow`。

这套模型在 GitHub Project 仍较弱时是合理的，但在当前现场中暴露出几个明显摩擦：

1. 用户已经确认了 `repo issue`，但 execution 入口仍容易被“先看到 roadmap mirror”这一事实前置卡住。
2. 远端已经有 issue dependency、sub-issue、parent issue、PR linked issue auto-close 等原生能力，本地若继续维护独立关系语义，会和 GitHub 形成双真源。
3. 当前 `roadmap sync` 已经在做 GitHub Project mirror，但它仍偏向“拉 title/body/refs”，没有把远端关系完整投影回本地。
4. 当前仓库在收口、串行 PR、stacked PR、handoff 清理等行为上已经积累了多条治理 issue，需要一个统一母题而不是继续点状修补。

因此，本轮设计的核心不是“再给本地加更多字段”，而是明确：

- GitHub 已支持的关系语义，直接跟随 GitHub
- GitHub 不支持但业务确有需要的，只做最小本地补充
- 本地共享状态退回 projection / cache / backup，而不是第二套关系真源

## Execution Preconditions

在进入本设计的正式实施前，先插入一个明确前置条件：

1. 先冻结仓库术语与对象边界，避免后续实现继续带着历史混用语义推进。
2. 再处理 `worktrees.json` 清退，把它从“现场真源”降级成兼容期 cache / audit hint，直至完全退出主模型。
3. 最后才进入 remote-first roadmap / sync / closeout 的正式实施阶段。

这样排的原因是：当前仓库仍存在“标准已说 branch 是开放 flow 锚点，但部分数据模型/实现仍把 `worktrees.json` 当现场真源”的混合状态。若不先冻结语义，后续每个实现步骤都可能继续把 `flow`、`branch`、`worktree` 混写成不同层对象。

本设计因此增加三个明确前提：

- `worktree` 只表示 Git 物理目录，不再承担 flow 身份语义。
- `flow` 是对 branch 的逻辑交付现场包装；branch 是开放现场锚点，worktree 只是承载容器。
- `roadmap.json` 当前保留，但在语义上只强调为 projection / cache / backup；是否继续长期保留这一层，留到后续实现和运行证据充分后再决定。

对应交付物：

- 语义冻结前置计划：`docs/plans/2026-03-13-gh-157-semantic-cleanup-prerequisite-plan.md`
- `worktrees.json` 清退计划：`docs/plans/2026-03-13-gh-157-worktrees-json-retirement-plan.md`

## External Capability Baseline

以下能力已由 GitHub 原生提供，可作为本仓库的优先语义来源：

- Issue dependency：GitHub 已支持 issue blocked-by / blocking 关系，并能在 Issues / Projects 中识别 blocked 状态。
  Source: [Creating issue dependencies](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/creating-issue-dependencies)
- Sub-issues / parent issue：GitHub 已支持 issue hierarchy，可在 issue 页面和 Projects 中浏览层级。
  Source: [Browsing sub-issues](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/browsing-sub-issues)
- Project hierarchy fields：GitHub Projects 已支持 `Parent issue` 与 `Sub-issue progress` 字段。
  Source: [About parent issue and sub-issue progress fields](https://docs.github.com/en/issues/planning-and-tracking-with-projects/understanding-fields/about-parent-issue-and-sub-issue-progress-fields)
- PR linked issue auto-close：GitHub 已支持以 keyword 或手工链接让 PR 在 merge 到 default branch 后自动关闭 issue。
  Source: [Linking a pull request to an issue](https://docs.github.com/enterprise-cloud%40latest/issues/tracking-your-work-with-issues/linking-a-pull-request-to-an-issue)

基于这些资料，一个合理推论是：

- “大 issue / 小 issue / 依赖 / 项目视图 / PR closeout” 的主语义不应继续由本地自造模型主导
- 本地只应保存远端关系的 mirror，以及 execution layer 自己独有的桥接事实

另一个重要推论是：

- 我没有找到足够稳定的 GitHub 官方能力，能把“当所有 sub-issues 完成后自动关闭 parent issue”当作核心数据模型假设
- 因此 parent auto-close 若要做，只能作为后续 automation / policy，不应先写进核心数据契约

## Recommended Model

### 1. Source of Truth

- `repo issue`：来源层真源，优先来自 GitHub
- `task issue`：不是与 `repo issue` 平行的新实体，而是 `repo issue` 在 execution 层承担主闭环职责时的角色
- `issue dependency / parent issue / sub-issue / linked PR`：关系真源，优先来自 GitHub
- `roadmap item`：规划投影，优先是 GitHub Project item 的本地 mirror / cache
- `task`：execution record，本地真源
- `flow`：runtime / delivery scene，本地真源

### 2. Anchor Strength

本轮建议把桥接关系重新定义成“强锚点 + 弱锚点”：

- `task` 的强锚点：`issue_refs + spec_standard/spec_ref`
- 若一个 task 已有明确主闭环 issue，应在语义上视作存在一个 `task issue`
- `roadmap_item_ids`：task 的弱锚点，可选规划桥接
- `flow`：只消费已有 task，不再承担规划补洞

效果是：

- 用户主链保持 `repo issue -> flow -> plan/spec -> commit -> PR -> done`
- 内部桥接链仍可存在 `repo issue -> roadmap item -> task -> flow`
- 但 roadmap 不再成为 execution 的硬前置门

### 3. Local Roadmap Role

本地 `roadmap.json` 的定位建议收敛为：

- GitHub Project 的本地 mirror
- 远端关系的 query cache / offline snapshot
- 本地治理审计和故障恢复时的备份层

它不应继续承担：

- execution gate 真源
- 比 GitHub 更高优先级的 issue hierarchy / dependency 解释权
- 独立于 GitHub 的长期 issue registry

补充提醒：

- 当前阶段保留 `roadmap.json` 的主要理由是 query 性能、离线可读性、审计与恢复，而不是继续给 execution 提供身份真源。
- 后续若运行证据证明 remote-first 直接查询已足够稳定，可以再决定是否逐步淘汰部分 cache 能力；本设计不预先承诺永久保留本地 roadmap cache。

## Local-First Exception

虽然总方向是 remote-first，但本地仍可能需要一个显式例外：

- `vibe roadmap add --local`

该能力的意义不是把本地升级成主真源，而是支持“先本地草拟，再显式推送到 GitHub Project”的受控路径。

若保留该例外，建议约束如下：

- 默认仍是 remote-first
- `--local` 必须显式声明
- local draft 只适用于规划层草稿，不适用于 issue dependency / sub-issue / PR closeout 等已有远端原生语义的对象
- local draft 需要明确同步生命周期，例如：
  - `source_type=local`
  - `github_project_item_id=null`
  - `sync_state=pending_push`（新字段，或等价能力）

同步成功后：

- 回填 `github_project_item_id`
- 回填远端 `source_refs`
- 由 mirror 继续跟随远端

## Delivery Semantics

### 1. Big Issue / Small Issue

优先跟随 GitHub 的 parent issue / sub-issue 语义：

- 大 issue 承担母题、范围和进度汇总
- 小 issue 承担可独立关闭的具体交付单元
- `task issue` 是这些 `repo issue` 中对某个 task 承担主交付锚点职责的那个 issue 角色
- 一个 task 可以对应多个小 issue
- 一个 task 不应直接等价于一个大 issue 的完整完成

### 2. PR and Issue Closure

PR 与 issue 的归属建议继续跟随 GitHub 官方行为：

- 单个 PR 只通过 keyword 或手工 link 关闭它真正完成的 issue
- 若 PR 指向非 default branch，则不要依赖 keyword 自动关闭语义
- 在串行 / stacked PR 场景下，必须在 PR 层明确哪些 issue 由该 PR 解决，不能把全部 issue 一股脑挂在母题上

### 3. Parent Issue Closure

parent issue 自动关闭不应在本轮作为核心契约：

- 若 GitHub 已有官方机制，后续可直接跟进
- 若没有，则只能作为 workflow automation 的 follow-up
- 当前阶段只要求 parent issue 的结构化可见性和 progress 可见性

## Sync Contract Direction

`vibe roadmap sync` 建议演进为两个方向明确的能力：

### Pull

从 GitHub 拉回本地 mirror：

- Project item 官方字段
- issue dependency
- parent/sub-issue hierarchy
- linked PR / issue refs 的可镜像部分

### Push

只负责显式 local draft 上推：

- 本地 `--local` roadmap item push 到 GitHub Project
- 成功后回填 remote id 和 official refs

不建议继续维持“一个 sync 同时模糊承担 intake、bootstrap、execution gate”的现状心智。

## Issue Map

建议将本轮治理对象按“总 / 设计 / 实施支撑 / 后置实现”分层：

### 总 issue

- `#157 governance(closeout): converge flow/runtime/handoff cleanup debt`

### 总设计 issue

- `#158 design(data-model): let task bind repo issue directly and support local-first roadmap drafts`

### 设计支撑 issue

- `#100 explore(roadmap): 为 roadmap item 引入轻量依赖声明与 ready/blocked 视图`
- `#101 explore(roadmap): 定义 repo issue 进入 GitHub Project 的 intake gate`
- `#105 explore(roadmap): 提供 repo issue intake 视图而非本地长期缓存真源`

### 已知实现 / 运营问题

- `#119` runtime branch / pr_ref 持久化缺口
- `#122` roadmap sync intake 性能
- `#152` flow show 在 closeout 后的解释问题
- `#153` stacked PR merge order 恢复
- `#154` review evidence / PR comment 治理
- `#155` Serena local gate 兼容性

## Recommended Execution Order

### Phase 0: Freeze the semantics

先把设计层冻结，而不是立即改 shell：

- 明确 remote-first / local projection 的正式口径
- 明确 `worktree != flow != branch`，并把 `worktrees.json` 从主模型真源降级为待清退兼容层
- 明确 `task` 的强锚点改成 `issue_refs + spec_*`
- 明确 `task issue` 只是 `repo issue` 的 execution role，不单独创造一类平行对象
- 明确 local-first roadmap draft 只是显式例外

### Phase 1: Unblock execution from roadmap mirror

最先应做的是“解除 task 对 roadmap mirror 的硬依赖”：

- 让 `task add` / `vibe-start` 在 roadmap item 缺席时仍可从 issue 起步
- 保持 `roadmap_item_ids` 为可选桥接

这是最先做的原因：

- 它直接消除当前用户链路最强的绕路感
- 它不要求先把全部 sync / dependency / hierarchy 做完

### Phase 2: Rebuild roadmap sync as remote-first projection

然后重做 roadmap sync：

- pull 远端 Project / dependency / hierarchy / refs
- push 显式 local draft
- 清理 current intake / bootstrap / mirror 语义混杂

### Phase 3: Normalize delivery contract

最后处理交付规则：

- 一个 task 对多个小 issue
- 一个 PR 解决哪些 issue
- 串行 PR / stacked PR 下 keyword 和 manual link 的使用规范
- handoff / closeout 与 issue close 的一致规则

## Non-Goals

- 本轮不直接实现 shell 代码
- 本轮不把 parent issue auto-close 当作必须落地的核心能力
- 本轮不引入新的本地长期 issue registry
- 本轮不把 GitHub Projects 变成 execution record 真源

## Acceptance Criteria

- 明确 remote-first / local projection 的正式语义
- 明确 `task` 与 `roadmap item` 的主锚点和弱锚点关系
- 明确 `sync` 的 pull / push 方向
- 明确总 issue / 分 issue / 先后依赖 / 推荐推进顺序
- 为后续 implementation plan 提供可直接执行的阶段拆分
