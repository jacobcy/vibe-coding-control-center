---
title: Task & Flow 业务使用指南
date: 2026-03-22
status: active
purpose: 说明 repo issue → task → flow 完整业务链路的实际操作方法
---

# Task & Flow 业务使用指南

**维护者**: Vibe Team
**最后更新**: 2026-03-23

> 本文档是用户操作手册，命令设计规范见 [vibe3-command-standard.md](../standards/vibe3-command-standard.md)

## 概念说明

`vibe3` 的任务管理围绕三个对象：

| 对象 | 真源 | 本地存储 | 说明 |
|------|------|----------|------|
| **repo issue** | GitHub Issues | 仅 issue_links 索引 | 需求/缺陷，代表"要做什么" |
| **task issue** | GitHub Issues + Project | 仅 issue_links 索引 | 可执行单元，代表"具体做哪件事" |
| **flow** | 本地 SQLite | flow_state 表 | 执行现场，代表"正在哪个 branch 上做" |

关系：一个 repo issue 可以拆成多个 task issue，每个 task issue 对应一个 flow（branch）。

```
repo issue #219
  ├── task issue #221  →  flow: task/reports-unified-storage
  ├── task issue #222  →  flow: task/pr-show-complete
  └── task issue #223  →  flow: task/reports-cleanup
```

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

### 场景一：把 repo issue 提升为 task

适用于：一个 repo issue 直接对应一个可执行单元。

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

# 3. 关联来源 repo issue（role=repo）
vibe3 task link 219 --role repo

# 4. 绑定 GitHub Project item（通过 issue 反查）
vibe3 task bridge link-project --from-issue 220

# 5. 验证
vibe3 task show task/my-feature
```

输出示例：
```
Branch: task/my-feature
Project Item [bound]: PVTI_xxx
Task Issue: #220
Repo Issue(s): #219
[remote] Title:    打通 Task 真源桥接
[remote] Status:   Todo
[remote] Assignees: jacobcy
```

---

### 场景二：把 repo issue 拆成多个 task

适用于：一个 repo issue 包含多个独立子需求，需要并行或分批执行。

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

字段说明：`#task_issue  flow_slug  flow_status  [bound/unbound]  branch`

### 从 repo issue 反查所有关联 task

```bash
vibe3 task list --repo-issue 219
```

输出：
```
Tasks linked to repo issue #219:
  #221  reports-unified-storage  active  [bound]  branch=task/reports-unified-storage
  #222  pr-show-complete         active  [bound]  branch=task/pr-show-complete
  #223  reports-cleanup          active  [bound]  branch=task/reports-cleanup
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
Repo Issue(s): #219
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
  branch       task/reports-unified-storage
  task         #221
  task issues  #221
  repo issues  #219
```

### 查看所有 flow

```bash
vibe3 flow list
vibe3 flow list --status active   # 按状态过滤
```

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
Repo Issue(s): #219
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

# 2. 确认 task issue 和 repo issue 都已关联
vibe3 flow show <branch>

# 3. 确认 GitHub Project item 已绑定，远端字段可读
vibe3 task show <branch>

# 4. 更新远端状态
vibe3 task status "In Progress"

# 5. 再次确认状态已同步
vibe3 task show <branch>
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

**Q: flow show 的 `task` 字段和 `task issues` 字段有什么区别**

`task` 字段来自 `flow_state.task_issue_number`（主 task），`task issues` 来自 `flow_issue_links` 表中 role=task 的记录。正常情况下两者一致。
