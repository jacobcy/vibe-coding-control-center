---
name: vibe-roadmap
description: Use when the user wants project-level roadmap planning, version goals, backlog triage, or issue placement decisions, asks what the current or next version should contain, or mentions "vibe roadmap", "/vibe-roadmap", "/roadmap", "版本规划", "下一个版本做什么", or "这个 issue 放哪一版".
---

# /vibe-roadmap - 版本规划助手

维护版本路线图，管理 milestone、roadmap 桶和规划层优先级元数据，决定哪些 issue 进入哪个版本窗口。

**核心原则:** `/vibe-roadmap` 是版本规划层，不是 runtime 调度器。它负责给 issue 设定规划元数据，供后续治理与执行参考；shell 层只负责暴露现场事实。

**新增核心原则:** 所有 roadmap 管理通过 GitHub issue labels 触发，不在本地实现数据存储，遵循 GitHub-as-truth 原则。

**核心职责:**

- 判断 issue 属于哪个版本窗口或是否暂缓
- 为有效 issue 设定规划层 metadata：milestone、`roadmap/*`、必要时的 `priority/[0-9]`
- 管理版本目标与版本窗口边界
- 输出规划层候选集，供后续执行 skill 使用

intake gate 约束：

- 不是所有 `repo issue` 都自动进入 GitHub Project。
- 只有经过 `vibe-roadmap` triage 的候选 `repo issue`，才应纳入 task item / GitHub Project。
- shell 层不负责智能 intake gate；是否纳入 Project 属于 skill / workflow 的规划判断。
- `vibe-roadmap` 消费的是 `repo issue intake 视图`，而不是本地长期 issue cache / registry。
- intake 视图应来自运行时查询与 flow/status 总览对比。
- 若未来需要留痕，优先保存 triage 决策快照，而不是复制 issue 整池真源。

对象约束：

- `repo issue`: 需求来源
- `vibe-roadmap` 只处理规划元数据，不负责 execution record
- 任何规划判断都必须先读 GitHub 与 shell 输出，再做编排

> 项目命令参考见 `skills/vibe-instruction/SKILL.md`
> 标签定义参考见 `docs/standards/github-labels-reference.md`
> Roadmap 管理指南见 `docs/standards/roadmap-label-management.md`

**Announce at start:** "我正在使用 /vibe-roadmap 技能来管理版本路线图。"

**命令自检:** 对 `vibe3 task status`、`gh issue list`、`gh issue edit` 等参数、子命令或 flag 有任何不确定时，先运行 `--help`。shell 命令是 agent 的工具入口，不是面向用户的命令教学清单。

## Trigger Examples

- `vibe roadmap`
- `/vibe-roadmap`
- `/roadmap`
- `版本规划`
- `下一个版本做什么`
- `管理许愿池`
- `版本目标`
- `issue 标签管理`
- `设置 issue 优先级`
- `分配 milestone`

## Hard Boundary

- 只负责规划层调度，不负责 `repo issue` 创建、flow 注册修复或 runtime 修复
- 必须先运行 `vibe3 task status` / `gh issue list` 等命令理解当前版本与候选池
- 不得直接修改 `.git/vibe3/handoff.db` 底层数据
- 远端写操作优先通过 `gh` / GitHub 原生命令完成
- 只有涉及本地 flow 绑定时才使用 `vibe3 flow bind`
- 调度器无法判断优先级时，必须要求人类讨论
- 若涉及主 issue / sub-issue，只承接 skill/workflow 已做出的范围判断，不在 shell 层发明 parent/sub-issue 运行时逻辑
- 所有 roadmap 管理通过 GitHub issue labels 触发，不在本地实现数据存储
- 不负责根据当前 active / ready / blocked 现场判断“现在下一个该做谁”；这是 `vibe-orchestra` 的职责

边界对照：

- `repo issue` intake、模板补全、查重：交给 `vibe-issue`
- `task <-> flow` 映射核对与修复：交给 `vibe-task`
- `task <-> flow` / worktree runtime 修复：交给 `vibe-check`
- 基于当前运行现场寻找下一个值得处理的 issue：交给 `vibe-orchestra`
- parent issue / sub-issue 的范围判断：交给 `vibe-issue` 等 skill/workflow；`vibe-roadmap` 只消费判断结果

## 基于 Label 的 Roadmap 管理

### 核心标签类型

根据 `docs/standards/github-labels-reference.md`，roadmap 管理主要使用以下标签：

#### Priority 标签 (priority/\*)

| 标签名称         | 描述       | 使用场景                        |
| ---------------- | ---------- | ------------------------------- |
| `priority/[0-9]` | 细粒度顺位 | 同一 roadmap 桶内的前后顺序提示 |

补充说明：

- 新规划建议优先使用 `priority/[0-9]`，默认 `0`，数字越大越靠前。
- legacy `priority/high|medium|low|critical` 仅作为兼容读取输入，不建议作为新规划主路径。

#### Roadmap 状态标签 (roadmap/\*)

| 标签名称         | 描述             | 使用场景           |
| ---------------- | ---------------- | ------------------ |
| `roadmap/p0`     | 当前迭代必须完成 | 阻断性问题         |
| `roadmap/p1`     | 下个迭代优先完成 | 重要功能           |
| `roadmap/p2`     | 有容量时完成     | 一般功能           |
| `roadmap/next`   | 下个迭代规划中   | 待确认的功能       |
| `roadmap/future` | 未来考虑         | 长期规划           |
| `roadmap/rfc`    | RFC/设计阶段     | 需要讨论设计的功能 |

### Milestone 管理

- Milestone 用于标识版本目标，如 "Phase 1: 基础设施"、"Phase 2: 核心功能" 等
- 每个 issue 可以分配一个 Milestone，表示其所属的版本
- Milestone 与 roadmap 状态标签配合使用

## Workflow

### Step 1: 检查版本目标

先运行获取当前版本目标状态；必要时再补充文本输出：

```bash
# 查看当前 flow / issue 总览
vibe3 task status

# 查看开放的 issues
gh issue list

# 查看带有特定标签的 issues
gh issue list -l "priority/5"
gh issue list -l "roadmap/p0"
```

获取：

- 当前版本目标是什么
- 有哪些 `repo issue` 等待分类
- 各版本窗口下有多少候选 issue
- 现有 issues 的 milestone / roadmap / priority 分布

### Step 2: 版本规划决策

根据当前状态做出决策：

**场景 A: 没有版本目标**

- 提示用户定义版本目标
- 展示许愿池中的 `repo issue` 供选择
- 要求人类讨论确定目标

**场景 B: 有版本目标但有新 `repo issue`**

- 对新的 `repo issue` 进行分类：
- 1.  分配适当的 Milestone
- 2.  添加 roadmap 状态标签（`roadmap/p0`、`roadmap/p1`、`roadmap/p2` 等）
- 3.  必要时补 `priority/[0-9]` 作为同一 roadmap 桶内的细粒度顺位提示
- 对候选 `repo issue` 做 intake gate 判断：纳入 / 不纳入 / 待讨论
- 输出版本窗口内的候选集合，但不根据当前 runtime 现场判断“现在该做谁”
- 若该 issue 来自已有治理母题，先读取上游 skill/workflow 的范围判断：
  - 仍在原主 issue 范围内，可继续按 sub-issue 进入规划
  - 已超出原范围，要求拆成新的独立 issue，再决定归类

**场景 C: 版本结束**

- 确认下一版本目标
- 重新评估待分类 Issue
- 更新 roadmap 状态标签

### Step 3: 应用标签和 Milestone

使用 GitHub CLI 为 issues 添加标签和 Milestone：

```bash
# 分配 Milestone
gh issue edit <issue_number> --milestone "Phase 1: 基础设施"

# 添加 roadmap 状态标签
gh issue edit <issue_number> --add-label "roadmap/p0"

# 添加细粒度 priority 标签
gh issue edit <issue_number> --add-label "priority/5"

# 同时添加多个标签
gh issue edit <issue_number> --milestone "Phase 1: 基础设施" --add-label "roadmap/p0" --add-label "priority/5"
```

详细操作指南见 `docs/standards/roadmap-label-management.md`。

### Step 4: 输出状态

输出当前路线图状态：

```text
## 当前版本: Phase 1: 基础设施

### P0 (紧急)
- #36: GitHub Projects 整合 [priority/8, roadmap/p0]

### 当前版本
- #34: Issue 同步 [priority/5, roadmap/p1]
- #35: save 自动关联 [priority/5, roadmap/p1]

### 下一个版本
- #37: 智能调度 [priority/3, roadmap/p2]

### 延期
- #38: 性能优化 [priority/0, roadmap/future]
```

### Step 5: 响应 vibe-new 调用

当 `/vibe-new` 触发时：

- 检查是否有版本目标
- 无目标 → 要求人类讨论确定
- 有目标 → 提示当前规划窗口有哪些候选 issue 可继续进入执行现场
- 是否此刻就开始处理、在多个候选里当前先做哪个，由 `vibe-orchestra` 或人类结合 runtime 现场决定

### Step 6: 落地规划结果

规划层远端写操作优先直接使用 GitHub / `gh`：

```bash
gh issue edit <issue_number> --add-label "roadmap/p0"
gh issue edit <issue_number> --milestone "Phase 1: 基础设施"
```

如需把某个 issue 进入当前执行现场，再交给 `/vibe-new` 或 `vibe3 flow bind` 处理本地绑定。

## Label 触发机制

所有 roadmap 管理操作通过 GitHub issue labels 触发：

1. **版本规划**: 通过 `milestone` 与 `roadmap/*` 控制
2. **同桶细粒度顺位**: 必要时通过 `priority/[0-9]` 控制
3. **Milestone 分配**: 通过 GitHub Milestone 功能控制
4. **执行状态**: 通过 `state/*` 标签控制（由执行层管理，非 roadmap 职责）

Agent 应通过以下方式使用标签触发机制：

- 定期扫描带有特定标签的 issues
- 为新 issues 分配适当的规划标签
- 当版本窗口变化时更新 milestone / roadmap / priority 元数据
- 不在这里根据当前 active / ready 现场做即时抢占排序

详细触发机制见 `docs/standards/roadmap-label-management.md`。

## Milestone 显示

`vibe3 flow show` 命令会显示当前 flow 绑定 issue 的 Milestone 信息：

- 从 GitHub API 获取 Milestone 数据
- 显示 Milestone 标题、进度和相关 issues
- 提供 Milestone 上下文用于规划决策

## Failure Handling

如果 shell 命令失败：

- 直接展示 CLI 返回的阻塞原因
- 明确告诉用户当前无法进行路线图管理
- 不要自行 fallback 到直接修改数据库

## Reference Documents

- [docs/standards/github-labels-reference.md](../../docs/standards/github-labels-reference.md) - 完整的标签定义参考
- [docs/standards/roadmap-label-management.md](../../docs/standards/roadmap-label-management.md) - 详细的 roadmap 标签管理指南
- [docs/standards/v3/command-standard.md](../../docs/standards/v3/command-standard.md) - V3 命令标准
- [docs/standards/issue-standard.md](../../docs/standards/issue-standard.md) - Issue 标准

## Terminology Contract

- `版本目标`: 当前版本要完成的目标
- `许愿池`: GitHub `repo issues`（需求池）
- `repo issue`: 需求来源与讨论入口，不是 execution record
- `Task`: 执行层最小单元，不属于 roadmap 直接管理范围
- `Flow`: task 的运行时容器，不属于 roadmap 直接管理范围
- `priority label`: 细粒度顺位标签，如 `priority/5`
- `roadmap label`: 路线图状态标签，如 `roadmap/p0`
- `Milestone`: 版本目标标识，如 "Phase 1: 基础设施"
