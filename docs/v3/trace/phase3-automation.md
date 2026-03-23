---
document_type: plan
title: Codex Review Phase 3 - 自动化与 CI/CD 集成
status: draft
author: Claude Sonnet 4.6
created: 2026-03-16
last_updated: 2026-03-16
related_docs:
  - docs/v3/trace/phase1-infrastructure.md
  - docs/v3/trace/phase2-integration.md
  - docs/v3/trace/codex-auto-review-plan.md
---

# Codex Review Phase 3 - 自动化与 CI/CD 集成

> [!NOTE]
> 本阶段实现 Git Hook 自动化审核和 GitHub Workflow 集成。
>
> **前置条件**: Phase 1 和 Phase 2 已完成

---

## 目标

1. **Git Hook 自动化** - 基于 commit 复杂度自动触发审核
2. **GitHub Workflow 集成** - PR 自动审核与行级评论
3. **Merge gate 实现** - 高风险 PR 阻断合并
4. **完整 CI/CD 流程** - 从 commit 到 merge 的全流程自动化

---

## 任务清单

### 1. Commit 复杂度分析

**目标**: 分析 commit 改动规模，决定是否触发审核

#### 1.1 Commit Analyzer Service

**位置**: `services/commit_analyzer.py`

**功能**:
- 分析 commit 改动规模
- 计算复杂度分数
- 决定是否触发审核

**复杂度计算**:
```python
def analyze_commit_complexity(commit_sha: str) -> dict:
    """分析 commit 复杂度

    Returns:
        {
            "lines_changed": int,
            "files_changed": int,
            "complexity_score": int,
            "should_review": bool
        }
    """
    # 从配置读取阈值
    config = load_config()
    thresholds = config.review.auto_trigger

    # 统计改动
    lines_changed = count_lines(commit_sha)
    files_changed = count_files(commit_sha)

    # 计算复杂度
    score = calculate_score(lines_changed, files_changed)

    # 决定是否审核
    should_review = score >= thresholds.min_complexity

    return {
        "lines_changed": lines_changed,
        "files_changed": files_changed,
        "complexity_score": score,
        "should_review": should_review
    }
```

**实现任务**:
- [ ] 创建 `services/commit_analyzer.py`
- [ ] 实现 `analyze_commit_complexity()` - 分析复杂度
- [ ] 实现 `count_lines()` - 统计改动行数
- [ ] 实现 `count_files()` - 统计改动文件
- [ ] 实现 `calculate_score()` - 计算复杂度分数
- [ ] 添加日志和异常处理
- [ ] 编写测试：`tests/services/test_commit_analyzer.py`

#### 1.2 复杂度评分规则

**评分标准**:
```python
def calculate_score(lines: int, files: int) -> int:
    """计算复杂度分数 (0-10)

    规则:
    - 改动 1-50 行: 1 分
    - 改动 51-200 行: 3 分
    - 改动 201-500 行: 5 分
    - 改动 >500 行: 8 分

    - 改动 1-2 文件: +1 分
    - 改动 3-5 文件: +2 分
    - 改动 >5 文件: +3 分
    """
    score = 0

    # 行数评分
    if lines > 500:
        score += 8
    elif lines > 200:
        score += 5
    elif lines > 50:
        score += 3
    else:
        score += 1

    # 文件数评分
    if files > 5:
        score += 3
    elif files > 2:
        score += 2
    else:
        score += 1

    return min(score, 10)
```

---

### 2. Git Hook 实现

**目标**: Post-commit hook 自动触发审核

#### 2.1 Hook 脚本

**位置**: `.git/hooks/post-commit`

**流程**:
```bash
#!/bin/bash
# post-commit - 自动审核 hook

VIBE_ROOT="$(git rev-parse --show-toplevel)"

# 1. 分析 commit 复杂度
COMPLEXITY=$(python3 -m vibe3.services.commit_analyzer --commit HEAD)

# 2. 检查是否需要审核
SHOULD_REVIEW=$(echo "$COMPLEXITY" | python3 -c "import json,sys; print(json.load(sys.stdin)['should_review'])")

if [ "$SHOULD_REVIEW" = "True" ]; then
    echo "🔍 Commit complexity exceeds threshold, triggering review..."

    # 3. 调用审核（使用 vibe review commit）
    vibe review commit HEAD

    # 4. 检查审核结果
    if [ $? -ne 0 ]; then
        echo "⚠️  Review found issues. Consider addressing before push."
    fi
fi
```

**实现任务**:
- [ ] 创建 `.git/hooks/post-commit`
- [ ] 实现复杂度检查
- [ ] 实现自动触发审核
- [ ] 显示审核摘要
- [ ] 添加错误处理

#### 2.2 Hook 安装命令

**位置**: `commands/hooks.py`

**命令列表**:
- `vibe review install-hooks` - 安装 Git hooks
- `vibe review uninstall-hooks` - 卸载 Git hooks

**实现示例**:
```python
import typer
import shutil
from pathlib import Path

app = typer.Typer()

@app.command()
def install_hooks():
    """安装 Git hooks"""
    vibe_root = Path(__file__).parent.parent.parent.parent
    hooks_src = vibe_root / "scripts" / "hooks"
    hooks_dst = vibe_root / ".git" / "hooks"

    # 复制 hooks
    for hook in ["post-commit"]:
        src = hooks_src / hook
        dst = hooks_dst / hook
        shutil.copy(src, dst)
        dst.chmod(0o755)
        typer.echo(f"✅ Installed {hook}")

@app.command()
def uninstall_hooks():
    """卸载 Git hooks"""
    vibe_root = Path(__file__).parent.parent.parent.parent
    hooks_dst = vibe_root / ".git" / "hooks"

    # 删除 hooks
    for hook in ["post-commit"]:
        dst = hooks_dst / hook
        if dst.exists():
            dst.unlink()
            typer.echo(f"✅ Uninstalled {hook}")
```

**实现任务**:
- [ ] 创建 `commands/hooks.py`
- [ ] 实现 `install_hooks` 命令
- [ ] 实现 `uninstall_hooks` 命令
- [ ] 添加权限设置 (chmod +x)

---

### 3. 配置扩展

**目标**: 添加自动触发和 hook 配置

**`.vibe/config.yaml` 新增**:
```yaml
review:
  auto_trigger:
    enabled: true
    min_complexity: 3          # 最低复杂度触发审核
    min_lines_changed: 50      # 最少改动行数
    min_files_changed: 3       # 最少改动文件数

  hooks:
    post_commit: true          # 启用 post-commit hook
    pre_push: false            # 禁用 pre-push hook（避免阻塞）
```

**实现任务**:
- [ ] 扩展 `config/settings.py` - 添加 `ReviewConfig`
- [ ] 扩展 `ReviewConfig` - 添加 `auto_trigger` 和 `hooks`
- [ ] 更新配置验证逻辑

---

### 4. GitHub Workflow 集成

**目标**: PR 自动审核与行级评论

#### 4.1 Workflow 定义

**位置**: `.github/workflows/ai-pr-review.yml`

**触发条件**:
- `pull_request` 事件
- 目标分支: `main`、`v3-dev`

**流程**:
```yaml
name: AI PR Review

on:
  pull_request:
    branches: [main, v3-dev]

jobs:
  review:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # 完整历史用于 base 对比

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r src/requirements.txt

      - name: Run review
        env:
          GH_TOKEN: ${{ secrets.GH_TOKEN }}
          CODEX_API_KEY: ${{ secrets.CODEX_API_KEY }}
        run: |
          vibe review pr ${{ github.event.pull_request.number }}

      - name: Post review comments
        env:
          GH_TOKEN: ${{ secrets.GH_TOKEN }}
        run: |
          python3 -m vibe3.commands.review post-comments \
            --pr ${{ github.event.pull_request.number }} \
            --review /tmp/review.md \
            --score /tmp/final_score.json
```

**实现任务**:
- [ ] 创建 `.github/workflows/ai-pr-review.yml`
- [ ] 配置环境变量（GH_TOKEN、CODEX_API_KEY）
- [ ] 实现审核步骤
- [ ] 实现 review comments 发布

#### 4.2 Merge Gate 实现

**目标**: 高风险 PR 阻断合并

**实现方式**:
1. 计算风险分数
2. 判定风险等级（LOW/MEDIUM/HIGH/CRITICAL）
3. CRITICAL 级别自动设置 `status: failure`
4. GitHub Branch Protection 检查状态

**实现示例**:
```python
# 在 commands/review.py 中
def post_comments(pr: int, review: str, score: str):
    """发布 review comments 和 merge gate 状态"""

    # 解析分数
    score_data = json.loads(score)
    risk_level = score_data["risk_level"]

    # 发布 review comments
    # ...

    # Merge gate: CRITICAL → failure
    if risk_level == "CRITICAL":
        github_client.create_status(
            sha=github_client.get_pr_sha(pr),
            state="failure",
            description="CRITICAL risk score - review required",
            context="vibe-review/risk-score"
        )
    else:
        github_client.create_status(
            sha=github_client.get_pr_sha(pr),
            state="success",
            description=f"{risk_level} risk score",
            context="vibe-review/risk-score"
        )
```

**实现任务**:
- [ ] 实现 `create_status()` - GitHub Status API
- [ ] 实现 merge gate 逻辑
- [ ] 配置 Branch Protection Rules
- [ ] 测试高风险 PR 阻断

---

### 5. 行级 Review Comments

**目标**: 精准定位错误位置

**GitHub API 支持**:
- Issue Comment: 整个 PR 的总结
- Review Comment: 精准到 `file:line` 的评论

**实现**:
- 解析 Codex 输出的 `file:line` 格式
- 调用 GitHub API `POST /repos/{owner}/{repo}/pulls/{pull_number}/comments`
- 精准定位错误位置

**实现任务**:
- [ ] 扩展 `review_parser.py` - 解析 `file:line` 格式
- [ ] 扩展 `github_client.py` - 实现 review comments API
- [ ] 实现 `post_comments` 命令
- [ ] 测试行级评论

---

## 验收标准

### Git Hook 自动化

- [ ] Post-commit hook 可以自动触发审核
- [ ] 复杂度分析正确计算分数
- [ ] `vibe review install-hooks` 可以安装 hooks
- [ ] `vibe review uninstall-hooks` 可以卸载 hooks

### GitHub Workflow 集成

- [ ] PR 创建时自动触发审核
- [ ] Review comments 正确发送到 PR
- [ ] Merge gate 正确阻断高风险 PR
- [ ] Branch Protection Rules 配置正确

### 配置验证

- [ ] `auto_trigger` 配置生效
- [ ] `hooks` 配置生效
- [ ] 配置验证命令可以检查配置

### 测试覆盖

- [ ] `tests/services/test_commit_analyzer.py` - 复杂度分析测试
- [ ] `tests/commands/test_hooks.py` - Hook 命令测试
- [ ] 测试不同复杂度的 commit

---

## 文件清单

### 新增文件

```
src/vibe3/services/commit_analyzer.py  # Commit 分析服务
src/vibe3/commands/hooks.py            # Hook 管理命令
scripts/hooks/post-commit                          # Post-commit hook
.github/workflows/ai-pr-review.yml                 # GitHub Workflow
```

### 修改文件

```
src/vibe3/config/settings.py            # 添加 review 配置
src/vibe3/commands/review.py            # 添加 post-comments
src/vibe3/clients/github_client.py      # 添加 status API
```

---

## 完整流程

### Commit 流程

```
git commit
    ↓
post-commit hook
    ↓
commit_analyzer → 复杂度分数
    ↓
should_review? → Yes
    ↓
vibe review commit HEAD
    ↓
显示审核摘要
```

### PR 流程

```
PR created (target: main)
    ↓
GitHub Workflow triggered
    ↓
vibe review base origin/main
    ↓
1. serena_service → impact.json
2. dag_service → dag.json
3. pr_scoring_service → score.json
4. codex review → review.md
    ↓
post_comments → GitHub API
    ↓
risk_level == CRITICAL? → Merge gate: failure
```

---

## 最终交付

Phase 3 完成后，整个 Codex Review 系统实现：

✅ **基础设施** (Phase 1)
- v3 配置管理系统
- 服务迁移与架构重组
- 风险评分系统

✅ **审核流程** (Phase 2)
- 统一审核入口
- GitHub API 集成
- 行级 review comments

✅ **自动化** (Phase 3)
- Git Hook 自动审核
- GitHub Workflow 集成
- Merge gate 实现

**总计**: ~1520 行 Python 代码（配置系统 + 服务迁移 + 评分系统 + 自动化）