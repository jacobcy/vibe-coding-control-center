# Vibe3 Review Codeagent Wrapper Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 重写 `vibe3 review` 主链路，用 `codeagent-wrapper` 承接基于 `inspect` 的审查上下文，并把本地 `pre-push` 风险触发审查接上。

**Architecture:** 本次只做“本地 review 管道重构”，把 `review` 收敛成 `inspect --json` + diff + prompt/policy + `codeagent-wrapper` 调用 + 结果解析。CLI 表面尽量缩小，只保留真正有用的入口；`pr ready` 触发云审查单独拆到后续 PR，避免把本地重构和 GitHub 侧副作用混在一起。

**Tech Stack:** Typer CLI、Pydantic、`codeagent-wrapper`、Git diff/inspect JSON、shell hooks、pytest、mypy。

---

## Scope Decision

### In Scope for next PR

- 用 `codeagent-wrapper` 替换 `codex exec`
- 支持 `--agent` 和 `--model` 参数透传
- 把 `review` 改成“消费 inspect 输出”的薄命令层
- 清理不实用子命令，收敛到少量稳定入口
- 在 `pre-push` 增加语法检查、metrics 检查、基于风险评分触发本地 review
- 更新测试和文档，确保新入口稳定

### Out of Scope for next PR

- `pr ready` 自动触发云端 review
- GitHub review 发布策略重构
- 多 agent 并发审查
- V2 shell 侧长期兼容性优化

### Recommended CLI Surface

- 保留：`vibe3 review base <branch>`
- 可选同做：`vibe3 review pr <number>`
- 删除：`uncommitted`、`commit`、`analyze-commit`

理由：
- `base` 已经覆盖本地开发和 pre-push 场景，是最稳定的主入口。
- `pr` 有价值，但会引入 GitHub diff / 发布行为边界；可以同做，但只做“本地生成 review 文本”，不要和 `pr ready` 耦合。
- `uncommitted` 与 agent review 质量不稳定，且容易把工作区噪音带进去。
- `commit` / `analyze-commit` 已经和新的 risk-score + inspect 主链重复，继续保留只会增加维护面。

### Recommended Delivery Split

- PR A: 本地 `review` 管道重构 + `pre-push` 自动触发
- PR B: `pr ready` / 云审查 / GitHub 发布联动

不要把 PR B 合并进 PR A。原因是 PR A 已经会动到 CLI、prompt、parser、hook、测试面；再叠加云侧副作用，回归面会过大。

### Task 1: Freeze the target CLI contract

**Files:**
- Modify: `src/vibe3/commands/review.py`
- Test: `tests/vibe3/commands/test_review_help.py`
- Test: `tests/vibe3/commands/test_review_base.py`
- Test: `tests/vibe3/commands/test_review_pr.py`
- Test: `tests/vibe3/commands/test_review_commit.py`
- Test: `tests/vibe3/commands/test_review_uncommitted.py`
- Test: `tests/vibe3/commands/test_review_analyze_commit.py`

**Step 1: Write the failing help/command-surface tests**

```python
def test_review_help_only_shows_supported_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "base" in result.output
    assert "pr" in result.output
    assert "commit" not in result.output
    assert "uncommitted" not in result.output
    assert "analyze-commit" not in result.output
```

如果决定本次不做 `pr`，就把 `pr` 也改成 `not in result.output`。

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/vibe3/commands/test_review_help.py -v`

Expected: FAIL，因为当前 help 还包含 `commit` / `uncommitted` / `analyze-commit`。

**Step 3: Remove dead subcommands from the CLI**

最小改动方向：

```python
app = typer.Typer(
    name="review",
    help="Code review using inspect context and codeagent-wrapper",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
```

然后删除或下线：
- `commit()`
- `uncommitted()`
- `analyze_commit()`

保留：
- `base()`
- `pr()`（如果本 PR 同做）

**Step 4: Rewrite or delete stale tests**

- `tests/vibe3/commands/test_review_commit.py` 删除或替换为“命令不存在”测试
- `tests/vibe3/commands/test_review_uncommitted.py` 删除或替换为“命令不存在”测试
- `tests/vibe3/commands/test_review_analyze_commit.py` 删除或替换为“命令不存在”测试

建议保留一个明确断言：

```python
def test_review_commit_command_removed():
    result = runner.invoke(app, ["commit", "HEAD"])
    assert result.exit_code != 0
```

**Step 5: Run focused tests**

Run: `uv run pytest tests/vibe3/commands/test_review_help.py tests/vibe3/commands/test_review_base.py tests/vibe3/commands/test_review_pr.py -v`

Expected: PASS

**Step 6: Commit**

```bash
git add src/vibe3/commands/review.py tests/vibe3/commands/test_review_*.py
git commit -m "refactor(review): simplify cli surface"
```

### Task 2: Add a real codeagent-wrapper runner

**Files:**
- Create: `src/vibe3/services/review_runner.py`
- Modify: `src/vibe3/commands/review_helpers.py`
- Test: `tests/vibe3/services/test_review_runner.py`

**Step 1: Write the failing runner tests**

```python
def test_run_review_uses_codeagent_wrapper_with_agent_and_model():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = CompletedProcess(args=[], returncode=0, stdout="VERDICT: PASS", stderr="")
        run_review_agent("prompt body", agent="codex", model="gpt-5.4")

    command = mock_run.call_args.args[0]
    assert command[0].endswith("codeagent-wrapper")
    assert "--agent" in command
    assert "--model" in command
```

再补两个失败用例：
- wrapper 返回非 0 时抛出明确异常
- wrapper 不存在时给出可操作错误

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/vibe3/services/test_review_runner.py -v`

Expected: FAIL，因为 `review_runner.py` 还不存在。

**Step 3: Implement the minimal runner**

建议新增一个独立服务，不要继续把执行细节塞在 `review_helpers.py`。

```python
from dataclasses import dataclass
from pathlib import Path
import subprocess


@dataclass(frozen=True)
class ReviewAgentOptions:
    agent: str = "codex"
    model: str | None = None
    backend: str = "codex"
    timeout_seconds: int = 600


def run_review_agent(prompt: str, options: ReviewAgentOptions) -> str:
    command = [
        str(Path.home() / ".claude/bin/codeagent-wrapper"),
        "--backend",
        options.backend,
        "--agent",
        options.agent,
    ]
    if options.model:
        command.extend(["--model", options.model])

    result = subprocess.run(
        [*command, "-", "."],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=options.timeout_seconds,
        check=False,
    )
```

实现要求：
- 默认 `backend="codex"`，但允许未来扩展
- `agent` 和 `model` 明确透传
- 不在这一层拼业务 prompt
- 错误信息中包含 stderr 摘要

**Step 4: Adapt helper imports**

把 `review_helpers.py` 改成只保留：
- `run_inspect_json()`
- 如参数组装开始重复，再抽 `build_inspect_args()` 一类薄函数；否则保持最小实现

删除 `call_codex()`，避免旧命名继续污染。

**Step 5: Run focused tests**

Run: `uv run pytest tests/vibe3/services/test_review_runner.py tests/vibe3/commands/test_review_base.py tests/vibe3/commands/test_review_pr.py -v`

Expected: PASS

**Step 6: Commit**

```bash
git add src/vibe3/services/review_runner.py src/vibe3/commands/review_helpers.py tests/vibe3/services/test_review_runner.py
git commit -m "feat(review): add codeagent wrapper runner"
```

### Task 3: Turn inspect output into a stable review prompt

**Files:**
- Modify: `src/vibe3/services/context_builder.py`
- Modify: `src/vibe3/commands/review.py`
- Test: `tests/vibe3/commands/test_review_base.py`
- Test: `tests/vibe3/commands/test_review_pr.py`

**Step 1: Write the failing prompt-shape test**

```python
def test_build_review_context_includes_policy_inspect_sections_and_diff():
    context = build_review_context(
        diff="diff --git a/x.py b/x.py",
        impact='{"symbols": []}',
        dag='{"nodes": []}',
        score='{"score": 7}',
    )
    assert "Risk Score" in context
    assert "Impact DAG" in context
    assert "Git Diff" in context
    assert "Output format requirements" in context
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/vibe3/commands/test_review_base.py -v`

Expected: FAIL，因为当前 prompt 只是旧 `Codex` 文案，没有强约束输出格式。

**Step 3: Add a single prompt contract**

目标是把 prompt 做成稳定协议，而不是每个命令拼一版文案。

建议 `build_review_context()` 输出结构：

```text
[policy markdown]

## Review Task
- Review only changed code
- Prioritize correctness, regression, config drift, deleted-file risk
- Use inspect score as triage, not as sole decision

## Inspect Summary
```json
...
```

## Git Diff
```diff
...
```

## Output format requirements
path/to/file.py:42 [MAJOR] concise issue
VERDICT: PASS|MAJOR|BLOCK
```

实现细节：
- 把 `impact`、`dag`、`score` 收口成一个 `inspect_payload` 参数也可以，减少重复参数
- 默认 policy 先继续读 `.codex/review-policy.md`，本 PR 不强制改目录名，避免引入文档迁移噪音
- 删掉 `get_git_diff()` 这类与当前链路无关的死代码，或者至少标记为待删除

**Step 4: Wire the new runner into `review.py`**

为 `base` / `pr` 增加参数：

```python
_AGENT_OPT = Annotated[str, typer.Option("--agent", help="Agent preset for codeagent-wrapper")]
_MODEL_OPT = Annotated[str | None, typer.Option("--model", help="Model override for codeagent-wrapper")]
```

在命令里调用：

```python
raw = run_review_agent(
    context,
    ReviewAgentOptions(agent=agent, model=model),
)
```

**Step 5: Run focused tests**

Run: `uv run pytest tests/vibe3/commands/test_review_base.py tests/vibe3/commands/test_review_pr.py -v`

Expected: PASS

**Step 6: Commit**

```bash
git add src/vibe3/services/context_builder.py src/vibe3/commands/review.py tests/vibe3/commands/test_review_base.py tests/vibe3/commands/test_review_pr.py
git commit -m "refactor(review): build prompt from inspect context"
```

### Task 4: Make the parser robust against codeagent-wrapper output noise

**Files:**
- Modify: `src/vibe3/services/review_parser.py`
- Test: `tests/vibe3/services/test_review_parser.py`

**Step 1: Write the failing parser test**

```python
def test_parse_review_ignores_wrapper_preamble_and_extracts_findings():
    raw = '''
    [session] started
    src/vibe3/foo.py:12 [MAJOR] Missing error handling
    VERDICT: BLOCK
    '''
    parsed = parse_codex_review(raw)
    assert parsed.verdict == "BLOCK"
    assert len(parsed.comments) == 1
```

再补一个测试，覆盖绝对路径和多余空行。

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/vibe3/services/test_review_parser.py -v`

Expected: FAIL 或缺少测试文件。

**Step 3: Implement the minimal parser hardening**

不要急着大改协议，先保持兼容：
- 可以保留 `parse_codex_review()` 名字，本 PR 只改实现
- 接受 wrapper 前导日志、空行、markdown 标题
- 当没有 `VERDICT:` 时，默认 `PASS` 仍可接受

如果你愿意顺手清命名，可新增别名：

```python
def parse_review_output(raw: str) -> ParsedReview:
    ...


parse_codex_review = parse_review_output
```

**Step 4: Run focused tests**

Run: `uv run pytest tests/vibe3/services/test_review_parser.py tests/vibe3/commands/test_review_base.py tests/vibe3/commands/test_review_pr.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/vibe3/services/review_parser.py tests/vibe3/services/test_review_parser.py
git commit -m "test(review): harden parser for wrapper output"
```

### Task 5: Replace complexity trigger with inspect-score trigger in pre-push

**Files:**
- Modify: `scripts/hooks/pre-push.sh`
- Modify: `src/vibe3/services/commit_analyzer.py`
- Modify: `src/vibe3/commands/review.py`
- Test: `tests/vibe3/commands/test_hooks_cli.py`
- Create: `tests/vibe3/hooks/test_pre_push_review_gate.py`

**Step 1: Write the failing hook tests**

至少覆盖三个场景：

```python
def test_pre_push_runs_compile_metrics_and_review_when_risk_is_high():
    ...


def test_pre_push_skips_review_when_risk_is_low():
    ...


def test_pre_push_fails_fast_when_compile_check_fails():
    ...
```

如果仓库里没有 shell hook 测试框架，可以用 `subprocess.run(["bash", "scripts/hooks/pre-push.sh"], ...)` 配合临时 PATH stub。

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/vibe3/commands/test_hooks_cli.py tests/vibe3/hooks/test_pre_push_review_gate.py -v`

Expected: FAIL，因为现有 hook 既没有语法检查，也没有基于 `inspect` 的 review 触发。

**Step 3: Replace the inline Python snippet with stable CLI calls**

推荐的 hook 顺序：

```bash
uv run python -m compileall -q src/vibe3
uv run mypy src
bash scripts/hooks/check-python-loc.sh
bash scripts/hooks/check-shell-loc.sh
uv run python src/vibe3/cli.py inspect base main --json > /tmp/vibe-inspect.json
```

然后从 JSON 里读出：
- `score.score`
- `score.risk_level`

风险高时触发：

```bash
uv run python src/vibe3/cli.py review base main --agent codex --model gpt-5.4
```

建议 phase 1 策略：
- `compileall` / `mypy` / metrics 失败：阻断 push
- inspect 失败：阻断 push，因为这是我们新的真源链路
- review 失败：先阻断 `CRITICAL/BLOCK`，`MAJOR` 只提示

**Step 4: Remove or quarantine old complexity logic**

`commit_analyzer.py` 当前依赖 `.vibe/config.yaml`，已经和仓库真源漂移。

本 PR 二选一：
- 最佳：删除 `analyze-commit` 命令后，把 `commit_analyzer.py` 标记为 deprecated 并从主链路移除
- 最小：保留文件，但不再被 hook 或 review CLI 调用

不要再新增任何基于 `complexity_score` 的触发逻辑。

**Step 5: Run focused tests**

Run: `uv run pytest tests/vibe3/commands/test_hooks_cli.py tests/vibe3/hooks/test_pre_push_review_gate.py -v`

Expected: PASS

**Step 6: Commit**

```bash
git add scripts/hooks/pre-push.sh src/vibe3/services/commit_analyzer.py tests/vibe3/commands/test_hooks_cli.py tests/vibe3/hooks/test_pre_push_review_gate.py
git commit -m "feat(hooks): trigger review from inspect risk score"
```

### Task 6: Decide whether `review pr` ships now or later

**Files:**
- Modify: `src/vibe3/commands/review.py`
- Modify: `tests/vibe3/commands/test_review_pr.py`
- Modify: `tests/vibe3/commands/test_pr_ready.py`
- Docs: `docs/plans/2026-03-19-vibe3-review-codeagent-wrapper-plan.md`

**Step 1: Make the decision explicit before code lands**

推荐结论：
- 本 PR 可以保留 `review pr`
- 但它只负责“生成本地 review 输出”
- 不做 `--publish`
- 不改 `pr ready`

**Step 2: If keeping `review pr`, write the failing no-publish test**

```python
def test_review_pr_does_not_call_github_publish_path():
    result = runner.invoke(app, ["pr", "42"])
    assert result.exit_code == 0
    mock_create_review.assert_not_called()
```

**Step 3: Remove GitHub side effects from the command**

把 `publish` 选项和 `create_review()` / `create_commit_status()` 分支移除。

如果后续确实还需要发布能力，把它搬到：
- `pr ready`
- 或一个单独的 `review publish` 命令

**Step 4: Run focused tests**

Run: `uv run pytest tests/vibe3/commands/test_review_pr.py tests/vibe3/commands/test_pr_ready.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/vibe3/commands/review.py tests/vibe3/commands/test_review_pr.py tests/vibe3/commands/test_pr_ready.py
git commit -m "refactor(review): keep pr review local-only"
```

### Task 7: Update docs and operator guidance

**Files:**
- Modify: `docs/references/codeagent-wrapper-guide.md`
- Modify: `CLAUDE.md`
- Modify: `.agent/rules/common.md`
- Test: `tests/vibe3/commands/test_review_help.py`

**Step 1: Write the failing docs/help expectation**

```python
def test_review_help_mentions_agent_and_model_options():
    result = runner.invoke(app, ["base", "--help"])
    assert "--agent" in result.output
    assert "--model" in result.output
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/vibe3/commands/test_review_help.py -v`

Expected: FAIL，直到 CLI 帮助更新。

**Step 3: Document the new operator path**

至少补齐三条文档事实：
- `vibe3 review base main --agent codex --model gpt-5.4`
- `review` 依赖 `inspect`，不是独立分析器
- `pre-push` 在高风险时会主动拉起本地 review

**Step 4: Run focused tests**

Run: `uv run pytest tests/vibe3/commands/test_review_help.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add docs/references/codeagent-wrapper-guide.md CLAUDE.md .agent/rules/common.md tests/vibe3/commands/test_review_help.py
git commit -m "docs(review): document codeagent review flow"
```

### Task 8: Run final verification for PR A

**Files:**
- No new files

**Step 1: Run the review-focused test suite**

Run:

```bash
uv run pytest \
  tests/vibe3/commands/test_review_help.py \
  tests/vibe3/commands/test_review_base.py \
  tests/vibe3/commands/test_review_pr.py \
  tests/vibe3/services/test_review_runner.py \
  tests/vibe3/services/test_review_parser.py \
  tests/vibe3/commands/test_hooks_cli.py \
  tests/vibe3/hooks/test_pre_push_review_gate.py -v
```

Expected: PASS

**Step 2: Run type checks**

Run: `uv run mypy src/vibe3`

Expected: `Success: no issues found`

**Step 3: Run one real smoke test**

Run:

```bash
uv run python src/vibe3/cli.py review base main --agent codex --model gpt-5.4
```

Expected:
- 命令能启动
- 会先消费 `inspect base main`
- 输出 review 文本和 `VERDICT`

**Step 4: Commit**

```bash
git add -A
git commit -m "test(review): verify codeagent review pipeline"
```

## Follow-up Plan for PR B

PR B 只做这几件事：
- `pr ready` 触发一次云侧 review
- 把本地 `review pr` 结果和 GitHub review/comment/status 的职责边界拆清
- 明确失败重试和重复发布策略

PR B 开始前要满足：
- PR A 已合并
- `review base` 本地链路稳定
- `pre-push` 已经能稳定拉起本地审查

## Notes for the implementer

- 仓库真源优先：配置从 `config/settings.yaml` 读取，不要新引入 `.vibe/config.yaml` 依赖。
- 先保守复用 `.codex/review-policy.md`，不要在同一 PR 顺手做 policy 文件迁移。
- `review` 的核心是“消费 inspect”，不要在 review 再做第二套分析系统。
- 只做最小必要命令面，避免把“也许以后有用”的入口继续保留下来。
