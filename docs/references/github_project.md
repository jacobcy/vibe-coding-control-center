# GitHub Project Semantics Reference

> 本文档用于以 GitHub 官方语义为基线，定义本项目如何对齐和收缩这些语义。它是参考文档，不是标准真源；正式规则以后仍应沉淀到 `docs/standards/`。

## 1. 文档目的

这篇文档只做三件事：

1. 说明 GitHub 标准语义里，各对象分别是什么
2. 说明我们项目如何在不冲突的前提下使用这些对象
3. 说明我们项目有哪些额外约束

核心原则：

```text
项目语义不得与 GitHub 标准语义冲突，只能是其子集或更严格约束。
```

## 2. GitHub 标准语义

### 2.1 Repo Issue

GitHub 仓库中的 issue 是需求、问题、讨论结果和追踪项的基础对象。

在本项目里，后续统一称为：

```text
repo issue
```

这样可以避免把“GitHub repo issue”和我们本地的执行任务混叫成 `issue`。

### 2.2 GitHub Project Item

GitHub Project 中的 item 是 Project 视图里的工作项。

它可以来自：

- issue
- pull request
- draft issue

在本项目里，我们本地的：

```text
roadmap item
```

应该对齐为：

```text
mirrored GitHub Project item
```

也就是说，`roadmap item` 不再是一个完全自造的概念，而是本地对 GitHub Project item 的镜像与补充表达。

### 2.3 Milestone

GitHub 标准里，milestone 是版本、阶段、交付窗口的标准对象。

因此本项目如果要表达：

- 当前版本目标
- 某个交付阶段
- 某一轮发布窗口

优先应该对齐到：

```text
milestone
```

而不是把这些含义混进别的概念里。

### 2.4 Issue Type

GitHub 支持 issue type，用于表示工作项类型。

因此我们项目里 roadmap item 的分类，应优先对齐到：

- `feature`
- `task`
- `bug`

如果未来确实需要更高层组织概念，可以另行讨论；当前这版先不把 `epic` 当作标准必备概念引入。

### 2.5 Pull Request

PR 是代码交付和审查单元。

PR 负责：

- 展示变更
- 承载 review
- 运行 CI
- 合并进入主分支

PR 不负责需求建模，也不负责长期规划。

## 3. 我们项目里的对齐语义

### 3.1 Repo Issue = 来源层对象

在我们项目里：

- `repo issue` 是来源
- `repo issue` 是需求入口
- `repo issue` 是讨论和追踪对象

它不是本地执行单元，也不是 flow runtime 的主语。

### 3.2 Roadmap Item = GitHub Project Item 镜像

在我们项目里：

- `roadmap item` 是本地规划真源
- 它应该镜像 GitHub Project item
- 它应携带与 GitHub Project 一致的基础语义

因此：

- `roadmap sync` 的正确语义是同步本地 roadmap item 与 GitHub Project item
- `roadmap item` 不应再被理解成“随便一个本地 feature 草稿对象”

### 3.3 Feature / Task / Bug = Roadmap Item Type

在这版收敛里：

- `feature`
- `task`
- `bug`

都不是独立顶层实体，而是：

```text
roadmap item 的 type
```

这能最大程度对齐 GitHub Project / Issue Type 语义，减少自造概念。

因此：

- `feature` 是一种 roadmap item
- `task` 是一种 roadmap item
- `bug` 是一种 roadmap item

### 3.4 Milestone = 版本或阶段窗口

如果我们要表达：

- 当前版本
- 当前交付阶段
- 当前发布目标

应以 milestone 作为标准语义锚点。

这意味着我们项目里原本用 `version_goal` 或类似概念表达的内容，未来应评估如何与 milestone 对齐。

## 4. 我们项目的特别约束

这些不是 GitHub 原生要求，而是项目级更严格约束。

### 4.1 `1 feature = 1 branch = 1 PR`

这是我们项目的交付切片约束。

含义是：

- 一个 `type=feature` 的 roadmap item
- 对应一条主 branch
- 对应一个主 PR

这不是 GitHub 标准要求，但不与 GitHub 语义冲突，属于更严格子集约束。

### 4.2 一个 feature 可以包含若干 task

这表示：

- 一个 `type=feature` 的 roadmap item
- 可以拆成多个 `type=task` 的 roadmap item

因此在项目实践里，feature 和 task 的关系应该是：

```text
feature -> many tasks
```

### 4.3 Flow 为当前执行任务服务

flow 不是规划对象，而是运行时现场。

在项目里：

- flow 不负责挑需求
- flow 不负责定义 roadmap item
- flow 只负责承载当前执行对象

如果当前 PR 是某个 feature 的 PR，那么这个 flow 的执行内容应服务于该 feature 及其下属 task。

## 5. 对 shell / skill 语义的直接影响

### 5.1 `vibe roadmap sync`

`vibe roadmap sync` 应被理解为：

```text
sync local roadmap items <-> GitHub Project items
```

它不应该再承担：

- 自动完成完整 triage
- 自动完成语义拆分
- 自动决定 feature / task 关系

如果 sync 报错，处理原则应该是：

- 优先修正本地 roadmap item
- 让本地 roadmap 真源恢复可同步状态
- 再重新推送或重新接收 GitHub Project 变更

### 5.2 `vibe-roadmap`

`vibe-roadmap` 的职责应是：

- 维护 roadmap item
- 维护 roadmap item 的 type
- 维护 roadmap item 和 milestone / repo issue / task 的关系
- 决定哪些 item 应进入当前规划窗口

### 5.3 `vibe-task`

如果我们保留本地 `task registry`，那它的职责应收缩为：

- 执行层镜像
- runtime 绑定
- 当前 task 清单
- 当前 task 状态

也就是说，本地 task 不应再被理解成另一套产品规划对象，而应理解成：

```text
execution record for roadmap items
```

### 5.4 `vibe flow new`

`vibe flow new <slug>` 不应再带有“创建 feature”的语义。

它只应表示：

- 创建一个执行现场
- 为后续绑定当前执行任务做准备

### 5.5 `vibe flow bind <task-id>`

`vibe flow bind <task-id>` 应显式对接任务清单。

也就是说：

- flow 绑定的是执行记录
- 执行记录再回指对应的 roadmap item
- 而不是让 flow 直接承担 GitHub planning 语义

## 6. 推荐的工程化链路

如果按 GitHub 标准语义校正项目心智，推荐链路应为：

```text
repo issue
  -> GitHub Project item
  -> local roadmap item
  -> local execution task
  -> flow
  -> PR
```

对应到我们项目：

1. 创建或接收 `repo issue`
2. 将其纳入 GitHub Project
3. `roadmap sync` 同步本地 roadmap item
4. 明确该 item 的 `type`
5. 若为 `feature`，则可拆出若干 `task`
6. 本地 task registry 记录执行对象
7. `vibe flow new`
8. `vibe flow bind <task-id>`
9. 提交 PR

## 7. 我们接下来要纠正的地方

基于这版参考，后续标准和实现应重点检查：

1. 是否还在把 `issue` 和本地 task 混说
2. 是否还在把 `roadmap item` 错当成纯本地 feature 概念
3. 是否还在把 `sync` 说成“拉 issue 原料回家”而不是“同步 Project item”
4. 是否还在让 `flow new <feature>` 承担 feature 定义语义
5. 是否已经把 milestone 作为标准版本窗口语义锚点
6. 是否能把已有 PR 和 commit 反向补齐为 task 记录

## 8. 最终收口

这版参考文档的核心结论只有 4 句：

```text
repo issue 是来源层对象
roadmap item 是 GitHub Project item 的本地镜像
feature / task / bug 是 roadmap item 的 type
flow 和 PR 是执行与交付层对象
```

如果后续我们改标准、入口文件和 skills，都以这 4 句为约束，就能最大程度减少语义冲突。
