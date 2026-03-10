---
name: "Vibe: Save"
description: Save session context, tasks, and decisions to project memory
category: Workflow
tags: [workflow, vibe, memory, persistence]
---

# Save Session Context

**Input**: Run `/vibe-save` when finishing a session or reaching a milestone.

对象约束：

- `task = execution record`
- `spec_standard/spec_ref` 是 execution spec 扩展字段，不是 GitHub 官方身份
- `/vibe-save` 必须先读 shell 输出，再决定是否同步共享真源

**Steps**

1. **Acknowledge the command**
   Immediately say: "Invoking the vibe-save skill to preserve the current session context."

2. **Call the underlying skill**
   You MUST invoke the `vibe-save` skill to perform the actual saving. This skill is responsible for gathering the context and writing to `.agent/context/memory.md` and related topic files, and it handles `.agent/governance.yaml` hooks.
   Do not try to write the files yourself manually; let the skill do it.

3. **Respect execution spec boundary**
   - 先读取 shell 输出中的 task / flow 事实，再决定保存内容。
   - 若需要同步 `spec_standard/spec_ref`，只能通过 `vibe task update` 这类 Shell API 写入。
   - 不得把 execution spec 扩展字段重写成 GitHub Project 官方来源类型。

4. **Report Status**
   Once the skill finishes execution, provide a short summary of what was saved.
