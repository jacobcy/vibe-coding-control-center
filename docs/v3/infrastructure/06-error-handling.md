---
document_type: implementation-guide
title: Vibe 3.0 - Error Handling
status: active
author: Claude Sonnet 4.6
created: 2026-03-15
last_updated: 2026-03-19
related_docs:
  - docs/standards/error-handling.md  # 错误处理规范（权威）
  - docs/standards/error-handling-fix-summary.md  # 修复总结
  - docs/standards/v3/handoff-store-standard.md
  - docs/standards/v3/github-remote-call-standard.md
  - docs/v3/infrastructure/02-architecture.md
  - docs/v3/infrastructure/03-coding-standards.md
---

# Vibe 3.0 - 异常处理实现指南

> **权威规范**：[docs/standards/error-handling.md](../../standards/error-handling.md)
> **本文档定位**：实现指南，提供代码示例和架构说明

---

## 核心原则

**简单但统一**：
- ✅ 统一的异常基类
- ✅ 区分 **SystemError**、**UserError**、**BatchError** 三类错误
- ✅ CLI 层统一捕获和展示
- ✅ **统一使用 `--yes` 参数绕过业务逻辑错误**

**详细规范请参考**：[错误处理规范](../../standards/error-handling.md)

---

## 异常层级实现

详见：[src/vibe3/exceptions/__init__.py](../../../src/vibe3/exceptions/__init__.py)

```python
# exceptions/__init__.py (简化版)

class VibeError(Exception):
    """所有 Vibe 异常的基类"""
    def __init__(self, message: str, recoverable: bool = False):
        self.message = message
        self.recoverable = recoverable
        super().__init__(message)

# 用户错误（可恢复，提供 --yes 绕过）
class UserError(VibeError):
    def __init__(self, message: str):
        super().__init__(message, recoverable=True)

# 系统错误（不可恢复，立即抛出）
class SystemError(VibeError):
    def __init__(self, message: str):
        super().__init__(message, recoverable=False)

# 批量错误（继续执行，最后报告）
class BatchError(SystemError):
    def __init__(self, message: str, errors: list[dict]):
        super().__init__(f"{message} ({len(errors)} failures)")
        self.errors = errors
```

---

## 各层异常处理策略

### Layer 1: CLI 层（统一捕获）

CLI 层负责捕获所有异常，根据类型显示不同格式的错误信息。

```python
# cli.py
import sys
from typer import Exit
from rich.console import Console
from vibe3.exceptions import UserError, SystemError, BatchError

def main():
    """CLI 入口，统一异常处理"""
    try:
        app()
    except UserError as e:
        # 用户错误：简洁提示 + 提示使用 --yes 绕过
        console = Console()
        console.print(f"\n[yellow]⚠️  {e.message}[/]")
        console.print("[dim]Use --yes to bypass this check[/]")
        sys.exit(1)

    except BatchError as e:
        # 批量错误：显示汇总
        console = Console()
        console.print(f"\n[red]❌ Batch operation failed: {len(e.errors)} errors[/]")
        for error in e.errors[:5]:
            console.print(f"  [red]✗ {error.get('file', 'unknown')}: {error['error']}[/]")
        sys.exit(1)

    except SystemError as e:
        # 系统错误：显示详情
        console = Console()
        console.print(f"\n[red]❌ System error: {e.message}[/]")
        console.print("[dim]This is a bug. Please report to developers.[/]")
        sys.exit(99)

    except Exception as e:
        # 未知错误：打印完整栈
        logger.exception("Unexpected error")
        sys.exit(99)
```

### Layer 2: Command 层（业务错误处理）

Command 层处理业务错误，提供 `--yes` 绕过选项。

```python
# commands/pr_lifecycle.py
import typer

@app.command()
def ready(
    pr_number: int,
    yes: bool = typer.Option(False, "--yes", help="绕过业务逻辑检查并自动确认"),
):
    """Mark PR as ready with quality gates."""
    # 业务错误：使用 --yes 绕过
    run_coverage_gate(yes=yes)

    # 系统错误：自然抛出
    service = PRService()
    service.mark_ready(pr_number)

def run_coverage_gate(yes: bool = False) -> None:
    """运行覆盖率检查（业务错误）"""
    if yes:
        console.print("[yellow]⚠️  Skipping coverage gate (--yes)[/]")
        return

    coverage_service = CoverageService()
    # 系统错误：如果服务调用失败，会自然抛出 SystemError
    coverage = coverage_service.run_coverage_check()

    # 业务错误：覆盖率不足，可通过 --yes 绕过
    if not coverage.all_passing:
        console.print("[red]✗ Coverage gate failed[/]")
        console.print("[dim]Increase coverage or use --yes to bypass[/]")
        raise Exit(1)
```

### Layer 3: Service 层（系统错误处理）

Service 层处理系统错误，立即抛出，不捕获。

```python
# services/serena_service.py
from exceptions import SerenaError

class SerenaService:
    def analyze_file(self, file: str) -> dict:
        """分析单个文件（系统错误）"""
        # 系统错误：立即抛出，不捕获，不降级
        overview = self.client.get_symbols_overview(file)
        return {"symbols": overview}

    def analyze_files(self, files: list[str]) -> list:
        """批量分析文件（批量错误）"""
        results = []
        errors = []

        for file in files:
            try:
                result = self.analyze_file(file)
                results.append(result)
            except SerenaError as e:
                errors.append({"file": file, "error": str(e)})
                # 继续处理其他文件

        if errors:
            # 批量错误：收集后统一报告
            raise BatchError("Batch analysis failed", errors)

        return results
```

### Layer 4: Client 层（抛出具体异常）

Client 层负责与外部系统交互，抛出具体的异常类型。

```python
# clients/github_client.py
from exceptions import GitError, GitHubError

class GitHubClient:
    def get_pr(self, pr_number: int) -> PR:
        """获取 PR（调用 gh CLI）"""
        result = subprocess.run(
            ["gh", "pr", "view", str(pr_number), "--json"],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            if "404" in result.stderr:
                raise GitHubError(404, f"PR #{pr_number} not found")
            raise GitError("view PR", result.stderr)

        return PR.parse_raw(result.stdout)
```

---

## 测试示例

```python
# tests/test_exceptions.py
import pytest
from vibe3.exceptions import UserError, SystemError, BatchError

def test_user_error_recoverable():
    """测试用户错误可恢复"""
    error = UserError("test")
    assert error.recoverable is True

def test_system_error_not_recoverable():
    """测试系统错误不可恢复"""
    error = SystemError("test")
    assert error.recoverable is False

def test_batch_error_collects_errors():
    """测试批量错误收集"""
    errors = [{"file": "a.py", "error": "syntax error"}]
    error = BatchError("Failed", errors)
    assert len(error.errors) == 1
    assert "1 failures" in error.message
```

---

## 核心要点

✅ **必须实现**：
- 统一的异常基类 `VibeError`
- CLI 层统一异常处理
- 区分 `SystemError`、`UserError`、`BatchError` 三类错误
- **统一使用 `--yes` 参数绕过业务逻辑错误**

📚 **详细规范**：[错误处理规范](../../standards/error-handling.md)

🎯 **相关文档**：
- [错误处理修复总结](../../standards/error-handling-fix-summary.md)
- [CLAUDE.md - HARD RULES 第11条](../../../CLAUDE.md)