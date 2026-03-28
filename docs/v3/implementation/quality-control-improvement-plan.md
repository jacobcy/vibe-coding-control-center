# Vibe Center 质量控制系统改进计划

> **文档定位**：本计划基于审计报告和三个设计文档，制定务实、分阶段的改进方案
> **核心原则**：解决实际问题，不过度工程化，优先利用已有能力

---

## 一、现状分析

### 1.1 审计报告核心问题

| 问题 | 优先级 | 状态 | 影响 |
|------|--------|------|------|
| 🔴 `enable_trace()` 重复代码 (47行) | P0 | 未修复 | 维护成本高 |
| 🟡 缺少 pre-push hook | P1 | 未修复 | 不合规代码可能被推送 |
| 🟡 Merge 缺少 review comments 检查 | P1 | 未修复 | 合并风险 |
| 🟡 配置读取不统一 | P1 | 未修复 | 潜在不一致 |
| 🟡 质量门禁逻辑分散 | P1 | 部分存在 | 维护困难 |

### 1.2 当前质量控制阶段分析

#### Commit 阶段 (Pre-commit)

**已有检查**（`.pre-commit-config.yaml`）：
- ✅ ShellCheck (bash/sh scripts)
- ✅ Custom Lint (scripts/hooks/lint.sh)
- ✅ Ruff (Python linter) + Black (formatter)
- ✅ MyPy (Python type checker)
- ✅ Shell LOC ceiling (≤ 7000)
- ✅ Python LOC ceiling (≤ config limit)
- ✅ Per-file LOC (default 200, max 300)
- ✅ Test file LOC check

**缺失检查**：
- ❌ 无测试运行（注释掉，避免减慢commit）
- ❌ 无覆盖率检查
- ❌ 无代码审查

**Post-commit Hook**：
- ⚠️ `scripts/hooks/post-commit` 存在但依赖已废弃的命令
- ⚠️ 调用 `vibe review analyze-commit` 和 `vibe review commit` (功能已移除或重命名)

**结论**：
- ✅ **Commit阶段只做基本检查是合理的**（快速反馈）
- ❌ Post-commit hook已失效，需要清理或重新设计

---

#### Push 阶段 (Pre-push)

**已有检查**：
- ❌ **无 pre-push hook**
- ❌ 无任何检查

**缺失检查**：
- ❌ 无本地代码审查
- ❌ 无覆盖率检查
- ❌ 无风险评分检查

**结论**：
- 🔴 **这是一个严重漏洞**：不合规代码可能被推送
- 🔴 **应该在此阶段添加本地review**

---

#### PR Ready 阶段

**已有检查**（`src/vibe3/commands/pr_quality_gates.py`）：
- ✅ `run_coverage_gate()` - 分层覆盖率检查
  - Services ≥ 80%
  - Clients ≥ 80%
  - Commands ≥ 80%
- ✅ `run_risk_gate()` - 风险评分检查
  - 调用 `inspect pr` 获取风险评分
  - 高风险PR自动阻断

**已实现服务**（`src/vibe3/services/coverage_service.py`）：
- ✅ `CoverageService` - 运行pytest并分析分层覆盖率
- ✅ 生成 `CoverageReport` 和 `LayerCoverage` 数据模型
- ✅ 解析 pytest-cov JSON 输出
- ✅ 分层统计（services/clients/commands）

**集成状态**：
- ✅ 已集成到 `vibe pr ready` 命令
- ✅ 支持 `--skip-coverage` 跳过
- ✅ 支持 `--force` 强制跳过质量门禁

**结论**：
- ✅ **PR Ready阶段质量门禁已基本完善**
- ⚠️ 需要确保开发者正确使用

---

#### PR Merge 阶段

**已有检查**（`src/vibe3/commands/pr_lifecycle.py:merge()`）：
- ✅ PR ready 状态检查
- ✅ CI 通过检查
- ❌ Review comments 检查（TODO，功能已移除）

**结论**：
- 🟡 需要补充 review comments 检查

---

### 1.3 已有能力清单

#### 已实现但未充分利用

| 能力 | 实现位置 | 当前使用状态 | 潜在用途 |
|------|---------|------------|---------|
| **CoverageService** | `services/coverage_service.py` | ✅ PR ready使用 | 可用于pre-push |
| **风险评分** | `inspect pr` + `pr_scoring_service.py` | ✅ PR ready使用 | 可用于pre-push |
| **AST分析** | `services/serena_service.py` | ✅ inspect使用 | 可用于本地review |
| **依赖图分析** | `services/dag_service.py` | ✅ inspect使用 | 可用于影响分析 |

**关键发现**：
- 🎯 **CoverageService已完整实现，可以直接用于pre-push**
- 🎯 **风险评分已实现，可以直接用于pre-push**
- 🎯 **本地review能力已存在（`vibe review pr`），但未集成到hooks**

---

### 1.4 hook 脚本现状

**当前入口**：
```bash
bash scripts/hooks/pre-push.sh
bash scripts/hooks/check-python-loc.sh
bash scripts/hooks/check-shell-loc.sh
```

**问题**：
- 需要保持 shell 脚本与 CI 共用同一实现
- 不应额外维护独立的 Python CLI 包装层

---

## 二、改进方案

### 2.1 核心原则

1. **解决实际问题**：优先修复审计报告中的具体问题
2. **充分利用已有能力**：复用已实现的服务，避免重复开发
3. **不过度工程化**：不急于部署复杂的分级系统
4. **分阶段实施**：先修复，再增强，最后评估

### 2.2 阶段职责重新定义

#### Commit 阶段 (Pre-commit)

**目标**：快速反馈，基本质量保证

**职责**：
- ✅ Lint检查（Shell + Python）
- ✅ Type检查（MyPy）
- ✅ Format检查（Black）
- ✅ LOC限制检查（防止代码膨胀）
- ❌ **不做**：测试运行、覆盖率检查、代码审查

**执行时间**：< 5秒

---

#### Push 阶段 (Pre-push) 🆕

**目标**：本地审查，拦截明显问题，减少CI浪费

**职责**：
- ✅ Lint + Type + LOC检查（复用pre-commit）
- ✅ 本地代码审查（`vibe review pr` 或简化版）
- ✅ 覆盖率检查（复用 `CoverageService`）
- ✅ 风险评分检查（复用 `inspect pr`）

**执行时间**：30-60秒

**阻断策略**：
- 覆盖率不达标 → 阻断并提示
- 风险评分过高 → 阻断并提示
- Review发现重大问题 → 阻断并提示

**跳过机制**：
- `--skip-coverage` 跳过覆盖率检查
- `--skip-review` 跳过代码审查

---

#### PR Ready 阶段

**目标**：正式质量门禁，确保代码质量

**职责**：
- ✅ 覆盖率检查（强制）
- ✅ 风险评分检查（强制）
- ✅ CI检查（GitHub自动）
- 🟡 Review comments检查（待实现）

**阻断策略**：
- 质量门禁失败 → 阻断
- CI未通过 → 阻断

**跳过机制**：
- `--force` 强制跳过（不推荐）

---

#### PR Merge 阶段

**目标**：最后的安全检查

**职责**：
- ✅ PR状态检查（已ready）
- ✅ CI状态检查（已通过）
- 🟡 Review comments检查（待实现）

**阻断策略**：
- 未ready → 阻断
- CI未通过 → 阻断
- 有未处理review comments → 警告 + 确认

---

## 三、实施计划

### Phase 1: 修复审计问题 (立即，1-2天)

#### 1.1 消除代码重复 (P0)

**任务**：
- 创建 `src/vibe3/utils/trace.py`
- 提取 `enable_trace()` 到共享模块
- 更新 `review_helpers.py` 和 `inspect_helpers.py` 导入

**工作量**：0.5小时

**验证**：
```bash
uv run pytest tests/vibe3/ -v
uv run mypy src/vibe3
```

---

#### 1.2 创建 commit-msg hook (P1)

**任务**：
- 创建 `scripts/hooks/commit-msg` hook
- 检查commit message前缀（Conventional Commits格式）
- 自动附加AST分析到commit message
- 解决手工commit写不清楚的问题

**重要澄清**：
- ✅ **commit-msg hook可以修改commit message**：在commit完成前运行
- ✅ **自动附加AST分析**：补充改动信息到commit message
- ✅ **可以阻断commit**：格式不合规时阻断

**设计方案**：

Commit-msg hook完成两个任务：

1. **Commit格式检查**
   - 检查commit message前缀（feat/fix/refactor等）
   - 符合Conventional Commits规范
   - 格式不合规 → 阻断commit并提示

2. **自动附加AST分析**
   - 在commit message末尾附加改动信息
   - Files changed, Impact modules, Touches paths
   - 不阻断流程，只补充信息

**工作量**：1小时

**验证**：
```bash
# 测试格式检查
git commit -m "invalid commit"
# 应该被阻断，提示正确格式

# 测试AST附加
git commit -m "feat: test commit-msg hook"
# commit message应该包含AST分析
git log -1  # 查看完整commit message
```

---

#### 1.3 简化 post-commit hook (可选，P2)

**任务**：
- 简化或移除 `scripts/hooks/post-commit`
- 因为commit-msg已经完成格式检查和AST附加

**方案：保留轻量通知**
```bash
#!/usr/bin/env bash
# 只输出commit信息
echo "✓ Commit created: $(git rev-parse --short HEAD)"
```

**工作量**：0.5小时

---

#### 1.4 实现 review comments 检查 (P1)

**任务**：
- 在 `pr_lifecycle.py:merge()` 中添加检查
- 调用 GitHub API 获取 pending review comments
- 优雅降级（警告 + 确认）

**实现**：
```python
# src/vibe3/commands/pr_lifecycle.py:merge()

# 1.3 检查 pending review comments
pending = gh.get_pending_review_comments(pr_number)
if pending > 0:
    console.print(f"\n[yellow]⚠️  有 {pending} 条待处理的 review comments[/]")
    if not force and not typer.confirm("是否仍然合并？"):
        raise typer.Exit(1)
```

**工作量**：1小时

---

#### 1.4 统一配置读取 (P1)

**任务**：
- 统一使用 `get_config()`（带缓存）
- 修改 `inspect_helpers.py` 中的 `load_config()` 调用

**工作量**：0.5小时

---

### Phase 2: 添加 Pre-push Hook + 完善 PR Ready (优先级提升，4.5小时)

**重要说明**：云端额度已用完，本地审查更紧迫，优先级提升。

#### 2.1 创建 pre-push hook 脚本 (2小时)

**任务**：
- 创建 `scripts/hooks/pre-push.sh`
- 集成本地审查能力

**流程设计**：
```bash
#!/usr/bin/env bash
# scripts/hooks/pre-push.sh
set -euo pipefail

echo "🔍 Running pre-push checks..."

# 1. 基本检查（快速，<5s）
echo "  → Lint + Type + LOC checks..."
uv run ruff check src
uv run mypy src
bash scripts/hooks/check-python-loc.sh

# 2. 覆盖率检查（强制，~30s）
echo "  → Coverage check..."
uv run pytest tests/vibe3/ --cov=src/vibe3 --cov-report=json -q

python3 << 'EOF'
import json
from pathlib import Path

cov = json.load(open("coverage.json"))
# 调用CoverageService进行分层检查
from vibe3.services.coverage_service import CoverageService
service = CoverageService()
report = service.run_coverage_check()

if not report.all_passing:
    print(f"❌ Coverage check failed")
    for layer in report.get_failing_layers():
        print(f"  {layer.layer_name}: {layer.coverage_percent:.1f}% < {layer.threshold}%")
    exit(1)
print(f"✓ Coverage: {report.overall_percent:.1f}%")
EOF

# 3. 风险评分判断（快速，<2s）
echo "  → Risk assessment..."
RISK_LEVEL=$(uv run python -m vibe3 inspect commit HEAD --json | \
             python3 -c "import json,sys; print(json.load(sys.stdin).get('score',{}).get('level','LOW'))")

if [ "$RISK_LEVEL" = "HIGH" ] || [ "$RISK_LEVEL" = "CRITICAL" ]; then
    echo "  ⚠️  High risk detected, running local review..."
    uv run python -m vibe3 review base main --skip-confirmation
fi

echo "✓ All pre-push checks passed"
```

**决策逻辑**：
- 覆盖率检查：强制，失败则阻断
- 风险评分：
  - LOW/MEDIUM → 跳过review
  - HIGH/CRITICAL → 运行本地review

**工作量**：2小时

---

#### 2.2 集成到 pre-commit (1小时)

**任务**：
- 在 `.pre-commit-config.yaml` 添加 pre-push hook配置
- 更新安装脚本

**实现**：
```yaml
# .pre-commit-config.yaml 新增
- repo: local
  hooks:
    - id: pre-push-checks
      name: Pre-push checks (coverage + risk-based review)
      entry: scripts/hooks/pre-push.sh
      language: script
      pass_filenames: false
      stages: [push]
```

**安装命令**：
```bash
pre-commit install --hook-type pre-push
```

**工作量**：1小时

---

#### 2.3 明确 PR Ready 的检查逻辑 (澄清，无需修改代码)

**重要**：PR Ready必须检查覆盖率，确保最终状态达标。

**理由**：
- Pre-push是中间检查，commit B, C可能降低覆盖率
- PR Ready是最后的门禁，必须确保最终状态

**现有实现**（已正确）：
- ✅ `run_coverage_gate()` - 分层覆盖率检查
- ✅ `run_risk_gate()` - 风险评分检查
- ✅ 支持 `--skip-coverage` 和 `--force`

**保持不变**：PR Ready继续执行覆盖率和风险评分检查。

---

#### 2.4 增强 hooks 命令 (1.5小时)

**任务**：
- 在 `src/vibe3/commands/hooks.py` 添加 `list` 命令
- 支持管理所有hooks（pre-commit, pre-push, post-commit）

**实现**：
```python
@app.command("list")
def list_hooks() -> None:
    """List all Git hooks status.

    Example: vibe hooks list
    """
    hooks_dir = _ROOT / ".git" / "hooks"
    hooks = ["pre-commit", "pre-push", "post-commit"]

    console = Console()
    console.print("\nInstalled Git hooks:\n")

    for hook in hooks:
        hook_path = hooks_dir / hook
        if hook_path.exists():
            console.print(f"  ✓ {hook}")
        else:
            console.print(f"  ✗ {hook} [dim](not installed)[/]")

    # 显示各hook的具体检查项
    console.print("\n[bold]Pre-commit hooks[/] (fast, <5s):")
    checks = [
        "shellcheck (bash/sh)",
        "lint-sh (custom)",
        "ruff (Python linter)",
        "black (Python formatter)",
        "mypy (Python type checker)",
        "check-shell-loc",
        "check-python-loc",
        "check-per-file-loc",
        "check-test-file-loc",
    ]
    for check in checks:
        console.print(f"  • {check}")

    console.print("\n[bold]Pre-push checks[/] (~30-60s):")
    checks = [
        "lint + type + LOC (fast)",
        "coverage check (mandatory)",
        "risk assessment → conditional review",
    ]
    for check in checks:
        console.print(f"  • {check}")

    console.print("\n[bold]Post-commit analysis[/] (<3s, non-blocking):")
    checks = [
        "commit message format check",
        "AST change analysis",
        "risk level + suggestions",
    ]
    for check in checks:
        console.print(f"  • {check}")


@app.command("install")
def install_hook(
    hook_name: Annotated[str, typer.Argument(help="Hook name: pre-commit, pre-push, or post-commit")],
) -> None:
    """Install a specific Git hook.

    Examples:
        vibe hooks install pre-commit
        vibe hooks install pre-push
        vibe hooks install post-commit
    """
    import subprocess

    if hook_name not in ["pre-commit", "pre-push", "post-commit"]:
        raise typer.BadParameter(f"Invalid hook: {hook_name}")

    try:
        if hook_name in ["pre-commit", "pre-push"]:
            subprocess.run(
                ["pre-commit", "install", "--hook-type", hook_name],
                check=True,
            )
        else:  # post-commit
            source = _ROOT / "scripts" / "hooks" / "post-commit"
            target = _ROOT / ".git" / "hooks" / "post-commit"
            shutil.copy2(source, target)
            target.chmod(0o755)

        typer.echo(f"✓ {hook_name} hook installed")
    except Exception as e:
        raise HookManagerError(operation="install", details=str(e)) from e
```

**工作量**：1.5小时

---

### Phase 3: 优化与监控 (1-2周)

#### 3.1 观察指标

**收集数据**：
- Pre-push hook 执行时间
- 覆盖率检查通过率
- 风险评分分布
- 开发者反馈

**决策点**：
- 如果 pre-push 太慢 → 考虑跳过某些检查
- 如果误报率高 → 调整阈值
- 如果云端额度持续不足 → 考虑 self-hosted runner

---

#### 3.2 可选：Self-hosted Runner

**前置条件**：
- 云端额度持续不足（当前已不足）
- 团队规模扩大
- 需要更快的CI反馈

**决策**：
- 如果决定实施，参考 `docs/v3/design/local-hosted-runner.md`
- 初期只用于运行本地review，不部署完整审查系统

---

#### 3.3 可选：分级审查系统

**前置条件**：
- PR ready后仍有大量质量问题
- 需要更细粒度的审查策略
- 有足够资源维护AST分析

**决策**：
- 如果决定实施，参考 `docs/v3/design/dazzling-wandering-oasis.md`
- 先实施L0-L2分级，观察效果
- 暂缓L3和完整决策引擎

---

## 四、验收标准

### Phase 1 完成标准

- [ ] `enable_trace()` 重复代码消除
- [ ] Commit-msg hook创建（格式检查 + AST附加）
- [ ] Post-commit hook简化或移除
- [ ] Merge review comments检查实现
- [ ] 配置读取统一
- [ ] 所有测试通过
- [ ] 类型检查通过

### Phase 2 完成标准

- [ ] Pre-push hook脚本创建
- [ ] 覆盖率检查集成（强制）
- [ ] 风险评分决策逻辑（条件review）
- [ ] 文档更新（README + CLAUDE.md）

### 关键澄清

#### ⚠️ Post-commit检查的是什么？

**Commit message格式**（不依赖PR）：

检查commit是否符合Conventional Commits规范：
```
<type>(<scope>)?: <description>

类型：feat|fix|refactor|docs|test|chore|perf|ci|build|revert
作用域：可选，如 (core), (api)
示例：feat(core): add coverage service
```

**不检查PR标签**：
- PR标签（如 `type/feat`）是GitHub层面的
- Commit时可能还没有PR
- Post-commit只检查commit本身的格式

#### ⚠️ PR Ready必须检查覆盖率

**反驳"Push检查过就不需要再检查"**：

1. **Push后可能新增commit**：
   ```
   Pre-push检查 (commit A) → 覆盖率85% ✅
   Push到远程
   继续开发 (commit B, C) → 覆盖率降到70% ❌
   PR Ready → 必须检查最终状态
   ```

2. **类比**：
   > Pre-push检查 = 出门时检查护照
   > PR Ready检查 = 登机前检查护照
   > 不能因为"出门时检查过"就不再登机检查

3. **实施**：
   - Pre-push：覆盖率检查（拦截明显问题）
   - PR Ready：覆盖率检查（确保最终状态达标）

### 系统级验收

**行为层**：
- ✅ Trivial改动不会触发无意义检查
- ✅ 覆盖率不足在push阶段被拦截
- ✅ 高风险改动在push阶段触发review
- ✅ PR ready阶段质量门禁完善（覆盖率 + 风险评分 + 本地review）
- ✅ Merge阶段有最后的安全检查
- ✅ Post-commit提供辅助信息，不阻断流程

**架构层**：
- ✅ 质量门禁逻辑集中（服务质量）
- ✅ Hooks职责清晰（pre-commit快速，pre-push深度，post-commit辅助）
- ✅ 服务复用良好（CoverageService, inspect）

**资源层**：
- ✅ Pre-commit快速（< 5秒）
- ✅ Pre-push合理（30-60秒）
- ✅ 本地优先，云端补充

---

## 五、风险与缓解

### 5.1 技术风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| Pre-push太慢影响开发体验 | 中 | 高 | 提供跳过机制，优化检查速度 |
| 覆盖率阈值不合理 | 中 | 中 | 允许配置覆盖，提供数据支撑调整 |
| 本地review质量不稳定 | 低 | 低 | 作为辅助检查，不强制阻断 |

### 5.2 维护风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| Hooks配置复杂 | 低 | 中 | 提供清晰的 shell 脚本文档 |
| 服务依赖过多 | 低 | 中 | 保持服务独立，最小依赖 |

---

## 六、时间估算

| Phase | 任务 | 工作量 | 优先级 |
|-------|------|--------|--------|
| Phase 1.1 | 消除重复代码 | 0.5h | P0 |
| Phase 1.2 | 创建commit-msg hook（格式检查+AST附加） | 1h | P1 |
| Phase 1.3 | 简化post-commit hook | 0.5h | P2 |
| Phase 1.4 | Review comments检查 | 1h | P1 |
| Phase 1.5 | 统一配置读取 | 0.5h | P1 |
| Phase 2.1 | Pre-push hook脚本（覆盖率+风险决策） | 2h | P1 (提升) |
| Phase 2.2 | 集成pre-commit | 1h | P1 (提升) |
| Phase 2.3 | 明确PR Ready检查逻辑 | 0h (澄清) | P1 |
| Phase 2.4 | 增强hooks命令（list + install） | 1.5h | P1 (提升) |
| **总计** | **Phase 1-2** | **8h** | - |

**注意**：
- Phase 2.3无需修改代码，只是澄清逻辑（PR Ready已有正确的实现）
- 大部分工作是集成已有能力，不是重新开发

---

## 七、下一步行动

### 立即行动 (Phase 1)

1. ✅ 消除 `enable_trace()` 重复代码 (0.5h)
2. ✅ 创建 commit-msg hook：
   - Commit message格式检查（Conventional Commits）
   - 自动附加AST分析到commit message (1h)
3. ✅ 简化或移除 post-commit hook (0.5h)
4. ✅ 实现 merge review comments 检查 (1h)
5. ✅ 统一配置读取 (0.5h)

### 优先行动 (Phase 2)

1. 🎯 创建 pre-push hook 脚本：
   - 覆盖率检查（强制）
   - 风险评分决策（条件review）(2h)
2. 🎯 集成到 pre-commit 配置 (1h)
3. 🎯 保持 hook 脚本与 CI 共享同一实现
4. 🎯 更新文档

### 澄清说明

**PR Ready覆盖率检查**：
- ✅ 必须检查（确保最终状态）
- ✅ 理由：Push后可能新增commit，覆盖率可能降低
- ✅ 当前实现已正确，无需修改

**Post-commit职责**：
- ✅ 检查commit message格式（不依赖PR）
- ✅ 提供AST分析（辅助信息）
- ✅ 不阻断流程

### 后续评估 (Phase 3)

1. ⏸️ 观察pre-push效果
2. ⏸️ 评估是否需要self-hosted runner
3. ⏸️ 评估是否需要分级审查系统

---

## 八、参考文档

- **审计报告**：`docs/audit/code-architecture-audit-report.md`
- **PR Ready设计**：`docs/v3/design/inspect-pr-integration.md`
- **Self-hosted Runner**：`docs/v3/design/local-hosted-runner.md`
- **审查系统设计**：`docs/v3/design/dazzling-wandering-oasis.md`
- **项目规则**：`CLAUDE.md`, `SOUL.md`

---

**文档版本**：3.0
**创建日期**：2026-03-19
**最后更新**：2026-03-19
**更新说明**：
- v3.0: **关键修正**：使用commit-msg hook而非post-commit，可以修改commit message并附加AST分析
- v2.0: 明确post-commit检查commit格式（不依赖PR），澄清PR Ready必须检查覆盖率
- v1.0: 初始版本
