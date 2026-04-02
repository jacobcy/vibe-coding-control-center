---
name: vibe-start
description: Use when you have switched to an existing branch (via git checkout) and need to resume or set up the execution environment for that flow — verify flow state, ensure issue is bound, create PR draft if missing. This is the "resume" counterpart to vibe-new.
---

# /vibe-start - 恢复执行环境

`/vibe-start` 切换到已有分支后，快速确认并补齐执行环境。

---

## 核心职责

1. 检查当前 branch 的 flow 状态
2. 确认 issue 绑定是否正确
3. 若缺 PR draft，补创建
4. 输出当前任务摘要，准备好继续开发

---

## 停止点

完成后输出：

- ✅ flow 状态已确认
- ✅ issue 绑定已验证
- ✅ PR draft 已就绪（如缺少则已创建）
- **下一步**：继续编码，完成后运行 `/vibe-commit`

---

## 完整流程

```
/vibe-start
  ├─ Step 1: 确认当前 flow 状态
  │   ├─ vibe3 flow show
  │   └─ 检查 flow 是否存在、issue 是否绑定
  │
  ├─ Step 2: 补齐缺失环境（如有需要）
  │   ├─ 无 flow → 提示用 vibe3 flow update 注册
  │   ├─ 无 issue 绑定 → vibe3 flow bind <issue> --role task
  │   └─ 无 PR draft → vibe3 pr create --base main
  │
  └─ Step 3: 输出任务摘要并停止
      ├─ 显示 issue 内容摘要
      ├─ 显示 PR 链接
      └─ 确认 next_step
```

---

## Workflow

### Step 1: 确认当前 flow 状态

```bash
vibe3 flow show
```

检查：
- `flow_status`：active / blocked / stale？
- `task_issue_number`：是否已绑定？
- `pr_number`：是否已有 PR？
- `next_step`：之前记录的下一步是什么？

若 flow 为 `blocked` 状态：

```bash
# 确认阻塞原因
vibe3 flow show
# 检查依赖 issue 是否已解决
gh issue view <blocking-issue>
```

### Step 2: 补齐缺失环境

**无 flow（branch 未注册）**：

```bash
# 注册当前分支
vibe3 flow update
# 绑定 task issue
vibe3 flow bind <issue-number> --role task
```

**有 flow 但无 PR draft**：

```bash
vibe3 pr create --base main
```

> 若无提交记录导致创建失败：`git commit --allow-empty -m "chore: init flow"`

### Step 3: 输出任务摘要

```bash
# 最终确认
vibe3 flow show
gh issue view <task-issue-number>
```

输出摘要格式：

```markdown
## 当前任务摘要

- branch: <branch-name>
- issue: #<number> - <title>
- pr: #<number> (<url>)
- flow_status: active
- next_step: <记录的下一步>

准备好开始/继续开发。完成后运行 /vibe-commit。
```

---

## 核心边界

- 允许：读取 flow 状态、补绑定 issue、补创建 PR draft、输出摘要
- 不允许：修改业务代码、创建新 issue、创建新 branch、跨 worktree 调度

## Restrictions

- 若当前 branch 没有任何 flow 记录且也没有对应 issue，建议使用 `/vibe-new` 从头开始
- 不得把 handoff 当真源，以 `vibe3 flow show` 输出为准
