---
document_type: implementation_plan
title: Phase 04 - Handoff And Cutover Implementation Plan
status: draft
author: Claude Sonnet 4.6
created: 2026-03-21
last_updated: 2026-03-21
related_docs:
  - docs/v3/handoff/04-handoff-and-cutover.md
  - docs/standards/v3/handoff-store-standard.md
  - docs/standards/v3/handoff-governance-standard.md
---

# Phase 04: Handoff And Cutover 实施计划

> **设计文档**: [04-handoff-and-cutover.md](04-handoff-and-cutover.md) - 本文档的实施依据
> **目标**: 将设计规范转化为可执行的代码实现

---

## 实施概览

### 当前状态

**已完成**：
- ✅ 语义一致性修正
  - `flow_status` 已统一为 `active / blocked / done / stale`
  - `issue_role` 已统一为 `task / repo`
  - `flow_events.event_type` 标准已扩展
- ✅ Truth Model 设计规范已定义
- ✅ 数据职责边界已明确

**待实施**：
- ❌ Handoff Command 实现
- ❌ 验证与测试
- ❌ 文档完善

---

## 任务分解

### Task 1: 实现 Handoff Command（优先级 P0）

**目标**: 实现 `vibe handoff` 命令族，覆盖 SQLite 最小索引更新和共享 `current.md` 的轻量交接能力

**设计依据**: [04-handoff-and-cutover.md §6](04-handoff-and-cutover.md#6-handoff-command-contract)、[04-handoff-and-cutover.md §7](04-handoff-and-cutover.md#7-shared-currentmd-role)

#### 1.1 创建 Handoff Command 骨架

**文件**: `src/vibe3/commands/handoff.py`

**实现内容**:
```python
"""Handoff command implementation."""

import typer
from typing import Optional
from vibe3.services.handoff_service import HandoffService
from vibe3.ui.display import console

app = typer.Typer(help="Handoff management commands")


@app.command("init")
def handoff_init() -> None:
    """Ensure shared current.md exists for current branch."""
    service = HandoffService()
    path = service.ensure_current_handoff()
    console.print(f"[green]✓[/green] Handoff file ready: {path}")


@app.command("show")
def handoff_show() -> None:
    """Show shared current.md for current branch."""
    service = HandoffService()
    console.print(service.read_current_handoff())


@app.command("append")
def handoff_append(
    message: str = typer.Argument(..., help="Lightweight handoff update"),
    actor: str = typer.Option("unknown", help="Actor identifier"),
    kind: str = typer.Option("note", help="Update kind"),
) -> None:
    """Append a lightweight update block to shared current.md."""
    service = HandoffService()
    path = service.append_current_handoff(message, actor, kind)
    console.print(f"[green]✓[/green] Appended handoff update: {path}")


@app.command("plan")
def handoff_plan(
    plan_ref: str = typer.Argument(..., help="Plan document reference"),
    next_step: Optional[str] = typer.Option(None, help="Next step suggestion"),
    blocked_by: Optional[str] = typer.Option(None, help="Blocker description"),
    actor: str = typer.Option("unknown", help="Actor identifier"),
) -> None:
    """Record plan handoff."""
    service = HandoffService()
    service.record_plan(plan_ref, next_step, blocked_by, actor)
    console.print(f"[green]✓[/green] Plan handoff recorded: {plan_ref}")


@app.command("report")
def handoff_report(
    report_ref: str = typer.Argument(..., help="Report document reference"),
    next_step: Optional[str] = typer.Option(None, help="Next step suggestion"),
    blocked_by: Optional[str] = typer.Option(None, help="Blocker description"),
    actor: str = typer.Option("unknown", help="Actor identifier"),
) -> None:
    """Record report handoff."""
    service = HandoffService()
    service.record_report(report_ref, next_step, blocked_by, actor)
    console.print(f"[green]✓[/green] Report handoff recorded: {report_ref}")


@app.command("audit")
def handoff_audit(
    audit_ref: str = typer.Argument(..., help="Audit document reference"),
    next_step: Optional[str] = typer.Option(None, help="Next step suggestion"),
    blocked_by: Optional[str] = typer.Option(None, help="Blocker description"),
    actor: str = typer.Option("unknown", help="Actor identifier"),
) -> None:
    """Record audit handoff."""
    service = HandoffService()
    service.record_audit(audit_ref, next_step, blocked_by, actor)
    console.print(f"[green]✓[/green] Audit handoff recorded: {audit_ref}")
```

**验收标准**:
- [ ] `vibe handoff init --help` 输出正确
- [ ] `vibe handoff show --help` 输出正确
- [ ] `vibe handoff append --help` 输出正确
- [ ] `vibe handoff plan --help` 输出正确
- [ ] `vibe handoff report --help` 输出正确
- [ ] `vibe handoff audit --help` 输出正确

#### 1.2 实现 HandoffService

**文件**: `src/vibe3/services/handoff_service.py`

**设计依据**: [04-handoff-and-cutover.md §6.1](04-handoff-and-cutover.md#61-命令职责)

**实现内容**:
```python
"""Handoff service implementation."""

from loguru import logger
from pathlib import Path
from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient


class HandoffService:
    """Service for managing handoff records."""

    def __init__(
        self,
        store: SQLiteClient | None = None,
        git_client: GitClient | None = None,
    ) -> None:
        """Initialize handoff service."""
        self.store = store or SQLiteClient()
        self.git_client = git_client or GitClient()

    def ensure_current_handoff(self) -> Path:
        """Ensure `.git/vibe3/handoff/<branch-safe>/current.md` exists."""
        ...

    def read_current_handoff(self) -> str:
        """Read shared current.md content for current branch."""
        ...

    def append_current_handoff(self, message: str, actor: str, kind: str = "note") -> Path:
        """Append a lightweight update block to shared current.md."""
        ...

    def record_plan(
        self,
        plan_ref: str,
        next_step: str | None,
        blocked_by: str | None,
        actor: str,
    ) -> None:
        """Record plan handoff.

        Args:
            plan_ref: Plan document reference
            next_step: Next step suggestion
            blocked_by: Blocker description
            actor: Actor identifier
        """
        logger.bind(
            domain="handoff",
            action="record_plan",
            plan_ref=plan_ref,
            actor=actor,
        ).info("Recording plan handoff")

        branch = self.git_client.get_current_branch()

        # Update flow state only with refs and minimal scene hints
        self.store.update_flow_state(
            branch,
            plan_ref=plan_ref,
            planner_actor=actor,
            latest_actor=actor,
            next_step=next_step,
            blocked_by=blocked_by,
        )

        # Add event
        self.store.add_event(
            branch,
            "handoff_plan",
            actor,
            f"Plan recorded: {plan_ref}",
        )

        logger.success("Plan handoff recorded")

    def record_report(
        self,
        report_ref: str,
        next_step: str | None,
        blocked_by: str | None,
        actor: str,
    ) -> None:
        """Record report handoff.

        Args:
            report_ref: Report document reference
            next_step: Next step suggestion
            blocked_by: Blocker description
            actor: Actor identifier
        """
        logger.bind(
            domain="handoff",
            action="record_report",
            report_ref=report_ref,
            actor=actor,
        ).info("Recording report handoff")

        branch = self.git_client.get_current_branch()

        # Update flow state
        self.store.update_flow_state(
            branch,
            report_ref=report_ref,
            reviewer_actor=actor,
            latest_actor=actor,
            next_step=next_step,
            blocked_by=blocked_by,
        )

        # Add event
        self.store.add_event(
            branch,
            "handoff_report",
            actor,
            f"Report recorded: {report_ref}",
        )

        logger.success("Report handoff recorded")

    def record_audit(
        self,
        audit_ref: str,
        next_step: str | None,
        blocked_by: str | None,
        actor: str,
    ) -> None:
        """Record audit handoff.

        Args:
            audit_ref: Audit document reference
            next_step: Next step suggestion
            blocked_by: Blocker description
            actor: Actor identifier
        """
        logger.bind(
            domain="handoff",
            action="record_audit",
            audit_ref=audit_ref,
            actor=actor,
        ).info("Recording audit handoff")

        branch = self.git_client.get_current_branch()

        # Update flow state
        self.store.update_flow_state(
            branch,
            audit_ref=audit_ref,
            reviewer_actor=actor,
            latest_actor=actor,
            next_step=next_step,
            blocked_by=blocked_by,
        )

        # Add event
        self.store.add_event(
            branch,
            "handoff_audit",
            actor,
            f"Audit recorded: {audit_ref}",
        )

        logger.success("Audit handoff recorded")
```

**验收标准**:
- [ ] `current.md` 路径固定为 `.git/vibe3/handoff/<branch-safe>/current.md`
- [ ] `current.md` 缺失时能自动初始化模板
- [ ] 不引入 JSON / YAML 主文件
- [ ] 单元测试覆盖所有方法
- [ ] 错误处理完善（分支不存在、数据库错误等）
- [ ] 日志记录符合规范

#### 1.3 注册 Handoff Command 到 CLI

**文件**: `src/vibe3/cli.py`

**修改内容**:
```python
# 在现有 import 后添加
from vibe3.commands import handoff

# 在现有 app.add_typer() 后添加
app.add_typer(handoff.app, name="handoff")
```

**验收标准**:
- [ ] `vibe handoff --help` 输出正确
- [ ] 子命令可以正常调用

---

### Task 2: 实现验证命令（优先级 P1）

**目标**: 实现 `vibe check` 命令，验证 handoff store 与共享 `current.md` 的边界一致性

#### 2.1 创建 Check Command

**文件**: `src/vibe3/commands/check.py`

**实现内容**:
```python
"""Check command implementation."""

import typer
from vibe3.services.check_service import CheckService
from vibe3.ui.display import console

app = typer.Typer(help="Verification commands")


@app.command("check")
def check_flow(
    fix: bool = typer.Option(False, "--fix", help="Auto-fix issues"),
) -> None:
    """Verify handoff store consistency.

    Checks:
    - Current branch exists in flow_state
    - task_issue_number exists on GitHub
    - Only one task issue per branch
    - pr_number matches current branch
    - plan_ref / report_ref / audit_ref files exist
    - shared current.md exists for active flow
    - current.md 不被误用为主链事实副本
    """
    service = CheckService()
    result = service.verify_current_flow(fix=fix)

    if result.is_valid:
        console.print("[green]✓[/green] All checks passed")
    else:
        console.print("[red]✗[/red] Issues found:")
        for issue in result.issues:
            console.print(f"  - {issue}")

        if fix:
            console.print("\n[yellow]Attempting auto-fix...[/yellow]")
            fix_result = service.auto_fix(result.issues)
            if fix_result.success:
                console.print("[green]✓[/green] Issues fixed")
            else:
                console.print(f"[red]✗[/red] Fix failed: {fix_result.error}")
```

**验收标准**:
- [ ] `vibe check --help` 输出正确
- [ ] 检查逻辑完整
- [ ] 自动修复功能可用

#### 2.2 实现 CheckService

**文件**: `src/vibe3/services/check_service.py`

**实现内容**:
```python
"""Check service implementation."""

from dataclasses import dataclass
from loguru import logger
from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient


@dataclass
class CheckResult:
    """Result of consistency check."""

    is_valid: bool
    issues: list[str]


@dataclass
class FixResult:
    """Result of auto-fix."""

    success: bool
    error: str | None = None


class CheckService:
    """Service for verifying handoff store consistency."""

    def __init__(
        self,
        store: SQLiteClient | None = None,
        git_client: GitClient | None = None,
        github_client: GitHubClient | None = None,
    ) -> None:
        """Initialize check service."""
        self.store = store or SQLiteClient()
        self.git_client = git_client or GitClient()
        self.github_client = github_client or GitHubClient()

    def verify_current_flow(self, fix: bool = False) -> CheckResult:
        """Verify current flow consistency.

        Args:
            fix: Whether to auto-fix issues

        Returns:
            Check result with issues list
        """
        logger.bind(domain="check", action="verify").info("Verifying flow consistency")

        branch = self.git_client.get_current_branch()
        issues: list[str] = []

        # Check 1: Flow exists
        flow_data = self.store.get_flow_state(branch)
        if not flow_data:
            issues.append(f"No flow record for branch '{branch}'")
            return CheckResult(is_valid=False, issues=issues)

        # Check 2: Task issue exists on GitHub
        task_issue = flow_data.get("task_issue_number")
        if task_issue:
            issue = self.github_client.get_issue(task_issue)
            if not issue:
                issues.append(f"Task issue #{task_issue} not found on GitHub")

        # Check 3: Only one task issue per branch
        issue_links = self.store.get_issue_links(branch)
        task_issues = [link for link in issue_links if link["issue_role"] == "task"]
        if len(task_issues) > 1:
            issues.append(f"Multiple task issues for branch '{branch}'")

        # Check 4: PR matches branch
        pr_number = flow_data.get("pr_number")
        if pr_number:
            pr = self.github_client.get_pr(pr_number)
            if pr and pr.head_branch != branch:
                issues.append(f"PR #{pr_number} does not match branch '{branch}'")

        # Check 5: Ref files exist
        for ref_field in ["plan_ref", "report_ref", "audit_ref"]:
            ref_value = flow_data.get(ref_field)
            if ref_value:
                # TODO: Implement file existence check
                pass

        # Check 6: Shared current.md exists
        # TODO: verify .git/vibe3/handoff/<branch-safe>/current.md presence

        is_valid = len(issues) == 0
        logger.bind(is_valid=is_valid, issues_count=len(issues)).info("Check completed")

        return CheckResult(is_valid=is_valid, issues=issues)

    def auto_fix(self, issues: list[str]) -> FixResult:
        """Auto-fix identified issues.

        Args:
            issues: List of issues to fix

        Returns:
            Fix result
        """
        logger.bind(domain="check", action="auto_fix").info("Auto-fixing issues")

        # TODO: Implement auto-fix logic
        return FixResult(success=False, error="Auto-fix not implemented yet")
```

**验收标准**:
- [ ] 所有检查逻辑实现完整
- [ ] 日志记录符合规范
- [ ] 错误处理完善

---

### Task 3: 测试覆盖（优先级 P0）

**目标**: 确保测试覆盖率 >= 80%

#### 3.1 HandoffService 单元测试

**文件**: `tests/vibe3/services/test_handoff_service.py`

**测试内容**:
- [ ] `test_record_plan_success` - 成功记录 plan
- [ ] `test_record_report_success` - 成功记录 report
- [ ] `test_record_audit_success` - 成功记录 audit
- [ ] `test_record_with_next_step` - 带下一步提示
- [ ] `test_record_with_blocked_by` - 带阻塞信息
- [ ] `test_record_without_flow` - flow 不存在时的错误处理
- [ ] `test_event_recorded` - 事件正确记录
- [ ] `test_ensure_current_handoff_creates_template` - 自动创建共享 handoff 模板
- [ ] `test_read_current_handoff` - 正确读取共享 handoff 内容

#### 3.2 CheckService 单元测试

**文件**: `tests/vibe3/services/test_check_service.py`

**测试内容**:
- [ ] `test_verify_flow_valid` - 有效 flow 通过检查
- [ ] `test_verify_flow_missing` - flow 不存在
- [ ] `test_verify_task_issue_missing` - task issue 不存在
- [ ] `test_verify_multiple_task_issues` - 多个 task issue
- [ ] `test_verify_pr_mismatch` - PR 不匹配
- [ ] `test_verify_current_handoff_exists` - 共享 handoff 文件存在
- [ ] `test_auto_fix_not_implemented` - 自动修复未实现

#### 3.3 Command 集成测试

**文件**: `tests/vibe3/commands/test_handoff_command.py`

**测试内容**:
- [ ] `test_handoff_plan_command` - CLI 调用成功
- [ ] `test_handoff_report_command` - CLI 调用成功
- [ ] `test_handoff_audit_command` - CLI 调用成功
- [ ] `test_handoff_init_command` - 共享 handoff 模板创建成功
- [ ] `test_handoff_show_command` - 共享 handoff 内容显示成功
- [ ] `test_handoff_with_options` - 带可选参数

**验收标准**:
- [ ] `uv run pytest tests/vibe3/services/test_handoff_service.py -v` 全部通过
- [ ] `uv run pytest tests/vibe3/services/test_check_service.py -v` 全部通过
- [ ] `uv run pytest tests/vibe3/commands/test_handoff_command.py -v` 全部通过
- [ ] 测试覆盖率 >= 80%

---

### Task 4: 文档完善（优先级 P2）

#### 4.1 更新命令快速参考

**文件**: `docs/v3/infrastructure/08-command-quick-ref.md`

**新增内容**:
```markdown
## Handoff Commands

### `vibe handoff plan <plan_ref>`
Record plan handoff.

**Options**:
- `--next-step <text>` - Next step suggestion
- `--blocked-by <text>` - Blocker description
- `--actor <actor>` - Actor identifier (default: unknown)

**Example**:
```bash
vibe handoff plan docs/plans/feature-x.md --next-step "Start implementation" --actor "codex/gpt-5.4"
```

### `vibe handoff init`
Ensure shared handoff file exists for current branch.

**Behavior**:
- create `.git/vibe3/handoff/<branch-safe>/current.md` if missing
- scaffold fixed Markdown template

### `vibe handoff show`
Show shared handoff file for current branch.

### `vibe handoff append <message>`
Append a lightweight update block to shared handoff file for current branch.

### `vibe handoff report <report_ref>`
Record report handoff.

**Options**:
- `--next-step <text>` - Next step suggestion
- `--blocked-by <text>` - Blocker description
- `--actor <actor>` - Actor identifier (default: unknown)

**Example**:
```bash
vibe handoff report docs/reports/review-2026-03-21.md --next-step "Address feedback" --actor "claude/sonnet-4.6"
```

### `vibe handoff audit <audit_ref>`
Record audit handoff.

**Options**:
- `--next-step <text>` - Next step suggestion
- `--blocked-by <text>` - Blocker description
- `--actor <actor>` - Actor identifier (default: unknown)

**Example**:
```bash
vibe handoff audit docs/audits/security-check.md --actor "reviewer/sonnet-4.6"
```

## Verification Commands

### `vibe check`
Verify handoff store consistency.

**Options**:
- `--fix` - Auto-fix issues

**Checks**:
- Current branch exists in flow_state
- task_issue_number exists on GitHub
- Only one task issue per branch
- pr_number matches current branch
- plan_ref / report_ref / audit_ref files exist

**Example**:
```bash
vibe check
vibe check --fix
```
```

#### 4.2 更新 handoff/README.md

**文件**: `docs/v3/handoff/README.md`

**修改**: 在 Phase 04 部分添加实际实现状态

---

## 实施顺序

### 阶段 1: 核心实现（1-2 天）

1. **Task 1.1**: 创建 Handoff Command 骨架（3-4 小时）
2. **Task 1.2**: 实现 HandoffService 与共享 `current.md` 路径工具（4-6 小时）
3. **Task 1.3**: 注册 Handoff Command 到 CLI（1 小时）

### 阶段 2: 验证功能（1 天）

4. **Task 2.1**: 创建 Check Command（2-3 小时）
5. **Task 2.2**: 实现 CheckService（3-4 小时）

### 阶段 3: 测试与文档（1 天）

6. **Task 3**: 测试覆盖（4-6 小时）
7. **Task 4**: 文档完善（2-3 小时）

---

## 验收清单

### 功能验收

- [ ] `vibe handoff init` 成功创建共享 `current.md`
- [ ] `vibe handoff show` 成功显示共享 `current.md`
- [ ] `vibe handoff plan <ref>` 成功记录 plan
- [ ] `vibe handoff report <ref>` 成功记录 report
- [ ] `vibe handoff audit <ref>` 成功记录 audit
- [ ] `vibe check` 正确检测一致性问题
- [ ] `vibe check --fix` 尝试自动修复
- [ ] 所有命令包含 `--actor` 参数
- [ ] 所有命令支持 `--next-step` 和 `--blocked-by`
- [ ] handoff 中间态固定写入 `.git/vibe3/handoff/<branch-safe>/current.md`

### 测试验收

- [ ] 单元测试覆盖率 >= 80%
- [ ] 所有测试用例通过
- [ ] 集成测试验证 CLI 调用

### 文档验收

- [ ] 命令快速参考更新完整
- [ ] 使用示例正确
- [ ] handoff/README.md 反映实际状态

### 代码质量

- [ ] `uv run mypy src/vibe3` 无错误
- [ ] `uv run ruff check src/vibe3` 无错误
- [ ] 日志记录符合规范
- [ ] 错误处理完善

---

## 风险与缓解

### 风险 1: 共享 `current.md` 被误当成真源

**风险等级**: 高

**缓解措施**:
- 在设计文档和标准文档中明确其为中间态
- `plan / report / audit` 仍只更新 SQLite ref 和最小索引字段
- `vibe check` 增加边界检查，避免把主链事实复制进 `current.md`

### 风险 2: HandoffService 与现有服务冲突

**风险等级**: 低

**缓解措施**:
- HandoffService 只负责 handoff 相关操作
- 与 FlowService / PRService 保持清晰的职责边界
- 通过单元测试验证独立性

### 风险 3: Check 功能误报

**风险等级**: 中

**缓解措施**:
- 提供详细的错误信息
- 支持 `--fix` 参数自动修复
- 在自动修复不可用时给出明确提示

### 风险 4: 测试覆盖不足

**风险等级**: 低

**缓解措施**:
- 优先编写单元测试
- 使用 mock 隔离外部依赖
- 集成测试覆盖主要使用场景

---

## 后续工作

完成本实施计划后，后续工作包括：

1. **Phase 05**: Verification & Cleanup
   - 性能优化（`time bin/vibe3 flow status` < 1.0s）
   - 清理所有 TODO 和 print()
   - 最终验收测试

2. **增强功能**（可选）:
   - `vibe handoff history` - 显示 handoff 历史
   - `vibe check` 的自动修复功能完善

---

## 参考资料

### 设计文档
- **[04-handoff-and-cutover.md](04-handoff-and-cutover.md)** - Truth Model 和设计约束
- **[handoff-store-standard.md](../../standards/v3/handoff-store-standard.md)** - 数据库标准

### 相关代码
- `src/vibe3/services/flow_service.py` - Flow 管理服务
- `src/vibe3/services/pr_service.py` - PR 管理服务
- `src/vibe3/clients/sqlite_client.py` - SQLite 客户端

### 测试示例
- `tests/vibe3/services/test_flow_service.py` - FlowService 测试
- `tests/vibe3/services/test_pr_service.py` - PRService 测试

---

**维护者**: Vibe Team
**最后更新**: 2026-03-21
**预估时间**: 3-4 天
