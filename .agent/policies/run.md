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

## 输出提醒

- 结果面向交付，不面向表演。
- 重点报告真实改动、真实验证、真实风险。
- 输出格式遵循当前执行链路约定的结构化合同。
