## Context

在对 Vibe Proprietary Skills 进行 Advanced Tool Use 原则的审计后，我们发现在大型文件审查、差异比对（如 `git diff`）等操作时，向大模型输送海量原始日志将导致严重的 Token 污染。如果模型要执行诸如 `vibe-commit`, `vibe-audit` 等强分析型命令，常常因为被庞大无关的差异数据淹没而失去对任务脉络的把握。同时，各类复杂编排 Skill 因缺少使用范例，经常令 Agent 在选用和传参时出现幻觉。

为此，已经在 `CLAUDE.md` 内定下了第 10 条 Hard Rule：**防污染原则**（严禁直接通过终端打印大文件或全量 `git diff`，硬性要求使用 Subagent，或者 `head/tail` 执行长文本截断截取）。

## Goals / Non-Goals

**Goals:**
- 将 `vibe-commit` 重构为基于摘要截断的防污染设计。
- 在相关的 `/skills` 的配置头引入 `input_examples`。
- 将对防长文本污染（如禁用 `cat` 原生输出全量文本，强制要求 Subagent 预处理/截断）的思想沉淀到关键的执行脚本内。

**Non-Goals:**
- 从头重写整个 `vibe-check` 链路底层架构。
- 将全部现有 `vibe-` CLI 内核替换为纯 Python 脚本（仍以 Zsh 等作为底层分发，只改造出参或调用方式）。

## Decisions

### 1. 拦截长文本爆炸的实施形式 (The PTC-lite Approach)
**决定**：由于目前主要依托 Shell 和 CLI 工具链，我们不会原生实现一套复杂的容器化 PTC (Programmatic Tool Calling) 环境，而是采取基于 Subagent 与 `head/tail` 的脚本截断模式（PTC-lite）。
- **具体策略**：对于 `vibe-commit` 里的 `git diff` 操作，禁止在主模型 Prompt 中执行大段内容的回显。改由触发子调度器（或者让模型主动在执行命令时加入 `| head -n 100` 或者专门的 Diff 分析器，诸如 `git diff --stat` 配合文件概要来获得局部快照）。

### 2. YAML Input Examples 的配置规范
**决定**：必须在 `vibe-orchestrator`, `vibe-audit` 对应的 `SKILL.md` 的 YAML 文件中，清晰编写 `input_examples`，不仅标明如何传参，更要展示边界使用案例。
- 采用原生 YAML Array 结合 `- prompt/call` 键值对，这能无缝契合以后如果底层 API 支持时的无修改打通。

## Risks / Trade-offs

- **[Risk] 部分逻辑重用导致摘要丢失过度细节** → **Mitigation**: 对于确实需要看到代码细节的场景，鼓励子级 Agent （Subagent）进行定点查看（如调用 `grep_search` 或特定行的 `view_file`），而不是从全局终端输出获取。

## Migration Plan
- 直接修改对应的 `.md` 和 `vibe-commit` 相关指导说明，推行新的规范。无破坏性兼容影响。
