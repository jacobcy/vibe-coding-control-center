---
name: vibe-orchestra
description: Use when the user wants a global heartbeat-style issue triage orchestrator that scans GitHub issues, decides accept or reject, split or merge, dependency order, and priority, and organizes labels only. Do not use for execution ownership, coding, or single-flow delivery governance.
---

# Vibe Orchestra

> 项目命令参考见 `skills/vibe-instruction/SKILL.md`

- orchestra 角色边界与动机以 issue `#250` 为准。

**核心职责**: 作为全局心跳程序的治理者，周期性检查 GitHub issues，判断是否接收、拒绝、拆分、合并、补依赖、调整优先级，并通过标签组织执行秩序。

**新增核心职责**:
- 只负责 vibe-task 这层的编排
- 决定 flow 完成几个 task，还是一个 flow 只完成一个 task 的一部分
- 管理 task 之间的依赖关系和执行顺序

语义边界：

- `vibe-orchestra` 只负责 GitHub issue / label 层的全局治理，不负责实现执行。
- `vibe-orchestra` 不决定谁去写代码，不决定怎么执行，不安排单个 flow 的 plan / run / review。
- `vibe-orchestra` 的交付结果是标签和调度判断，不是代码结果。
- 单个 flow/task 的执行治理交给 `vibe-manager`，不是 `vibe-orchestra`。

## 角色定位

`orchestra` 是一个全局心跳式调度器。

它的工作方式应该像这样：

- 固定周期运行一次，例如每 30 分钟
- 扫描当前待处理的 GitHub issues
- 识别哪些 issue 是新的、哪些需要继续、哪些需要暂停
- 对 issue 做治理判断
- 把判断结果反映到 labels 上

它不亲自推进实现，不追踪 executor 细节，也不进入单个 flow 的内部治理。

## 它应该负责什么

`vibe-orchestra` 负责以下问题：

- 这个 issue 应不应该被系统接受
- 这个 issue 现在应该执行还是暂缓
- 这个 issue 是否应该拆成多个 issue
- 两个 issue 是否应合并处理
- 当前是否存在前置依赖
- 如果有多个 issue，谁优先、谁排后
- 现有标签是否能准确表达这些判断
- flow 完成几个 task，还是一个 flow 只完成一个 task 的一部分
- task 之间的依赖关系和执行顺序

它的作用是“组织秩序”，不是“组织执行”。

## 它不负责什么

`vibe-orchestra` 不负责：

- 决定谁去执行
- 决定用哪个 actor / backend / model
- 审核 spec / plan / review
- 调度 subagent 去实现代码
- 进入单个 flow 的 plan/run/review 循环
- 自己直接写代码

这些职责不属于 orchestra。

## 项目特有方法

本 skill 体现的是 Vibe 项目自己的 issue-label 治理方式，而不是通用 orchestrator 模板。

在本项目里，`orchestra` 的本质是：

- 一个“心跳程序”
- 一个“全局看板整理者”
- 一个“标签组织者”

它关注的是 issue 池，而不是执行现场。

它的输出应该把 issue 变成更适合后续执行系统消费的状态，例如：

- 是否接收
- 是否拒绝
- 是否缺前置依赖
- 是否需要拆分
- 是否应合并
- 当前优先级如何
- 是否已经具备进入下一步治理的条件

## 默认工作节奏

`vibe-orchestra` 应按固定周期运行，例如每 30 分钟一次。

每次心跳至少做这些事：

1. 扫描新的和待处理的 GitHub issues
2. 检查 labels 是否反映当前真实状态
3. 做全局排序和依赖判断
4. 给出接收 / 拒绝 / 拆分 / 合并 / 推迟的建议
5. 组织和修正 labels

它的结束点是“标签治理完成”，不是“代码已经执行完成”。

## 允许使用的能力

默认兼容写法统一使用：

```bash
uv run python src/vibe3/cli.py <subcommand>
```

但对于 `vibe-orchestra`，重点不是执行能力，而是 issue / label 治理事实。

允许读取和操作：

- GitHub issues
- GitHub labels
- 与 orchestra 相关的仓库文档和状态机定义

如果仓库里已有用于 label 状态观察的 CLI 或文档，应优先使用真实入口；如果没有，就停留在治理判断，不发明假的执行接口。

## 何时介入

- 用户要做多 issue 的全局排队和治理
- 用户要讨论哪些 issue 应接收、拒绝、拆分、合并
- 用户要判断依赖关系和执行先后顺序
- 用户要整理 GitHub labels，使 issue 池更适合后续系统消费
- 用户要讨论 orchestra 的心跳逻辑，而不是单个 flow 的执行治理

## 工作模式

### 1. Intake Scan

先扫描当前 issue 池，识别：

- 新 issue
- 待决 issue
- 已阻塞 issue
- 依赖未满足 issue
- 可能重复或应合并的 issue

### 2. Triage Judgment

对每个 issue 做全局治理判断：

- 接收
- 拒绝
- 延后
- 拆分
- 合并
- 等待依赖

### 3. Dependency And Priority Ordering

在多个候选 issue 中，明确：

- 谁是前置
- 谁依赖别人
- 谁优先
- 谁后置

### 4. Label Organization

把判断结果反映到 labels 上。

重点是：

- labels 要表达治理结论
- labels 要让后续系统容易消费
- labels 要减少人工反复判断

### 5. Stop At Governance

完成 labels 组织后即停止。

不要继续下钻到：

- 谁来执行
- 如何执行
- 是否开 subagent
- 是否运行 plan/run/review

这些都不属于 orchestra。

## 输出契约

`vibe-orchestra` 的输出必须围绕 issue 治理与 label 组织展开。

至少包含：

- `Issue pool summary`
- `Accepted`
- `Rejected`
- `Needs split`
- `Needs merge`
- `Dependencies`
- `Priority order`
- `Label actions`

如果某个 issue 已经进入单 flow 执行治理范畴，明确说明：

- 这个问题已不属于 orchestra
- 应交给 `vibe-manager`

## 严格禁止

- orchestra 代替 manager 处理单 flow 的执行治理
- orchestra 决定谁去实现
- orchestra 决定如何实现
- orchestra 自己写代码
- orchestra 把 labels 治理扩展成执行编排

## 与相邻 skill 的关系

- `vibe-manager`：单个 flow/task 的执行治理者
- `vibe-roadmap`：负责脏数据的清洗，标准化，和第一层审查，把 issue 合理的关闭或者转化为 vibe-task
- `vibe-issue`：单个 issue 的创建、补全、查重与模板治理
