# vibe-review-pr Backlog 约束机制测试验证

## 测试目标

验证改进后的 vibe-review-pr skill 是否正确实现了：
1. Phase 0 创建所有 Backlog task
2. agent idle 自动处理
3. Phase 5 执行模式选择

## 测试用例

### 测试 1: Phase 0 创建 Backlog task

**前置条件**：
- TMUX 已设置
- CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1

**测试步骤**：
1. 执行 `/vibe-review-pr <pr_number>`
2. 等待 Phase 0 完成
3. 执行 TaskList 查看所有 task

**预期结果**：
- ✅ Phase 1-5 的 Backlog task 全部创建
- ✅ 每个 task 的 status 为 "pending"
- ✅ blockedBy 正确设置（Phase 2 blockedBy Phase 1，依此类推）
- ✅ 每个 task 的 metadata 包含 phase_order 和 depends_on_phase

**验证命令**：
```bash
# 检查 task 数量
TaskList | grep "Phase" | wc -l
# Expected: 5
```

---

### 测试 2: agent idle 自动处理

**前置条件**：
- Phase 2 已启动
- 至少一个 agent 处于 idle 状态

**测试步骤**：
1. 观察 team-lead 收到 agent idle 通知后的行为
2. 检查 team-lead 是否自动执行：
   - 检查 inbox
   - 检查 pane
   - 重新握手（如需要）

**预期结果**：
- ✅ team-lead 自动检查 inbox/pane
- ✅ 如果未完成，自动重新握手
- ✅ 通过 TaskUpdate 同步状态
- ✅ 最多重试 3 次

**验证方法**：
- 观察 team-lead 的 Bash 工具调用（tmux capture-pane）
- 检查 TaskUpdate 的 metadata.handshake_status 变化

---

### 测试 3: Phase 5 执行模式选择

**前置条件**：
- Phase 4 完成
- 生成了最终决策和审查报告

**测试步骤**：
1. 观察 Phase 5 的执行模式选择
2. 如果是 ask-each，验证是否正确询问用户
3. 如果是 auto-decide，验证复杂度计算是否正确

**预期结果**：
- ✅ 根据 execution_mode 参数选择正确流程
- ✅ ask-each 询问用户选择（1/2/3）
- ✅ auto-decide 计算复杂度得分并选择策略
- ✅ auto-fix 仅在满足条件时执行
- ✅ comment-only 只写 comment 不修复

**验证方法**：
- 检查 team-lead 的输出是否包含执行模式说明
- 检查是否正确触发对应流程

---

## 回归测试

### 测试 4: 完整流程执行

**测试步骤**：
1. 执行 `/vibe-review-pr <real_pr_number>`
2. 观察 Phase 0-5 的完整流程
3. 验证每个 Phase 的 Backlog task 状态变化

**预期结果**：
- ✅ Phase 0 创建所有 Backlog task
- ✅ Phase 1-5 按 blockedBy 顺序执行
- ✅ 每个 Phase 结束时补充下一 Phase 的 metadata
- ✅ 最终生成完整的审查报告

---

## 测试报告模板

| 测试项 | 结果 | 备注 |
|--------|------|------|
| Phase 0 创建 Backlog | PASS/FAIL | |
| agent idle 处理 | PASS/FAIL | |
| Phase 5 执行模式 | PASS/FAIL | |
| 完整流程回归 | PASS/FAIL | |

**测试日期**: YYYY-MM-DD
**测试人员**: [Name]
**测试环境**: [tmux/Claude Code version]
