# Vibe3 代码分析工具指南

## 项目特色工具

- **Serena**：符号分析引擎，提供 AST 级别的代码分析
- **DAG Service**：依赖图服务，分析影响范围

## 工具选择优先级（CRITICAL）

**按场景选择正确的工具**：

1. **精确符号查找** → 用 `vibe3 inspect symbols`
   - 查找函数/类的所有引用（精确到行号）
   - 分析改动的影响范围
   - 示例：`uv run python src/vibe3/cli.py inspect symbols file.py:function_name`

2. **语义理解** → 用 `mcp__auggie__codebase-retrieval`
   - 理解功能实现方式
   - 探索系统架构
   - 查找相关代码和文档

## Vibe3 Inspect（符号级分析）

### 核心命令
```bash
# 符号引用分析（优先用于影响评估）
uv run python src/vibe3/cli.py inspect symbols <file|file:symbol>

# 文件结构 + 依赖关系
uv run python src/vibe3/cli.py inspect structure <file>

# commit 影响范围（符号 + DAG）
uv run python src/vibe3/cli.py inspect commit <sha>

# branch 风险分析（用于 pre-push hook）
uv run python src/vibe3/cli.py inspect base [--json]
```

### 典型场景
```bash
# 场景 1: 检查方法是否被使用
$ uv run python src/vibe3/cli.py inspect symbols git_client.py:_get_pr_diff
=== Symbol: _get_pr_diff ===
  References: 1
  Referenced by: git_client.py:137  # 精确位置！

# 场景 2: 重构前评估影响
$ uv run python src/vibe3/cli.py inspect commit abc123
# 显示该 commit 修改的所有符号及其引用

# 场景 3: 分支风险分析
$ uv run python src/vibe3/cli.py inspect base --json
# 返回 JSON：core_files, impacted_modules, score, changed_symbols
```
