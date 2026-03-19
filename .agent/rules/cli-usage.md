# CLI Usage Guide

## V3 常用命令

### 基础命令
```bash
uv run python src/vibe3/cli.py          # 运行 CLI
uv run pytest                           # 运行测试
uv run mypy src/vibe3                   # 类型检查
```

### 代码分析工具

**inspect 命令**：
```bash
# 文件结构 + 依赖关系
uv run python src/vibe3/cli.py inspect structure <file>

# 符号引用分析
uv run python src/vibe3/cli.py inspect symbols <file|file:symbol>

# commit 影响范围分析
uv run python src/vibe3/cli.py inspect commit <sha>

# 详细帮助
uv run python src/vibe3/cli.py inspect --help
```

### 代码审查

**review 命令**（基于 inspect 上下文 + codeagent-wrapper）：
```bash
# 审查分支改动（本地）
uv run python src/vibe3/cli.py review base main

# 审查 PR（本地，不发布到 GitHub）
uv run python src/vibe3/cli.py review pr 42

# 指定 agent 和 model
uv run python src/vibe3/cli.py review base main --agent codex --model gpt-5.4

# 详细帮助
uv run python src/vibe3/cli.py review --help
```

**review 依赖 inspect**：
- review 命令内部调用 `inspect` 获取风险评分和影响分析
- 输出格式要求：`path/to/file.py:42 [MAJOR] issue description`
- VERDICT 输出：`PASS | MAJOR | BLOCK`

**pre-push 自动审查**：
- pre-push hook 会自动运行 `inspect base main --json` 获取风险评分
- 当风险等级为 HIGH 或 CRITICAL 时，自动触发本地 review
- CRITICAL 风险且 VERDICT 为 BLOCK 时，会阻断 push

### 格式化输出

**PR 显示**：
```bash
uv run python src/vibe3/cli.py pr show --json      # JSON 格式
uv run python src/vibe3/cli.py pr show --yaml      # YAML 格式
uv run python src/vibe3/cli.py pr show --trace     # 带 trace 的结构化输出
```

**命令结构查看**：
```bash
uv run python src/vibe3/cli.py inspect commands pr show          # YAML 调用树（默认）
uv run python src/vibe3/cli.py inspect commands pr show --tree   # ASCII 树形
uv run python src/vibe3/cli.py inspect commands pr show --mermaid # Mermaid 图表
```

## V2 常用命令

```bash
bin/vibe check                          # 验证环境
bin/vibe tool                           # 工具管理
bin/vibe keys <list|set|get|init>       # 密钥管理
bin/vibe flow <start|review|pr|done|status|sync>  # 流程管理
```

## 代码搜索工具

### 工具选择优先级（CRITICAL）

**按场景选择正确的工具**：

1. **精确符号查找** → 用 `vibe3 inspect symbols`
   - 查找"某个函数/类的所有引用"
   - 查找"某个符号在哪里定义/使用"
   - 分析"改动的影响范围"
   - **示例**：`uv run python src/vibe3/cli.py inspect symbols git_client.py:get_pr_diff`

2. **语义理解** → 用 `mcp__auggie__codebase-retrieval`
   - 理解"某个功能是如何实现的"
   - 查找"相关的代码和文档"
   - 探索"系统的架构设计"

3. **精确字符串匹配** → 用 `Grep`
   - 查找"某个字符串字面量"
   - 搜索"配置项、错误消息、注释"
   - **NOT** 用于符号引用（用 inspect）

### Vibe3 Inspect（符号级分析）

**用途**：精确的符号定义和引用分析

**核心命令**：
```bash
# 符号引用分析（优先用于影响评估）
uv run python src/vibe3/cli.py inspect symbols <file|file:symbol>

# 文件结构 + 依赖关系
uv run python src/vibe3/cli.py inspect structure <file>

# commit 影响范围（符号 + DAG）
uv run python src/vibe3/cli.py inspect commit <sha>
```

**典型场景**：
```bash
# 场景 1: 检查方法是否被使用
$ uv run python src/vibe3/cli.py inspect symbols git_client.py:_get_pr_diff
=== Symbol: _get_pr_diff ===
  References: 1
  Referenced by: git_client.py:137  # 精确位置！

# 场景 2: 分析类/函数的影响范围
$ uv run python src/vibe3/cli.py inspect symbols git_client.py:GitClient
# 显示所有使用该类的地方

# 场景 3: 重构前评估影响
$ uv run python src/vibe3/cli.py inspect commit abc123
# 显示该 commit 修改的所有符号及其引用
```

**优势**：
- ✅ 精确到行号的引用定位
- ✅ 自动统计引用次数
- ✅ 支持跨文件分析
- ✅ 集成 DAG 依赖图

### Auggie MCP（语义搜索）

**用途**：理解代码意图和架构

**工具名称**：`mcp__auggie__codebase-retrieval`

**使用场景**：
- 探索性查询："用户认证流程是怎么实现的？"
- 架构理解："这个模块的职责是什么？"
- 文档发现："有哪些相关的测试和文档？"

**示例**：
```
mcp__auggie__codebase-retrieval
  directory_path: /path/to/project
  information_request: "How does the inspect command work?"
```

### Grep（字符串匹配）

**用途**：精确字符串匹配

**适用场景**：
- 搜索字符串字面量（配置项、错误消息）
- 查找注释、文档片段
- 统计某个模式出现次数

**不适用**：查找符号引用（应该用 `inspect symbols`）