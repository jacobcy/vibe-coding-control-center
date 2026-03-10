---
name: "Vibe: Check"
description: Read shell audit output, explain task-flow or runtime discrepancies, and invoke the vibe-check skill for safe Shell-API repair of deterministic task-worktree binding gaps.
category: Workflow
tags: [workflow, vibe, verification, shared-state]
---

# Verify Task-Flow Consistency

**Input**: Run `/vibe-check` to inspect task-flow/runtime consistency and repair deterministic task-worktree binding gaps through Shell APIs when safe.

对象约束：

- `roadmap item = GitHub Project item mirror`
- `task = execution record`
- `spec_standard/spec_ref` 是 execution spec 扩展字段
- 必须先读 shell 审计输出，再做修复判断

**Steps**

1. **Acknowledge the command**
   Immediately say: "Invoking the vibe-check skill to read shell audit output and repair deterministic shared-state gaps through Shell APIs."

2. **Call the underlying skill**
   You MUST invoke the `vibe-check` skill.

3. **Respect shell / skill boundary**
   - 先读 shell 输出，再解释问题归属。
   - `vibe check(shell)` only audits.
   - `vibe-check` skill only handles `task <-> flow` / runtime repair.
   - Shared-state writes must go through Shell APIs such as `vibe task update`.
   - `spec_standard/spec_ref` 只作为扩展层证据，不得覆盖 GitHub 官方身份字段。
   - `roadmap <-> task` repair belongs to `vibe-task`, not `vibe-check`.

4. **Report status**
   Show:
   - shell audit findings
   - fixes executed through shell commands
   - items requiring user confirmation
   - any missing shell capability that blocks safe repair
