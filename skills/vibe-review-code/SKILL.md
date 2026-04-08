---
name: vibe-review-code
description: Use when the user wants a structured code review for local or PR-bound code changes, asks for a pre-PR implementation audit, wants to validate fixes against PR review feedback, or says "review this code" for source changes. Do not use for docs-only review or concept/documentation governance review.
---

# Vibe Code Review Protocol

> 项目命令参考见 `skills/vibe-instruction/SKILL.md`

**核心职责**: 代码质量审查（PR 提交前后的深度分析）

**使用场景**:

1. **PR 前**: 在创建 PR 之前，进行深度静态分析
2. **PR 后**: 根据 `vibe3 review pr` 的反馈修复代码

语义边界：

- `vibe-review-code` 负责 source code diff、实现风险、调用影响、测试覆盖与 review feedback 复核。
- 仅当用户要审查代码实现本身，或根据 review feedback 回修代码时介入。
- 文档、标准、changelog、概念漂移的审查交给 `vibe-review-docs`。

When invoked as a code reviewer, you are a Senior Staff Engineer tasked with guarding the project against entropy, dead code, and standard violations.

## 0. Token 优化策略（推荐）

**此 skill 消耗大量 token（读取大量代码文件）。强烈建议使用以下策略：**

### 方案 A：使用 Subagent（推荐）

```bash
# 在独立 agent 中运行审查，避免污染主会话
# AI 会自动使用 Agent tool 启动 subagent
```

**优势**:

- 隔离执行环境
- 主会话 token 不被消耗
- 可并行执行其他任务

### 方案 B：使用本地审查（最快）

```bash
# 使用 vibe3 进行本地代码审查
vibe3 review base
```

**优势**:

- 零外部 token 消耗
- 执行速度最快
- 深度静态分析

### 方案 C：传统 AI 审查

直接在主会话中执行审查（不推荐，消耗大量 token）

## 1. 与验证流程的关系（互补）

- **自动验证**: 包含 Lint、Tests。通常在代码改完后由 /vibe-commit 触发。
- `vibe-review-code`: 偏人工审查结论，适合 PR 前人工把关、PR 后针对 review comment 复核。
- 推荐顺序：先让自动验证跑出基础质量结果，再用本 skill 输出最终审查意见。

## 触发时机

- 你准备发起 PR，需要先做一轮严格审查时
- 你收到 review comment，需要确认修复是否引入回归时
- 你需要一份结构化审查结论（Blocking/Major/Minor/Nit）时
- 用户说"review 这段代码 / 这次改动 / 这个实现"且对象是 source changes 时

## 1. Context Gathering (Align Truth)

- **Identify Intent**: Run `vibe3 review base` (Physical Tier 1) to determine the current state of the PR and project health.
- **Fetch Diff**:
  - If a PR exists (opened): Use `gh pr diff` to fetch the source of truth for changes.
  - If local only: Use `git diff main...HEAD`.
- If local: Use `git diff` and `git diff --cached` for uncommitted changes; use `git diff main...HEAD` for committed branch diffs.
- **Review Context**: Cross-reference with the Task README and the original goal from `vibe3 handoff show`.

## 2. 影响分析（审查前）

在判断改动严重性之前，先做影响面分析。按以下工具优先级执行：

### 2.1 首选：`vibe3 inspect`（项目自有 AST 分析）

工具使用顺序遵循 `.agent/policies/common.md` 定义：

```bash
# 看分支风险与影响面
uv run python src/vibe3/cli.py inspect base --json

# 看提交级符号级波及范围
uv run python src/vibe3/cli.py inspect commit <sha>

# 检查改动点的引用关系
uv run python src/vibe3/cli.py inspect symbols <file>
uv run python src/vibe3/cli.py inspect symbols <file>:<symbol>

# 理解单文件职责、LOC、imports 与 imported-by
uv run python src/vibe3/cli.py inspect files <file>
```

必须检查：
1. 改动的每个函数/类，谁在调用它
2. 移除的函数/类，是否还有调用者残留
3. 签名变更是否波及所有调用方

### 2.2 语义理解：`mcp_auggie_codebase-retrieval`

不知道代码在哪、职责边界不清、需要理解实现意图时使用：

```
# 通过 MCP 工具调用
mcp_auggie_codebase-retrieval(information_request="<自然语言描述>", directory_path="<项目根路径>")
```

适合场景：
- 找负责某项功能的 module
- 理解 plan / review / run 链路如何拼装
- 理解配置、命令、service 之间的关系
- 跨文件语义探索

**不要**拿它代替精确引用分析；涉及"谁调用了谁"时，优先回到 `vibe3 inspect`。

### 2.3 补充：精确字符串查找

只在需要精确字面量时使用 `rg`：
- 查错误消息、配置 key、prompt 文案
- 查固定路径、文件名、常量名

**不要**把 `rg` 当主分析工具，不替代 AST 分析。

### 2.4 备选：Serena（外部工具）

当 `vibe3 inspect` 无法覆盖深度符号级分析时：

```bash
uvx --from git+https://github.com/oraios/serena@v0.1.4 serena start-mcp-server
```

前置条件：`uv/uvx` 可用且项目有 `.serena/project.yml`。

如果 Serena 不可用：记录原因，继续用 `vibe3 inspect` + grep 作为 fallback，不阻断审查。

## 3. Review Standards (Vibe V3 Paradigm Gate)

审查必须参考以下文件：
- `.agent/policies/review.md` — 审查策略（正确性、回归、边界违规、安全性）
- `.agent/policies/common.md` — 工具使用顺序和现场约束
- `.agent/rules/python-standards.md` — Python 实现标准
- `CLAUDE.md` — 项目上下文与硬规则

### 3.1 代码质量门

1. **LOC 限制**：检查改动文件是否触及 `config/settings.yaml` 中的单文件限制（default 300, max 400）和 exception 清单。新增文件不应一开始就接近上限。
2. **零死代码**：每个新增函数/类必须有明确调用者。使用 `vibe3 inspect symbols` 验证。无调用者的新增代码标记为 `Major`。
3. **Python 标准**：类型注解完整（禁止 `Any`）、Pydantic 模型、分层架构不越界。
4. **测试覆盖**：功能修复/新增必须伴随 `tests/vibe3/` 的对应修改。
5. **Lint 验证**：`uv run ruff check src tests/vibe3` 通过。

### 3.2 死代码检测

审查时必须检查：
- 本次改动是否引入了无调用者的新函数/类/方法
- 本次改动是否废弃了旧路径但未清理（兼容层残留、过时 import）
- 本次改动是否留下了 unreachable 代码分支（永远为 True/False 的条件、空的 catch/except）

发现死代码时：
- 若为本次改动新增 → 标记 `Major`，要求清理
- 若为历史遗留、本次改动触及附近 → 标记 `Minor`，记录线索供后续 issue
- 若为历史遗留、本次改动未触及 → 不标记，但可在手记中提及

### 3.3 审查优先级

按 `.agent/policies/review.md` 定义的优先级：
1. **正确性** — 逻辑是否成立、边界条件、错误处理、输出契约
2. **回归风险** — 公开命令行为、prompt/context 拼接、配置路径一致性
3. **项目边界违规** — 绕过 handoff 真源、直接改共享状态、跨 worktree 假设
4. **安全性与稳定性** — 输入处理、外部命令调用、凭证、失败路径

### 3.4 高风险审查点

命中以下路径时提高强度：
- `config/settings.yaml` 中 `review_scope.critical_paths` 定义的关键路径
- `review_scope.public_api_paths` 定义的公开 API
- `plan` / `review` / `run` 的 context builder
- prompt policy、tools guide、output contract
- 影响 inspect 结果解释或 risk scoring 的逻辑

## 3.5 Document Governance Check

When the change touches documentation, you MUST also review it against:

- `SOUL.md`
- `docs/standards/glossary.md`
- `docs/standards/action-verbs.md`
- `docs/standards/doc-quality-standards.md`

Check these questions:
1. Is the document acting within its role (`入口文件` / `标准文件` / `参考文件` / `规则文件`)?
2. Does it redefine a concept that should only live in `glossary.md`?
3. Does it use a high-frequency action verb in a way that conflicts with `action-verbs.md`?
4. Is an entry document carrying too much detail that should move to `docs/standards/` or `.agent/rules/`?
5. If the file is historical or superseded, is that status made explicit?

If any answer fails, report it as a documentation governance finding even if the prose itself is clear.

## 4. Review Process

1. **Understand Intent**: Compare implementation against the `docs/plans/` or plan file.
2. **Impact Analysis**: Run `vibe3 inspect` on changed files/symbols before judging severity.
3. **Line-by-Line Analysis**: Point out exact files and lines where issues exist.
4. **Actionability**: Never just say "it's bad", always provide the code snippet to fix it.

## 5. Output: The Code Review Report

Construct a structured report using Markdown with strict severity buckets:

- `Blocking`
- `Major`
- `Minor`
- `Nit`

Each finding MUST include:

- `file/function`
- `issue`
- `failure mode`
- `minimal fix`

## 6. Handoff 记录

完成审查后，更新 handoff：

```bash
uv run python src/vibe3/cli.py handoff append "vibe-review-code: Code review completed" --actor vibe-review-code --kind milestone
```
