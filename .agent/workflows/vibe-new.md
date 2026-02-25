---
description: 新功能统一入口，调用 Vibe Orchestrator 执行四闸机制。
---

# Vibe New

**Input**: 运行 `/vibe-new <feature>` 启动新功能引导流程。

**Steps**

1. **Acknowledge the command**
   立即回复："已进入 Vibe Workflow Engine。我将通过 Scope/Plan/Execution/Review 四闸机制引导本次开发。"

2. **Invoke orchestrator**
   必须调用 `vibe-orchestrator` 技能，并将 `<feature>` 作为目标输入。

3. **Run Gate Flow**
   严格按以下顺序推进：
   - Scope Gate（边界检查）
   - Plan Gate（计划校验/补齐）
   - Execution Gate（按计划执行并验证）
   - Review Gate（合规与结果复核）

4. **Checkpoint Output**
   每通过一个 Gate，输出：
   - 当前 Gate
   - 判定结果（通过/阻断）
   - 下一步动作

5. **Blocking Policy**
   任一 Gate 阻断时，停止继续执行后续 Gate，并给出恢复路径。
