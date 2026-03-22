# Task & Flow 操作指南

**维护者**: Vibe Team
**最后更新**: 2026-03-23

> 本文档是用户操作手册，命令设计规范见 [vibe3-command-standard.md](../standards/vibe3-command-standard.md)

## 概念说明

`vibe3` 的任务管理围绕三个核心概念：

| 对象 | 真源 | 本地存储 | 说明 |
|------|------|----------|------|
| **GitHub Issue** | GitHub Issues API | flow_issue_links 索引 | 工作项，可以是需求、任务或缺陷 |
| **Issue Role** | SQLite flow_issue_links | flow_issue_links 表 | Issue 在 Flow 中的角色（唯一真源）|
| **Flow** | 本地 SQLite | flow_state 表 | 执行现场，代表"正在哪个 branch 上做" |

### Flow 标识

**`branch` 是指针（PRIMARY KEY）**，`flow_slug` 是显示名称。

```sql
-- SQLite flow_state 表
CREATE TABLE flow_state (
    branch TEXT PRIMARY KEY,        -- 这是指针，唯一标识
    flow_slug TEXT NOT NULL,        -- 这是显示名称
    task_issue_number INTEGER,
    ...
)
```

**生成规则**：
- `branch = "task/my-feature"` → `flow_slug = "my-feature"`
- 代码：`flow_slug = branch.split("/")[-1] if "/" in branch else branch`

**查询方式**：
- 所有命令都按 `branch` 查询，不支持按 `flow_slug` 查询

### Issue Role 语义

Issue Role 定义了 issue 在特定 flow 中的角色（相对于 flow 的关系语义）：

| Role | 含义 | 示例 |
|------|------|------|
| `task` | Flow 的主要执行目标 | #220: 实现统一存储 |
| `related` | 相关 issue（需求来源、参考） | #219: 实现报告系统 |
| `dependency` | 依赖的其他 task | #218: 基础设施准备 |

**重要**：
- Issue Role 是**关系语义**，不是 issue 的类型属性
- 同一个 issue 可以在不同的 flow 中有不同的 role
- Issue Role 是**唯一真源**，GitHub label 只是同步副作用

### 关系图

```
related issue #219 (需求来源)
  ├── task issue #220 (主要执行) → flow: task/reports-unified-storage
  ├── task issue #221 (主要执行) → flow: task/pr-show-complete
  └── dependency issue #218 (依赖) → flow: task/infra-setup
```

**数据存储**：
```sql
-- SQLite flow_issue_links 表（唯一真源）
flow_issue_links:
  - branch: task/reports-unified-storage, issue_number: 220, issue_role: task
  - branch: task/reports-unified-storage, issue_number: 219, issue_role: related
  - branch: task/reports-unified-storage, issue_number: 218, issue_role: dependency
```

**GitHub Label 同步**：
- role=task 或 dependency → 后续自动化可镜像 `vibe-task` 标签
- role=related → 不镜像 `vibe-task`
- Label 只用于 GitHub 视角过滤，不是真源

---

## 前置配置

`config/settings.yaml` 中配置 GitHub Project：

```yaml
github_project:
  owner_type: "user"   # 个人账号用 "user"，组织用 "org"
  owner: "jacobcy"     # GitHub 用户名或组织名
  project_number: 17   # GitHub Project number
```

认证：设置 `GITHUB_TOKEN` 环境变量，或已登录 `gh auth login`。

---

## Flow 生命周期管理

Flow 代表执行现场，围绕 Git branch 的生命周期进行管理。

### Flow 状态流转

```
[new] → [active] → [done]      (正常完成)
              ↓
         [blocked]              (被阻塞)
              ↓
         [active] → [done]      (解除阻塞后继续)

         [active] → [aborted]   (废弃)
```

### 创建 Flow

**命令**：`vibe3 flow new [name] [--issue <issue>] [--branch <ref>] [--save-unstash]`

**功能**：创建新分支并初始化 flow_state 记录。

**参数**：
- `name` - Flow 名称（可选，默认从 branch 生成）
- `--issue` - 绑定 task issue（可选）
- `--branch` - 起点分支（默认：origin/main）
- `--save-unstash` - 将当前未提交改动带入新分支

**示例**：

```bash
# 1. 基本用法：创建新 flow
vibe3 flow new my-feature
# → 创建分支 task/my-feature
# → 初始化 flow_state 记录

# 2. 绑定 issue
vibe3 flow new --issue 220
# → 创建分支 task/flow-status-transitions（从 issue 标题生成）
# → 绑定 #220 为 task issue

# 3. 从非 main 分支创建
vibe3 flow new feature-b --branch origin/dev
# → 从 origin/dev 创建分支

# 4. 带入未提交改动
# 假设当前在 feature-a 分支有未提交改动
vibe3 flow new feature-b --save-unstash
# → stash 当前改动
# → 创建新分支 task/feature-b
# → 恢复 stash 到新分支
```

**错误处理**：
- 分支已存在 → 报错提示使用 `flow switch`
- 工作目录不干净且未指定 `--save-unstash` → 报错提示使用该选项

### 切换 Flow

**命令**：`vibe3 flow switch <name>`

**功能**：切换到已有的 flow 分支。

**行为**：
1. 自动 stash 当前分支的未提交改动
2. 切换到目标分支
3. 恢复 stash 到目标分支

**示例**：

```bash
# 切换到已有 flow
vibe3 flow switch my-feature
# → stash 当前改动（如果有）
# → 切换到 task/my-feature 分支
# → 恢复 stash
```

**注意**：
- 只能切换到未关闭的 flow
- 已有 PR 的 flow 不能切换（需要通过 PR 继续）

### 完成 Flow

**命令**：`vibe3 flow done [--branch <ref>] [--yes]`

**功能**：关闭 flow 并删除分支。

**前置条件**：
- PR 已 merge，或
- 有 review evidence 且 merge 成功

**参数**：
- `--branch` - 指定分支（默认：当前分支）
- `--yes` - 跳过 PR 检查（危险操作）

**示例**：

```bash
# 1. 正常完成（PR 已 merge）
vibe3 flow done
# → 检查 PR 已 merge
# → 删除本地分支
# → 删除远程分支（如果存在）
# → 标记 flow_status = done

# 2. 指定分支
vibe3 flow done --branch task/my-feature

# 3. 强制完成（跳过 PR 检查）
vibe3 flow done --yes
# ⚠️ 危险：可能删除未合并的分支
```

**错误处理**：
- PR 未 merge 且无 review evidence → 报错
- 工作目录不干净 → 报错提示先提交或 stash

### 阻塞 Flow

**命令**：`vibe3 flow blocked --reason <reason> [--branch <ref>]`

**功能**：标记 flow 为 blocked 状态，保留分支。

**示例**：

```bash
# 标记为 blocked
vibe3 flow blocked --reason "等待依赖 #218 完成"
# → flow_status = blocked
# → blocked_by = "等待依赖 #218 完成"
# → 保留分支

# 解除阻塞（切换回 active）
vibe3 task status active
# 或
vibe3 flow switch <other-flow>
```

**使用场景**：
- 等待依赖完成
- 等待外部反馈
- 等待资源分配

### 废弃 Flow

**命令**：`vibe3 flow aborted [--branch <ref>]`

**功能**：废弃 flow 并删除分支。

**示例**：

```bash
# 废弃当前 flow
vibe3 flow aborted
# → flow_status = aborted
# → 删除本地分支
# → 删除远程分支（如果存在）
```

**使用场景**：
- 需求变更，不再需要此 flow
- 方案被更好的实现替代
- 探索性代码，不需要保留

---

## 标准工作流

### 场景一：从需求 issue 创建 task

适用于：一个需求 issue 直接对应一个可执行任务。

```bash
# 1. 创建 flow 并绑定 issue
vibe3 flow new --issue 220
# → 创建分支 task/flow-status-transitions（从 issue 标题生成）
# → 绑定 #220 为 task issue
# → 初始化 flow_state 记录

# 或指定自定义名称
vibe3 flow new my-feature --issue 220
# → 创建分支 task/my-feature

# 2. 为当前 flow 记录补充 issue 关系
vibe3 task link 219 --role related
# → 在本地 flow_issue_links 中记录 role=related

vibe3 task link 218 --role dependency
# → 在本地 flow_issue_links 中记录 role=dependency

# 3. 绑定 GitHub Project item（通过 issue 反查）
vibe3 task bridge link-project --from-issue 220

# 4. 验证
vibe3 task show task/my-feature
```

输出示例：
```
Branch: task/my-feature
Project Item [bound]: PVTI_xxx
Task Issue: #220 (role: task)
Related Issue(s): #219
Dependencies: (none)
[remote] Title:    实现统一存储
[remote] Status:   Todo
[remote] Assignees: jacobcy
```

---

### 场景二：拆分需求 issue 为多个 task

适用于：一个需求 issue 包含多个独立子任务，需要并行或分批执行。

**Step 1：在 GitHub 上创建子 task issue**

```bash
gh issue create \
  --title "feat(reports): coverage.json 统一存放" \
  --body "来源：#219\n\n具体范围：..." \
  --label "enhancement"
# → 创建 #221

gh issue create \
  --title "feat(pr): pr show 显示完整信息" \
  --body "来源：#219\n\n具体范围：..." \
  --label "enhancement"
# → 创建 #222
```

**Step 2：把子 task issue 加入 GitHub Project**

```bash
gh project item-add 17 --owner jacobcy \
  --url "https://github.com/jacobcy/vibe-coding-control-center/issues/221"

gh project item-add 17 --owner jacobcy \
  --url "https://github.com/jacobcy/vibe-coding-control-center/issues/222"
```

**Step 3：为每个 task 创建 flow 并绑定**

```bash
# task #221
vibe3 flow new --issue 221
# → 创建分支 task/reports-unified-storage
# → flow_slug 自动生成: reports-unified-storage

vibe3 task link 219 --role related
# 为当前 flow 记录 role=related

vibe3 task bridge link-project --from-issue 221

# task #222
vibe3 flow new --issue 222
# → 创建分支 task/pr-show-complete
# → flow_slug 自动生成: pr-show-complete

vibe3 task link 219 --role related
# 为当前 flow 记录 role=related

vibe3 task bridge link-project --from-issue 222
```

---

## 查询命令

### 查看所有 task

```bash
vibe3 task list
```

输出：
```
  #220  task-bridge-github-project  active  [bound]  branch=task/task-bridge-github-project
  #221  reports-unified-storage     active  [bound]  branch=task/reports-unified-storage
  #222  pr-show-complete            active  [bound]  branch=task/pr-show-complete
  #223  reports-cleanup             active  [bound]  branch=task/reports-cleanup
```

### 搜索 issue

当前 `vibe3 task list` 只支持 `--issue` 反查 flow，不支持 `--search` / `--status`。

如需搜索 GitHub issue，请使用：

```bash
gh search issues "report"
```

### 从 task issue 反查 flow

```bash
vibe3 task list --issue 221
```

输出：
```
Flows linked to issue #221 as task:
  #221  reports-unified-storage  active  [bound]  branch=task/reports-unified-storage
```

### 查看单个 task 详情（含远端字段）

```bash
vibe3 task show task/reports-unified-storage
```

输出：
```
Branch: task/reports-unified-storage
Project Item [bound]: PVTI_lAHOAAGiOs4BRZJ8zgoAgV0
Task Issue: #221
Related Issue(s): #219
[remote] Title:    feat(reports): coverage.json 和 review 结果统一存放
[remote] Status:   In Progress
[remote] Assignees: jacobcy
```

### 查看 flow 详情（含 issue 角色区分）

```bash
vibe3 flow show task/reports-unified-storage
```

输出：
```
reports-unified-storage  active
  branch: task/reports-unified-storage
  task_issue: #221  feat(reports): coverage.json 和 review 结果统一存放
  related_issues:
    - #219  实现报告系统
  dependencies:
    - #218  基础设施准备
```

### 查看所有 flow

```bash
vibe3 flow list
vibe3 flow list --status active   # 按状态过滤
```

---

## 命令语义说明

### flow show vs task show

两个命令都显示 flow 信息，但视角不同：

| 命令 | 视角 | 用户 | 数据源 | 核心关注点 |
|------|------|------|--------|-----------|
| `flow show` | 执行现场管理 | 开发者 | SQLite + GitHub Issues/PRs | 开发流程状态、文档引用、阻塞关系 |
| `task show` | GitHub Project 管理 | 管理者 | SQLite + GitHub Project | Project 字段、绑定状态、数据一致性 |

**flow show 独有功能**：
- 显示 issue titles（从 GitHub Issues API）
- 显示 PR 信息（从 GitHub PRs API）
- 显示 plan/execute/review actors 和 refs
- 支持 optional branch 参数（默认当前分支）

**task show 独有功能**：
- 显示 Project Item 绑定状态（bound/unbound）
- 显示 Project 字段（Status, Priority, Assignees）
- 检查 identity_drift（本地与远端一致性）
- 显示 offline_mode 标识

### 命令参数说明

**参数语义**：
- `flow new [name] --issue <issue>` — name 可选，默认从 branch 生成
- `flow show [branch]` — 参数是 branch name（可选，默认当前分支）
- `flow bind <issue> [--role <role>] [--branch <branch>]` — 绑定 issue 到 flow（可选 branch，默认当前）
- `task show [branch]` — 参数是 branch name（可选，默认当前分支）
- `task link <issue> [--role <role>]` — 为当前 flow 补充 related/dependency 关系

**重要**：
- Task 不是独立实体，是 flow 的属性（有 task_issue_number 的 flow）
- `vibe3 task show` 中的参数是 `branch name`，默认当前分支
- 没有独立的 "task name"，只有关联的 issue number

### flow bind vs task link

**两种不同的关系**：

| 命令 | 关系 | 存储位置 | 操作 |
|------|------|----------|------|
| `flow bind` | Issue → Flow | SQLite 本地 | 记录到 flow_issue_links，必要时更新 task 指针 |
| `task link` | 当前 flow 的补充 issue 关系 | SQLite 本地 | 记录 `related/dependency` |

**示例**:
```bash
# flow bind: 指定 issue 是 flow 的 task
vibe3 flow bind 220
# SQLite: flow_issue_links(branch, 220, role='task')

# task link: 为当前 flow 记录 related issue
vibe3 task link 219 --role related
# SQLite: flow_issue_links(branch, 219, role='related')
```

### 使用场景选择

**场景 1：开发者查看当前工作**

```bash
# 在 feature 分支上
vibe3 flow show
# 显示：我需要做什么（task issue）
#        依赖什么（dependencies）
#        规划文档在哪（plan_ref）
#        下一步做什么（next_step）
```

**推荐**：`flow show` ✅

**场景 2：管理者查看项目状态**

```bash
vibe3 task show task/my-feature
# 显示：Project 状态是什么（Status: In Progress）
#        优先级（Priority: P1）
#        谁负责（Assignees）
#        绑定是否正常（bound/unbound）
```

**推荐**：`task show` ✅

---

## 状态管理

### 更新远端 GitHub Project task 状态

task 状态的真源是 GitHub Project，通过以下命令更新：

```bash
# 切换到对应 branch
git checkout task/reports-unified-storage

# 更新远端状态
vibe3 task status "In Progress"
vibe3 task status "Done"
vibe3 task status "Todo"
```

状态值必须与 GitHub Project 中配置的 Status 选项名称完全匹配（大小写不敏感）。

### 更新本地 flow 执行状态

flow_status 是本地执行现场状态，与 GitHub Project task 状态独立：

```bash
# 通过 task service（内部 API，暂无独立 CLI）
# flow_status 取值：active / blocked / done / stale
```

---

## 绑定方式

### 方式一：通过 issue number 反查绑定（推荐）

```bash
vibe3 task bridge link-project --from-issue 221
```

自动在 GitHub Project 17 中查找 issue #221 对应的 item，完成绑定。

### 方式二：直接提供 Project item ID

```bash
vibe3 task bridge link-project PVTI_lAHOAAGiOs4BRZJ8zgoAgV0
```

适用于已知 item ID 的场景。

### 强制覆盖已有绑定

```bash
vibe3 task bridge link-project --from-issue 221 --force
```

---

## 离线降级

当 GitHub API 不可用时，`task show` 自动降级为 offline mode，只显示本地 bridge 字段：

```
Branch: task/reports-unified-storage
Project Item [bound]: PVTI_xxx
Task Issue: #221
Related Issue(s): #219
[offline mode] 远端读取失败，仅显示本地 bridge 字段
```

本地 bridge 字段（始终可用）：
- `project_item_id` — GitHub Project item ID
- `task_issue_number` — task issue number
- `spec_ref` / `next_step` / `blocked_by` — 执行上下文

---

## 完整链路验证

```bash
# 1. 确认 flow 已创建
vibe3 flow list

# 2. 确认 task / related / dependency 关系都已写入
vibe3 flow show [<branch>]

# 3. 确认 GitHub Project item 已绑定，远端字段可读
vibe3 task show [<branch>]

# 4. 更新远端状态
vibe3 task status "In Progress"

# 5. 再次确认状态已同步
vibe3 task show [<branch>]
# 应显示 [remote] Status: In Progress
```

### Flow 生命周期示例

```bash
# 1. 创建新 flow
vibe3 flow new feature-a --issue 220
# → 分支：task/feature-a
# → 绑定 issue #220

# 2. 开发过程中切换到另一个 flow
vibe3 flow new feature-b --issue 221
# → 分支：task/feature-b
# → 绑定 issue #221

# 3. 切换回 feature-a
vibe3 flow switch feature-a
# → 自动 stash feature-b 的改动
# → 切换到 task/feature-a
# → 恢复 stash

# 4. feature-a 被阻塞
vibe3 flow blocked --reason "等待依赖 #218"
# → flow_status = blocked
# → 保留分支

# 5. 解除阻塞继续开发
vibe3 task status active
# → flow_status = active

# 6. 完成 feature-a
# 6.1 创建 PR 并合并
vibe3 pr create
vibe3 pr ready
# （等待 PR merge）

# 6.2 关闭 flow
vibe3 flow done
# → 检查 PR 已 merge
# → 删除分支
# → flow_status = done

# 7. 废弃某个 flow
vibe3 flow switch feature-b
vibe3 flow aborted
# → flow_status = aborted
# → 删除分支
```

---

## 常见问题

**Q: `--from-issue` 报 not_found**

原因：issue 未加入 GitHub Project，或 project items 超过 100 条需要分页（已支持自动分页）。

解决：先把 issue 加入 project：
```bash
gh project item-add 17 --owner jacobcy \
  --url "https://github.com/jacobcy/vibe-coding-control-center/issues/221"
```

**Q: `task status` 报 not_found status 选项**

原因：传入的状态值与 GitHub Project 中的 Status 选项名称不匹配。

解决：检查 Project 中实际配置的选项名称（如 "Todo"、"In Progress"、"Done"）。

**Q: `task show` 显示 `[unbound]`**

原因：当前 branch 的 flow 未绑定 GitHub Project item。

解决：
```bash
vibe3 task bridge link-project --from-issue <task_issue_number>
```

**Q: flow show 和 task show 有什么区别**

- `flow show`：执行现场视角，显示开发流程状态（plan/execute/review）、issue titles、PR 信息、阻塞关系
- `task show`：项目管理视角，显示 GitHub Project 字段（Status/Priority/Assignees）、绑定状态、数据一致性

详见"命令语义说明"章节。

**Q: 为什么 `vibe3 task show task/temp` 中的参数叫 task/temp**

参数实际是 `branch name`，不是 task 标识。Task 不是独立实体，是 flow 的属性（有 task_issue_number 的 flow）。没有独立的 "task name"，只有关联的 issue number。
