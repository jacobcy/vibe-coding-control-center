# Common Rules And Tools

术语以 [docs/standards/glossary.md](../../docs/standards/glossary.md) 为准。

## 总原则

- 先理解上下文，再动代码。
- 能用项目内建分析能力，就不要先靠猜。
- 先做影响评估，再决定是否修改。
- Python 相关命令必须走 `uv run`，不要直接用 `python` 或 `pip`。
- 当前主线以 V3 和治理规则为中心；如遇历史 shell 入口，只按兼容现场处理，不把它当默认实现路径。
- 多 worktree 并行开发时，共享运行时数据位于主仓库 git common dir，也就是主仓库 `.git`，不是当前 worktree 自己的局部 `.git`。
- 当前 flow 的结构化 handoff 以 `vibe3 handoff show` 为准，不要先读 `.agent/context/task.md`。
- 当前 flow 的共享 handoff 文件路径模式为 `.git/vibe3/handoff/<branch-safe>-<hash>/current.md`。
- 执行过程中出现 finding、bug、blocker、next step、note 等需要留痕的事项，用 `vibe3 handoff append` 单独记录。
- 这类执行中发现事项不要混进 plan、review、run 的主体输出中冒充正式结论。

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
uv run python src/vibe3/cli.py inspect symbols <file|file:symbol>
uv run python src/vibe3/cli.py inspect structure <file>
uv run python src/vibe3/cli.py inspect commit <sha>
uv run python src/vibe3/cli.py inspect base --json
```

使用规则：
- 改函数前，先跑 `inspect symbols` 看引用位置。
- 理解单文件职责时，先跑 `inspect structure`。
- 评估一组提交或 review 范围时，优先 `inspect commit`。
- 判断当前分支风险和影响面时，优先 `inspect base --json`。

### 2. 语义理解与跨文件探索

不知道代码在哪、职责边界不清、需要理解实现意图时，使用 `mcp__auggie__codebase_retrieval`。

适合：
- 找负责某项功能的模块
- 理解 plan / review / run 链路如何拼装 prompt
- 理解配置、命令、service 之间的关系

不要拿它代替精确引用分析；涉及“谁调用了谁”时，还是优先回到 `vibe3 inspect`。

### 3. 精确字符串与配置项查找

只在需要精确字面量时使用 `rg`。

适合：
- 查错误消息、配置 key、prompt 文案
- 查固定路径、文件名、常量名
- 补充确认 retrieval / inspect 的发现

不适合：
- 判断架构归属
- 判断某函数真实影响面
- 替代 AST 分析

### 4. Handoff 现场读取与记录

涉及当前 flow 的现场、交接、执行中发现的问题时，优先使用仓库内的 handoff CLI 入口。

首选命令：

```bash
uv run python src/vibe3/cli.py handoff show
uv run python src/vibe3/cli.py handoff append "<message>" --kind finding --actor "<actor>"
```

使用规则：
- 查看当前 flow 结构化 handoff，优先使用 `handoff show`，不要自己猜底层存储位置。
- 执行过程中出现 finding、bug、blocker、next step 等需要留痕的事项，用 `handoff append` 单独记录。
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
uv run python src/vibe3/cli.py inspect structure path/to/file.py
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

至少确认：
- 受影响文件
- 关键依赖
- 公开入口或高风险路径
- 对应验证方式
- 当前 flow handoff 现场

推荐先看：

```bash
uv run python src/vibe3/cli.py handoff show
```

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
