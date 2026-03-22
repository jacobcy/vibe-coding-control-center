# Plan: vibe3 diff --check

## 背景

OpenAI 提供了：
- `.agent/agent-spec.yaml` — 机器可读的 agent 行为规则（diff 限制、commit 格式、scope 约束）

核心价值是：把 SOUL.md 里"最小正确改动"的原则变成一个可执行的 CLI 卡口。

## 问题

`vibe diff --check` 命令不存在。

## 目标

实现 `vibe3 diff --check`：读取当前 git diff，对照 `agent-spec.yaml` 规则，输出违规报告。

## 使用场景

```
agent 改完代码 → vibe3 diff --check → pre-commit → commit
```

不是"改之前跑"，而是"改完之后、commit 之前跑"，作为 pre-commit 的前置补充。
专注检查 agent 行为规范层面，不检查代码质量。

## 输出格式

```
[ERROR][T1] src/unrelated.py is outside task scope
[WARN ][D2] 12 files changed — consider splitting
[OK   ][C2] Commit message format valid
```

exit code: 有 ERROR 返回 1，仅 WARN 返回 0。

## 规则映射

来自 `agent-spec.yaml`，按优先级：

| 规则 ID | 检查内容 | 严重级别 | 实现方式 |
|---------|---------|---------|---------|
| T1 | 改动文件是否在 task scope 内 | ERROR | 读 `.agent/context/task.md` 的 scope 字段 |
| D1 | 是否整个文件覆盖重写 | ERROR | diff 行数 vs 文件总行数比例 |
| D2 | 改动是否局部最小化 | WARN | 改动文件数 > max_files_changed |
| C1 | commit 是否单一职责 | ERROR | 改动文件跨多个模块 |
| C2 | commit message 格式 | ERROR | 正则匹配 forbidden_patterns |

T1 依赖 task scope，初期可以跳过（scope 未定义时降级为 WARN）。

## 实现结构

```
src/vibe3/
  commands/diff.py          # CLI 入口，vibe3 diff --check
  services/diff_service.py  # 规则引擎，读 yaml + 跑检查
```

复用现有：
- `GitClient.get_changed_files()` — 获取改动文件列表
- `GitClient.get_diff()` — 获取 diff 内容
- `agent-spec.yaml` — 规则数据源

## 不做的事

- 不实现"改之前模拟 diff"（过于复杂，实际价值低）
- 不替换现有 pre-commit（互补，不替代）
- 不实现 `--fix` 自动修复（规则违规需要人工判断）

## 与现有 risk gate 的关系

项目已有 `run_risk_gate`（`pr_quality_gates.py`），在 `vibe3 pr ready` 时触发：
- 调用 `inspect pr` 分析符号变更影响范围
- 风险评分超标则阻断 PR

两者不重叠：

| | vibe diff --check | risk gate |
|---|---|---|
| 时机 | commit 之前，本地 | PR ready，需要 PR 号 |
| 检查内容 | agent 行为规范（scope、diff 大小） | 代码风险（符号影响范围） |
| 依赖 | 纯本地 git diff | GitHub PR + inspect 分析 |

## 优先级

低。risk gate 已覆盖 PR 层面的风险拦截，pre-commit 覆盖代码质量。
当 agent 越 scope 乱改的问题变得频繁时再实现。
