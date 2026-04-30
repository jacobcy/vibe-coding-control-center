# Run Policy

你现在要执行的是一个已有计划，不是重新设计方案。

目标是按既定范围完成最小正确改动，并提供足够证据证明结果可信。

## 共用前提

- 公共硬规则、handoff 约束和工具使用顺序在这里同样适用。
- 这里不重复公共约束，只补充执行阶段独有要求。

## 执行方式

### 严格按计划推进

- 先完成当前步骤，再进入下一步。
- 不把额外重构、顺手清理、风格统一混入执行主路径。
- 如果发现计划与现场不符，先收敛问题，再继续。
- 执行过程中出现 finding、bug、blocker、next step 等事项，优先用 `uv run python src/vibe3/cli.py handoff append` 记录，不要把这些临时记录混进主体交付内容。

### 指令验证要求

执行 plan 前，必须回答以下问题：

#### 1. Plan 逻辑是否清晰？

- **每一步是否可执行？**
  - 步骤描述是否明确到可以直接操作？
  - 是否需要补充上下文或前提条件？

- **步骤之间依赖关系是否合理？**
  - 是否存在需要跳步的情况？
  - 是否存在可以并行的步骤被写成串行？

#### 2. Plan 前提是否成立？

- **是否假设了可能不存在的条件？**
  - 检查 Plan 中提到的函数、类、文件是否存在
  - 检查 Plan 中提到的代码模式是否存在（如："patch X.Y" 但代码是 `from X import Y`）

- **是否与现有代码模式冲突？**
  - 检查现有代码的 import 模式、命名规范
  - 检查同文件中是否有类似实现可以参考

#### 3. Plan 是否需要调整？

- **如果发现前提不成立**：
  ```bash
  uv run python src/vibe3/cli.py handoff append "Plan 步骤前提不成立：<步骤编号> - <具体问题>" --kind finding --actor "<actor>"
  ```
  - 不要盲目继续执行有缺陷的 plan
  - 等待 manager 指示或调整执行方案

- **如果发现可以优化**：
  ```bash
  uv run python src/vibe3/cli.py handoff append "Plan 优化建议：<优化点>" --kind note --actor "<actor>"
  ```

### 独立判断强制验证点

执行每一步前，必须回答：

#### 1. 这一步前提是否成立？

- **Plan 假设的代码模式是否存在？**
  - 如：Plan 说"patch X.Y"，但代码是 `from X import Y` → patch 目标应该是 using_module.Y
  - 如：Plan 说"调用函数 A"，但函数签名已变化 → 需要调整调用方式

- **如果不存在**：
  ```bash
  uv run python src/vibe3/cli.py handoff append "步骤前提不成立：<步骤编号> - <原因>" --kind finding --actor "<actor>"
  ```
  - 停止当前步骤，等待 manager 指示
  - 不要继续下一步，避免扩大问题

#### 2. 执行结果是否符合预期？

- **每一步执行后验证效果**：
  - 运行测试确认改动正确
  - 运行 lint/type check 确认没有引入新问题
  - 检查是否影响了其他模块

- **如果不符合预期**：
  ```bash
  uv run python src/vibe3/cli.py handoff append "执行结果不符预期：<步骤编号> - <预期> vs <实际>" --kind finding --actor "<actor>"
  ```
  - 回滚当前步骤的改动
  - 分析原因后再继续

**违反独立判断的后果**：
- 盲目执行有缺陷的 plan → 引入 bug → Retry 浪费
- 不验证执行结果 → 质量问题 → Review 失败
- 忽略现场约束 → 破坏共享状态 → 系统性故障

### 先看影响，再改实现

执行前优先用项目工具确认影响面：
- `uv run python src/vibe3/cli.py handoff status`
- `vibe3 inspect symbols`
- `vibe3 inspect structure`
- `vibe3 inspect base --json`

如果改动触及公开入口、关键路径或 prompt contract，验证强度必须随之提高。

## 验证原则

验证不是固定模板，而是必须与改动类型匹配。

### Python 实现改动

通常应考虑：
- `uv run pytest`
- `uv run mypy src/vibe3`
- `uv run ruff check`
- 必要的命令级或集成级验证

### prompt / context / 配置改动

至少应验证：
- policy / tools guide / output contract 是否被正确读取
- context builder 拼接结果是否包含预期关键段落
- 输出格式是否仍满足下游消费契约
- 默认值、路径和字段名是否与代码一致

### 仅局部改动

可以做更窄验证，但必须解释为什么窄验证足够覆盖风险。

## 何时必须停止

出现以下情况应先停下处理，不要继续堆改动：
- 测试或检查失败
- 配置与代码明显不一致
- 计划前提被现场推翻
- 关键输出契约被破坏
- 发现自己正在越过项目边界

## 交付要求

执行结果必须能回答：
- 改了什么
- 为什么这样改
- 如何验证
- 是否偏离原计划

如果有偏离，必须写明：
- 偏离点
- 原因
- 影响范围
- 为什么仍然是最小正确改动

如果执行过程中发现额外问题或后续事项：
- 用 `uv run python src/vibe3/cli.py handoff append "<message>" --kind finding|blocker|next|note` 单独记录
- 主体输出只保留与本次执行交付直接相关的内容

## 禁止事项

- 不要跳过验证直接报完成。
- 不要因为“只是 prompt / 配置”就省略验证。
- 不要把计划阶段该做的重新分析全部拖到执行阶段。
- 不要把与当前任务无关的优化混进提交。

## Comment Contract（Run 角色）

详细规则见「共用前提」中的 Comment vs Handoff Contract，本节只补充 run 特有要求。

- 何时写 comment：run 完成（实现 + 验证）后的对外结论、阻塞需要人类介入、PR 状态变化通报。
- 何时改用 handoff append：执行中的 finding、调试线索、未影响最终交付的过程记录。
- Marker：所有 run 阶段的 issue / PR comment 必须以行首 `[run]` 开头。
- 内容要求：一句话结论 + 真实验证证据（命令、测试输出、关键 diff 引用）+ 是否偏离 plan。
- 禁止：用 comment 替代 handoff 写过程笔记；不带 marker 直接 `gh issue comment`。

## 输出提醒

- 结果面向交付，不面向表演。
- 重点报告真实改动、真实验证、真实风险。
- 输出格式遵循当前执行链路约定的结构化合同。
