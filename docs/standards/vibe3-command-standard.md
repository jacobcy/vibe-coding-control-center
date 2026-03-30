# Vibe3 命令设计标准

**维护者**: Vibe Team
**最后更新**: 2026-03-27
**状态**: Active

---

> 状态确认优先、最小纠正与 `flow/task/pr` 联动判定表见
> [vibe3-state-sync-standard.md](vibe3-state-sync-standard.md)。

## 一、核心概念

### 1.1 数据模型

```
SQLite (本地缓存)                 GitHub (真源)
├── flow_state                   ├── Issues (真源)
│   ├── branch (PK)              │   └── 所有 issue 都是 GitHub issue
│   ├── flow_slug                │
│   ├── flow_status              └── Projects (真源)
│   ├── project_item_id              └── Project items
│   ├── project_node_id          │
│   └── updated_at               └── Pull Requests (真源)
│                                    └── pr_number (真源)
│
└── flow_issue_links (关系真源)
    ├── branch
    ├── issue_number
    └── issue_role (task/related/dependency)
```

**重要**: SQLite 只保留运行时执行现场与最小离线索引，GitHub 真源字段实时读取。

### 1.2 Hydration 规则

以下字段为运行时计算字段（Hydrated Fields），禁止持久化到 `flow_state`：

- `task_issue_number`: 优先从 `flow_issue_links` (role=task) 读取
- `pr_number`: 从 GitHub PR API 实时查询
- `pr_ready_for_review`: 从 GitHub PR API 实时查询

### 1.3 Flow 标识

**`branch` 是 PRIMARY KEY（指针）**，`flow_slug` 是显示名称。

- `branch = "task/my-feature"` → `flow_slug = "my-feature"`
- 所有命令都按 `branch` 查询，不支持按 `flow_slug` 查询

### 1.3 Issue Role

| Role | 含义 | 示例 |
|------|------|------|
| `task` | Flow 的主要执行目标 | #220: 实现统一存储 |
| `related` | 相关 issue（需求来源） | #219: 实现报告系统 |
| `dependency` | 依赖的其他 task | #218: 基础设施准备 |

**重要**：
- Issue Role 是**关系语义**，不是 issue 的类型属性
- 同一个 issue 可以在不同的 flow 中有不同的 role
- Issue Role 是**唯一真源**，GitHub label 是同步副作用

### 1.4 Task Issue 概念

**定义**: vibe3 视角概念，指被 vibe3 管理的 GitHub issue

**判定标准**（同时满足）:
1. SQLite `flow_issue_links` 有记录，`issue_role = task` 或 `dependency`
2. 若启用标签自动化，GitHub issue 应镜像 `vibe-task` 标签

**重要区别**:
- **Task** = SQLite 有记录的 issue（正式纳入 flow 管理）
- **vibe-task 标签** = 后续自动化可镜像的 GitHub 过滤标签
- 如果 issue 被记录为 task/dependency，后续自动化应可据此补齐标签

**注意**: Task 不是独立实体，是 flow 的属性（有 task_issue_number 的 flow）

---

## 二、命令设计目标

### 2.1 命令职责

| 命令 | 职责 | 视角 | 用户 |
|------|------|------|------|
| `flow add` | 注册当前分支为 flow，可选绑定 task/spec | Flow 创建 | 开发者 |
| `flow create` | 创建新分支并注册 flow，可选绑定 task/spec | Flow 创建 | 开发者 |
| `flow show` | 显示完整执行现场信息 | 执行现场管理 | 开发者 |
| `flow bind` | 绑定 issue 到 flow（指定 role） | Flow 绑定 | 开发者 |
| `task show` | 显示 GitHub Project 管理信息 | 项目管理 | 管理者 |
| `task list` | 列出所有 task | Task 查询 | 所有用户 |
| `snapshot build/show/diff` | 代码库结构基线与对比 | 结构治理 | 开发者 |
| `pr create/show/ready` | PR 生命周期联动（读取/写入当前 flow） | PR 协作 | 开发者 |

**兼容说明**：
- `flow new` 为历史别名，标准入口为 `flow add`
- `task status` 不再作为标准流程推荐（收敛到 flow 驱动）

### 2.2 flow show vs task show

**flow show** - 执行现场视角（完整）
- ✅ 显示所有 issues（task, related, dependency）
- ✅ 显示 issue titles（从 GitHub Issues API）
- ✅ 显示 PR 信息（从 GitHub PRs API）
- ✅ 显示 plan/execute/review 引用
- ✅ 显示阻塞关系

**结构入口**
- `snapshot build/show/diff` 是结构与快照视角的标准入口
- review / governance 语义以 `snapshot` 为准

**task show** - GitHub Project 管理视角
- ✅ 显示 Project 绑定状态（bound/unbound）
- ✅ 显示 Project 字段（Status, Priority, Assignees）
- ✅ 显示 task issue
- ✅ 检查 identity_drift（数据一致性）

### 2.3 Issue 关联规则

**统一关系入口**:

```bash
# flow bind: 统一写入 issue -> flow 关系
vibe3 flow bind 220
# SQLite: flow_issue_links(branch, 220, role='task')

vibe3 flow bind 219 --role related
# SQLite: flow_issue_links(branch, 219, role='related')

vibe3 flow bind 218 --role dependency
# SQLite: flow_issue_links(branch, 218, role='dependency')
```

**关键原则**:
- `flow bind`: Issue → Flow 关系，存本地，是 task 指针入口
- 一个 flow 只能有一个 task issue
- 标签自动化只能镜像 `issue_role`，不能反向决定 `issue_role`

---

## 三、Task 搜索规则

### 3.1 Task 定义

| 类型 | 定义 | SQLite 记录 | vibe-task 标签 |
|------|------|------------|----------------|
| **正式 Task** | 纳入 flow 管理 | ✅ flow_issue_links 有记录 | ✅ 有 |
| **计划中 Task** | 列入计划但未开始 | ❌ 无 | ✅ 有 |
| **普通 Issue** | 未被管理 | ❌ 无 | ❌ 无 |

**SQLite 记录**:
- `flow_issue_links` 表存储 **issue 和 flow 的关系**
- `issue_role = task/related/dependency` 表示 issue 在 flow 中的角色
- GitHub body / label 自动化若启用，也只能镜像这套关系

### 3.2 搜索范围

当前 `task list` 已实现的是：

1. 默认列出有 `task_issue_number` 的 flow
2. `--issue` 当前按 task issue 查询 flow
3. 更广义的搜索/过滤属于后续扩展，不应在当前标准里当作已实现能力

### 3.3 搜索实现

**实现逻辑**:
```python
# 1. 搜索正式 task（SQLite 有记录）
flows = store.get_all_flows()  # 从 flow_state
tasks = [f for f in flows if f.task_issue_number]
formal_tasks = filter_by_issue_search(tasks, keyword)  # 搜索 issue title/body

# 2. 搜索计划中 task（只有 vibe-task 标签）
planned_issues = github_client.search_issues(
    label="vibe-task",
    query=keyword
)
planned_tasks = [i for i in planned_issues if not in_sqlite(i.number)]

# 3. 合并输出，明确区分
```

---

## 三、参数命名标准

### 3.1 统一命名原则

| 参数类型 | 命名 | 类型 | 说明 |
|---------|------|------|------|
| Branch | `branch` | `str` | Branch name（可选时默认当前分支） |
| Issue | `issue` | `str` | Issue number 或 URL |
| Flow name | `name` 或 `slug` | `str` | Flow 显示名称 |
| Role | `role` | `Literal` | Issue role (task/related/dependency) |

### 3.2 Issue 参数设计

**所有接受 issue 的命令**:
- 参数类型: `str`（支持数字或 URL）
- 参数名: `issue`
- 帮助文本: "Issue number (or URL)"

**支持格式**:
- `219` — 直接输入数字
- `https://github.com/owner/repo/issues/219` — 从浏览器复制

**内部处理**:
```python
def parse_issue_ref(issue_ref: str) -> int:
    """Parse issue number from reference (number or GitHub URL)."""
    if issue_ref.isdigit():
        return int(issue_ref)
    # 解析 URL...
```

---

## 四、Flow 命令参数规范

### 4.1 flow add

```bash
vibe3 flow add <name> [--task <issue>] [--spec <spec-ref>]
```

**参数**:
- `name`: Flow 显示名称（必需）
  - 类型: `str`
- `--task`: Task issue 引用（可选，支持 number/#number/URL）
  - 类型: `str`
- `--spec`: spec 引用（可选，支持文件路径或 issue 引用）
  - 类型: `str`

**行为**:
- 在当前分支注册 flow（不创建新分支）
- 初始化 flow_state 记录
- 如提供 `--task/--spec`，注册后统一走绑定编排

**示例**:
```bash
# 在当前分支注册 flow
vibe3 flow add reports-storage

# 注册并绑定 task/spec
vibe3 flow add reports-storage --task 220 --spec docs/specs/reports.md
```

### 4.2 flow create

```bash
vibe3 flow create <name> [--task <issue>] [--spec <spec-ref>] [--base <ref>]
```

**行为**:
- 创建新分支 `task/<name>`
- 在新分支注册 flow
- 如提供 `--task/--spec`，注册后走与 `flow add` 相同的绑定编排

**示例**:
```bash
vibe3 flow create reports-storage --task 220
vibe3 flow create inspect-metrics --task 279 --spec 279
```

**兼容说明**:
- `flow new` 保留为兼容别名，标准文档不再作为主入口
- 历史调用示例等价迁移到 `flow add` / `flow create`
```

### 4.3 flow switch

```bash
vibe3 flow switch <name>
```

**参数**:
- `name`: Flow 名称或分支名（必需）
  - 类型: `str`
  - 帮助: "Flow name or branch to switch to"

**行为**:
- Stash 当前分支的未提交改动
- 切换到目标分支
- 恢复 stash 到目标分支

**示例**:
```bash
vibe3 flow switch my-feature
# → stash 当前改动
# → 切换到 task/my-feature
# → 恢复 stash
```

### 4.4 flow done

```bash
vibe3 flow done [--branch <ref>] [--yes]
```

**参数**:
- `--branch`: 指定分支（可选，默认当前分支）
  - 类型: `str | None`
  - 帮助: "Branch to close"
- `--yes`: 跳过 PR 检查（可选）
  - 类型: `bool`
  - 帮助: "Skip PR merged check"

**行为**:
- 检查 PR 是否已 merge
- 如果未 merge 且无 `--yes`，提示错误
- 删除本地分支
- 删除远程分支（如果存在）
- 标记 flow_status = done

**示例**:
```bash
# 正常完成（PR 已 merge）
vibe3 flow done

# 强制完成
vibe3 flow done --yes
```

### 4.5 flow blocked

```bash
vibe3 flow blocked [--reason <reason>] [--by <issue>] [--branch <ref>]
```

**参数**:
- `--reason`: 阻塞原因描述（可选）
  - 类型: `str | None`
  - 帮助: "Block reason description"
- `--by`: 依赖的 issue number（可选）
  - 类型: `int | None`
  - 帮助: "Dependency issue number"
- `--branch`: 指定分支（可选，默认当前分支）
  - 类型: `str | None`
  - 帮助: "Branch to block"

**行为**:
- 如果指定 `--by`，自动添加 dependency issue link
- 更新 flow_status = blocked
- 设置 blocked_by 字段

**示例**:
```bash
# 仅记录阻塞原因
vibe3 flow blocked --reason "等待外部反馈"

# 标记依赖 issue（自动生成描述）
vibe3 flow blocked --by 218

# 同时指定依赖和原因
vibe3 flow blocked --by 218 --reason "需要 #218 先完成"
```

### 4.6 flow aborted

```bash
vibe3 flow aborted [--branch <ref>]
```

**参数**:
- `--branch`: 指定分支（可选，默认当前分支）
  - 类型: `str | None`
  - 帮助: "Branch to abort"

**行为**:
- 标记 flow_status = aborted
- 删除本地分支
- 删除远程分支（如果存在）

**示例**:
```bash
vibe3 flow aborted
```

### 4.7 flow show

```bash
vibe3 flow show [branch]
```

**参数**:
- `branch`: Branch name（可选，默认当前分支）
  - 类型: `str | None`
  - 帮助: "Branch name"

**前置条件**:
- 指定分支（或当前分支）必须已在 `flow_state` 中有记录
- 如果分支不在 flow_state 中，会报错 `Flow not found: <branch>`

**行为**:
- 显示 flow 的完整信息
- 包括所有 issues（task, related, dependency）

### 4.8 flow bind

```bash
vibe3 flow bind <issue> [--role <role>] [--branch <branch>]
```

**参数**:
- `issue`: Issue number (or URL)（必需）
  - 类型: `str`
  - 帮助: "Issue number (or URL)"
- `--role`: Issue role（可选，默认 "task"）
  - 类型: `Literal["task", "related", "dependency"]`
  - 默认值: `"task"`
  - 帮助: "Issue role in flow (task/related/dependency)"
- `--branch`: Branch name（可选，默认当前分支）
  - 类型: `str | None`
  - 帮助: "Branch name (default: current branch)"

**行为**:
- 绑定 issue 到 flow，指定其在 flow 中的角色
- Issue → Flow 关系，存储在 SQLite `flow_issue_links`
- 默认 role=task，绑定为主执行目标
- 若启用标签自动化，可根据 role=task/dependency 镜像 `vibe-task`
- 如果 role=task，更新 `flow_state.task_issue_number`

**示例**:
```bash
# 绑定为 task issue（默认）
vibe3 flow bind 220
# issue #220 绑定为当前 flow 的 task issue

# 绑定为 related issue
vibe3 flow bind 219 --role related
# issue #219 绑定为当前 flow 的相关 issue

# 绑定为 dependency issue
vibe3 flow bind 218 --role dependency
# issue #218 绑定为当前 flow 的依赖 issue

# 绑定指定 flow
vibe3 flow bind 220 --branch task/my-feature
```

## 五、Task 命令参数规范

### 5.1 task show

```bash
vibe3 task show <branch>
```

**参数**:
- `branch`: Branch name（必需）
  - 类型: `str`
  - 帮助: "Branch name"

**行为**:
- 显示 GitHub Project 管理信息
- 包括 Project 字段、绑定状态

### 5.2 task list

```bash
vibe3 task list [--issue <issue>]
```

**参数**:
- 无（仅 `--trace` / `--json` 等通用输出参数）

**行为**:
- 列出所有 task（有 task_issue_number 的 flow）
- 搜索和状态过滤属于后续扩展

**示例**:
```bash
# 列出所有 task
vibe3 task list
```

### 5.3 迁移与弃用

标准流程收敛后，以下命令不再推荐：
- `task status` → 目标由 flow 生命周期自动联动远端 Project 状态

在兼容期内如果命令仍存在，视为历史兼容入口，不作为标准流程的一部分。

---

## 六、PR 命令参数规范

### 6.1 pr create

```bash
vibe3 pr create -t <title> [-b <body>] [--base <branch>]
```

**参数**:
- `-t, --title`: PR 标题（必需）
  - 类型: `str`
  - 帮助: "PR title"
- `-b, --body`: PR 描述（可选，默认 ""）
  - 类型: `str`
  - 帮助: "PR description"
- `--base`: 目标分支（可选，默认 "main"）
  - 类型: `str`
  - 帮助: "Base branch"

**Metadata 自动读取**:
- 不需要用户手动指定 task、flow、spec、planner、executor
- 系统自动从当前 flow_state 读取：
  - `task_issue_number` → Task issue
  - `flow_slug` → Flow
  - `spec_ref` → Spec reference
  - `planner_actor` → Planner agent
  - `executor_actor` → Executor agent

**行为**:
- 从当前分支创建 draft PR
- 自动在 PR body 中添加 Vibe3 Metadata 章节
- 添加 pr_draft 事件（不再持久化 pr_number 到 flow_state）

**示例**:
```bash
# 最简单的用法 - metadata 自动读取
vibe3 pr create -t "feat: 添加用户认证功能"

# 指定详细描述
vibe3 pr create -t "feat: 用户认证" -b "实现了登录和注册功能"

# 指定目标分支
vibe3 pr create -t "feat: 用户认证" --base develop
```

**设计原则**:
- **单一事实来源**: Flow 是 metadata 的唯一真源
- **避免重复**: 用户不需要重复输入已在 flow 中设置的信息
- **简化操作**: 只关心 PR 内容本身

### 6.2 pr show

```bash
vibe3 pr show [PR_NUMBER] [-b <branch>]
```

**参数**:
- `PR_NUMBER`: PR 号码（可选）
  - 类型: `int | None`
  - 帮助: "PR number"
- `-b, --branch`: 分支名（可选）
  - 类型: `str | None`
  - 帮助: "Branch name"

**智能查找**:
1. 如果未提供 pr_number 和 branch：
   - 先从当前 flow_state 查找 pr_number
   - 如果找到，自动使用该 PR
   - 如果未找到，使用当前分支名查询
2. 如果提供 pr_number：直接查询该 PR
3. 如果提供 branch：查询该分支的 PR

**行为**:
- 显示 PR 基本信息（标题、状态、链接等）
- 如果提供了 pr_number，自动执行 change analysis：
  - Risk Level 和 Score
  - Changed Files
  - Impacted Modules
  - Recommendations

**错误处理**:
- 当前分支无 PR：友好提示如何创建 PR
- PR 不存在：显示 "PR #xxx not found" 或 "branch 'xxx' not found"

**示例**:
```bash
# 查看当前 flow 的 PR
vibe3 pr show

# 查看指定 PR
vibe3 pr show 123

# 查看指定分支的 PR
vibe3 pr show -b task/my-feature
```

### 6.3 pr ready

```bash
vibe3 pr ready PR_NUMBER [-y]
```

**参数**:
- `PR_NUMBER`: PR 号码（必需）
  - 类型: `int`
  - 帮助: "PR number"
- `-y, --yes`: 绕过质量门禁检查（可选）
  - 类型: `bool`
  - 帮助: "Bypass quality gates and auto-confirm"

**质量门禁检查**:
1. **覆盖率检查**（分层覆盖率统计）
   - 检查测试覆盖率是否达标
   - 显示覆盖率详情
2. **风险评分检查**（来自 inspect pr）
   - 评估代码变更风险
   - 显示风险等级和原因

**行为**:
- 将 draft PR 标记为 ready for review
- 执行质量门禁检查（除非使用 --yes）
- 更新 flow_state 添加 pr_ready 事件

**示例**:
```bash
# 标记 PR 为 ready（通过质量门禁）
vibe3 pr ready 123

# 强制标记为 ready（绕过检查）
vibe3 pr ready 123 --yes
```

**使用场景**:
- 开发完成后，将 draft PR 转为 ready for review
- 质量门禁确保代码符合标准
- 使用 `--yes` 仅在紧急情况下跳过检查

---

## 七、Handoff 命令参数规范

### 6.1 handoff plan

```bash
vibe3 handoff plan <plan_ref> [--next-step <text>] [--blocked-by <text>] [--actor <actor>]
```

**参数**:
- `plan_ref`: Plan 文档引用（必需）
  - 类型: `str`
  - 帮助: "Plan document reference"
- `--next-step`: 下一步建议（可选）
  - 类型: `str | None`
  - 帮助: "Next step suggestion"
- `--blocked-by`: 阻塞原因（可选）
  - 类型: `str | None`
  - 帮助: "Blocker description"
- `--actor`: Actor 标识（可选，默认 "unknown"）
  - 类型: `str`
  - 帮助: "Actor identifier"

**行为**:
- 更新 flow_state.plan_ref
- 更新 flow_state.planner_actor
- 更新 flow_state.next_step
- 更新 flow_state.blocked_by
- 添加 handoff_plan 事件

**Actor 映射**: `planner_actor`

### 6.2 handoff report

```bash
vibe3 handoff report <report_ref> [--next-step <text>] [--blocked-by <text>] [--actor <actor>]
```

**参数**:
- `report_ref`: Report 文档引用（必需）
  - 类型: `str`
  - 帮助: "Report document reference"
- `--next-step`: 下一步建议（可选）
  - 类型: `str | None`
  - 帮助: "Next step suggestion"
- `--blocked-by`: 阻塞原因（可选）
  - 类型: `str | None`
  - 帮助: "Blocker description"
- `--actor`: Actor 标识（可选，默认 "unknown"）
  - 类型: `str`
  - 帮助: "Actor identifier"

**行为**:
- 更新 flow_state.report_ref
- 更新 flow_state.executor_actor
- 更新 flow_state.next_step
- 更新 flow_state.blocked_by
- 添加 handoff_report 事件

**Actor 映射**: `executor_actor`

### 6.3 handoff audit

```bash
vibe3 handoff audit <audit_ref> [--next-step <text>] [--blocked-by <text>] [--actor <actor>]
```

**参数**:
- `audit_ref`: Audit 文档引用（必需）
  - 类型: `str`
  - 帮助: "Audit document reference"
- `--next-step`: 下一步建议（可选）
  - 类型: `str | None`
  - 帮助: "Next step suggestion"
- `--blocked-by`: 阻塞原因（可选）
  - 类型: `str | None`
  - 帮助: "Blocker description"
- `--actor`: Actor 标识（可选，默认 "unknown"）
  - 类型: `str`
  - 帮助: "Actor identifier"

**行为**:
- 更新 flow_state.audit_ref
- 更新 flow_state.reviewer_actor
- 更新 flow_state.next_step
- 更新 flow_state.blocked_by
- 添加 handoff_audit 事件

**Actor 映射**: `reviewer_actor`

### 6.4 handoff append

```bash
vibe3 handoff append <message> [--kind <kind>] [--actor <actor>]
```

**参数**:
- `message`: Handoff 更新消息（必需）
  - 类型: `str`
  - 帮助: "Lightweight handoff update"
- `--kind`: 更新类型（可选，默认 "note"）
  - 类型: `str`
  - 帮助: "Update kind, e.g. finding/blocker/next"
- `--actor`: Actor 标识（可选，默认 "unknown"）
  - 类型: `str`
  - 帮助: "Actor identifier"

**行为**:
- 更新 flow_state.latest_actor
- 追加消息到当前 handoff 文档

**Actor 映射**: `latest_actor`

---

## 八、设计原则

### 8.1 架构原则

1. **单一真源**: GitHub 是真源，SQLite 是缓存
2. **不包装 gh**: 不简单包装 `git/gh` 已有的命令
3. **不做第二真源**: 避免与 GitHub 状态冲突

### 8.2 命名原则

1. **统一命名**: 相同概念使用相同术语
2. **语义清晰**: 参数名反映实际含义
3. **用户友好**: 支持便捷输入方式（如 URL 复制）

### 8.3 职责分离

1. **flow 命令**: Flow 生命周期管理
2. **task 命令**: Issue 关联和 Project 管理
3. **避免重叠**: 明确每个命令的职责边界

---

## 九、参考文档

- [glossary.md](glossary.md) - 术语定义
- [issue-standard.md](issue-standard.md) - Issue 标准
- [../standards/vibe3-user-guide.md](../standards/vibe3-user-guide.md) - 操作手册
