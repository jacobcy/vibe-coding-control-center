---
document_type: plan
title: Vibe3 Parallel Rebuild Design
status: proposed
author: GPT-5 Codex
created: 2026-03-13
last_updated: 2026-03-16
related_docs:
  - docs/standards/v3/handoff-store-standard.md
  - docs/standards/v3/github-remote-call-standard.md
  - docs/standards/glossary.md
  - docs/standards/v2/command-standard.md
  - docs/standards/v2/data-model-standard.md
  - docs/plans/2026-03-13-gh-157-remote-first-roadmap-governance-design.md
  - docs/plans/2026-03-13-shell-thinning-python-core-design.md
related_issues: []
---

# Vibe3 Parallel Rebuild Design

## Goal

在不打断当前仓库标准、skills 和已有 CLI 入口的前提下，启动一个可并行演进的 `vibe3`，用最低迁移成本完成 3.0 重建。

核心目标不是继续修补 `lib/`，而是冻结 2.x，并为 3.0 建立一个可独立讨论、可逐步落地的新实现线，实现：

- `vibe2 = 当前实现`
- `vibe3 = 新实现`
- `vibe = 当前默认入口，后续只通过切换入口指向完成过渡`

## Why This Design

当前仓库最有价值的资产已经不是 2.x 的 shell 实现，而是：

- 标准文件
- skills / workflows
- 最近几轮语义清理与 `worktrees.json` 清退结论
- remote-first / thin-shell / Python-core 的架构判断

因此不值得开新仓库，也不值得继续在旧 `lib/` 上做深重构。

## Key Decision

采用“同仓并行重建”而不是“原地重写”或“新仓复制”：

1. 保留当前 `lib/`、`tests/` 作为 2.x 冻结实现，继续承接其他分支必要的 bugfix / 小修复。
2. 新增 `lib3/`、`tests3/` 与 Python 核心，实现 3.0。
3. 切换点固定在 `bin/vibe`，而不是通过改目录名或软链接切换实现层。

## Frozen Directory Decisions

以下目录结构决策已正式冻结：

### 保留现有 2.x 目录

- `lib/`：2.x shell runtime，**继续保留**，不立即迁移或改名
- `tests/`：2.x tests，**继续保留**，不立即迁移或改名
- `bin/vibe`：默认入口，初期仍指向 2.x，后期切到 3.0

### 新增 3.0 目录

- `lib3/`：3.0 薄 shell wrapper / CLI glue
- `tests3/`：3.0 tests
- `src/`：3.0 结构化数据层与远端接口层

### 入口策略

- `bin/vibe2`：显式运行 2.x（**可选**，不是当前第一优先级）
- `bin/vibe3`：显式运行 3.0
- `bin/vibe`：默认入口，通过入口切换完成迁移

### 域分域结构

3.0 目录**优先按领域分子目录**：

```text
bin/
lib3/flow/
lib3/task/
lib3/pr/
src/flow/
src/task/
src/pr/
tests3/flow/
tests3/task/
tests3/pr/
```

### 冻结约束

1. **不先做大规模目录迁移**：当前阶段不需要把 `lib/` 改名成 `lib2/`
2. **不先创建 Python 骨架**：在完成最终设计冻结与实施计划（Task 4/5）前，不创建新实现目录
3. **本地缓存不承担主链真源职责**：本地状态只作为 cache
4. **真正的 cutover 是入口切换**：不是目录切换

### 后续决策

- 是否迁移旧目录（`lib/`、`tests/`），留到 3.0 稳定后再决定
- `bin/vibe2` 是否创建，视实际需求而定

## Directory Strategy

推荐目录如下：

```text
bin/vibe
bin/vibe2
bin/vibe3
lib/
lib3/
tests/
tests3/
src/
```

语义约束：

- `lib/`：2.x shell runtime，保留，不立即迁移或改名
- `tests/`：2.x tests，保留，不立即迁移或改名
- `lib3/`：3.0 薄 shell wrapper / CLI glue
- `tests3/`：3.0 tests
- `src/`：3.0 结构化数据层与远端接口层

补充说明：

- 当前阶段不需要先把 `lib/` 改名成 `lib2/`
- 当前阶段不需要先把 `tests/` 改名成 `tests2/`
- 当前阶段也不承诺未来一定 `mv`；是否迁移旧目录，留到 3.0 稳定后再决定

这样做的原因很简单：当前仓库有大量路径直接写死 `lib/` 和 `tests/`，现在就整体改名只会制造额外迁移噪音，而不会提升 3.0 设计质量。

## Command Strategy

命令层采用三入口并行：

- `bin/vibe2`：显式运行 2.x（可选；不是当前第一优先级）
- `bin/vibe3`：显式运行 3.0
- `bin/vibe`：默认入口，初期仍指向 2.x，后期切到 3.0

切换顺序：

1. 初期：`vibe` 继续指向当前 2.x
2. 设计期：`vibe3` 独立存在，但还不接管默认入口
3. 稳定期：`vibe` 与 `vibe3` 并行验证
4. 切换期：`vibe -> vibe3`
5. 后评估：再决定是否保留、迁移或删除旧 `lib/` / `tests/`

这意味着：

- 不需要靠软链接改 `lib/`
- 不需要靠软链接改 `tests/`
- 真正的 cutover 是入口切换，不是目录切换

## Architecture Boundary

3.0 的核心边界固定为：

- shell：只做入口、参数解析、help、输出胶水
- Python：处理共享真源、GitHub API、GitHub Project、结构化聚合
- skills：继续保留，主要调整调用契约，不重建技能体系
- standards：继续作为真源，先于实现

这和 2.x 的根本区别是：3.0 不再把 `lib/*.sh` 当成主逻辑承载层。

## V3 Semantic Target

`v3` 优先对齐：

- `docs/plans/2026-03-13-gh-157-semantic-cleanup-prerequisite-plan.md`

当前建议冻结为以下主链：

`repo issue -> task issue(Project) -> flow(branch) -> plan/spec ready -> draft PR -> merge`

各层职责如下：

- `repo issue`
  - 需求来源
  - 负责“提需求”和问题来源追踪
- `task issue`
  - 进入 GitHub Project
  - 负责总 / 分 / 依赖
  - 是执行锚点
- `flow`
  - 只对接 `branch`
  - 不再对接 `worktree`
- `draft PR`
  - 作为 planner 完成准备后的收尾动作
  - 是当前交付线的远端可见锚点
  - 让人能快速看清 branch / task issue / repo issue 的对应关系

补充约束：

- `plan`、`report`、`audit` 都属于 merge 前必须可见的审查文件
- `plan` 是 planner -> executor 交接
- `report` 是 executor -> reviewer 交接
- `audit` 是 reviewer -> ready/merge 交接

补充约束：

- `worktree` 彻底退出身份语义，只是物理目录容器
- 本地状态只作为 cache，可随时从 `git + gh + project` 重建
- 不再依赖本地 JSON 数据库维持主链路认知

## Handoff Identity And Authorship

`v3` 不再引入独立的 `vibe auth` 体系。

身份声明、阶段交接、署名与责任链统一通过 `vibe handoff` 完成。

**设计理念**：
- **基于文件的编辑**：handoff 内容存储在 `.agent/handoff/` 目录下的 JSON 文件中
- **单命令架构**：只提供 `edit` 命令，agent 直接编辑 JSON 文件，系统自动同步到数据库
- **内容开放**：没有权限控制，全靠 agent 自觉遵守
- **自动署名**：每条记录自动保存 agent/model，显示时自动加署名

**查看命令**（只读不写）：
```bash
vibe handoff plan          # 读取指定 flow 的 plan handoff 信息
vibe handoff report        # 读取指定 flow 的 report handoff 信息
vibe handoff audit         # 读取指定 flow 的 audit handoff 信息
```

**身份登记命令**（使用 `auth` 子命令）：
```bash
vibe handoff auth plan --agent <agent> --model <model>    # 声明这个 flow 的 planner 是谁
vibe handoff auth report --agent <agent> --model <model>  # 声明这个 flow 的 executor 是谁
vibe handoff auth audit --agent <agent> --model <model>   # 声明这个 flow 的 reviewer 是谁
```

**语义说明**：
- 使用 `auth` 子命令明确表示”身份注册/登记”动作
- `--agent` 参数提供执行者名称（如 `codex`、`claude`）
- `--model` 参数提供具体模型信息（如 `gpt-5.4`、`sonnet-4.5`）
- 区别于”查看命令”：`vibe handoff plan` (读取) vs `vibe handoff auth plan` (注册)

展示署名优先使用 `agent/model` 形态，推荐示例：
- `codex/gpt-5.4`
- `claude/sonnet-4.5`

**设计意图**：
- 同一 agent 名称跨模型时不会混淆（可以区分 `claude/sonnet-4.5` 和 `claude/opus-4.6`）
- 审计、复盘、回退都能明确看到”是谁 + 用的什么模型”
- 不需要额外的 `sessions.json` / PID / 进程级 auth 基础设施

这条规则应同时作用于：
- `plan / report / audit` 文档署名
- `flow show / flow status` 输出
- PR metadata 显示
- reviewer 结论记录

**编辑命令**（基于文件）：
```bash
vibe handoff edit plan     # 编辑 plan handoff（打开 JSON 文件）
vibe handoff edit report   # 编辑 report handoff（打开 JSON 文件）
vibe handoff edit audit    # 编辑 audit handoff（打开 JSON 文件）
```

**工作流程**：
1. 执行 `vibe handoff edit plan`，系统打开 JSON 文件：
   ```bash
   $EDITOR .agent/handoff/{branch}/plan.json
   ```
2. Agent 在编辑器中直接编辑 JSON 文件：
   - 添加新记录：在 `items` 数组末尾添加新对象
   - 修改记录：直接修改对应记录的 `content` 字段
   - 删除记录：从数组中移除对应的对象
3. 保存并关闭编辑器
4. 系统自动解析 JSON 文件并同步到 SQLite `handoff_items` 表
5. 系统自动记录 `flow_events` 审计日志

**JSON 文件格式**：
```json
{
  “flow_slug”: “vibe3-parallel-rebuild”,
  “branch”: “task/vibe3-parallel-rebuild”,
  “handoff_type”: “plan”,
  “items”: [
    {
      “sequence_number”: 1,
      “actor”: “claude/sonnet-4.5”,
      “content”: “完成了数据模型的初步设计”
    },
    {
      “sequence_number”: 2,
      “actor”: “codex/gpt-5.4”,
      “content”: “实现了 SQLite handoff store”
    }
  ]
}
```

**文件路径规则**：
- `.agent/handoff/{branch-safe-name}/plan.json`
- `.agent/handoff/{branch-safe-name}/report.json`
- `.agent/handoff/{branch-safe-name}/audit.json`
- `{branch-safe-name}` 是将 branch 名称中的 `/` 替换为 `-` 后的结果
- 示例：`task/vibe3-parallel-rebuild` → `task-vibe3-parallel-rebuild`

**编辑规则**：

1. **添加新记录**：
   - 在 `items` 数组末尾添加新对象
   - **不要填写 `sequence_number`**（系统自动分配）
   - **不要填写 `actor`**（系统自动从当前注册身份读取）
   - **不要填写 `created_at` 和 `updated_at`**（系统自动生成）
   - 只需要填写 `content` 字段
   - 示例：
     ```json
     {
       “content”: “完成了第三阶段的设计审查”
     }
     ```

2. **修改记录**：
   - 直接修改对应记录的 `content` 字段
   - **不要修改 `sequence_number`、`actor`、`created_at`**
   - 系统会自动更新 `updated_at`
   - **建议只修改自己的记录**（但**不强制检查**，内容开放，全靠 agent 自觉遵守）

3. **删除记录**：
   - 从 `items` 数组中移除对应的对象
   - **建议只删除自己的记录**（但**不强制检查**，内容开放，全靠 agent 自觉遵守）
   - 删除后 `sequence_number` 不回收，保持历史可追溯性

4. **批量删除**：
   - 从 `items` 数组中移除多个对象
   - 删除所有记录：将 `items` 设为空数组 `[]`

**同步规则**：
- 系统会比较 JSON 文件和数据库的内容
- 自动检测新增、修改、删除的记录
- 自动分配 `sequence_number`（新增记录）
- 自动更新 `updated_at`（修改记录）
- 自动记录所有变更到 `flow_events` 表

**自动编号规则**：
- `sequence_number` 在每个 `(branch, handoff_type)` 组合内**从 1 开始递增**
- 删除记录后**不回收编号**，保持插入顺序的可追溯性
- 显示时按 `sequence_number` 排序，编号可能有空缺
- 示例：
  ```text
  [1] [claude/sonnet-4.5] 完成了设计初稿
  [3] [claude/sonnet-4.5] 审查通过
  ```
  （编号 2 被删除，显示时跳过，但编号保留）

**设计意图**：
- **基于文件的编辑**更符合 agent 的工作方式，agent 可以直接编辑文件
- **单命令架构**简化交互，不需要记忆多个命令（add/edit/delete）
- **自动署名**确保每条记录都能追溯”是谁 + 什么时候 + 用什么模型”写的
- **内容开放**（没有权限控制）让 agent 可以自由纠错，全靠自觉遵守
- **软性约束**通过署名机制 + 审计日志建立，而不是硬性权限控制
- **自动编号**保持插入顺序，删除不回收避免历史引用混乱

### Local Handoff Boundary

`v3` 本地不再承担 GitHub Project 镜像缓存。

远端真源固定为：

- `repo issue`
- `task issue`
- `branch`
- `PR`
- `GitHub Project`

本地只保存责任链与阶段交接。若需要结构化存储，也只允许有一个很小的 flow-scoped handoff store，最小目标是记录：

- `flow`
- `branch`
- `task_issue`
- `pr`
- `plan_ref`
- `report_ref`
- `audit_ref`
- `planner`
- `executor`
- `reviewer`
- `latest_actor`
- `blocked_by`
- `next`

`.agent/context/task.md` 在 3.0 中只视为 2.x legacy local handoff，不再承接主责任链语义。

## V3 Command Shape

`v3` 的核心用户命令面建议收敛为：

- `flow`
- `task`
- `pr`

其中：

- `roadmap` **退出主命令面**
- `check` 若保留，也应退回辅助审计层，而不是用户主链入口

### `flow`

`flow` 负责 branch 现场与执行链路绑定，核心子命令建议为：

- `flow new`
- `flow bind --issue <repo-issue>`
- `flow bind task <repo-issue>`
- `flow switch`
- `flow show`
- `flow status`
- `flow freeze --by <repo-issue|task-issue|flow>`
- `flow done`

语义说明：

- `flow new`
  - 新建 branch 对应的逻辑现场
  - 不再承担 worktree 语义
  - 保留 `--save-unstash`
  - 若当前工作区有未提交改动，先明确提示，再按参数决定是否 stash 带入
- `flow bind --issue <repo-issue>`
  - 把当前 flow 绑定到一个或多个 `repo issue`
- `flow bind task <repo-issue>`
  - 把一个 `repo issue` 显式设为当前 flow 的唯一 `task issue`
  - 也就是把这个 `repo issue` 提升为执行主锚点
- `flow switch`
  - 在多个 branch / flow 间切换
  - 默认走 stash / restore 语义，避免多 flow 切换时丢现场
  - 若工作区 dirty，先提示，再按非交互规则要求显式确认参数
- `flow freeze`
  - 显式标记“先不做”
  - `--by` 表示“被谁冻住 / 先去做谁”
  - 让多 flow 并行时可以看清阻塞链
- `flow done`
  - 结束当前交付线

## Binding Rules

`v3` 的绑定规则建议固定为：

- 一个 `flow` 可以绑定多个 `repo issue`
- 一个 `flow` 只能绑定一个 `task issue`

这样做的原因是：

- `repo issue` 可以表达多个来源、补充、上下游讨论线程
- `task issue` 只保留一个执行主锚点，避免多条主线同时挂在同一 flow 上

对用户可见的效果是：

- `flow show` 能同时看到“我参考了哪些 repo issue”
- 也能明确看到“这条线当前真正对接的是哪个 task issue”

补充约束：

- `flow bind task <repo-issue>` 的输入统一使用 GitHub issue 编号
- 可以写成 `7`，也可以写成 `#7`
- 不再要求用户额外记另一套本地 issue 标识

## Human Shortcut vs Agent Path

建议同时支持两条路径：

**设计意图**：
- 人类通常上下文完整，可以快速完成端到端操作
- Agent 通常需要分步判断，避免在上下文不完整时把多个动作揉在一起
- 两条路径最终达到相同状态，但过程可审计性不同

### 人类快捷路径

人类可以一步到位：

```bash
flow new <slug> --bind <repo-issue>
```

语义如下：

- `--bind` 传入的是普通 `repo issue`
- 系统自动把它提升为当前 flow 的 `task issue`
- 自动打上进入 GitHub Project 所需的标记或角色
- 然后由 planner 在 plan/spec/现场准备完成后再创建 draft PR

如果人类已经明确完成 planning，也可以使用快捷收尾：

```bash
flow new <slug> --bind <repo-issue>
pr draft
```

### Agent 推荐路径

agent 仍然建议走分步路径，避免在上下文不完整时把多个动作揉在一起：

```bash
task add --link <repo-issue>
flow bind task <repo-issue>
pr draft
```

**分步语义说明**：
- `task add --link <repo-issue>`：先把 repo issue 提升为 task issue（进入 GitHub Project）
- `flow bind task <repo-issue>`：再把 task issue 绑定到当前 flow（建立执行锚点）
- `pr draft`：最后创建 draft PR（建立远端锚点）

其中 `pr draft` 不是 planning 前置动作，而是 planner 在 plan/spec/现场准备完成后的收尾动作。

必要时再补多个来源 issue：

```bash
flow bind --issue <repo-issue>
```

这样做的好处是：

- 每一步都更可审计（能看清每个动作的作用）
- 更适合 agent 在复杂现场里做显式判断
- 不会在 planning 尚未完成时过早产生远端副作用

### `task`

`task` 不再以本地 CRUD 为中心思考。

`task` 的常规增删改查仍然存在，但在 `v3` 中不是设计重点；重点应放在：

- task issue 与 GitHub Project 的对接
- 依赖关系
- 与多个 `repo issue` 的链接关系
- 当前 flow / 当前 PR 对应的执行锚点

推荐把最小核心能力收成：

- `task add --repo-issue <repo-issue> --group <feature|bug|docs|chore>`
- `task add --repo-issue <repo-issue>`
- `task link <repo-issue>`
- `task show`
- `task list`
- `task update`

其中：

- **`task add --repo-issue <repo-issue>`**
  - **语义**：把一个 `repo issue` **提升**为 `task issue`
  - **作用**：
    - 使该 issue 进入 GitHub Project（成为执行锚点）
    - 可显式标记执行分组（`feature` / `bug` / `docs` / `chore`）
    - 该 issue 将作为 flow 的唯一主执行目标
  - **区别于 `task link`**：`add` 是"提升"，`link` 只是"链接"

- **`task link <repo-issue>`**
  - **语义**：只负责**补充链接关系**
  - **作用**：
    - 标记该 issue 与当前 task 相关，但不提升为执行主锚点
    - 用于记录参考来源、上下游讨论等辅助信息
  - **区别于 `task add`**：`link` 不改变 issue 的身份和状态

**语义总结**：
- `task add --repo-issue`：**提升** issue 为执行主锚点（一对一关系）
- `task link <repo-issue>`：**链接** issue 作为参考来源（多对多关系）

换句话说：

- CRUD 是基础能力
- 依赖与 issue 链接才是 `v3 task` 的主价值

补充一条执行边界：

- planner 在创建 `flow` 和 `task issue` 时，必须把 task 范围拆到单个 executor 可安全完成的粒度
- 若 executor 判断当前 task 过大、范围混杂、无法一次完成，可以显式提出 scope challenge
- scope challenge 应退回给人类 / planner 决定是否拆成 sub issue / 子 task
- executor 不应在未拆分前擅自扩面实现

### Task / PR Grouping

`v3` 需要把 `task` / `pr` 分组显式化，因为这会直接影响发布策略，而不是只影响展示。

建议先收成最小分组：

- `feature`
- `bug`
- `docs`
- `chore`

推荐规则：

- `task issue` 应携带一个主分组
- `pr` 默认继承当前 `task issue` 的主分组
- 若一个 flow 绑定了多个 `repo issue`，也仍只允许一个主分组作为 publish 默认策略来源

当前最重要的默认策略是：

- `feature`
  - 默认进入版本发布路径
  - `pr ready` 可执行自动版本号与 changelog
- `bug`
  - 默认不 bump 版本
  - 只有显式传参才允许 bump
- `docs`
  - 默认不 bump 版本
  - 只有显式传参才允许 bump
- `chore`
  - 默认不 bump 版本
  - 只有显式传参才允许 bump

这条规则的目标不是否认 bugfix 也可能发布，而是把默认行为收紧：只有明确属于发布功能增量时才自动 bump，其余类型保持保守，需要人显式确认。

### `pr`

`pr` 应从 `flow` 中单独抽出来，成为独立命令域。

核心子命令建议为：

- `pr draft`
- `pr show`
- `pr review`
- `pr ready`
- `pr merge`

语义说明：

- `pr draft`
  - 作为 planner 收尾动作创建 draft PR
  - 前提是当前 flow 的 plan/spec/现场准备已经 ready
  - 一旦 draft PR 存在，用户就能直观看到：
    - 当前在哪个 branch
    - 对接哪个 task issue
    - 对应哪个 repo issue
  - 默认同步最小链路元数据到 PR：
    - `task issue`
    - `repo issues`
    - `spec ref`
    - `agent`
- `pr merge`
  - 合并后推动 task issue 进入完成态
- `pr review`
  - 拉取当前 PR 现场
  - 允许使用本地 Codex 进行静态审查
  - 审查结论需要结构化回贴到 PR comment，而不是只停留在本地终端

补充字段建议：

- `task --agent <agent>`
- `pr --agent <agent>`

作用：

- 显式记录当前执行者 / 提交者
- 让多 agent 协同时，Project / PR / flow 链路里仍能看清是谁在推进

补充约束：

- `pr --agent` 不只用于作者署名，也用于标记 review agent
- `pr review --agent codex` 是一个合理的一等路径
- review 输出应同时满足：
  - 本地终端可读
  - 可回贴到 PR
  - 需要时能对 review comment 做回复，而不是只生成离线报告

## 修正与撤销 (Correction & Undo)

`v3` 必须提供基本的错误恢复能力，确保 MVP 阶段的操作容错率不会过低。以下命令专门用于修正、撤销和清理。

### `task` 域修正命令

- **`task unlink --repo-issue <id>`**
  - 解除 Task 与参考 Issue 的关联
  - 只删除 `flow_issue_links` 表中的链接关系
  - 不影响 GitHub 远端 Issue 状态
  - 用途：当错误地链接了不相关的 Issue 时进行修正

- **`task update <id> --status <status> --group <group>`**
  - 手动修正任务状态和分组
  - `--status` 可选值：`todo`, `in_progress`, `done`, `blocked`
  - `--group` 可选值：`feature`, `bug`, `docs`, `chore`
  - **⚠️ 影响发布策略**：修改 `group` 会影响后续 `pr ready` 的默认 bump 策略
    - `feature` → 默认执行 bump / changelog（进入版本发布路径）
    - `bug` / `docs` / `chore` → 默认不 bump，除非显式传参 `--bump`
    - 详见 "Task / PR Grouping" 章节
  - 用途：当任务分类或状态需要人工调整时使用
  - 建议在 `pr ready` 前修正 group，避免发布策略混乱

### `flow` 域修正命令

- **`flow unbind task`**
  - 解除当前 Flow 与主 Task (Execution Anchor) 的 1:1 绑定关系
  - 删除 `flow_issue_links` 表中 `issue_role='task'` 的记录
  - 不删除 `flow_state` 表中的 `task_issue_number`（需要 `vibe check --fix` 清理）
  - 用途：当需要更换 Task 锚点或重新规划 Flow 时

- **`flow unbind --issue <id>`**
  - 解除当前 Flow 与特定参考 Issue 的绑定
  - 只删除 `flow_issue_links` 表中 `issue_role='repo'` 的指定记录
  - 不影响 Task Issue（如需解除 Task，必须使用 `flow unbind task`）
  - 用途：移除不再相关的参考 Issue

- **`flow abort`**
  - 显式废弃当前 Flow
  - **删分支**：删除本地和远端 branch
  - **删 draft PR**：删除关联的 draft PR（如果存在）
  - **不要求完美状态**：即使工作区 dirty 或链路不完整也允许 abort
  - **与 `flow done` 的区别**：
    - `abort`：表示交付线终止但不成功，清理现场并释放分支绑定
    - `done`：要求完美终点（工作区干净、链路完整、PR merged）
  - 操作对象是 GitHub，GitHub 接受即可
  - 有错报错，不做隐式修复

### `pr` 域修正命令

- **`pr close`**
  - 本地感知 PR 关闭，用于触发 Task 状态回退
  - 当 PR 在 GitHub 上被关闭（非 merged）时，本地应感知并：
    - 将 Task 状态从 `in_progress` 回退到 `todo`
    - 清理 `flow_state.pr_number` 字段
    - 保留 `task_issue_number` 和其他链路信息
  - 用途：处理 PR 被拒绝或关闭后的状态恢复

### 责任链支持命令

- **`vibe handoff plan --agent <agent> --model <model>`**
  - 声明当前 flow 的 planner 身份
  - 写入 `handoff.db` 的 `planner_actor` 和 `planner_session_id` 字段
  - 署名格式：`agent/model`（如 `codex/gpt-5.4`）

- **`vibe handoff report --agent <agent> --model <model>`**
  - 声明当前 flow 的 executor 身份
  - 写入 `handoff.db` 的 `executor_actor` 和 `executor_session_id` 字段

- **`vibe handoff audit --agent <agent> --model <model>`**
  - 声明当前 flow 的 reviewer 身份
  - 写入 `handoff.db` 的 `reviewer_actor` 和 `reviewer_session_id` 字段

### 设计原则

**实现优先级**：
- 修正与撤销命令属于**Phase 3-4**，可在主链（01-03）完成后逐步实现
- 优先级低于主链命令（flow/task/pr 基础命令）
- 这些命令用于错误恢复，不影响主链必需功能

**薄接口原则**：
- Shell / Python 层只提供接口，有错报错，不替用户做业务决策
- Skill 层承担业务逻辑、编排、上下文理解
- 远端真源是 GitHub (gh) 和 GitHub Project

**错误处理原则**：
- 所有命令强调**有错报错**
- 错误对实际业务**没有任何影响**（远端数据在 gh）
- 只是**不能使用我们的快捷键**而已
- 不做"智能修复"或"隐式决策"

**本地 Handoff 定位**：
- 本地 handoff 是**记录本**，不是缓存，也不做真源使用
- **必须以现场（GitHub）为准**
- agent 写入有自由度，可以乱写也可以不写
- 如果本地记录与现场不一致，以现场为准

**标准与实现说明**：
- 本地 handoff store 的正式结构见 `docs/standards/v3/handoff-store-standard.md`
- 上述所有修正/撤销命令的 event 记录已包含在标准中
- 写入规则遵循 handoff-store-standard 第 7 节 "Write Rules"

## Retained V2 Delivery Strengths

`v3` 虽然重做命令边界，但不应把 `v2` 已验证有效的交付护栏丢掉。

这轮扫描后，建议明确保留以下能力，并把它们当成 `pr` 域的设计约束，而不是“以后想起来再补”：

### 1. 自动版本号与自动 changelog

- 自动版本号与 `CHANGELOG` 仍应保留
- 但它们应跟 `draft PR` 解耦，不必在刚建 draft 时立刻执行
- 更合理的阶段是：
- `pr draft`
  - 在 planning ready 后建立远端锚点
  - 补齐 issue / spec / agent 链路
  - 默认不做版本 bump
  - `pr ready`
    - 进入 publish gate
    - 仅在分组或参数允许时执行版本号 bump
    - 仅在发生 bump 时更新 `CHANGELOG`
    - 校验 release note / changelog message

这样既保留了自动发布能力，也避免“刚开 draft PR 就反复制造版本噪音”。

### 2. changelog message 首次必填，后续可复用

`v2` 已验证的好设计应继续保留：

- 首次进入 publish gate 时，若没有明确 changelog message，则阻断
- 不允许空值、`...` 或默认占位文案进入 `CHANGELOG`
- 同一 branch / flow 上已经确认过的 changelog message，可以在后续 `pr ready` 重试时复用

补充默认策略：

- `feature` 默认要求进入 changelog / bump 判断
- `bug` / `docs` / `chore` 默认跳过 bump 与 changelog
- 若人类显式传入 `--bump`，则按显式意图进入版本发布路径

是否保留 branch-scoped cache 文件，是实现细节；但“首次必须明确、后续可复用、不得写入占位文本”这三个语义应直接进入 `v3` 设计。

### 3. `spec_ref` 必须显式进入 PR 链路

`spec_ref` 是当前仓库非常有价值的 execution bridge，`v3` 不应退化成“flow show 里能看见，但 PR 里断了链”。

建议明确：

- `pr draft` / `pr ready` 必须读取当前 flow 的 `spec_ref`
- 若当前交付线要求执行 spec，但缺少 `spec_ref`，应在 publish preflight 中阻断
- `spec_ref` 应作为可见元数据写入 PR 描述或等价字段
- `flow show`、`flow status`、`pr show` 三处都应能看到 `spec_ref`

### 4. issue auto-link 与 GitHub closeout 语义

`v2` 已有“把 issue 自动写入 PR 链路”的优秀设计，`v3` 应保留：

- `pr draft` 默认把当前 `task issue` 与已绑定的 `repo issues` 带入 PR 元数据
- 对 default branch 生效的 close keyword，可按 GitHub 规则自动关闭真正完成的 issue
- 非 default branch、stacked PR 或 parent issue 场景，不应夸大 auto-close 的语义

也就是说：

- 要保留 auto-link
- 但不能把 GitHub 没保证的 auto-close 行为写成 `v3` 核心真相

### 5. publish preflight 继续保留

`v2` 的 metadata preflight 方向是对的，`v3` 不该丢。

进入 `pr ready` 或等价 publish 动作前，至少应检查：

- 当前 flow 是否已绑定唯一 `task issue`
- 当前 branch / flow 链路是否完整
- `spec_ref` 是否存在
- `repo issue` 链接是否为空
- 当前 PR base / stacked 关系是否安全

建议延续“hard block / warning”分层：

- `hard block`
  - 缺 `task issue`
  - 缺 `spec_ref`
  - branch / PR 关键链路不一致
- `warning`
  - 缺补充 `repo issue`
  - 缺非关键扩展信息

### 6. 成功摘要与可读错误不能回退

`gh-112` 已证明“命令成功也必须输出执行摘要”非常重要，`v3` 必须继续保留：

- 写操作成功后必须输出对象、状态、关键链路、下一步
- 空结果要给显式提示
- 错误必须可读，且给出恢复建议

这不只是 UX，而是 agent / 人类协作时减少二次探查成本的核心能力。

### 7. 串行发布与 stacked PR 安全

Issue / PR 扫描显示，PR 顺序、安全 merge、stacked 场景一直是高频问题，`v3` 的 `pr` 域不能退化成“只会 create / merge”。

建议保留这些最小护栏：

- `pr draft` / `pr ready` 要明确展示 `head` / `base`
- 若存在冲突中的 open PR / stacked 依赖，需要显式提示，而不是静默继续
- merge 顺序与 base 选择错误时，要优先报错，不要隐式替用户做危险决定

这部分不一定第一版就做全自动编排，但至少要在设计上保留为核心约束。

## PR Review Direction

`v3` 不应把 review 完全留在 skill 外围文案里，而应在 `pr` 域内保留一个明确入口。

建议收敛为：

- `pr review`
  - 读取当前 PR / diff / review 现场
  - 默认优先支持本地 Codex 审查
  - 审查结果不仅输出到终端，也要支持回贴到 PR

最小能力建议为：

- 生成结构化 review 结论
- 把结论发到 PR comment
- 若是在已有 review 线程上跟进，支持显式回复 comment

这条能力的价值在于：

- 避免“本地 review 做了，但 GitHub 现场没有证据”
- 让 `flow -> pr -> review -> merge` 链真正闭合
- 与已有 `review evidence / PR comment` 治理方向保持一致

## Project-Driven Status Model

Project 视图中的状态建议尽量直接跟随远端事实：

- 有 draft PR -> task `in_progress`
- PR merged -> task `done`

这样做的好处是：

- 状态解释简单
- 不需要再额外维护一层本地执行数据库
- `flow status` 可以直接展示当前每条线的远端链路

## Why Draft PR Matters

当前多 flow / branch / task 并行时最痛的点，是“找不到路径”。

当 planner 完成准备并创建 `draft PR` 后，整条链可以被显式暴露出来：

- 这是哪个 branch
- 对应哪个 flow
- 对应哪个 task issue
- 对应哪个 repo issue

于是：

- `flow show` 能看单条链
- `flow status` 能看所有活跃 flow 的链路
- Project 视图能看 task issue 是否已进入执行、是否已完成

这正是 `v3` 相比 `v2` 最值得保留的新主锚点。

## Issue Identity And Display

`v3` 中所有 `repo issue` / `task issue` 的用户可见标识，建议统一直接使用 GitHub issue 编号：

- `7`
- `#7`

展示时建议默认带上标题，形态类似：

- `#7 fix login redirect`
- `#157 remote-first governance`

这样人类和 agent 都能一眼对应到 GitHub 现场，不需要再翻译另一套本地编号。

## Output Rules

`v3` 的每个命令都必须有清晰输出。

禁止：

- 空回复
- 只有退出码，没有解释
- 只打印内部字段，不提示下一步

统一要求：

- 成功时：说明当前做了什么
- 失败时：说明为什么失败
- 必要时：提示人类或 agent 需要注意什么
- 需要确认时：先明确提示风险，再要求显式 `-y` / `--yes`

即使报错，也必须给出“可读错误”，不允许沉默失败。

补充约束：

- `v3` 默认仍是非交互命令
- 不允许通过交互式问答完成关键写操作
- 所有高风险写操作一律先提示，再要求显式确认参数

## `flow show` Output Model

`flow show` 的默认文本输出建议保留现有优点，并固定至少展示这些字段：

- `title`
- `state`
- `next`
- `task issue`（主 issue）
- `spec ref`
- `repo issues`（格式：`#number name`）
- `branch`
- `pr`

推荐输出形态示意：

```text
Flow: vibe3-parallel-rebuild
Title: V3 Parallel Rebuild
State: active
Next: finalize command boundary
Task Issue: #157 remote-first governance
Spec Ref: docs/plans/2026-03-13-vibe3-parallel-rebuild-design.md
Repo Issues:
  - #157 remote-first governance
  - #158 semantic cleanup expansion
Branch: task/vibe3-parallel-rebuild
PR: #201 (draft)
```

设计目标是：

- 人一眼知道当前这条线在做什么
- agent 一眼知道下一步该接哪条链
- 不需要额外翻多个本地 JSON 文件才能恢复上下文

## `flow status` Output Model

`flow status` 应面向“同时做多个 flow 时不乱”这个核心问题。

因此每条活跃 flow 至少应展示：

- `flow name`
- `state`
- `task issue`
- `repo issue` 摘要
- `branch`
- `pr`
- `freeze / blocked by`
- `next`

这样用户在一个列表里就能看到：

- 哪条线正在推进
- 哪条线被谁冻住
- 哪条线已经有 draft PR
- 哪条线下一步该做什么

## Dirty Workspace And Stash Rules

多 flow / branch 切换时，dirty workspace 是高频风险点，`v3` 必须把这个规则写死：

- `flow new --save-unstash`
  - 继续保留
  - 先提示工作区有未提交改动
  - 再按参数决定是否 stash 带入新 flow
- `flow switch`
  - 默认按 stash / restore 语义工作
  - 切换前若工作区 dirty，先给清晰提示
  - 若操作可能覆盖或重排现场，要求显式 `-y`

目标不是“替用户做决定”，而是“不给沉默副作用”。

## Handoff Direction

`v3` 的 handoff 不应再只作为 skill 附属文案存在，而应提升为 flow 级固定备忘。

当前建议方向：

- 每个 flow 有一份固定 handoff memo
- 先继续使用 Markdown
- 不把它升级为共享真源数据库
- 未来若需要更稳定的固定区块更新，再考虑让 Python helper 负责写入

语义边界：

- handoff memo 仍然不是共享真源
- 它是当前 flow 的本地备忘与会话桥接层
- 固定部分由命令自动刷新
- 自由备注部分由 agent 增删 item，而不是整段重写

推荐拆成两类内容：

- 固定区块
  - flow
  - branch
  - task issue
  - repo issues
  - spec ref
  - pr
  - state
  - next
  - freeze / blocked by
- 自由区块
  - blockers
  - reminders
  - follow-ups
  - temporary notes

设计目标是：

- 人类可以直接查看当前 flow memo
- 每个命令执行后自动把固定区块刷新到最新
- agent 日常只需要 add / remove note item

当前阶段的保守实现约束：

- 先写 Markdown，不引入 handoff 本地数据库
- 若要引入 Python helper，也只负责稳定更新固定区块，不承担真源职责
- 不能让 handoff 重新长成第二套 shared-state

## Directory Direction

`v3` 的目录建议优先按领域分子目录，而不是继续把大量逻辑堆在一个平面层：

```text
bin/
lib3/flow/
lib3/task/
lib3/pr/
src/flow/
src/task/
src/pr/
tests3/flow/
tests3/task/
tests3/pr/
```

这只是方向，不代表最终目录名已经冻结，但结构原则建议固定为：

- flow / task / pr 分域
- shell 薄层分域
- Python 核心分域
- tests 也按域拆开

## Python Tooling Direction

Python 侧建议使用：

- `uv`
- 最小依赖

补充约束：

- 若标准库足够，就不要引入三方依赖
- 若不是实现必需，就先不要加
- `check` 暂时不进入 `v3` 第一批实现
- cache 也暂时后置，不作为第一批设计承诺

## PR Domain Decision

结合当前保留能力与 `v3` 新主链，`pr` 域建议按两阶段理解：

- `pr draft`
  - 建远端锚点
  - 绑定 `task issue` / `repo issues` / `spec_ref` / `agent`
  - 默认不 bump 版本
- `pr ready`
  - 进入 publish gate
  - 跑 metadata preflight
  - 按 group / 显式参数决定是否执行自动版本号与 changelog
  - 保持 issue auto-link 和 stacked/base safety

这能同时满足两类目标：

- 在 planning ready 后创建 draft PR，解决“多 flow 会乱”的痛点，同时不把远端锚点前置到 planning 之前
- 晚做 publish 动作，保留自动版本与 changelog 的优秀设计而不制造过早噪音

## Frozen Command Decisions

以下命令边界已正式冻结：

### 主链与命令边界

- `v3` 主链：`repo issue -> task issue(Project) -> flow(branch) -> plan/spec ready -> draft PR -> merge`
- `roadmap` **退出主命令面**，只保留在 `vibe roadmap` 作为规划层命令
- `pr` **独立成域**，从 `flow` 中完全分离
- `flow` **只对接 branch**，不再对接 worktree
- `check` **退出第一批实现**

### Flow 命令边界

- `flow new`：创建逻辑 flow 现场，保留 `--save-unstash`
- `flow bind --issue <repo-issue>`：绑定多个 repo issue
- `flow bind task <repo-issue>`：把 repo issue 提升为唯一的 task issue
- `flow switch`：默认 stash/restore，工作区 dirty 时要求显式确认
- `flow freeze --by <repo-issue|task-issue|flow>`：标记阻塞链
- `flow show`：展示单条链的完整链路（见下方输出模型）
- `flow status`：展示所有活跃 flow 的链路大盘（见下方输出模型）

### Task 命令边界

- `task add --repo-issue <repo-issue> --group <group>`：提升 repo issue 为 task issue
- `task link <repo-issue>`：只负责补充链接，不提升
- `task --agent <agent>`：记录执行者署名

### PR 命令边界

- `pr draft`：planning ready 后的收尾动作，创建远端锚点，绑定元数据
- `pr ready`：publish gate，执行版本 bump 与 changelog
- `pr review`：本地审查并回贴到 PR comment
- `pr --agent <agent>`：记录作者/审查者署名

### 分组与发布策略

- `task` / `pr` 分组：`feature`、`bug`、`docs`、`chore`
- `feature`：默认 bump 版本与 changelog
- `bug` / `docs` / `chore`：默认不 bump，需显式 `--bump`

### 身份与署名

- `vibe auth` **退出 3.0**
- 统一使用 `vibe handoff plan/report/audit --agent <agent> --model <model>`
- 署名展示：`agent/model`（如 `claude/sonnet-4.5`）

### 输出模型

**`flow show` 输出**（第665-692行已定义）：
```text
Flow: vibe3-parallel-rebuild
Title: V3 Parallel Rebuild
State: active
Next: finalize command boundary
Task Issue: #157 remote-first governance
Spec Ref: docs/plans/2026-03-13-vibe3-parallel-rebuild-design.md
Repo Issues:
  - #157 remote-first governance
  - #158 semantic cleanup expansion
Branch: task/vibe3-parallel-rebuild
PR: #201 (draft)
```

**`flow status` 输出**（第700-720行已定义）：
- 展示所有活跃 flow 的列表
- 每条 flow 包含：name、state、task issue、repo issues、branch、pr、freeze/blocked by、next

### 审查与交接

- `plan`：planner -> executor 交接
- `report`：executor -> reviewer 交接
- `audit`：reviewer -> ready/merge 交接
- `plan/report/audit` 作为 merge 前必须可见的审查文件

### 护栏与约束

- 自动版本号/changelog 保留在 `pr` 域
- `spec_ref` 必须进入 PR 链路
- issue auto-link、preflight、stacked/base safety 保留
- handoff 提升为 flow 级 memo
- 所有命令必须有清晰输出，禁止空回复

## Design Freeze Status

以下核心架构决策已正式冻结：

- **v3 主链与命令边界**：已冻结
- **目录结构**：已冻结（lib3/, tests3/, src/ 分域结构）
- **Python 框架与依赖策略**：已冻结（uv + stdlib 优先）

待决项将在后续实施计划中通过分阶段交付物（docs/v3/）收敛：

- **迁移与切换计划**：具体如何从 v2 过渡到 v3 的操作步骤

## Shared-State Direction

3.0 彻底移除本地业务 JSON 数据库作为真源：

- `handoff.db` (SQLite)：本地责任链、handoff 与 flow 状态的真源
- `registry.json`：**停用**，功能由 `handoff.db` 与 GitHub API 替代
- `flow-history.json` / `worktrees.json`：**停用**，由 `handoff.db` 统一管理
- `roadmap.json`：**停用**，真源回归 GitHub Project

roadmap 方向继续采用 remote-first：

- 不再恢复本地 roadmap item 全量 CRUD 心智
- GitHub issue / GitHub Project 是优先真源
- 本地若保留 cache，只允许是读侧 cache

## Skill Strategy

skills 不重做，但要分阶段适配：

1. 先维持 skill 语义不变，仍围绕现有标准工作。
2. 当 `vibe3` 提供可用命令契约后，逐步把 skill 底层调用从 `vibe` / `vibe2` 导向 `vibe3`。
3. skills 的重心仍是 orchestration，不承担数据层逻辑。

## Testing Strategy

2.x 与 3.0 的测试分开：

- `tests/`：旧测试冻结，只用于旧实现回归和回退兜底
- `tests3/`：新测试
- Python 核心测试优先进入 `tests3/python/` 或等效目录
- 新测试只围绕 3.0 合同，不为兼容 2.x 内部细节背债

## Migration Principles

3.0 重建必须遵守：

1. 不在 2.x 上继续做架构性重构
2. 不开新仓库
3. 不先做大规模目录迁移
4. 先建平行实现，再切默认入口
5. 只有在 `vibe3` 稳定并经过复盘后，才决定旧 `lib/` 和 `tests/` 的去留
6. 核心架构（命令、目录、技术栈）已冻结，后续按 docs/v3/ 计划进入物理实施

## Non-goals

- 本轮不追求 `vibe3` 一开始就 100% 兼容所有旧内部实现
- 本轮不立即删除 2.x
- 本轮不先整理历史测试目录
- 本轮不先重构 skills 体系
- 本轮不靠软链接切换正式实现
- 本轮不假装 `v3` 的命令、目录和 Python 栈已经定稿

## Specification (规格说明)

本章节明确 Vibe3 Parallel Rebuild 的具体规格，作为后续实施和审核的依据。

---

### 1. 实施阶段规格 (Implementation Phases)

#### Phase 1: 核心骨架与数据层 (Foundation)
**目标**：建立基础架构和数据持久化层

**交付物**：
- [ ] `bin/vibe3` CLI 入口脚本
- [ ] `src/vibe3/cli.py` Typer 应用入口 (< 50 行)
- [ ] `src/vibe3/clients/sqlite_client.py` Vibe3Store SQLite 实现
- [ ] `src/vibe3/clients/git_client.py` Git 客户端封装
- [ ] `src/vibe3/models/flow.py` Pydantic 数据模型

**验收标准**：
- ✅ `vibe3 --help` 返回有效帮助信息
- ✅ `handoff.db` 在 `.git/vibe3/` 正确创建
- ✅ 数据库包含所有必需表：`flow_state`, `flow_issue_links`, `flow_events`, `schema_meta`
- ✅ `mypy --strict` 无类型错误
- ✅ 所有文件符合行数限制 (cli.py < 50, clients < 200, models 无限制)

**依赖**：无

**预估时间**：2-3 天

---

#### Phase 2: Flow 命令域 (Flow Domain)
**目标**：实现完整的 flow 命令集

**交付物**：
- [ ] `src/vibe3/commands/flow.py` Flow 命令层 (< 100 行)
- [ ] `src/vibe3/services/flow_service.py` Flow 业务逻辑 (< 300 行)
- [ ] `src/vibe3/ui/flow_ui.py` UI 渲染层
- [ ] 命令实现：`new`, `bind`, `show`, `status`, `list`

**验收标准**：
- ✅ `vibe3 flow new <name>` 成功创建 flow 并写入数据库
- ✅ `vibe3 flow bind <task-id>` 绑定 task 到 flow
- ✅ `vibe3 flow show` 显示 flow 详细信息（格式见 §5.1）
- ✅ `vibe3 flow status` 显示所有活跃 flow 列表（格式见 §5.2）
- ✅ `vibe3 flow status --json` 返回有效 JSON
- ✅ `vibe3 flow list` 列出所有 flow
- ✅ Commands 层无业务逻辑，Services 层无 UI 逻辑
- ✅ `mypy --strict` 无类型错误
- ✅ 单元测试覆盖核心路径

**依赖**：Phase 1 完成

**预估时间**：3-4 天

---

#### Phase 3: Task 命令域 (Task Domain)
**目标**：实现完整的 task 命令集

**交付物**：
- [ ] `src/vibe3/commands/task.py` Task 命令层 (< 100 行)
- [ ] `src/vibe3/services/task_service.py` Task 业务逻辑 (< 300 行)
- [ ] `src/vibe3/ui/task_ui.py` UI 渲染层
- [ ] 命令实现：`add`, `link`, `show`, `list`, `update`

**验收标准**：
- ✅ `vibe3 task add --repo-issue <issue>` 提升为 task issue
- ✅ `vibe3 task link <issue>` 添加参考 issue 链接
- ✅ `vibe3 task show` 显示 task 详情
- ✅ `vibe3 task list` 列出所有 task
- ✅ `vibe3 task update <id> --status <status> --group <group>` 更新 task
- ✅ `flow_issue_links` 表的唯一约束生效（每个 flow 只有一个 task issue）
- ✅ `mypy --strict` 无类型错误
- ✅ 单元测试覆盖核心路径

**依赖**：Phase 2 完成

**预估时间**：3-4 天

---

#### Phase 4: PR 命令域 (PR Domain)
**目标**：实现 PR 命令集与发布流程

**交付物**：
- [ ] `src/vibe3/commands/pr.py` PR 命令层 (< 100 行)
- [ ] `src/vibe3/services/pr_service.py` PR 业务逻辑 (< 300 行)
- [ ] `src/vibe3/clients/github_client.py` GitHub API 客户端
- [ ] 命令实现：`draft`, `show`, `review`, `ready`, `merge`

**验收标准**：
- ✅ `vibe3 pr draft` 创建 draft PR 并绑定元数据
- ✅ `vibe3 pr show` 显示 PR 详情和链路信息
- ✅ `vibe3 pr ready` 执行 publish preflight 检查
- ✅ `vibe3 pr review` 执行审查并支持回贴到 PR
- ✅ `vibe3 pr merge` 合并 PR 并更新 task 状态
- ✅ PR 描述包含 `task issue`, `repo issues`, `spec_ref`, `agent` 信息
- ✅ `mypy --strict` 无类型错误
- ✅ 单元测试覆盖核心路径

**依赖**：Phase 3 完成

**预估时间**：4-5 天

---

#### Phase 5: 修正与撤销命令 (Correction & Undo)
**目标**：实现错误恢复能力

**交付物**：
- [ ] `task unlink`, `task update` 命令
- [ ] `flow unbind`, `flow abort` 命令
- [ ] `pr close` 命令
- [ ] `vibe handoff auth` 系列命令

**验收标准**：
- ✅ `vibe3 task unlink --repo-issue <id>` 正确解除链接
- ✅ `vibe3 flow unbind task` 正确解除 task 绑定
- ✅ `vibe3 flow abort` 删除分支和 draft PR
- ✅ `vibe3 pr close` 触发状态回退
- ✅ `vibe3 handoff auth plan --agent claude --model sonnet-4.5` 正确写入署名
- ✅ 所有修正操作记录到 `flow_events` 表
- ✅ `mypy --strict` 无类型错误
- ✅ 单元测试覆盖错误恢复路径

**依赖**：Phase 4 完成

**预估时间**：2-3 天

---

#### Phase 6: 集成测试与文档 (Integration & Documentation)
**目标**：完整测试覆盖和文档完善

**交付物**：
- [ ] 端到端集成测试
- [ ] `docs/v3/` 文档完善
- [ ] 迁移指南
- [ ] 用户手册

**验收标准**：
- ✅ 所有主链路径有集成测试覆盖
- ✅ 测试覆盖率 ≥ 80%
- ✅ 所有命令有完整文档说明
- ✅ 迁移指南清晰可执行
- ✅ 用户手册完整准确

**依赖**：Phase 5 完成

**预估时间**：3-4 天

---

### 2. 数据库规格 (Database Schema)

> **真源**: 所有数据库表结构、字段约束和索引定义见 [docs/standards/v3/handoff-store-standard.md](../../standards/v3/handoff-store-standard.md)。
>
> 本文档不重复定义，避免语义冲突。

#### 必需的表

详见真源文档：

1. **`flow_state`** - 见 [handoff-store-standard.md](../../standards/v3/handoff-store-standard.md) §4.1
2. **`flow_issue_links`** - 见 [handoff-store-standard.md](../../standards/v3/handoff-store-standard.md) §4.2
3. **`flow_events`** - 见 [handoff-store-standard.md](../../standards/v3/handoff-store-standard.md) §4.3
4. **`schema_meta`** - 见 [handoff-store-standard.md](../../standards/v3/handoff-store-standard.md) §3

#### 关键字段说明

**`session_id` 字段（预留）**:
- 见 [handoff-store-standard.md](../../standards/v3/handoff-store-standard.md) §4.1
- 用途：用于记录和恢复 agent 会话
- 现阶段：仅保留字段，不实现功能

**`*_actor` 字段**:
- 格式要求：`agent/model`
- 示例：`codex/gpt-5.4`, `claude/sonnet-4.5`

---

### 3. 命令接口规格 (Command Interface Specification)

#### 3.1 `vibe3 flow` 命令集

##### `vibe3 flow new <name> [--task <task-id>] [--actor <actor>]`

**输入参数**：
- `name`: REQUIRED, string, flow 名称
- `--task`: OPTIONAL, string, task ID to bind
- `--actor`: OPTIONAL, string, 默认 "claude"

**输出格式** (成功):
```
✓ Flow created: <name>
  Branch: <branch>
  Task: <task-id> (如果提供了 --task)
```

**输出格式** (失败):
```
✗ Failed to create flow: <error-message>
```

**数据库操作**：
- INSERT/UPDATE `flow_state` 表
- INSERT `flow_events` 表 (event_type='flow_created')

**验收标准**：
- ✅ flow_slug 字段正确设置
- ✅ branch 字段为当前 git branch
- ✅ latest_actor 字段正确设置
- ✅ 返回码: 0 (成功), 1 (失败)

---

##### `vibe3 flow bind <task-id> [--actor <actor>]`

**输入参数**：
- `task-id`: REQUIRED, string, task ID to bind
- `--actor`: OPTIONAL, string, 默认 "claude"

**输出格式** (成功):
```
✓ Task bound to flow: <flow-slug>
  Task: <task-id>
```

**输出格式** (失败):
```
✗ Failed to bind task: <error-message>
```

**数据库操作**：
- UPDATE `flow_state` 表
- INSERT `flow_events` 表 (event_type='task_bound')

**验收标准**：
- ✅ task 正确绑定到 flow
- ✅ latest_actor 字段更新
- ✅ 返回码: 0 (成功), 1 (失败)

---

##### `vibe3 flow show [<flow-name>]`

**输入参数**：
- `flow-name`: OPTIONAL, string, flow 名称。省略则使用当前 branch

**输出格式** (文本):
```
Flow: <flow-slug>
  Branch: <branch>
  Status: <status>
  Task Issue: #<number> (如果存在)
  PR: #<number> (如果存在)
  Spec: <spec-ref> (如果存在)
  Next Step: <next-step> (如果存在)
  Issues: #<n1>, #<n2> (如果存在)
```

**输出格式** (失败):
```
No flow found for branch: <branch>
```

**数据库操作**：
- SELECT `flow_state` 表
- SELECT `flow_issue_links` 表

**验收标准**：
- ✅ 显示完整 flow 信息
- ✅ 包含所有关联的 issue
- ✅ 返回码: 0 (成功), 1 (flow 不存在)

---

##### `vibe3 flow status [--json]`

**输入参数**：
- `--json`: OPTIONAL, boolean, 输出 JSON 格式

**输出格式** (文本):
```
         Flow Status
┏━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Field  ┃ Value                    ┃
┡━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Flow   │ <flow-slug>              │
│ Branch │ <branch>                 │
│ Status │ <status>                 │
└────────┴──────────────────────────┘
```

**输出格式** (JSON):
```json
{
  "branch": "<branch>",
  "flow_slug": "<flow-slug>",
  "flow_status": "<status>",
  "task_issue_number": <number> | null,
  "pr_number": <number> | null,
  "spec_ref": "<spec-ref>" | null,
  "next_step": "<next-step>" | null,
  "issues": [
    {
      "branch": "<branch>",
      "issue_number": <number>,
      "issue_role": "<role>"
    }
  ]
}
```

**输出格式** (无 flow):
```
No active flow
```

**数据库操作**：
- SELECT `flow_state` 表
- SELECT `flow_issue_links` 表

**验收标准**：
- ✅ JSON 输出格式正确
- ✅ 文本输出使用 Rich Table
- ✅ 返回码: 0 (成功), 0 (无 flow)

---

##### `vibe3 flow list [--status <status>]`

**输入参数**：
- `--status`: OPTIONAL, string, 过滤状态 (active/idle/missing/stale)

**输出格式**:
```
                              Flows
┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┓
┃ Flow                   ┃ Branch                      ┃ Status ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━┩
│ <flow-slug-1>          │ <branch-1>                  │ <status>│
│ <flow-slug-2>          │ <branch-2>                  │ <status>│
└────────────────────────┴─────────────────────────────┴────────┘
```

**输出格式** (无 flow):
```
No flows found
```

**数据库操作**：
- SELECT `flow_state` 表 (带可选过滤)

**验收标准**：
- ✅ 列表正确显示所有 flow
- ✅ 状态过滤生效
- ✅ 返回码: 0 (成功), 0 (无 flow)

---

### 4. 代码质量规格 (Code Quality Specification)

#### 4.1 类型安全
- **要求**: 所有 Python 文件必须通过 `mypy --strict` 检查
- **允许**: 无例外
- **验证**: CI 自动检查

#### 4.2 代码行数限制
| 文件类型 | 行数限制 | 说明 |
|---------|---------|------|
| `cli.py` | < 50 行 | 只负责创建 Typer app 和注册命令 |
| `commands/*.py` | < 100 行 | 参数定义、验证、格式化输出 |
| `services/*.py` | < 300 行 | 业务逻辑编排 |
| `clients/*.py` | < 200 行 | 外部系统封装 |
| `models/*.py` | 无限制 | Pydantic 数据模型 |
| `ui/*.py` | < 150 行 | UI 渲染逻辑 |

#### 4.3 测试覆盖率
- **最低要求**: 80% 代码覆盖率
- **核心路径**: 100% 覆盖（flow/task 命令集）
- **工具**: pytest + pytest-cov

#### 4.4 依赖管理
**允许的依赖** (见 [03-coding-standards.md](../v3/infrastructure/03-coding-standards.md)):
- typer: CLI 框架
- rich: 终端输出
- pydantic: 数据验证
- loguru: 日志
- pytest: 测试框架

**禁止的依赖**:
- ❌ argparse (用 typer 替代)
- ❌ ORM (SQLAlchemy, peewee)
- ❌ Web 框架 (Django, Flask, FastAPI)
- ❌ print() (用 logger 或 rich)

---

### 5. 输出格式规格 (Output Format Specification)

#### 5.1 `flow show` 输出格式

**完整格式**:
```
Flow: vibe3-parallel-rebuild
  Branch: task/vibe3-parallel-rebuild
  Status: active
  Task Issue: #157
  PR: #201 (draft)
  Spec: docs/plans/2026-03-13-vibe3-parallel-rebuild-design.md
  Next Step: finalize command boundary
  Issues: #157, #158
```

**最小格式** (仅有必需字段):
```
Flow: test-flow
  Branch: task/test-flow
  Status: active
```

**验证要点**:
- ✅ 字段顺序固定
- ✅ 缺失字段不显示
- ✅ 使用 Rich 颜色标注

---

#### 5.2 `flow status` 输出格式

**列表格式**:
```
         Flow Status
┏━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Field  ┃ Value                    ┃
┡━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Flow   │ test-flow                │
│ Branch │ task/phase-02-foundation │
│ Status │ active                   │
└────────┴──────────────────────────┘
```

**JSON 格式**:
```json
{
  "branch": "task/phase-02-foundation",
  "flow_slug": "test-flow",
  "flow_status": "active",
  "task_issue_number": null,
  "pr_number": null,
  "spec_ref": null,
  "next_step": null,
  "issues": []
}
```

**验证要点**:
- ✅ JSON 格式符合 Pydantic model_dump() 输出
- ✅ 表格使用 Rich Table
- ✅ 日期时间字段序列化为 ISO 8601 字符串

---

### 6. 性能规格 (Performance Specification)

#### 6.1 响应时间要求
| 操作类型 | 响应时间要求 | 说明 |
|---------|------------|------|
| `flow show` | < 500ms | 本地数据库查询 |
| `flow status` | < 1s | 本地数据库查询 |
| `flow list` | < 2s | 本地数据库查询 |
| `task add` | < 2s | 含 GitHub API 调用 |
| `pr draft` | < 5s | 含 GitHub API 调用 |

#### 6.2 数据库性能
- **数据库大小**: 预期 < 10MB (1000 个 flow)
- **查询性能**: < 100ms (本地 SQLite)
- **写入性能**: < 50ms (本地 SQLite)

---

### 7. 安全规格 (Security Specification)

#### 7.1 数据验证
- **输入验证**: 所有用户输入必须通过 Pydantic 验证
- **SQL 注入防护**: 使用参数化查询，禁止字符串拼接
- **路径遍历防护**: 验证所有文件路径

#### 7.2 身份认证
- **GitHub Token**: 从环境变量 `GH_TOKEN` 读取
- **不存储敏感信息**: 数据库不存储 token、密码等敏感信息

#### 7.3 权限控制
- **本地数据库**: 无权限控制，信任本地用户
- **GitHub API**: 继承 GitHub CLI 的权限模型

---

### 8. 错误处理规格 (Error Handling Specification)

#### 8.1 错误分类
| 错误类型 | 返回码 | 说明 |
|---------|-------|------|
| 成功 | 0 | 命令成功执行 |
| 用户错误 | 1 | 参数错误、验证失败 |
| 系统错误 | 2 | 数据库错误、网络错误 |
| 未找到 | 0 (特殊) | flow/task 不存在 |

#### 8.2 错误消息格式
```
✗ Failed to <action>: <error-message>

Recovery: <suggested-action>
```

**示例**:
```
✗ Failed to create flow: Database connection error

Recovery: Check if .git/vibe3/ directory exists and is writable
```

#### 8.3 日志规格
- **日志级别**: DEBUG, INFO, WARNING, ERROR
- **日志输出**: stderr (使用 loguru)
- **日志格式**: `{timestamp} | {level} | {module}:{function}:{line} - {message}`
- **生产环境**: 只显示 WARNING 及以上

---

### 9. 测试验收规格 (Test Acceptance Specification)

#### 9.1 单元测试要求
- **覆盖范围**: 所有 `services/` 和 `clients/` 模块
- **Mock 策略**: 使用 Protocol 接口 Mock 外部依赖
- **测试隔离**: 每个测试使用独立的内存数据库

#### 9.2 集成测试要求
- **测试场景**:
  1. 创建 flow -> 绑定 task -> 创建 PR
  2. 修正错误：unlink task -> rebind
  3. 废弃 flow -> 验证状态
- **数据验证**: 每个操作后验证数据库状态

#### 9.3 验收标准清单
- [ ] 所有单元测试通过 (100%)
- [ ] 所有集成测试通过 (100%)
- [ ] 代码覆盖率 ≥ 80%
- [ ] `mypy --strict` 无错误
- [ ] 所有命令有完整文档
- [ ] 所有错误消息清晰可读
- [ ] 性能符合规格要求

---

## Recommended First Deliverables

3.0 第一阶段剩余任务：

1. 产出迁移与切换计划

只有上述事项明确后，才进入实现。
