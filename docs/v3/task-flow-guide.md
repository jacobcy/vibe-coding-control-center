---
title: Task & Flow 业务使用指南
date: 2026-03-22
status: active
purpose: 说明 repo issue → task → flow 完整业务链路的实际操作方法
---

# Task & Flow 业务使用指南

## 概念说明

vibe3 的任务管理围绕三个对象：

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

## 标准工作流

### 场景一：把 repo issue 提升为 task

适用于：一个 repo issue 直接对应一个可执行单元。

```bash
# 1. 创建 task branch
git checkout -b task/my-feature

# 2. 创建 flow
vibe flow new my-feature --actor jacobcy

# 3. 关联 task issue（role=task）
vibe task link 220 --role task

# 4. 关联来源 repo issue（role=repo）
vibe task link 219 --role repo

# 5. 绑定 GitHub Project item（通过 issue 反查）
vibe task bridge link-project --from-issue 220

# 6. 验证
vibe task show task/my-feature
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
git checkout -b task/reports-unified-storage
vibe flow new reports-unified-storage --actor jacobcy
vibe task link 221 --role task
vibe task link 219 --role repo
vibe task bridge link-project --from-issue 221

# task #222
git checkout -b task/pr-show-complete
vibe flow new pr-show-complete --actor jacobcy
vibe task link 222 --role task
vibe task link 219 --role repo
vibe task bridge link-project --from-issue 222
```

---

## 查询命令

### 查看所有 task

```bash
vibe task list
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
vibe task list --repo-issue 219
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
vibe task show task/reports-unified-storage
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
vibe flow show task/reports-unified-storage
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
vibe flow list
vibe flow list --status active   # 按状态过滤
```

---

## 状态管理

### 更新远端 GitHub Project task 状态

task 状态的真源是 GitHub Project，通过以下命令更新：

```bash
# 切换到对应 branch
git checkout task/reports-unified-storage

# 更新远端状态
vibe task status "In Progress"
vibe task status "Done"
vibe task status "Todo"
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
vibe task bridge link-project --from-issue 221
```

自动在 GitHub Project 17 中查找 issue #221 对应的 item，完成绑定。

### 方式二：直接提供 Project item ID

```bash
vibe task bridge link-project PVTI_lAHOAAGiOs4BRZJ8zgoAgV0
```

适用于已知 item ID 的场景。

### 强制覆盖已有绑定

```bash
vibe task bridge link-project --from-issue 221 --force
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
vibe flow list

# 2. 确认 task issue 和 repo issue 都已关联
vibe flow show <branch>

# 3. 确认 GitHub Project item 已绑定，远端字段可读
vibe task show <branch>

# 4. 更新远端状态
vibe task status "In Progress"

# 5. 再次确认状态已同步
vibe task show <branch>
# 应显示 [remote] Status: In Progress
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
vibe task bridge link-project --from-issue <task_issue_number>
```

**Q: flow show 的 `task` 字段和 `task issues` 字段有什么区别**

`task` 字段来自 `flow_state.task_issue_number`（主 task），`task issues` 来自 `flow_issue_links` 表中 role=task 的记录。正常情况下两者一致。
