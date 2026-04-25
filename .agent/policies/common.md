# Common Rules And Tools

术语以 [docs/standards/glossary.md](../../docs/standards/glossary.md) 为准。

## 总原则

- 先理解上下文，再动代码。
- 能用项目内建分析能力，就不要先靠猜。
- 先做影响评估，再决定是否修改。
- Python 相关命令必须走 `uv run`，不要直接用 `python` 或 `pip`。
- 当前主线以 V3 和治理规则为中心；如遇历史 shell 入口，只按兼容现场处理，不把它当默认实现路径。
- 多 worktree 并行开发时，共享运行时数据位于主仓库 git common dir，也就是主仓库 `.git`，不是当前 worktree 自己的局部 `.git`。
- 当前 flow 的结构化 handoff 以 `vibe3 handoff status` 为准，不要先读 `.agent/context/task.md`。
- 当前 flow 的共享 handoff 文件路径模式为 `.git/vibe3/handoff/<branch-safe>-<hash>/current.md`。
- 执行过程中出现 finding、bug、blocker、next step、note 等需要留痕的事项，用 `vibe3 handoff append` 单独记录。
- 这类执行中发现事项不要混进 plan、review、run 的主体输出中冒充正式结论。

## 工作前必读 Manager 指令

开始任何工作（plan/run/review）前，必须先读取当前 flow 的 manager 交接指令：

```bash
uv run python src/vibe3/cli.py handoff status $(git branch --show-current)
```

Manager 可能已写入质量审查意见、具体修复要求、重点关注区域等指令。

## 项目记忆系统（claude-memory）

跨对话长期记忆，用于保存和检索架构共识、重要决策、最佳实践。

- **何时用**：需要回顾架构决策、寻找类似问题的解法、了解模块演进历史
- **推荐命令**：`smart_search`（智能搜索）、`timeline`（时间线）、`get_observations`（获取详情）
- **与 handoff 的区别**：claude-memory 是跨对话长期记忆；handoff 是当前 flow 的临时交接记录

## 工具选择顺序

### 1. 影响评估与符号引用

优先使用 `vibe3 inspect`。

它是本项目最有价值的专用工具，适合回答这些问题：
- 这个函数/类/命令被谁调用？
- 这次改动会波及哪些符号和模块？
- 这个分支风险为什么高？
- 提交里的改动是否触及关键路径或公开入口？

首选命令：

```bash
uv run python src/vibe3/cli.py inspect symbols <file>
uv run python src/vibe3/cli.py inspect symbols <file>:<symbol>
uv run python src/vibe3/cli.py inspect files <file>
uv run python src/vibe3/cli.py inspect commit <sha>
uv run python src/vibe3/cli.py inspect base --json
```

使用规则：
- 改函数前，先跑 `inspect symbols <file>:<symbol>` 看引用位置。
- 理解单文件职责、LOC、imports 与 imported-by 时，先跑 `inspect files`。
- 评估一组提交或 review 范围时，优先 `inspect commit`。
- 判断当前分支风险和影响面时，优先 `inspect base --json`。
- `inspect commands` 只在分析 CLI 拓扑、命令注册关系时使用，不作为默认第一选择。

注意：
- 当前实际 CLI 中**没有** `inspect structure` 子命令，不要继续引用它。
- `inspect symbols` 的稳定用法是 `<file>` 或 `<file>:<symbol>`；不要把“symbol-only 全仓搜索”当默认能力。

### 2. 精确字符串与配置项查找

只在需要精确字面量时使用 `rg`。

适合：
- 查错误消息、配置 key、prompt 文案
- 查固定路径、文件名、常量名
- 补充确认 retrieval / inspect 的发现

不适合：
- 判断架构归属
- 判断某函数真实影响面
- 替代 AST 分析

### 3. Handoff 记录

执行过程中出现 finding、bug、blocker、next step 等需要留痕的事项，用 `handoff append` 记录：

```bash
uv run python src/vibe3/cli.py handoff append "<message>" --kind finding --actor "<actor>"
```

使用规则：
- 这类记录不要混进 plan、review、run 的主体输出里，更不要塞进最终交付摘要里冒充正式结论。



## 高价值场景

### 修改实现前

先回答三个问题：
- 改动目标在哪里？
- 谁依赖它？
- 需要什么验证证据？

推荐顺序：

```bash
uv run python src/vibe3/cli.py inspect symbols path/to/file.py:symbol_name
uv run python src/vibe3/cli.py inspect files path/to/file.py
```

### 做 review 前

先看改动，再看影响。

推荐顺序：

```bash
uv run python src/vibe3/cli.py inspect base --json
uv run python src/vibe3/cli.py inspect commit <sha>
```

如果 inspect 已提供足够上下文，不要再把 review 退化成机械扫代码风格。

### 写 plan 前

plan 必须建立在真实影响面上，而不是凭直觉列步骤。

至少确认：受影响文件、关键依赖、公开入口或高风险路径、对应验证方式。

## 常用验证命令

```bash
uv run pytest
uv run mypy src/vibe3
uv run ruff check
```

只运行与本次改动相称的验证，但没有验证证据，不得声称完成。

## 禁止事项

- 不要把 `rg` 当主分析工具。
- 不要跳过 `inspect` 直接给出影响判断。
- 不要在缺少上下文时直接规划或直接审查。
- 不要默认所有问题都需要大范围搜索；先选最能回答当前问题的最小工具。
- 不要把本地草稿文件当当前 flow 的主 handoff 入口。
- 不要把执行过程中的 findings / bug 直接写进流程正文代替 handoff 记录。
