---
description: 新功能统一入口，调用 Vibe Orchestrator 执行 Vibe Guard 流程。
---

# Vibe New

**Input**: 运行 `/vibe-new <feature>` 启动新功能引导流程。

**Steps**

1. **Acknowledge the command**
   立即回复："已进入 Vibe Workflow Engine。我将通过 Vibe Guard 流程（Scope/Plan/Execution/Review 等）引导本次开发。"

2. **Invoke orchestrator**
   必须调用 `vibe-orchestrator` 技能，并将 `<feature>` 作为目标输入。

3. **Run Gate Flow**
   严格按 Vibe Guard 以下顺序推进：
   - Scope Gate（边界检查）
   - Spec Gate（契约校验）
   - Plan Gate（计划校验/补齐）
   - Test Gate（测试覆盖）
   - Execution Gate（按计划执行并验证）
   - Audit/Review Gate（合规与结果复核）

4. **Checkpoint Output**
   每通过一个 Gate，输出：
   - 当前 Gate
   - 判定结果（通过/阻断）
   - 下一步动作

5. **Blocking Policy**
   任一 Gate 阻断时，停止继续执行后续 Gate，并给出恢复路径。
