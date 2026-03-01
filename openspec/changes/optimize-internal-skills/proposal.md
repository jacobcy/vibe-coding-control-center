## Why

基于 Anthropic 的 Advanced Tool Use 报告发现，Vibe Center 项目日常运行受大量的上下文堆积（Tool Context Bloat）影响严重。尤其是内部重型技能如 `vibe-commit` 会在执行时抛出巨型的 `git diff` 日志撑爆上下文。此外，复杂工作流由于缺乏明确的使用用例说明，导致 Agent 时常进行错误的判断或参数传递。为了优化体验，提升准确率并大幅降本，我们需要主动进行改造。

## What Changes

1. **引入 Tool Use Examples**：为重点网关层（如 `vibe-orchestrator`）与复杂长流（如 `vibe-audit`）的 `SKILL.md` 加入 `input_examples`，用少量 Token 的提示数据规避混用和调用失败。
2. **重接并重构 `vibe-commit` 机制**：抛弃现有的全量展示 `git diff` 和 `git status` 到大模型标准输出带来的深水区。引入 PTC（Programmatic Tool Calling）理念，针对 `vibe-commit` 改用专门的数据提取/截去脚本提供变更“摘要”。

## Capabilities

### New Capabilities
- `skill-optimizations`: 基于 Advanced Tool Use 的理念重构自带技能。包含参数 Example 的撰写模式，以及大日志命令（如 diff/status）的信息提纯策略。

### Modified Capabilities

## Impact

- `skills/vibe-audit/SKILL.md` 与 `skills/vibe-orchestrator/SKILL.md` 会被修改以追加 YAML schema 定义。
- `skills/vibe-commit/SKILL.md` 及底层对应的调用脚本将被大幅重构，预期输出由”原生 Git Diff 日志“变为”逻辑变更聚合摘要“。
- 后续开发中的每轮对话上下文消耗将显著降低，提高 Agent 响应和质量。
