# inspect 命令优化建议 [已归档]

> ⚠️ **本文已被新方案替代**：详见 [inspect-snapshot-optimization.md](inspect-snapshot-optimization.md)
> 
> 原方案存在的问题：
> - 忽视了已有的 snapshot 模块（项目级结构分析）
> - 提议的重命名破坏了 inspect/snapshot 的职责边界
> - 统一 format 框架过度工程化
> - 成本-收益不匹配（9-14 天投入，边际收益低）
>
> 新方案采取不同思路：保留现有分工，通过**概览、下一步建议、自动工作流**让两个命令真正能用起来（1-5 天，零破坏性）。

---

## 原方案内容（保留备查）

## 当前状态评估

### 命令清单及实用价值

| 命令 | 实用价值 | 保留建议 | 问题 |
|------|---------|---------|------|
| `inspect files` | ⭐⭐⭐ 高 | ✅ 保留 | 命名模糊，应改为 `structure` |
| `inspect symbols` | ⭐⭐⭐ 高 | ✅ 保留 | 帮助文档与实现不一致 |
| `inspect base` | ⭐⭐⭐ 高 | ✅ 保留 | 命名模糊，应改为 `diff` |
| `inspect pr` | ⭐⭐ 中 | ✅ 保留 | 与 `inspect base` 功能重叠 |
| `inspect commit` | ⭐⭐ 中 | ✅ 保留 | 特定场景有用 |
| `inspect uncommit` | ⭐⭐ 中 | ✅ 保留 | 特定场景有用 |
| `inspect dead-code` | ⭐⭐⭐ 高 | ✅ 保留 | 未文档化 |
| `inspect commands` | ⭐ 低 | ❌ 移除 | 用途不清，输出价值低 |

### 核心问题

#### 1. 命名不一致
- `files` → 应该叫 `structure`（分析文件结构）
- `base` → 应该叫 `diff`（分析变更差异）
- `commands` → 用途不清，输出只是命令列表

#### 2. 帮助文档与实现不一致
```
# inspect symbols 帮助文档声称支持三种模式：
1. vibe inspect symbols <symbol>        # ❌ 实际不支持！
2. vibe inspect symbols <file>:<symbol> # ✅ 支持
3. vibe inspect symbols <file>          # ✅ 支持
```

#### 3. 输出格式不统一
- `inspect commands` 默认 YAML，支持 `--yaml/--tree/--mermaid`
- 其他命令默认文本，只支持 `--json`
- 缺少统一的 `--format` 选项

#### 4. `inspect commands` 实用价值低
```
# 当前输出只是命令列表
$ vibe3 inspect commands
Available commands: check, flow, handoff, inspect, internal, plan, pr, review, run, snapshot, status, task

# 这个信息用 vibe3 --help 就能得到，不需要单独命令
```

---

## 优化方案

### Phase 1: 命令重命名（破坏性变更）

| 当前命令 | 新命令 | 理由 |
|---------|--------|------|
| `inspect files` | `inspect structure` | 更清晰表达"分析结构" |
| `inspect base` | `inspect diff` | 更清晰表达"分析差异" |
| `inspect commands` | 删除 | 实用价值低，信息冗余 |

**迁移路径**：
1. 先添加新命令作为别名
2. 旧命令显示 deprecation warning
3. 下个版本移除旧命令

### Phase 2: 统一输出格式

```bash
# 所有命令统一支持 --format 选项
vibe3 inspect structure --format json
vibe3 inspect structure --format yaml
vibe3 inspect structure --format table  # 默认

vibe3 inspect diff --format json
vibe3 inspect diff --format table

vibe3 inspect symbols --format json
vibe3 inspect symbols --format table
```

**实现方式**：
```python
# 新增公共选项
from typing import Literal

FormatOption = Annotated[
    Literal["json", "yaml", "table"],
    typer.Option("--format", help="Output format")
]
```

### Phase 3: 修复 `inspect symbols` 帮助文档

**选项 A**：移除不支持的模式说明
```python
# 修改帮助文档，只说明支持的模式
"""
Two query modes:

1. File:Symbol (find specific symbol in file):
   vibe inspect symbols src/vibe3/services/dag_service.py:build_module_graph

2. File only (show all symbols in file):
   vibe inspect symbols src/vibe3/services/dag_service.py
"""
```

**选项 B**：实现纯符号搜索（需要 SerenaService 支持）
```python
# 实现跨文件符号搜索
else:
    # 纯符号搜索：遍历所有 Python 文件查找符号
    result = svc.search_symbol_across_codebase(symbol_spec)
```

### Phase 4: 增强发现性

```bash
# 添加顶层概览
$ vibe3 inspect
=== Inspect Overview ===

Structure Analysis:
  vibe3 inspect structure <file>   Analyze file structure (LOC, functions, imports)
  vibe3 inspect structure          Analyze all Python files

Change Analysis:
  vibe3 inspect diff [base]        Compare current branch vs base
  vibe3 inspect pr <number>        Analyze PR changes
  vibe3 inspect commit <sha>       Analyze commit changes
  vibe3 inspect uncommit           Analyze uncommitted changes

Symbol Analysis:
  vibe3 inspect symbols <file>:<symbol>   Find symbol references
  vibe3 inspect symbols <file>            List all symbols in file

Code Quality:
  vibe3 inspect dead-code          Find unused functions

Use --help on any subcommand for details.
```

---

## 实施计划

### 第一阶段：快速修复（1-2 天）

1. **修复 `inspect symbols` 帮助文档**
   - 文件：`src/vibe3/commands/inspect_symbols.py`
   - 移除不支持的模式说明

2. **删除 `inspect commands`**
   - 文件：`src/vibe3/commands/inspect.py`
   - 移除 `commands` 子命令
   - 更新相关测试

3. **添加 `inspect` 无参数概览**
   - 显示所有子命令及用途

### 第二阶段：命令重命名（3-5 天）

1. **添加新命令别名**
   - `structure` → 调用 `files` 实现
   - `diff` → 调用 `base` 实现

2. **添加 deprecation warning**
   - `files` → "Use 'inspect structure' instead"
   - `base` → "Use 'inspect diff' instead"

3. **更新文档**
   - 所有文档使用新命令名
   - 更新 skills 中的引用

### 第三阶段：统一输出格式（5-7 天）

1. **引入公共 `--format` 选项**
   - 创建 `src/vibe3/commands/inspect_format.py`
   - 统一 JSON/YAML/Table 输出逻辑

2. **迁移所有子命令**
   - 移除各命令的 `--json` 选项
   - 使用统一的 `--format` 选项

3. **更新测试**
   - 测试所有格式选项

---

## 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 命令重命名破坏现有脚本 | 中 | 添加别名 + deprecation warning |
| 删除 `inspect commands` | 低 | 该命令使用率低，信息冗余 |
| 统一 `--format` 破坏现有用法 | 中 | 保留 `--json` 作为 `--format json` 的别名 |

---

## 验收标准

- [ ] `inspect symbols` 帮助文档与实现一致
- [ ] 删除 `inspect commands` 命令
- [ ] 添加 `inspect structure` 作为 `files` 的别名
- [ ] 添加 `inspect diff` 作为 `base` 的别名
- [ ] 所有命令支持统一的 `--format` 选项
- [ ] `inspect` 无参数显示概览
- [ ] 所有测试通过
- [ ] 文档更新完成

---

## 附录：当前命令输出示例

### `inspect files` (保留，重命名为 structure)
```
=== File: src/vibe3/services/flow_service.py ===
  Language  : python
  Total LOC : 51
  Functions : 2
    L  28  __init__  (16 lines)
    L  45  get_current_branch  (7 lines)
  Imports (6):
    - vibe3.clients
    - vibe3.clients.git_client
    ...
```
**价值**：✅ 清晰展示文件结构，对代码审查有用

### `inspect dead-code` (保留)
```
=== Dead Code Report ===
  Total symbols scanned: 598
  Dead code found: 1
  Findings (1):
    [HIGH] src/vibe3/domain/handlers/_shared.py:dispatch_request
           Unused function with 0 references
```
**价值**：✅ 发现未使用代码，对代码质量有用

### `inspect commands` (删除)
```
Available commands: check, flow, handoff, inspect, internal, plan, pr, review, run, snapshot, status, task
```
**价值**：❌ 信息冗余，`vibe3 --help` 已提供
