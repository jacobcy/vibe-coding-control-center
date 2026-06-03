---
document_type: quick-reference
title: Vibe 3.0 - 命令参数快速参考
status: active
author: Claude Sonnet 4.6
created: 2026-03-17
last_updated: 2026-03-18
related_docs:
  - docs/v3/infrastructure/07-command-standards.md
---

# 命令参数快速参考

> **完整标准**: [07-command-standards.md](07-command-standards.md)

---

## 三层参数结构

```
全局层     vibe3 -v/-vv [COMMAND]
命令组层   vibe3 flow/handoff/... [-h]
子命令层   vibe3 flow update [--trace] [--format json] [-y]
```

---

## 全局层参数（`vibe3`）

| 参数 | 说明 |
|------|------|
| `-v` | INFO 日志 |
| `-vv` | DEBUG 日志 |
| `-h` / `--help` | 显示帮助 |
| （无参数） | 显示帮助 |

```bash
vibe3 -v flow status
vibe3 -vv flow show
vibe3 -h
vibe3 help
```

---

## 子命令层参数（所有叶子命令）

| 参数 | 短选项 | 用途 |
|------|--------|------|
| `--trace` | - | 调用链路追踪 + DEBUG（比 `-vv` 更重量级） |
| `--format` | - | 输出格式：table（默认）、json、yaml |
| `--yes` | `-y` | 自动确认（破坏性操作） |
| `--help` | `-h` | 显示帮助 |

```bash
vibe3 flow show --trace
vibe3 flow show --format json | jq '.status'
vibe3 flow show --trace --format json
vibe3 flow bind --help
vibe3 flow show -h
```

---

## `-v` vs `--trace` 对比

| | `-v` / `-vv` | `--trace` |
|---|---|---|
| 作用域 | 全局 | 子命令 |
| 日志级别 | INFO / DEBUG | DEBUG |
| 调用链追踪 | ❌ | ✅ |
| 性能开销 | 低 | 高 |
| 典型用途 | agent 日常调用 | 深度排查 |

---

## Handoff Commands

### `vibe3 handoff init`

Ensure shared handoff file exists for current branch.

**Behavior**:
- Creates `.git/vibe3/handoff/<branch-safe>/current.md` if missing
- Scaffolds fixed Markdown template

```bash
vibe3 handoff init
```

### `vibe3 handoff show`

Show a handoff artifact.

```bash
vibe3 handoff show
vibe3 handoff show @current
vibe3 handoff show @task-476/run-1.md
```

### `vibe3 handoff append <message>`

Append a lightweight update block to handoff file.

```bash
vibe3 handoff append "Need to align event taxonomy" --actor "codex/gpt-5.4" --kind finding
```

### `vibe3 handoff plan <plan_ref>`

Record plan handoff.

```bash
vibe3 handoff plan docs/plans/feature-x.md --actor "claude/sonnet-4.6"
```

### `vibe3 handoff report <report_ref>`

Record report handoff.

```bash
vibe3 handoff report docs/reports/review-2026-03-21.md --actor "claude/sonnet-4.6"
```

### `vibe3 handoff audit <audit_ref>`

Record audit handoff.

```bash
vibe3 handoff audit docs/audits/security-check.md --actor "reviewer/sonnet-4.6"
```

---

## Verification Commands

### `vibe3 check`

Verify handoff store consistency.

**Options**:
- `--fix` - Attempt auto-fix for detected issues
- `--branch <name>` - Check a single branch instead of all active flows
- `--init` - Scan merged PRs on GitHub and back-fill missing task_issue_number
- `--clean-branch` - Clean residual branches for done/aborted flows

**Checks**:
- Current branch exists in flow_state
- task_issue_number exists on GitHub
- Only one task issue per branch
- pr_number matches current branch
- plan_ref / report_ref / audit_ref files exist
- shared current.md exists for active flow

**Single Branch Check**:
Use `--branch` to check a specific branch instead of all active flows. This runs the same consistency checks as the full scan, but for a single flow:
- Verifies issue state on GitHub
- Checks PR merge status
- Validates handoff files
- Auto-fixes issues when possible

```bash
vibe3 check
vibe3 check --fix
vibe3 check --branch dev/issue-123
vibe3 check --branch task/issue-456
```

---

## 常用命令示例

```bash
# 查看帮助（任意层级）
vibe3 -h
vibe3 flow -h
vibe3 handoff -h

# 查看流程
vibe3 flow status
vibe3 flow show
vibe3 -vv flow update  # DEBUG 日志 + 更新

# Handoff 协作
vibe3 handoff show
vibe3 handoff append "context update"

# 共享状态审计
vibe3 check
vibe3 check --json
```

---

**完整标准**: [07-command-standards.md](07-command-standards.md)
