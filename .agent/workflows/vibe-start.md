---
name: "Vibe: Start"
description: Start execution engine (Execution Mode) to complete plan.md tasks step-by-step
category: Workflow
tags: [workflow, vibe, execution, automation]
---

# Vibe Start Stepper (Execution Mode)

**Input**: 运行 `/vibe-start` 启动步进式自动打勾执行机。

## Workflow 定位
- `/vibe-start` 专职处理 **Execution Mode (执行与编码阶段)**。
- 它遵循 **“结果导向 + 异常阻断 (Result-Oriented with Exception Blocking)”**。
- 它只执行明确计划文件中的 Checklist (`[ ]`)。
- `.agent/context/task.md` 只作为本地 handoff 补充，不是执行图纸。

## Truth Sources

以下语义以标准为准：

- `docs/standards/skill-standard.md`
- `docs/standards/command-standard.md`
- `docs/standards/shell-capability-design.md`
- `docs/standards/git-workflow-standard.md`
- `docs/standards/glossary.md`

## Execution Steps

1. **Acknowledge the command & Validation**
   - 回复用户：“启动 Execution 模式。我将先解析当前任务对应的计划文件，再按其中的 Checklist 步进执行。”
   - 计划来源只能是：
     - 用户显式指定的计划文件
     - 当前 task 元数据中的 `plan_path`
   - 如果不存在可解析的计划文件，拒绝执行并提示：“图纸缺失，异常挂起 🚨。请先提供计划文件，或先通过 `/vibe-new` / 其他正规流程产出带检查项的图纸。”

2. **Identity Check**
   - 先确认当前 executing agent 的真实身份和当前现场事实。
   - 如需 shell 帮助，使用现有 `vibe <command>` 的 `-h` / `--help`，不要把 `/vibe-start` 误当成 shell 子命令。
   - 如需读取当前 branch、dirty、task 绑定等事实，可使用共享真源与 `git` / `gh` 查询。
   - 如果发现环境存在需要修正的问题，只能使用仓库中真实存在且已文档化的入口；不要在 workflow 中发明隐式修复命令。

3. **Silent Loop (静默步进自执行)**
   只要有未完成的任务（`[ ]`），引擎自动进入以下内聚循环（不请示用户）：
   - **读取第一个未完成的任务。**
   - **任务来源必须是计划文件本身。**
   - **分析与检索**：读写必要文件，确认实现路径。
   - **读取 `task.md` 仅用于补充 blockers、临时方案和关键文件，不得把其中的临时 Checklist 当作正式执行图纸。**
   - **修改代码**：实际落地编码。
   - **自我检测 (Self-Test)**：写完代码后在后台自行调用 Test 或 Lint 脚本。如果测试不过报错，自行修。
   - 验证通过后，将 `[ ]` 更新为 `[x]` 并继续进入下一个任务逻辑。

4. **Exception Escalation Hook (异常举报挂起机制)**
   **这一原则至高无上：遇到以下两种情况时，引擎必须停止打勾，并呼叫督导 (Supervisor) 异常处理！绝不盲目跳过步骤。**
   1. **系统性死循环**：在 Self-Test 中遇到超过 3 次修不好的核心级错误（Deep Blocker），超出了微调范畴。
   2. **图纸崩盘缺陷**：执行到一半发现 `plan.md` 存在前置依赖未定义、组件缺失或者规范脱钩，按原计划执行必然会导致逻辑崩溃。
   
   **举报动作**：如果出现以上情形，引擎必须立刻抛出醒目的警告：
   "🚨 **异常中断：发现不可绕过的问题 (Deep Blocker / Plan Deficiency)**。描述：[发现的问题]。该情况已提报至 `vibe-orchestrator` 控制台。Execution 引擎已被安全挂起。等待项目经理 (人类) 的修复或指令！"

5. **Completion Delivery (全剧终收口)**
   当该计划文件中的每一个 `[ ]` 都标记成 `[x]` 后，引擎彻底宣告完工跳出：
   - "🎉 所有计划项均已落地。请查阅结果。"
   - 主动提示用户：“如果各项表现符合预期，可随时使用 `/vibe-commit` 生成 PR，或者使用 `/vibe-done` 完结此工单。”
