---
document_type: plan
title: Codex Review Phase 2 - 审核流程集成
status: draft
author: Claude Sonnet 4.6
created: 2026-03-16
last_updated: 2026-03-16
related_docs:
  - docs/review_plan/phase1-infrastructure.md
  - docs/review_plan/codex-auto-review-plan.md
  - docs/references/codex-review.md
  - docs/references/codex-serena-intetration.md
---

# Codex Review Phase 2 - 审核流程集成

> [!NOTE]
> 本阶段创建统一审核入口，集成评分系统，实现完整的审核流程。
>
> **前置条件**: Phase 1 已完成（配置系统、服务迁移、评分系统）

---

## 目标

1. **创建统一审核命令** - `vibe review` (通过 `commands/review.py`)
2. **集成评分系统** - 自动风险评分与报告生成
3. **实现审核命令** - check、uncommitted、base、commit
4. **GitHub API 集成** - 行级 review comments

---

## 任务清单

### 1. 命令职责分工

系统提供两个新的命令，职责清晰分离：

#### `vibe inspect` - 信息提供
提供代码分析信息，为 `vibe review` 提供上下文数据

**位置**: `commands/inspect.py`

**命令列表**:
- `vibe inspect` - 综合信息展示
- `vibe inspect --metrics` - 显示代码量指标
- `vibe inspect --structure` - 显示文件结构分析
- `vibe inspect --symbols` - 显示符号定义（命令来源/函数定义）
- `vibe inspect pr <number>` - PR 改动分析（输出 JSON）
- `vibe inspect commit <sha>` - Commit 改动分析（输出 JSON）
- `vibe inspect base <branch>` - 相对分支的改动分析（输出 JSON）

**架构对齐**:
- ✅ 符合 Tier 1 (Shell 能力层) 定位：确定性操作、结构化输出
- ✅ 为 `vibe review` 提供结构化数据输入

#### `vibe review` - 代码审核
基于 `vibe inspect` 提供的上下文，进行代码审核（发现 bug、安全、性能问题）

**位置**: `commands/review.py`

**命令列表**:
- `vibe review pr <number>` - 审核 PR（调用 inspect pr 获取上下文）
- `vibe review --uncommitted` - 审核未提交改动
- `vibe review base <branch>` - 审核相对分支的改动
- `vibe review commit <sha>` - 审核指定 commit

---

### 2. 审核流程编排

**完整流程图**（对齐参考资料架构）:
```
vibe review pr 42
    ↓
1. 内部调用 vibe inspect pr 42
    ↓
2. structure_service → structure.json (仓库结构摘要)
    ↓
3. serena_service → impact.json (符号分析)
    ↓
4. dag_service → dag.json (影响范围)
    ↓
5. pr_scoring_service → score.json (风险评分)
    ↓
6. 构建上下文 (structure + policy + impact + dag + score + diff)
    ↓
7. codex review --base main - < context.md
    ↓
8. 解析 Codex 结果，更新风险分数
    ↓
9. GitHub API → 行级 review comments + 风险报告
```

**关键职责边界**（来自参考资料）:
- **`vibe inspect`**: 信息提供者，输出结构化数据
- **Structure Service**: 仓库结构摘要（代码组织、模块划分）
- **Serena Service**: 事实层，给出符号和引用关系
- **DAG Service**: 缩小上下文，只看影响面
- **PR Scoring Service**: 决定风险级别（量化）
- **Codex Review**: 输出审查意见
- **GitHub API**: 落地到 PR 评论 / review comments

**实现任务**:
- [ ] 创建 `.codex/review-policy.md` (审核规则)
- [ ] 实现 `commands/inspect.py` 的所有子命令：
  - `--metrics` - 调用 metrics_service 显示代码量
  - `--structure` - 调用 structure_service 显示文件结构
  - `--symbols` - 调用 serena_service 显示符号定义
  - `pr` - PR 改动分析（集成 serena+dag+scoring，输出 JSON）
  - `commit` - Commit 改动分析（输出 JSON）
  - `base` - 相对分支的改动分析（输出 JSON）
- [ ] 实现 `commands/review.py` 的所有子命令：
  - `pr` - 审核 PR（调用 inspect pr 获取上下文）
  - `--uncommitted` - 审核未提交改动
  - `base` - 审核相对分支（调用 inspect base 获取上下文）
  - `commit` - 审核指定 commit
- [ ] 编排服务调用顺序（structure → serena → dag → scoring）
- [ ] 处理中间文件（structure.json, impact.json, dag.json, score.json）
- [ ] 实现上下文构建（`build_review_context()`）
- [ ] 生成最终报告

#### 2.1 上下文构建实现

**位置**: `services/context_builder.py`

**目标**: 将多个数据源构建成 Codex 的输入上下文

**实现**:
```python
from pathlib import Path
from typing import Optional

def build_review_context(
    policy_path: str,
    structure_path: str,
    impact_path: str,
    dag_path: str,
    score_path: str,
    diff: str
) -> str:
    """构建 Codex review 的完整上下文

    Args:
        policy_path: review-policy.md 路径
        structure_path: structure.json 路径
        impact_path: impact.json 路径
        dag_path: dag.json 路径
        score_path: score.json 路径
        diff: git diff 输出

    Returns:
        完整的上下文字符串
    """
    policy = Path(policy_path).read_text()
    structure = Path(structure_path).read_text()
    impact = Path(impact_path).read_text()
    dag = Path(dag_path).read_text()
    score = Path(score_path).read_text()

    return f"""
{policy}

---
## Repository Structure Summary
{structure}

---
## Serena Impact JSON
{impact}

---
## Review DAG JSON
{dag}

---
## Risk Score JSON
{score}

---
## Git Diff
```diff
{diff}
```
"""

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", required=True)
    ap.add_argument("--structure", required=True)
    ap.add_argument("--impact", required=True)
    ap.add_argument("--dag", required=True)
    ap.add_argument("--score", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    # 获取 git diff
    import subprocess
    diff = subprocess.check_output(
        ["git", "diff", "--unified=3", "main...HEAD"],
        text=True
    )

    context = build_review_context(
        args.policy,
        args.structure,
        args.impact,
        args.dag,
        args.score,
        diff
    )

    Path(args.out).write_text(context)
```

**实现任务**:
- [ ] 创建 `services/context_builder.py`
- [ ] 实现 `build_review_context()` - 构建上下文
- [ ] 实现 `get_git_diff()` - 获取 git diff
- [ ] 添加日志和异常处理
- [ ] 编写测试

---

### 3. GitHub API 集成

**目标**: 发送行级 review comments 和风险报告

#### 3.1 GitHub Client 扩展

**位置**: `clients/github_client.py`

**新增方法**:
- [ ] `post_review_comment()` - 行级评论
- [ ] `post_issue_comment()` - PR 评论
- [ ] `create_review()` - 创建完整 review

**实现示例**:
```python
def post_review_comment(
    self,
    pr_number: int,
    path: str,
    line: int,
    body: str,
    side: str = "RIGHT"
) -> dict:
    """发送行级 review comment

    Args:
        pr_number: PR 编号
        path: 文件路径
        line: 行号
        body: 评论内容
        side: "RIGHT" (新代码) 或 "LEFT" (旧代码)

    Returns:
        API 响应
    """
    return self._post(
        f"/repos/{self.owner}/{self.repo}/pulls/{pr_number}/comments",
        json={
            "path": path,
            "line": line,
            "body": body,
            "side": side
        }
    )
```

#### 3.2 Review 输出解析

**目标**: 解析 Codex 输出的 `file:line` 格式

**实现任务**:
- [ ] 创建 `services/review_parser.py`
- [ ] 实现 `parse_codex_review()` - 解析 Codex 输出
- [ ] 实现 `extract_file_line_pairs()` - 提取 `file:line` 对
- [ ] 实现 `convert_to_github_format()` - 转换为 GitHub API 格式

**解析格式**:
```python
# 输入 (Codex 输出):
"""
bin/vibe:42 - Error: Missing error handling
lib/flow.sh:128 - Warning: Untested function
"""

# 输出 (GitHub API):
[
    {"path": "bin/vibe", "line": 42, "body": "Error: Missing error handling"},
    {"path": "lib/flow.sh", "line": 128, "body": "Warning: Untested function"}
]
```

---

### 4. Inspect 命令实现

**位置**: `commands/inspect.py`

**命令列表**:
- `vibe inspect` - 综合信息展示
- `vibe inspect --metrics` - 显示代码量指标
- `vibe inspect --structure` - 显示文件结构分析
- `vibe inspect --symbols` - 显示符号定义
- `vibe inspect pr <number>` - PR 改动分析（输出 JSON）
- `vibe inspect commit <sha>` - Commit 改动分析（输出 JSON）
- `vibe inspect base <branch>` - 相对分支的改动分析（输出 JSON）

**实现示例**:
```python
import typer
import json
from pathlib import Path
from vibe3.services import (
    serena_service,
    dag_service,
    pr_scoring_service,
    structure_service,
    metrics_service
)

app = typer.Typer()

@app.command()
def inspect(
    metrics: bool = False,
    structure: bool = False,
    symbols: bool = False
):
    """综合信息展示（默认显示所有，或指定某项）"""
    if not any([metrics, structure, symbols]):
        # 默认显示所有
        metrics = structure = symbols = True

    if metrics:
        data = metrics_service.collect_metrics()
        typer.echo("=== Metrics ===")
        typer.echo(data)

    if structure:
        data = structure_service.analyze()
        typer.echo("\n=== Structure ===")
        typer.echo(data)

    if symbols:
        data = serena_service.extract_symbols()
        typer.echo("\n=== Symbols ===")
        typer.echo(data)

@app.command()
def pr(pr_number: int, json_output: bool = False):
    """PR 改动分析（输出结构化 JSON）"""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. 获取 PR 改动文件列表
        files = get_pr_files(pr_number)

        # 2. 符号分析
        impact = serena_service.analyze_symbols(files)
        Path(f"{tmpdir}/impact.json").write_text(impact)

        # 3. DAG 分析
        dag = dag_service.expand_impact(impact)
        Path(f"{tmpdir}/dag.json").write_text(dag)

        # 4. 风险评分
        score = pr_scoring_service.calculate_score(impact, dag)
        Path(f"{tmpdir}/score.json").write_text(score)

        # 输出 JSON
        result = {
            "pr": pr_number,
            "impact": json.loads(impact),
            "dag": json.loads(dag),
            "score": json.loads(score)
        }

        if json_output:
            typer.echo(json.dumps(result, indent=2))
        else:
            typer.echo("=== PR Impact Analysis ===")
            typer.echo(f"Impact: {result['impact']}")
            typer.echo(f"DAG: {result['dag']}")
            typer.echo(f"Score: {result['score']}")

@app.command()
def commit(sha: str, json_output: bool = False):
    """Commit 改动分析"""
    # 类似 pr 命令，但分析 commit
    pass

@app.command()
def base(branch: str, json_output: bool = False):
    """相对分支的改动分析"""
    # 类似 pr 命令，但分析 git diff
    pass
```

**实现任务**:
- [ ] 实现 `inspect` 主命令（综合信息展示）
- [ ] 实现 `--metrics` 选项（调用 metrics_service）
- [ ] 实现 `--structure` 选项（调用 structure_service）
- [ ] 实现 `--symbols` 选项（调用 serena_service）
- [ ] 实现 `pr` 命令（PR 改动分析）
- [ ] 实现 `commit` 命令（Commit 改动分析）
- [ ] 实现 `base` 命令（相对分支改动分析）
- [ ] 在 `bin/vibe` 中注册 `inspect` 命令

---

### 5. Review 命令实现

**位置**: `commands/review.py`

**命令列表**:
- `vibe review pr <number>` - 审核 PR
- `vibe review --uncommitted` - 审核未提交改动
- `vibe review base <branch>` - 审核相对分支
- `vibe review commit <sha>` - 审核指定 commit

**实现示例**:
```python
import typer
import json
import subprocess
from pathlib import Path
from vibe3.services import context_builder
from vibe3.commands import inspect as inspect_cmd

app = typer.Typer()

@app.command()
def pr(pr_number: int):
    """审核 PR（内部调用 inspect pr 获取上下文）"""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. 调用 inspect pr 获取改动分析
        inspect_result = subprocess.run(
            ["vibe", "inspect", "pr", str(pr_number), "--json"],
            capture_output=True,
            text=True
        )
        context_data = json.loads(inspect_result.stdout)

        # 2. 保存中间文件
        Path(f"{tmpdir}/impact.json").write_text(json.dumps(context_data["impact"]))
        Path(f"{tmpdir}/dag.json").write_text(json.dumps(context_data["dag"]))
        Path(f"{tmpdir}/score.json").write_text(json.dumps(context_data["score"]))

        # 3. 获取 structure
        structure = structure_service.analyze()
        Path(f"{tmpdir}/structure.json").write_text(structure)

        # 4. 构建上下文
        context = context_builder.build_review_context(
            policy_path=".codex/review-policy.md",
            structure_path=f"{tmpdir}/structure.json",
            impact_path=f"{tmpdir}/impact.json",
            dag_path=f"{tmpdir}/dag.json",
            score_path=f"{tmpdir}/score.json",
            base="main"
        )

        # 5. 调用 Codex
        result = subprocess.run(
            ["codex", "review", "--base", "main", "-"],
            input=context,
            text=True,
            capture_output=True
        )

        typer.echo(result.stdout)

        # 6. 更新风险分数（根据 Codex 结果）
        final_score = pr_scoring_service.update_from_review(
            review=result.stdout,
            score=json.dumps(context_data["score"])
        )

        typer.echo("\n=== Risk Score ===")
        typer.echo(final_score)

@app.command()
def uncommitted():
    """审核未提交改动"""
    import subprocess
    policy = Path(".codex/review-policy.md").read_text()
    result = subprocess.run(
        ["codex", "review", "--uncommitted", "-"],
        input=policy,
        text=True
    )
    return result.returncode

@app.command()
def base(branch: str):
    """审核相对分支（内部调用 inspect base 获取上下文）"""
    # 类似 pr 命令，但调用 inspect base
    pass

@app.command()
def commit(sha: str):
    """审核指定 commit（内部调用 inspect commit 获取上下文）"""
    # 类似 pr 命令，但调用 inspect commit
    pass
```

**实现任务**:
- [ ] 实现 `pr` 命令（调用 inspect pr 获取上下文）
- [ ] 实现 `uncommitted` 命令
- [ ] 实现 `base` 命令（调用 inspect base 获取上下文）
- [ ] 实现 `commit` 命令（调用 inspect commit 获取上下文）
- [ ] 添加错误处理和日志
- [ ] 在 `bin/vibe` 中注册 `review` 命令

---

## 验收标准

### 功能验证

#### `vibe inspect` 命令
- [ ] `vibe inspect` 可以展示综合信息
- [ ] `vibe inspect --metrics` 可以显示代码量指标
- [ ] `vibe inspect --structure` 可以显示文件结构分析
- [ ] `vibe inspect --symbols` 可以显示符号定义
- [ ] `vibe inspect pr 42` 可以分析 PR 改动（输出 JSON）
- [ ] `vibe inspect commit HEAD~1` 可以分析 commit 改动（输出 JSON）
- [ ] `vibe inspect base main` 可以分析相对分支的改动（输出 JSON）

#### `vibe review` 命令
- [ ] `vibe review pr 42` 可以审核 PR（调用 inspect pr 获取上下文）
- [ ] `vibe review --uncommitted` 可以审核未提交改动
- [ ] `vibe review base main` 可以审核相对分支的改动（调用 inspect base 获取上下文）
- [ ] `vibe review commit HEAD~1` 可以审核指定 commit

#### 系统集成
- [ ] 风险评分系统集成到审核流程
- [ ] GitHub API 可以发送行级 review comments

### 测试覆盖

- [ ] `tests/commands/test_inspect.py` - Inspect 命令测试
- [ ] `tests/commands/test_review.py` - Review 命令测试
- [ ] `tests/clients/test_github_client.py` - GitHub API 测试
- [ ] `tests/services/test_review_parser.py` - 解析器测试

### 日志与错误处理

- [ ] 所有命令添加 loguru 日志
- [ ] 统一异常处理
- [ ] 友好的错误提示

---

## 文件清单

### 新增文件

```
.codex/review-policy.md                          # 审核规则
scripts/python/vibe3/commands/inspect.py         # Inspect 命令（信息提供）
scripts/python/vibe3/commands/review.py          # Review 命令（代码审核）
scripts/python/vibe3/services/context_builder.py # 上下文构建器
scripts/python/vibe3/services/review_parser.py   # Review 解析器
```

### 修改文件

```
bin/vibe                                         # 添加 inspect 和 review 命令注册
scripts/python/vibe3/clients/github_client.py  # 添加 review API
```

---

## 下一步

Phase 2 完成后，进入 **Phase 3 - 自动化与 CI/CD 集成**：
- Git Hook 自动化审核
- GitHub Workflow 集成
- Merge gate 实现