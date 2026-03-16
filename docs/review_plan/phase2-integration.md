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

1. **创建统一审核入口** - `vibe-review.sh` Shell 入口
2. **集成评分系统** - 自动风险评分与报告生成
3. **实现审核命令** - check、uncommitted、base、commit
4. **GitHub API 集成** - 行级 review comments

---

## 任务清单

### 1. Shell 统一入口

**位置**: `scripts/vibe-review.sh`

**命令列表**:
- `vibe-review.sh check` - 检查环境（Serena、Codex、Claude）
- `vibe-review.sh uncommitted` - 审核未提交改动
- `vibe-review.sh base <branch>` - 审核相对分支的改动
- `vibe-review.sh commit <sha>` - 审核指定 commit
- `vibe-review.sh metrics` - 显示代码指标
- `vibe-review.sh structure` - 显示代码结构

**实现**:
```bash
#!/usr/bin/env bash
# vibe-review.sh - 统一审核入口
set -e

VIBE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

case "$1" in
  check)
    # 检查环境（Serena、Codex、Claude）
    python3 -m vibe3.commands.review check
    ;;
  uncommitted)
    # 直接调用 Codex CLI
    codex review --uncommitted - < "$VIBE_ROOT/.codex/review-policy.md"
    ;;
  base)
    # 1. 仓库结构摘要
    python3 -m vibe3.services.structure_service > /tmp/structure.json

    # 2. 符号分析
    python3 -m vibe3.services.serena_service --base "$2" > /tmp/impact.json

    # 3. DAG 分析
    python3 -m vibe3.services.dag_service --impact /tmp/impact.json > /tmp/dag.json

    # 4. 风险评分
    python3 -m vibe3.services.pr_scoring_service \
      --impact /tmp/impact.json \
      --dag /tmp/dag.json \
      --base "$2" \
      > /tmp/score.json

    # 5. 构建上下文
    python3 -m vibe3.services.context_builder \
      --policy "$VIBE_ROOT/.codex/review-policy.md" \
      --structure /tmp/structure.json \
      --impact /tmp/impact.json \
      --dag /tmp/dag.json \
      --score /tmp/score.json \
      --out /tmp/context.md

    # 6. 调用 Codex CLI
    codex review --base "$2" - < /tmp/context.md > /tmp/review.md

    # 7. 更新风险分数（根据 Codex 结果）
    python3 -m vibe3.services.pr_scoring_service \
      --update-from-review \
      --review /tmp/review.md \
      --score /tmp/score.json \
      > /tmp/final_score.json

    # 输出风险报告
    cat /tmp/final_score.json
    ;;
  commit)
    codex review --commit "$2" - < "$VIBE_ROOT/.codex/review-policy.md"
    ;;
  metrics)
    python3 -m vibe3.commands.metrics
    ;;
  structure)
    python3 -m vibe3.commands.structure
    ;;
  *)
    echo "Usage: vibe-review.sh {check|uncommitted|base|commit|metrics|structure}"
    exit 1
    ;;
esac
```

**实现任务**:
- [ ] 创建 `scripts/vibe-review.sh`
- [ ] 实现 `check` 命令
- [ ] 实现 `uncommitted` 命令
- [ ] 实现 `base` 命令（集成评分系统）
- [ ] 实现 `commit` 命令
- [ ] 实现 `metrics` 命令
- [ ] 实现 `structure` 命令
- [ ] 添加错误处理和日志

---

### 2. 审核流程编排

**完整流程图**（对齐参考资料架构）:
```
vibe-review.sh base main
    ↓
1. structure_service → structure.json (仓库结构摘要)
    ↓
2. serena_service → impact.json (符号分析)
    ↓
3. dag_service → dag.json (影响范围)
    ↓
4. pr_scoring_service → score.json (风险评分)
    ↓
5. 构建上下文 (structure + policy + impact + dag + score + diff)
    ↓
6. codex review --base main - < context.md
    ↓
7. 解析 Codex 结果，更新风险分数
    ↓
8. GitHub API → 行级 review comments + 风险报告
```

**关键职责边界**（来自参考资料）:
- **Structure Service**: 仓库结构摘要（代码组织、模块划分）
- **Serena Service**: 事实层，给出符号和引用关系
- **DAG Service**: 缩小上下文，只看影响面
- **PR Scoring Service**: 决定风险级别（量化）
- **Codex Review**: 输出审查意见
- **GitHub API**: 落地到 PR 评论 / review comments

**实现任务**:
- [ ] 创建 `.codex/review-policy.md` (审核规则)
- [ ] 实现 `commands/review.py`：
  - `check` 命令 - 检查环境
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

### 4. Review 命令实现

**位置**: `commands/review.py`

**命令列表**:
- `vibe review check` - 检查环境
- `vibe review base <branch>` - 审核相对分支
- `vibe review commit <sha>` - 审核指定 commit
- `vibe review uncommitted` - 审核未提交改动

**实现示例**:
```python
import typer
from vibe3.services import (
    serena_service,
    dag_service,
    pr_scoring_service
)
from vibe3.clients import github_client

app = typer.Typer()

@app.command()
def check():
    """检查环境（Serena、Codex、Claude）"""
    # 检查 Serena
    try:
        serena_service.check_availability()
        typer.echo("✅ Serena available")
    except Exception as e:
        typer.echo(f"❌ Serena not available: {e}")

    # 检查 Codex
    # ... 类似逻辑

@app.command()
def base(branch: str):
    """审核相对分支的改动"""
    # 1. 符号分析
    impact = serena_service.analyze_symbols(base=branch)

    # 2. DAG 分析
    dag = dag_service.expand_impact(impact)

    # 3. 风险评分
    score = pr_scoring_service.calculate_score(impact, dag)

    # 4. 调用 Codex
    # ...

    # 5. 发送 GitHub review
    # ...
```

**实现任务**:
- [ ] 实现 `check` 命令
- [ ] 实现 `base` 命令
- [ ] 实现 `commit` 命令
- [ ] 实现 `uncommitted` 命令
- [ ] 添加错误处理和日志

---

## 验收标准

### 功能验证

- [ ] `vibe-review.sh check` 可以检查环境
- [ ] `vibe-review.sh uncommitted` 可以审核未提交改动
- [ ] `vibe-review.sh base main` 可以审核相对分支的改动
- [ ] `vibe-review.sh commit HEAD~1` 可以审核指定 commit
- [ ] 风险评分系统集成到审核流程
- [ ] GitHub API 可以发送行级 review comments

### 测试覆盖

- [ ] `tests/commands/test_review.py` - 命令测试
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
scripts/vibe-review.sh                           # Shell 统一入口
.codex/review-policy.md                          # 审核规则
scripts/python/vibe3/commands/review.py          # Review 命令
scripts/python/vibe3/services/context_builder.py # 上下文构建器
scripts/python/vibe3/services/review_parser.py   # Review 解析器
```

### 修改文件

```
scripts/python/vibe3/clients/github_client.py  # 添加 review API
```

---

## 下一步

Phase 2 完成后，进入 **Phase 3 - 自动化与 CI/CD 集成**：
- Git Hook 自动化审核
- GitHub Workflow 集成
- Merge gate 实现