---
description: 启动执行引擎（Execution Mode），按图索骥静默完成 `plan.md` 中的开发任务。
---

# Vibe Start Stepper (Execution Mode)

**Input**: 运行 `/vibe-start` 启动步进式自动打勾执行机。

## Workflow 定位
- `/vibe-start` 专职处理 **Execution Mode (执行与编码阶段)**。
- 它遵循 **“结果导向 + 异常阻断 (Result-Oriented with Exception Blocking)”**。
- 它会寻找 `plan.md` 或当前 `task.md` 中的任务 Checklist (`[ ]`)，一个接一个地将其执行。

## Execution Steps

1. **Acknowledge the command & Validation**
   - 回复用户：“启动 Execution 静默引擎。我将读取当前任务对应的 `plan.md` 图纸或 Checklist，准备步进执行。”
   - 如果不存在相关任务或 `[ ]` 可以执行的计划框框，拒绝执行并提示：“图纸缺失，异常挂起 🚨。请确认你已经做过 `/vibe-new` 并且输出了带有检查项的图纸。”

2. **Silent Loop (静默步进自执行)**
   只要有未完成的任务（`[ ]`），引擎自动进入以下内聚循环（不请示用户）：
   - **读取第一个未完成的任务。**
   - **分析与检索**：读写必要文件，确认实现路径。
   - **修改代码**：实际落地编码。
   - **自我检测 (Self-Test)**：写完代码后在后台自行调用 Test 或 Lint 脚本。如果测试不过报错，自行修。
   - 验证通过后，将 `[ ]` 更新为 `[x]` 并继续进入下一个任务逻辑。

3. **Exception Escalation Hook (异常举报挂起机制)**
   **这一原则至高无上：遇到以下两种情况时，引擎必须停止打勾，并呼叫督导 (Supervisor) 异常处理！绝不盲目跳过步骤。**
   1. **系统性死循环**：在 Self-Test 中遇到超过 3 次修不好的核心级错误（Deep Blocker），超出了微调范畴。
   2. **图纸崩盘缺陷**：执行到一半发现 `plan.md` 存在前置依赖未定义、组件缺失或者规范脱钩，按原计划执行必然会导致逻辑崩溃。
   
   **举报动作**：如果出现以上情形，引擎必须立刻抛出醒目的警告：
   "🚨 **异常中断：发现不可绕过的问题 (Deep Blocker / Plan Deficiency)**。描述：[发现的问题]。该情况已提报至 `vibe-orchestrator` 控制台。Execution 引擎已被安全挂起。等待项目经理 (人类) 的修复或指令！"

4. **Completion Delivery (全剧终收口)**
   当这一个 `plan.md` 上的每一个 `[ ]` 都标记成 `[x]` 后，引擎彻底宣告完工跳出：
   - "🎉 所有计划项均已落地。请查阅结果。"
   - 主动提示用户：“如果各项表现符合预期，可随时使用 `/vibe-commit` 生成 PR，或者使用 `/vibe-done` 完结此工单。”
