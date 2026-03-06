---
document_type: standard
title: Serena Usage Standard
status: approved
scope: ai-workflow
author: GPT-5 Codex
created: 2026-03-07
last_updated: 2026-03-07
related_docs:
  - DEVELOPER.md
  - .serena/project.yml
  - supervisor/vibe-test-runner/SKILL.md
  - docs/standards/doc-quality-standards.md
---

# Serena 使用标准

## 概述

Serena 在本项目中是 **MCP AST 能力**，不是 `skills/` 目录里的 Skill 包。
它的职责是做符号级影响分析（调用关系、定义位置、函数概览），用于约束 Shell 代码修改风险。

## 启动方式

优先使用按需启动（无需全局安装 `serena` 命令）：

```bash
uvx --from git+https://github.com/oraios/serena serena start-mcp-server
```

前置条件：
- `uv` / `uvx` 可用
- 首次拉取可访问网络
- 项目根目录存在 `.serena/project.yml`

## 强制使用场景

| 场景 | 必须使用的能力 | 目的 |
|---|---|---|
| 修改任何函数前 | `find_referencing_symbols(<function>)` | 确认影响范围，避免断裂 |
| 删除任何函数前 | `find_referencing_symbols(<function>)` | 确认调用者为 0，避免删错 |
| 新增函数后 | `get_symbols_overview(<file>)` | 复核符号规模与结构 |
| 理解局部上下文 | `find_symbol` + `get_symbols_overview` | 替代整文件盲读 |
| Review 阶段死代码检查 | 对候选函数批量 `find_referencing_symbols` | 满足 Zero Dead Code |

## 与验证流程集成

`supervisor/vibe-test-runner/SKILL.md` 的 Layer 1 必须先执行 Serena 分析，再进入 Lint/Test。

最小流程：

```text
1) find_referencing_symbols("X")
2) 修改实现
3) find_referencing_symbols("X") 复核调用完整
4) 进入 Layer 2/3/4（Lint / Tests / Review Gate）
```

## 失败策略

若 Serena 因环境问题不可用（例如网络失败、`uvx` 不可用、配置缺失）：

1. 记录阻塞原因
2. 继续执行 Lint 与 Tests，避免完全阻塞交付
3. 在 Review Gate 结果中标记为 `Major`
4. 在最终报告明确“未完成 AST 影响分析”

## 禁止行为

- 不查引用直接修改函数签名
- 不查引用直接删除函数
- 用整文件盲读替代符号级检索（除非确有必要且已说明）

## 术语边界

- Serena：MCP AST 服务能力（工具层）
- Skill：`skills/*/SKILL.md` 中的流程定义（工作流层）

两者可协同，但不是同一个东西。
