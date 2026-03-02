---
author: Claude Sonnet 4.6
created: 2026-03-03
purpose: V3 Execution Plane 使用规则和最佳实践
related_docs:
  - ../CLAUDE.md
  - ../../v3/execution-plane/SPEC.md
  - ../../skills/execution-plane/SKILL.md
---

# V3 Execution Plane 使用规则

## 命名约定（强制）

### Worktree 命名
- **格式**: `wt-<owner>-<task-slug>`
- **示例**: `wt-claude-add-user-auth`, `wt-opencode-fix-bug-123`
- **冲突处理**: 自动追加 4 字符后缀（如 `-a1b2`）
- **验证**: 使用 `wtvalidate` 检查命名合规性

### Tmux Session 命名
- **格式**: `<agent>-<task-slug>`
- **示例**: `claude-add-user-auth`, `opencode-fix-bug-123`
- **必须匹配**: 与 worktree 名称一致（去掉 `wt-` 前缀）

## 执行模式

### Human Mode（默认）
```bash
wtnew add-user-auth claude main
# executor="human" 写入执行结果
```

### OpenClaw Mode（自动化）
```bash
export EXECUTOR=openclaw
wtnew implement-api openclaw main
# executor="openclaw" 写入执行结果
```

## 工作流程规范

### 1. 创建环境
```bash
# 创建 worktree
wtnew <task-slug> <agent> <base-branch>

# 创建 tmux session
tmnew <task-slug> <agent>

# 验证
wtvalidate wt-<agent>-<task-slug>
```

### 2. 切换环境
```bash
# 方法 1: 手动切换
wt wt-<agent>-<task-slug>  # 切换到 worktree
tmattach <agent>-<task-slug>  # 附加到 session

# 方法 2: 使用恢复命令（推荐）
wtrecover --task-id <task-slug>
```

### 3. 清理环境
```bash
# 删除 worktree（带确认）
wtrm wt-<agent>-<task-slug>

# 删除 session（带确认）
tmkill <agent>-<task-slug>

# 批量清理
wtrm all  # 删除所有 wt-* worktrees
```

## 执行结果契约

### 写入执行结果
```bash
# 自动写入（由 wtnew/tmnew 完成）
# 手动写入（仅用于特殊情况）
write_execution_result <task_id> <worktree> <session>
```

### 查询执行结果
```bash
# 按任务 ID
query_by_task_id <task-id>

# 按 worktree
query_by_worktree <worktree>

# 按 session
query_by_session <session>
```

### 执行结果格式
```json
{
  "task_id": "add-user-auth",
  "resolved_worktree": "wt-claude-add-user-auth",
  "resolved_session": "claude-add-user-auth",
  "executor": "human",
  "timestamp": "2026-03-03T06:30:00Z"
}
```

## 会话恢复规则

### 恢复优先级
1. **--task-id**: 最精确，推荐使用
2. **--worktree**: 适用于知道 worktree 名称
3. **--session**: 适用于知道 session 名称

### 恢复场景处理
- **Session 丢失**: 自动重建 session
- **Worktree 丢失**: 报错并给出手动恢复步骤
- **两者都丢失**: 报错，建议重新创建环境

### 恢复时间要求
- 目标: < 30 秒
- 包括: 查找执行结果 + 切换 worktree + 重建 session + 附加

## 验证规则

### Worktree 验证检查项
1. ✅ 命名约定合规性
2. ✅ Git 仓库完整性
3. ✅ 工作目录状态
4. ✅ 分支跟踪状态
5. ✅ Git fsck 完整性检查

### Tmux Session 验证检查项
1. ✅ Session 存在性
2. ✅ 命名约定合规性
3. ✅ 与 worktree 匹配性
4. ✅ 执行结果一致性

## 错误处理

### 命名冲突
```
⚠️ Naming conflict detected, auto-generated suffix: a1b2
✅ Created worktree: wt-claude-add-user-auth-a1b2
```
**处理**: 接受自动后缀，或手动删除冲突项后重新创建

### Session 丢失
```
⚠️ Session lost: claude-add-user-auth
   Recreating session...
✓ Session recreated: claude-add-user-auth
```
**处理**: 使用 `wtrecover` 自动重建

### 执行结果损坏
```
✗ Failed to validate execution result
```
**处理**:
1. 检查 JSON 格式
2. 使用 `cleanup_execution_results` 清理
3. 重新创建环境

## 性能要求

| 操作 | 性能目标 |
|------|---------|
| Worktree 创建 | < 5 秒 |
| Session 创建 | < 2 秒 |
| 执行结果查询 | < 1 秒 |
| Session 恢复 | < 30 秒 |
| Worktree 验证 | < 5 秒 |

## 并发限制

### 单 Agent 并发
- 建议同时 < 5 个活跃 worktrees
- 建议同时 < 5 个活跃 sessions
- 使用 `wtlist` 和 `tmlist` 监控

### 多 Agent 并发
- 使用不同的 agent 名称避免冲突
- 使用 owner 过滤查询: `wtlist claude`
- 冲突率应 ≈ 0（自动后缀处理）

## 禁止操作

### ❌ 禁止
1. 在 main 分支直接创建 worktree
2. 跳过 `--force` 标志批量删除 worktrees
3. 手动修改执行结果 JSON 文件
4. 在 worktree 外运行 worktree 命令
5. 删除正在使用的 session

### ✅ 正确做法
1. 始终从 main 创建新分支
2. 使用 `wtrm all` 并逐个确认
3. 使用 `update_execution_result` 命令
4. 先 `wt` 切换到目标 worktree
5. 先 detach session 再 kill

## 最佳实践

### 1. 环境生命周期
```bash
# 开始任务
wtnew add-feature claude main
tmnew add-feature claude

# 工作中...
# (开发)

# 验证
wtvalidate wt-claude-add-feature

# 完成任务
wtrm wt-claude-add-feature --force
tmkill claude-add-feature --force
```

### 2. 恢复中断的工作
```bash
# 系统重启后
wtrecover --task-id add-feature

# 检查恢复历史
wtrecover-history add-feature
```

### 3. 查询执行状态
```bash
# 查询当前任务
query_by_task_id add-feature | jq '.'

# 提取 worktree
query_by_task_id add-feature | jq -r '.resolved_worktree'
```

### 4. OpenClaw 自动化
```bash
export EXECUTOR=openclaw
skill_prepare_environment auto-task openclaw main
# (自动化操作)
skill_cleanup_environment auto-task openclaw
```

## 故障排除

### 问题: Worktree 创建失败
**症状**: `❌ Not in a git repo` 或 `⚠️ On 'feature-branch', not main`

**解决**:
```bash
cd $(git rev-parse --show-toplevel)
git checkout main
wtnew <task-slug>
```

### 问题: Session 无法附加
**症状**: `❌ Session not found`

**解决**:
```bash
# 检查 session 列表
tmlist

# 使用恢复命令
wtrecover --task-id <task-id>

# 或手动创建
tmnew <task-slug> <agent>
```

### 问题: 执行结果查询失败
**症状**: `Execution result not found`

**解决**:
```bash
# 检查文件
ls .agent/execution-results/

# 验证 JSON
jq empty .agent/execution-results/<task-id>.json

# 重建执行结果
write_execution_result <task-id> <worktree> <session>
```

## 集成检查清单

在提交包含 Execution Plane 使用的变更前，确认：

- [ ] 所有 worktree 遵循命名约定
- [ ] 所有 session 遵循命名约定
- [ ] 执行结果 JSON 有效且完整
- [ ] 恢复命令正常工作
- [ ] 清理命令删除所有相关资源
- [ ] 验证命令通过所有检查
- [ ] 性能满足要求（恢复 < 30s）
- [ ] 无命名冲突（或自动处理）
- [ ] 执行器模式正确（human/openclaw）
- [ ] 文档已更新（如需要）
