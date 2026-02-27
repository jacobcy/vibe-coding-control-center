# Serena AST 检索使用规范

## 概述

Serena MCP 提供 Bash LSP-based AST 检索能力。在 Vibe Center 项目中，所有 Agent 必须在特定场景强制使用 Serena 工具，以满足 MSC 规范的 Zero Dead Code 和影响分析要求。

## 强制使用场景

| 场景 | 必须使用的 Serena 工具 | 目的 |
|---|---|---|
| 修改任何函数前 | `find_referencing_symbols` | 确认影响范围，防止断裂 |
| 删除任何函数前 | `find_referencing_symbols` | 确认调用者为 0，确认是死代码 |
| 新增函数后 | `get_symbols_overview` | 确认不超过 functions_per_file 上限 |
| 理解代码上下文 | `find_symbol` + `get_symbols_overview` | 替代 cat 整文件 |
| PR Review 死代码检查 | `find_referencing_symbols` 对所有函数 | 确认 Zero Dead Code |

## 禁止行为

- ❌ 禁止用 `read_file` 读取整个文件来"理解上下文"
- ❌ 禁止在不查引用的情况下删除函数
- ❌ 禁止在不查引用的情况下修改函数签名

## 工具说明

### `find_referencing_symbols(symbol_name)`
- **用途**：查找所有引用指定 symbol 的位置
- **返回**：文件名 + 行号 + 代码片段的列表
- **何时用**：修改或删除函数前必须调用

### `find_symbol(symbol_name)`
- **用途**：定位 symbol 的定义位置
- **返回**：定义位置
- **何时用**：理解某函数功能时优先使用，而非 cat 整文件

### `get_symbols_overview(file_path)`
- **用途**：获取文件中所有 symbols 的概览
- **返回**：函数名列表 + 位置
- **何时用**：新增函数前检查文件规模；PR Review 时列出所有函数做死代码审计

## 与验证流程的集成

在 `vibe-test-runner` Skill 的 Layer 1 阶段，必须通过 Serena 完成影响分析：

```
Before modifying function X:
1. find_referencing_symbols("X")  → verify callers
2. make changes
3. find_referencing_symbols("X")  → verify no broken references
```
