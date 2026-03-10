# PRD: Vibe Start Stepper Controller

## 1. 目标 (Goal)
为了解决 AI Agent 常见的“捷径综合症”(Shortcut Syndrome)，即跳过规划直接修改代码，或者在改代码途中反复打扰用户，我们需要在现有的 Vibe Workflow 引擎之上，建立一个显式的 **状态机与分步控制器 (Stepper Controller)** 机制。
具体而言，我们要将现有的混沌执行流拆分为明确的**“人类审批点”**与**“AI 静默自驱点”**。

## 2. 核心架构设计 (Architecture)
引入双轨控制器模型，严格落实 User Global Constraint（Discussion Mode vs Execution Mode）。

### 2.1 /vibe-new (Discussion Mode 控制器)
- **定位**：规划起草器。
- **边界**：绝对禁止在此模式下修改任何业务代码 (`lib/`, `bin/`, 等)。
- **产出**：通过 `vibe-orchestrator` 的前置 Gate，最终生成一份 `plan.md`，并在生成后**强制挂起 (Hard Stop)**。
- **用户行为**：作为项目经理，人类审阅生成的 `plan.md`，确认技术细节与路线图无误。如果不满意，要求重新生成 Plan。

### 2.2 /vibe-start (Execution Mode 控制器) [新增实体]
- **定位**：全自动静默执行机与异常捕获器。
- **边界**：只针对 `plan.md` 中尚未打勾 (`[ ]`) 的任务进行改动。
- **自驱循环 (Silent Auto-Runner)**：
  - 读取第一个未打勾的任务。
  - 按下述过程内部循环：`Analyze -> Modify -> Internal Test/Lint -> Verify`。
  - 将 `[ ]` 更新为 `[x]`。
  - **自动加载并执行下一个** `[ ]`，直到全部任务完成 (`[x]`)。
- **人类停靠点 (Human Stopovers)**：执行期间，AI 必须保持静默，不应为了细枝末节询问用户。只有以下三种情况，执行引擎才允许强制挂起并向人类报错：
  1. **任务竣工**：所有任务都已被勾选为 `[x]`，交付最终结果，提示用户可以发起 `/vibe-commit`。
  2. **深度阻断 (Deep Blocker)**：代码层面陷入了连续 3 次以上的测试失败死循环，超出了 AI 的自我修复能力。
  3. **路线图崩塌 (Plan Deficiency)**：在执行过程中，AI 发觉缺失了极其重要的数据或前置文档（如缺少依赖、缺少必要的接口契约定义），且无法按原计划继续。此时触发 **"异常举报 (Exception Escalation)"**，将流程踢回给 `supervisor` 级别并向人类呼救。

## 3. 验收标准 / Action Items
1. **清理 `/vibe-new`**：
   - 移除所有关于“直接执行代码”或“进入 Execution Gate”的授权。
   - 规定其在产生 `plan.md` 后，必须提示用户使用 `/vibe-start` 启动。
2. **新增 `/vibe-start` Workflow 入口**：
   - 描述这是 Execution Mode 的唯一受控入口。
   - 定义“静默自打勾”循环。
   - 定义“异常举报挂起 (Escalation)”与“成功完结挂起”机制。
3. **强化 `supervisor/vibe-orchestrator` 规范**：
   - 写入“未看到 `/vibe-start` 命令或确认过 `plan.md` 前，AI 被剥夺修改代码权限”的原则约束。

---

*这份文档将作为 `2026-03-05-implement-vibe-start-stepper-controller` 的基础设计方案。任何 AI 在执行该需求时，必须严格参考本 PRD 中定义的分工作用与静默原则。*
