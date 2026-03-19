# Vibe Center 错误处理规范

> **文档定位**：定义系统错误处理策略，区分代码错误和业务错误
> **适用范围**：所有 Python 代码（v3）和 Agent 决策逻辑

---

## 一、错误分类体系

### Tier 1: SystemError（系统错误）🔴

**定义**：系统基础设施故障，影响功能正确性

**特征**：
- 代码依赖缺失或损坏（如 Serena 不可用）
- 外部服务故障（如 GitHub API 失败）
- 配置文件损坏或格式错误
- 类型错误、空指针等编程错误

**处理原则**：
- ✅ **立即抛出异常**
- ✅ **Fail-fast，不捕获，不降级**
- ✅ **记录完整错误栈到日志**
- ✅ **向用户显示清晰错误信息**

**示例**：
```python
# ✅ 正确：系统错误立即抛出
def analyze_file(self, file: str) -> dict:
    overview = self.client.get_symbols_overview(file)  # SerenaError 向上传播
    return {"symbols": overview}

# ❌ 错误：捕获后返回错误字典
def analyze_file(self, file: str) -> dict:
    try:
        overview = self.client.get_symbols_overview(file)
        return {"status": "ok", "symbols": overview}
    except SerenaError as e:
        return {"status": "error", "error": str(e)}  # 静默失败！
```

---

### Tier 2: UserError（业务错误）🟡

**定义**：用户操作不符合规范，但系统仍可正常运行

**特征**：
- 输入不符合格式要求（如 commit message 缺少前缀）
- 业务规则校验失败（如覆盖率不足）
- 可选步骤失败（如 AST 分析失败）

**处理原则**：
- ✅ **返回详细的错误提示**
- ✅ **提供 `-y` / `--yes` 绕过选项**
- ✅ **记录到日志（warning 级别）**
- ✅ **不阻断流程，除非用户确认**

**示例**：
```python
# ✅ 正确：业务错误提供绕过选项
def run_coverage_gate(console: Console, skip_coverage: bool = False) -> None:
    if skip_coverage:
        console.print("[yellow]⚠️  Skipping coverage gate (--skip-coverage)[/]")
        return

    coverage = coverage_service.run_coverage_check()  # SystemError 会自然抛出

    if not coverage.all_passing:
        console.print("[red]✗ Coverage gate failed[/]")
        # 业务错误：允许通过 --skip-coverage 绕过
        raise Exit(1)

# ✅ 正确：commit message 格式检查
def validate_commit_message(msg: str, yes: bool = False) -> None:
    if not msg.startswith(("feat:", "fix:", "refactor:")):
        if yes:
            console.print("[yellow]⚠️  Commit message format invalid (--yes)[/]")
            return
        else:
            console.print("[red]✗ Commit message must start with feat/fix/refactor[/]")
            console.print("[dim]Use --yes to skip this check[/]")
            raise Exit(1)
```

---

### Tier 3: BatchError（批量错误）🟠

**定义**：批量执行多个独立任务时，部分任务失败

**特征**：
- 批量操作多个文件/资源
- 每个任务是独立的
- 一个失败不应影响其他任务

**处理原则**：
- ✅ **继续执行其他任务**
- ✅ **收集所有错误**
- ✅ **最后统一报告**
- ✅ **至少有一个失败时，最终抛出异常**

**示例**：
```python
# ✅ 正确：批量处理，最后报告错误
def analyze_files(self, files: list[str]) -> dict:
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
        # 最后统一报告
        logger.error(f"Failed to analyze {len(errors)}/{len(files)} files")
        raise BatchError(f"Batch analysis failed: {len(errors)} errors", errors)

    return {"results": results}

# ❌ 错误：立即抛出，影响其他任务
def analyze_files(self, files: list[str]) -> dict:
    results = []
    for file in files:
        result = self.analyze_file(file)  # 失败立即退出
        results.append(result)
    return {"results": results}
```

---

## 二、实现规则

### 1. 异常类型映射

| 异常类型 | 层级 | 处理方式 | 示例 |
|---------|------|---------|------|
| `SerenaError` | SystemError | 向上抛出 | Serena agent 创建失败 |
| `GitError` | SystemError | 向上抛出 | git 命令执行失败 |
| `ConfigError` | SystemError | 向上抛出 | 配置文件格式错误 |
| `ValidationError` | UserError | 返回提示 + 绕过选项 | commit message 格式错误 |
| `CoverageGateError` | UserError | 返回提示 + 绕过选项 | 覆盖率不足 |
| `BatchError` | BatchError | 收集后统一报告 | 批量分析部分失败 |

### 2. CLI 层错误处理

**CLI 层职责**：
- 捕获所有异常
- 区分 SystemError 和 UserError
- 显示友好的错误信息

```python
# src/vibe3/cli.py
def main() -> None:
    try:
        app()
    except SystemError as e:
        # 系统错误：显示错误栈（开发模式）或简洁提示（用户模式）
        logger.exception(f"❌ System error: {e}")
        console.print(f"\n[red]❌ System error: {e.message}[/]")
        console.print(f"[dim]This is a bug. Please report to developers.[/]")
        sys.exit(99)
    except UserError as e:
        # 业务错误：显示友好提示
        logger.warning(f"⚠️  Validation error: {e}")
        console.print(f"\n[yellow]⚠️  {e.message}[/]")
        console.print(f"[dim]Use --yes to skip this check if needed.[/]")
        sys.exit(1)
    except BatchError as e:
        # 批量错误：显示汇总
        logger.error(f"Batch operation failed: {e}")
        console.print(f"\n[red]❌ Batch operation failed: {len(e.errors)} errors[/]")
        for error in e.errors[:5]:  # 显示前5个错误
            console.print(f"  [red]✗ {error['file']}: {error['error']}[/]")
        sys.exit(1)
```

---

## 三、Agent 决策规则

### 何时抛出异常？

```
IF 错误影响系统功能正确性：
    抛出 SystemError  # 立即失败
    示例：模块损坏、依赖缺失、配置错误

ELIF 错误是业务规范不符：
    返回 UserError  # 提示 + 绕过选项
    示例：格式不符、覆盖率不足、标签缺失

ELIF 批量任务中的单个失败：
    记录错误，继续执行  # 最后统一报告
    示例：批量分析文件、批量创建 PR
```

### 具体场景判断表

| 场景 | 错误类型 | 处理方式 |
|------|---------|---------|
| Serena AST 分析失败 | SystemError | 立即抛出 SerenaError |
| commit message 缺少 feat 前缀 | UserError | 提示 + `--yes` 绕过 |
| 覆盖率检查失败 | UserError | 提示 + `--skip-coverage` 绕过 |
| 批量分析 10 个文件，3 个失败 | BatchError | 继续执行，最后报告 3 个失败 |
| 配置文件格式错误 | SystemError | 立即抛出 ConfigError |
| GitHub API 调用失败 | SystemError | 立即抛出 GitHubError |
| PR 标签缺失（非强制） | UserError | 警告，但不阻断 |

---

## 四、代码审查检查清单

### 审查代码时，检查：

- [ ] **所有 `except` 块都有明确目的**
  - 如果是捕获 SystemError，必须重新抛出或包装
  - 如果是捕获 UserError，必须提供绕过选项

- [ ] **没有空 `except` 块**
  ```python
  # ❌ 禁止
  except Exception:
      pass
  ```

- [ ] **没有返回错误字典的静默失败**
  ```python
  # ❌ 禁止
  except SomeError as e:
      return {"status": "error", "error": str(e)}
  ```

- [ ] **批量操作有错误收集机制**
  ```python
  # ✅ 正确
  errors = []
  for task in tasks:
      try:
          process(task)
      except Error as e:
          errors.append(e)
  if errors:
      raise BatchError("Batch failed", errors)
  ```

- [ ] **SystemError 不被捕获为 UserError**
  ```python
  # ❌ 错误：捕获系统错误作为业务错误
  try:
      result = serena.analyze(file)  # SerenaError 是系统错误
  except SerenaError:
      console.print("Warning: analysis failed")  # 不应该这样处理
  ```

---

## 五、示例对比

### 场景 1: Serena AST 分析

```python
# ❌ 错误：静默失败
def analyze_file(self, file: str) -> dict:
    try:
        overview = self.client.get_symbols_overview(file)
        return {"status": "ok", "symbols": overview}
    except SerenaError as e:
        return {"status": "error", "error": str(e)}

# ✅ 正确：系统错误立即抛出
def analyze_file(self, file: str) -> dict:
    overview = self.client.get_symbols_overview(file)
    return {"symbols": overview}
```

### 场景 2: Commit Message 格式检查

```python
# ❌ 错误：强制要求，不提供绕过
def validate_commit_message(msg: str) -> None:
    if not msg.startswith("feat:"):
        raise ValidationError("Must start with feat:")

# ✅ 正确：业务错误提供绕过选项
def validate_commit_message(msg: str, yes: bool = False) -> None:
    if not msg.startswith(("feat:", "fix:", "refactor:")):
        if not yes:
            console.print("[red]✗ Invalid commit message format[/]")
            console.print("[dim]Use --yes to skip[/]")
            raise Exit(1)
        console.print("[yellow]⚠️  Format invalid (--yes)[/]")
```

### 场景 3: 批量文件分析

```python
# ❌ 错误：单个失败立即退出
def analyze_files(files: list[str]) -> list:
    results = []
    for file in files:
        result = analyze_file(file)  # 第一个失败就退出
        results.append(result)
    return results

# ✅ 正确：批量处理，最后报告
def analyze_files(files: list[str]) -> list:
    results = []
    errors = []
    for file in files:
        try:
            result = analyze_file(file)
            results.append(result)
        except SerenaError as e:
            errors.append({"file": file, "error": str(e)})

    if errors:
        raise BatchError(f"{len(errors)} files failed", errors)
    return results
```

---

## 六、更新 CLAUDE.md

在 CLAUDE.md 的 HARD RULES 中添加：

```markdown
11. **错误处理必须区分类型**：
    - **SystemError（系统错误）**：立即抛出，fail-fast
      - 示例：模块损坏、依赖缺失、配置错误、API 失败
      - 处理：不捕获，不降级，不返回错误字典
    - **UserError（业务错误）**：返回提示 + 绕过选项
      - 示例：格式不符、覆盖率不足、标签缺失
      - 处理：提供 `-y/--yes` 选项
    - **BatchError（批量错误）**：继续执行，最后报告
      - 示例：批量分析文件、批量创建 PR
      - 处理：收集错误，最后统一抛出
```

---

**文档版本**：1.0
**创建日期**：2026-03-19
**作者**：Claude Agent
**状态**：待用户确认