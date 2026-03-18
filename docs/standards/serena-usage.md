# 审核与 Serena 使用标准 (Review & Serena Standard)

## 0. 概述

本文档定义 Vibe Center 项目的 AI 代码审核体系与 Serena AST 检索的基础标准。遵循 `SOUL.md` 的单一事实原则，所有审核计划与执行方案必须引用本文档定义的标准。

## 1. Serena AST 检索规范

Serena 提供符号级（Symbol-level）语义上下文，是 AI 审核从“字符串匹配”提升到“语义审计”的核心。

### 1.1 强制使用场景

| 场景 | 必须使用的 Serena 工具 | 目的 |
|---|---|---|
| 修改任何函数前 | `find_referencing_symbols` | 确认影响范围，防止调用断裂 |
| 删除任何函数前 | `find_referencing_symbols` | 确认调用者为 0，定位死代码 |
| 新增函数后 | `get_symbols_overview` | 检查文件规模与符号命名规范 |
| 审核代码时 | `find_symbol` + `references` | 获取符号定义与引用图，辅助决策 |

### 1.2 DAG 影响分析支持

审核系统必须利用 Serena 产出的符号事实构建 DAG（有向无环图）：
- **符号追踪**：追踪从修改点出发的引用链。
- **模块波及分析**：基于 DAG 确定受影响的下游模块。
- **上下文收窄**：AI 审核应基于 DAG 剪枝，只读取受影响的符号上下文，而非全文件。

### 1.3 Context 增强 (Context Supplementation)

AI 审核 Prompt 必须包含 Serena 提供的结构化证据：
- **符号状态**：Changed / Referenced / New。
- **引用统计**：显示每个符号的调用次数。
- **证据化输出**：所有审核结论必须附带 `file:line` 或 `symbol: caller -> callee` 的 Serena 证据。

---

## 2. 审核网关标准 (Review Gate Standards)

项目通过四道质量网关执行审计：

### 2.1 Commit Hook (本地首道关)
- **触发**：`post-commit`。
- **策略**：轻量级、低延迟。
- **后端**：本地 Claude 或轻量级 Codex 模式。
- **目标**：防止明显 Bug、Shell 安全漏洞进入 HEAD。

### 2.2 PR Stage (仓库控制关)
- **触发**：GitHub Workflow (`pull_request`)。
- **策略**：全量 DAG 影响分析。
- **后端**：在线 Codex 或企业级后端。
- **目标**：结构化审计、变更风险评分、决定是否允许 Merge。

### 2.3 Skill 层 (流程编排关)
- **触发**：`/vibe-commit` / `/vibe-integrate` 流程中。
- **策略**：上下文敏感。
- **目标**：确保提交组符合原子性，同步 Spec 与代码。

### 2.4 Manual Audit (命令审计)
- **触发**：手动调用 `scripts/vibe-review.sh`。
- **参数标准**：
  - `--uncommitted`: 审阅未提交改动。
  - `--base <branch>`: 审阅相对基准分支的改动。
  - `--commit <hash>`: 审阅特定提交。

---

## 3. 命令与帮助标准

所有审核相关的工具命令应遵循以下标准，以方便 Agent 调用：

### 3.1 帮助与自检
- `scripts/vibe-review.sh --help`: 显示所有审核网关状态与配置。
- `scripts/vibe-review.sh check`: 审计本地审核环境（Serena 状态、API 额度）。

### 3.2 审计输出规范
所有审核后端（Codex/Claude）的输出必须包含：
1. **Risk Level**: (LOW | MEDIUM | HIGH | CRITICAL)
2. **Key Findings**: 结构化列表。
3. **Evidence**: 基于 Serena 的符号/行证据。
4. **Verdict**: (PASS | NEEDS_FIX | BLOCK)

---

## 4. 禁止行为

- ❌ 禁止 AI 在不调用 Serena 的情况下声称“已理解影响范围”。
- ❌ 禁止在审核报告中仅给出描述，不给出物理证据（文件/行号）。
- ❌ 禁止绕过 `vibe-check` 进行生产环境代码合并。

