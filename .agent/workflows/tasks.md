---
description: Perform task self-check and manage the task list
---

# Tasks Workflow

## 1. Prerequisites (前置准备)
- [ ] Task file exists: `.agent/context/task.md`.

## 2. Standards Check (规范检查)
- [ ] Ensure all tasks have IDs (e.g., `[TASK-001]`).
- [ ] Verify that the current task list accurately reflects the project state.

## 3. Execution (执行)
Analyze the current progress and present it for user review.

### 3.1 Display Current Status
// turbo
1. Read and display the current task list:
```bash
cat .agent/context/task.md
```

### 3.2 Audit & Refine
2. Identify incomplete tasks and their dependencies.
3. Suggest potential next steps based on `UPGRADE_FEATURES.md` or current project goals.

## 4. Interaction (交互)
4. Ask the user:
   - "Which task would you like to focus on next?"
   - "Are there any new tasks that need to be added?"
   - "Should any completed tasks be moved to the 'Completed' section?"

## 5. Verification (验证)
- [ ] Updated `.agent/context/task.md` if changes were made.
- [ ] Aligned on the next objective.
