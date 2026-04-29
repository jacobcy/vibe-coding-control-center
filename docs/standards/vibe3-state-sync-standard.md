# Vibe3 State Sync Standard

状态：Active

## 1. 目的

本标准定义 `state/*` labels 在 Vibe3 编排中的使用方式。

它回答三个问题：

- 哪些对象是真源
- `state/*` 分别表示什么
- manager、plan、run、review 各自对 state 做什么，不做什么

本标准不定义：

- GitHub Project 视图布局
- handoff 正文格式细节
- skill / supervisor 文案模板

这些分别以其他标准为准。

调试方法与日志规范见 [agent-debugging-standard.md](agent-debugging-standard.md)。

## 2. 真源分层

状态同步只允许使用以下真源：

- GitHub issue：任务身份真源
- GitHub `state/*` labels：编排状态真源
- 最新人类 issue comment：人类指示真源
- scene 事实：当前 issue / flow / branch / worktree / session
- handoff 与 authoritative refs：agent 交接真源

以下内容不是真源：

- 历史 comment 中写过的状态文字
- 历史 handoff 中写过的 `ready / claimed / blocked / in-progress`
- GitHub Project 字段
- 本地临时日志
- 自动保存到 `.git/vibe3/handoff/...` 的 plan/run/review artifact 路径本身

### 2.1 authoritative refs 与 artifact 的边界

本标准中的 `plan_ref` / `report_ref` / `audit_ref` 指的是 authoritative refs。

authoritative ref 只在以下条件同时满足时成立：

- 产物已写成 canonical 文档
- 通过 `vibe3 handoff plan|report|audit` 显式登记
- 对应 ref 已进入 flow state

因此：

- 自动保存到 `.git/vibe3/handoff/...` 的 plan/run/review artifact 只是共享 artifact，不自动等于 authoritative ref
- `temp/logs/*.async.log` 只是调试日志，不属于 handoff/ref 真源
- manager 读取的是当前 flow state 中的 refs，不是根据最新 artifact 文件名反推 ref

### 2.2 路径类型边界

Vibe3 中的路径必须先区分对象类型，再决定如何显示与如何写入。

#### 日志路径

- `log_path` 只表示执行日志
- 默认位于仓库执行目录下的 `temp/logs/...`
- 它服务于调试 / 观测，不得登记为 `plan_ref / report_ref / audit_ref`
- 任何 `*.async.log`、`temp/logs/...`、session wrapper log 都不得被解释为 handoff 文档

#### agent 交接文档路径

- agent 主动产出的 canonical 文档必须位于 agent worktree 内
- 典型位置是当前 worktree 下的 `docs/plans/...`、`docs/reports/...`
- `vibe3 handoff plan|report|audit <path>` 登记的 `*_ref` 必须指向这类 worktree 内文档
- 超出 agent worktree 的路径不得作为 canonical handoff ref，因为这会引发跨现场 / 权限问题

#### 共享 handoff artifact 路径

- `.git/vibe3/handoff/...` 属于共享 handoff store
- 它只承载共享 buffer / artifact，不承载 canonical agent deliverable ref
- agent 需要查看这类共享 artifact 时，必须通过 handoff 命令读取，而不是假设自己对 `.git/...` 路径有直接稳定访问能力

### 2.3 review 路径约束与事件区分

review 阶段存在两类写入，它们都必须与 worktree 边界兼容，但事件语义不同：

- agent 主动写入的 review 文档：
  - 必须位于 agent worktree 内
  - 通过 `vibe3 handoff audit <path>` 显式登记
  - 事件类型为 `handoff_audit`
- 系统被动写入的 review 文档：
  - 用于最小审计收口 / fallback / 自动登记
  - 必须优先写到对应 worktree 内，而不是 `temp/` 或 `.git/vibe3/handoff/`
  - 事件类型为 `audit_recorded`

因此：

- `handoff_audit` 表示 agent 主动交接
- `audit_recorded` 表示系统被动记录
- 两者都可以成为 review 观察材料，但语义不能混淆
- UI 与调试命令必须保留这种事件区分

如果历史描述与当前 GitHub labels 冲突，以当前 labels 为准。

## 3. 核心原则

### 3.1 状态由 labels 驱动

`plan / run / review` 是否应该启动，由当前 GitHub `state/*` labels 和现场真源共同决定。

不允许：

- 仅凭 handoff 文本直接启动下一 agent
- 仅凭历史 comment 推断当前阶段
- 让 manager 直接派发下游 agent 以绕过状态迁移

### 3.2 manager 是状态控制器，不是启动器

manager 的职责只有：

- 读 scene
- 读最新评论
- 读 handoff / refs
- 写 issue comment
- 写 handoff
- 改 `state/*` labels

manager 不直接：

- 启动 `plan`
- 启动 `run`
- 启动 `review`
- 修改代码

### 3.3 comment 与 handoff 分工

- 需要反馈给人类：写 issue comment
- 需要交给后续 agent：写 handoff

handoff 不代替 issue comment。

补充规则：

- 如果 manager 发现当前无法推进，必须先检查最新评论里是否已经说明原因
- 若最新评论没有明确原因，manager 必须写一条 issue comment 解释本轮为什么停止
- 如果 manager 进入 `state/blocked`，必须先检查已有 comments 是否已经覆盖同一 blocker
- 只有出现新的 blocker 时，manager 才应追加新的 issue comment
- 不允许在“无法推进”时静默退出，避免黑箱

### 3.4 每轮只处理当前 state

每一轮只处理当前 `state/*` 应做的事情。

不允许：

- 跳过 `state/claimed`
- 从 `state/ready` 直接假设进入 `state/in-progress`
- 让单轮 manager 判断同时完成多个阶段迁移

## 4. 状态定义

### `state/ready`

含义：

- issue 已进入编排域
- 可以由 manager 认领
- 尚未进入稳定执行现场

典型动作：

- manager 核查 scene
- 读取最新评论
- 决定是否迁移到 `state/claimed`

### `state/claimed`

含义：

- manager 已认领该 issue
- scene 已被确认或已可恢复
- 当前 issue 已被批准进入 planning

典型动作：

- plan agent 启动
- plan 完成后写 canonical plan 文档、登记 `plan_ref`，再回到 `state/handoff`
- 如果 planner 只产出 auto-saved artifact 而没有登记 authoritative `plan_ref`，该轮视为 no-op，进入 `state/blocked`

### `state/in-progress`

含义：

- 执行阶段正在进行
- 当前应以执行产物和 `report_ref` 为主要观察对象

典型动作：

- run agent 执行
- 执行结束后写 canonical report 文档、登记 `report_ref`，再回到 `state/handoff`
- 如果 executor 只产出 auto-saved artifact 而没有登记 authoritative `report_ref`，该轮视为 no-op，进入 `state/blocked`

### `state/handoff`

含义：

- 本阶段执行已结束
- 等待 manager 读取 handoff / refs 做下一步判断

典型动作：

- manager 读 `spec_ref / plan_ref / report_ref / audit_ref`
- 决定进入：
  - `state/claimed`
  - `state/in-progress`
  - `state/review`
  - `state/merge-ready`
  - `state/blocked`

### `state/review`

含义：

- 已进入审查阶段
- 当前应以 `audit_ref` 和 review 结论为主要观察对象

典型动作：

- review agent 执行
- 审查输出必须给出合法 `VERDICT: PASS | MAJOR | BLOCK`
- verdict 校验成功后，通过发布 `ReviewCompleted` 事件，由事件处理器自动登记一个最小 authoritative `audit_ref` 并更新状态
- 审查结束后回到 `state/handoff`

### `state/blocked`

含义：

- 当前 issue 暂不应继续推进
- 场景 1：**手动阻塞**（由人或 Manager 标记 `blocked_reason`）
- 场景 2：**依赖阻塞**（`flow_issue_links` 中有未完成的依赖 Issue）

典型动作：

- **主动巡逻**：Orchestra Dispatcher 会主动拉取该状态的 Issue 执行 Qualify Gate 校验。
- **自动解套**：当所有依赖 Issue 均到达 `closed` 终态且无手动 `blocked_reason` 时，系统自动解除阻塞。
- **智能恢复**：解封后，系统利用 `FlowResumeResolver` 根据本地 `pr_ref / audit_ref / report_ref / plan_ref` 自动推断并恢复到正确的目标状态（不限于 `state/ready`）。

关键规则：

- 依赖完成的唯一判据是 GitHub `issue.state == "closed"`。
- 解封后，Orchestra 保证 Label 变更先于 Intent 派发。
- 如果解封目标状态已有活动的 Agent Session，不会重复派发。

### `state/failed`

含义：

- `plan / run / review` 执行过程中发生了真实报错
- 发布 `IssueFailed` 事件，由处理器记录失败原因并更新状态
- 这是 bug / error 语义，不是 manager 的业务阻塞语义

典型动作：

- 记录失败 comment
- 暂停新的自动任务进入
- 由人类或修复任务先处理该错误，再决定恢复到对应阶段

### `state/merge-ready`

含义：

- manager 认为当前 issue 已达到“等待最终确认/合并”的状态

典型动作：

- 等待人类或 audit agent 最终确认

## 5. 推荐主链

推荐主链如下：

1. `state/ready`
2. manager scene audit
3. `state/claimed`
4. plan agent 启动
5. plan 完成并写 handoff
6. `state/handoff`
7. **manager 自动恢复**，读取 refs 后决定是否进入 `state/in-progress`
8. `state/in-progress`
9. run agent 启动
10. run 完成并写 handoff
11. `state/handoff`
12. **manager 自动恢复**，读取 refs 后决定是否进入 `state/review`
13. `state/review`
14. review agent 启动
15. review 完成并写 handoff
16. `state/handoff`
17. **manager 自动恢复**，最终判断
18. `state/merge-ready`

**Manager Handoff Resume**：

当 issue 处于 `state/handoff` 时，manager 会自动恢复执行（无需人工干预）。这个 resume 路径确保：

- Manager 始终是状态决策者
- 每次阶段完成后，manager 都有机会判断下一步
- Issue 不会卡在 `state/handoff` 等待人工触发

关键规则：

- agent 执行结束后，只写 handoff，不直接推进到下一状态
- 下一状态统一由 manager 决定
- manager 在 `state/handoff` 自动恢复（自动触发）
- manager 无法推进时使用 `state/blocked`
- `plan / run / review` 执行报错时使用 `state/failed`

## 6. manager 判定规则

### 6.1 `ready -> claimed`

manager 只有在以下条件都满足时，才应迁移：

- 当前 labels 真源显示 `state/ready`
- scene 健康或可恢复
- 最新人类 comment 没有明确要求暂停、等待或阻止推进

迁移后必须再次读取 labels 确认：

- `state/claimed` 已生效

在确认前，不得假设当前已经进入下一阶段。

补充硬规则：

- 在 `state/ready` 阶段，本轮必须落下明确状态结果
- 允许的结束结果只有：
  - `state/claimed`
  - `state/blocked`
- 不允许保持 `state/ready` 后直接停止

### 6.2 `claimed` 是 plan 启动标志

`state/claimed` 表示：

- manager 已认领
- scene 已确认
- 当前 issue 可以进入 planning

因此：

- `state/claimed` 是 plan agent 的启动标志
- manager 不在 `claimed` 阶段继续做 spec / plan / run / review 判断
- manager 在完成 `ready -> claimed` 后，应停止本轮判断

外部触发器/调度器在看到 `state/claimed` 后，应启动 plan agent。

plan agent 完成后：

- 写 handoff
- 发布 `PlanCompleted` 事件
- 由事件处理器验证 `plan_ref` 并将 issue 调整为 `state/handoff`
- **Manager 自动恢复**，读取 refs 并决定下一步

### 6.3 `handoff` 触发 manager 自动恢复

当 issue 进入 `state/handoff` 时，orchestra 会自动触发 manager resume：

**触发条件**：
- Issue 有 canonical task flow（`task/issue-*` 分支）
- 没有活动的 manager session

补充语义：

- manager 的 handoff resume 不以 `plan_ref` / `report_ref` / `audit_ref` 是否存在作为 dispatch 前置条件
- authoritative ref 缺失的硬校验应在 plan/run 完成阶段处理，而不是延后到 manager dispatch 阶段
- 因此 manager 会对 `state/handoff` 做重新分诊，但不把 handoff 目录中的 artifact 自动视为 authoritative ref

**去重机制**：
- 如果已有 live manager session，不会重复 dispatch
- 如果 session 结束且无进展，会 auto-block

**Progress Detection**：
Manager 在 `state/ready` / `state/handoff` 路径判断是否有进展时，主判断标准是：

- 当前状态是否已离开 `state/ready` 或 `state/handoff`
- 或 manager 是否明确执行了 abandon / close 等终止动作

仅出现以下信号，不足以单独视为 manager 路径的有效进展：

- 新的 issue comment
- 新的 handoff 文件
- 新的 auto-saved artifact
- Flow refs 更新但状态未迁移

Async runtime 和 sync CLI 执行使用相同的 progress 判断标准。

### 6.4 blocked 判断

**当前 manager mainline**:
- manager 是 flow owner，负责推进 issue
- 如果 manager session 结束且没有任何可观察的状态变化，自动迁移到 `state/blocked`
- blocked follow-up（如 doctor/aborted 处理）明确在当前 mainline 之外，未来扩展

manager 可以把 issue 调整到 `state/blocked`，但必须满足：

- blocker 来源于当前 labels、最新评论、当前 scene、或当前 refs
- blocker 是当前事实，而不是历史 handoff 中的旧验收结论

manager 不应：

- 用历史 handoff 中的旧 blocker 自动覆盖最新评论
- 用历史验收项自动阻止当前状态迁移
- 因为关联 issue 仍 open 就机械回退到 blocked

如果 blocker 需要人类确认，必须写 issue comment。

如果 manager 判断当前无法推进，但又不足以立即迁移到 `state/blocked`，也必须遵守同一条透明度规则：

- 先检查最新评论里是否已有原因说明
- 若没有，则写 issue comment 说明：
  - 当前卡点
  - 依据的真源
- 需要谁提供什么信息或决策

### 6.5 blocked 与 failed 的边界

`state/blocked` 只用于 manager 的业务判断：

- 依赖未满足
- 最新人类 comment 明确要求暂停
- 当前 scene 不健康，无法安全继续
- refs/证据不足，需要人类或上游补信息

`state/failed` 只用于执行器错误：

- plan agent 报错
- run agent 报错
- review agent 报错
- 触发链、环境、代码或解析错误导致当前阶段无法完成

规则：

- manager 不因为执行报错把 issue 标成 `blocked`
- `plan / run / review` 不因为业务阻塞把 issue 标成 `failed`
- server 看到 open 的 `state/failed` 时，应暂停新的自动任务进入，直到失败解除

### 6.6 `handoff` 下的 authoritative refs 判定顺序

在 `state/handoff` 下，manager 读取 `spec_ref / plan_ref / report_ref / audit_ref` 时，必须按下面顺序判断：

0. 先区分 artifact 与 authoritative ref
- `handoff show` 中出现的 artifact 路径，只表示有交接材料
- 只有 flow state 中已登记的 `spec_ref / plan_ref / report_ref / audit_ref` 才是 authoritative refs
- manager 不得根据 artifact 文件名、session log、或 handoff 正文去脑补 authoritative ref 已存在

1. 如果缺少 `spec_ref`
- 当前轮不进入 `run` / `review`
- 先补齐 spec 真源:
  - 绑定 issue 为 spec: `vibe flow bind <issue-number> --role task`
  - 或绑定 spec 文件: `vibe flow update --spec <file>`
- 写 issue comment 说明当前缺失的是 spec 真源
- 必要时写 handoff
- `exit()`

2. 如果已有 `spec_ref`，但缺少 `plan_ref`
- 说明 planning 尚未完成或 planning 产物不可用
- manager 可以据当前 scene 决定回到 `state/claimed` 或直接 `state/blocked`
- 但缺失 `plan_ref` 不能被 handoff artifact 自动补齐
- manager 不在这一轮直接替代 plan 产出 plan 结论

3. 只有当 `plan_ref` 已存在时，manager 才能继续判断是否进入 `state/in-progress`

4. 只有当 `report_ref` 已存在时，manager 才能继续判断是否进入 `state/review`

5. review 阶段的硬输入条件仍然是合法 verdict
- verdict 校验成功后，系统必须自动生成并登记最小 authoritative `audit_ref`
- manager 应优先读取该 canonical 审查引用，而不是直接消费原始 review stdout
- 完整审查文档仍可额外产出，但不再是 review 成功的额外格式负担

## 7. handoff 与 refs 的使用

handoff 的作用是：

- 记录交接上下文
- 记录 findings
- 记录 blocker
- 记录建议下一步

handoff 不是：

- 当前状态真源
- 人类反馈真源
- 直接触发下游 agent 的唯一依据

refs 的推荐语义：

- `spec_ref` / `plan_ref`：准备类产物
- `report_ref`：执行结果
- `audit_ref`：审查结果

生产规则：

- `plan_ref` 必须通过 `vibe3 handoff plan <path>` 显式登记
- `report_ref` 必须通过 `vibe3 handoff report <path>` 显式登记
- `audit_ref` 在 review verdict 校验成功后由系统自动登记；也允许显式 `vibe3 handoff audit <path>` 覆盖为更完整的审查文档
- auto-saved handoff artifact 只用于共享与审计，不自动升级为 authoritative ref

阶段硬规则：

- planner 成功但缺少 authoritative `plan_ref`，该轮按 no-op 进入 `state/blocked`
- executor 成功但缺少 authoritative `report_ref`，该轮按 no-op 进入 `state/blocked`
- reviewer 以合法 verdict 完成；系统随后自动补齐最小 authoritative `audit_ref`

manager 在 `state/handoff` 读取 refs 时，只做状态判断，不做实现。

## 8. agent 启动标志

### plan agent

启动标志：

- 当前 issue 为 `state/claimed`

manager 不负责直接启动 plan。
manager 只负责把 issue 迁移到 `state/claimed`。

### run agent

启动标志：

- 当前 issue 为 `state/in-progress`

manager 不负责直接启动 run。
manager 只负责在 `state/handoff` 读完 handoff/refs 后，决定是否将 issue 迁移到 `state/in-progress`。

### review agent

启动标志：

- 当前 issue 为 `state/review`

manager 不负责直接启动 review。
manager 只负责在 `state/handoff` 读完 handoff/refs 后，决定是否将 issue 迁移到 `state/review`。

## 9. 推荐观察面

manager / supervisor / 人机调试时，优先使用：

```bash
uv run python src/vibe3/cli.py task show <target-branch>
uv run python src/vibe3/cli.py task show <target-branch> --comments
uv run python src/vibe3/cli.py task status
uv run python src/vibe3/cli.py handoff show <target-branch>
gh issue view <issue-number> --json labels,state
```

其中：

- `task show <target-branch>`：单 task-scene 真源
- `task show <target-branch> --comments`：最新评论与最新人类指示
- `task status`：全局任务/队列状态（不是单个 `ready` issue 的健康真源）
- `handoff show <target-branch>`：当前交接材料

### 9.1 `handoff show` 与 `flow show` 的显示职责

两者不是重复入口，而是不同观察面：

- `handoff show` 是 agent / manager / reviewer 的交接入口
  - 默认显示相对路径
  - 相对路径以目标 worktree 为基准，避免跨 worktree 复制后失效
  - 当对象位于 `.git/vibe3/handoff/...` 时，仍通过 handoff 命令负责解析与展示
- `flow show` 是人类观测入口
  - 应显示绝对路径
  - 目标是让人类可以直接打开日志、交接文档、review 文档
  - 但显示绝对路径不改变对象类型：log 仍是 log，handoff 仍是 handoff

### 9.2 共享 handoff artifact 的命令入口

`.git/vibe3/handoff/...` 下的共享文件不得要求 agent 直接走文件系统路径访问。

必须提供并优先使用命令入口：

```bash
uv run python src/vibe3/cli.py handoff show <target-branch>
uv run python src/vibe3/cli.py handoff show --artifact <path>
```

规则：

- agent 读取共享 handoff store 时，优先使用 `handoff show`
- `--artifact` 用于读取共享 artifact 或指定 handoff 文件
- 不要求 agent 直接 `cat .git/vibe3/handoff/...`
- 这样可以避免 worktree 外路径导致的权限与可见性问题

补充规则：

- `state/ready` 阶段的 scene 健康判断，优先使用 `task show <target-branch>`、
  `handoff show <target-branch>`、`pwd`、`git branch --show-current`
- 全局 `task status` 中的 `Server: stopped/unreachable`、或“当前没有 active issues”
  这类信号，不能单独作为把当前 `ready` issue 调整为 `blocked` 的依据

## 10. 禁止事项

禁止以下认知偏差：

- 把历史 handoff 文本当成当前 state
- 把旧 blocker 当成永久 blocker
- 把 manager 当作下游 agent 启动器
- 让 `state/*` 与 GitHub Project 字段形成双真源
- 未确认 labels 已生效就假设状态已迁移

## 11. 对齐要求

如果其他文档与本标准冲突，以本标准为准，后续应同步修正：

- manager prompt / supervisor prompt
- task / status / flow 命令文案
- GitHub Project 视图说明
- 调试标准（见 [agent-debugging-standard.md](agent-debugging-standard.md)）
- orchestra 运行时标准（见 [vibe3-orchestra-runtime-standard.md](vibe3-orchestra-runtime-standard.md)）
