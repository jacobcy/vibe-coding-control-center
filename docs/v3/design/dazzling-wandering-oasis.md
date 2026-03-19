# PR Ready 质量门禁检查实现计划

## Context

**问题**：当前 `vibe3 pr ready` 命令只是简单地标记 PR 为 ready 状态，**没有任何质量检查**。这导致可能将测试覆盖率不足、质量不达标的代码标记为 ready，违反了 `config/settings.yaml` 中定义的质量标准。

**需求**：在标记 PR 为 ready 之前，自动检查测试覆盖率是否符合配置要求（services ≥ 80%, clients ≥ 70%, commands ≥ 60%）。如果不达标，阻止操作并给出清晰的提示，除非使用 `--force` 参数强制跳过。

**影响**：提高代码质量，防止低质量代码进入 review 流程，与项目的质量标准文档对齐。

---

## Implementation Approach

### 核心设计

采用分层架构，新增独立的 `CoverageService` 负责运行和解析覆盖率检查，修改 `pr ready` 命令集成质量门禁逻辑。

**架构分层**：
```
Commands (CLI)
    ↓ 调用
Services (CoverageService)
    ↓ 运行
pytest --cov (外部工具)
    ↓ 解析
JSON Report
```

**参数语义**：
- `--yes` / `-y`：跳过交互确认（保持现有语义）
- `--force`：强制跳过质量门禁检查（新增参数）

**错误处理**：
- 测试失败 → 阻止并提示修复测试
- 覆盖率不足 → 阻止并显示具体差距
- 工具未安装 → 提示安装命令

---

## Changes

### 1. 新增数据模型 (`src/vibe3/models/coverage.py`)

**目的**：定义覆盖率报告的数据结构，作为各层之间的数据契约。

**核心类**：
```python
class LayerCoverage(BaseModel):
    """单层覆盖率指标"""
    layer_name: str          # "services" / "clients" / "commands"
    covered_lines: int       # 覆盖行数
    total_lines: int         # 总行数
    coverage_percent: float  # 覆盖率百分比
    threshold: int           # 达标阈值

    @property
    def is_passing(self) -> bool:
        """是否达标"""
        return self.coverage_percent >= self.threshold

    @property
    def gap(self) -> float:
        """距离达标还差多少"""
        return self.threshold - self.coverage_percent

class CoverageReport(BaseModel):
    """完整覆盖率报告"""
    services: LayerCoverage
    clients: LayerCoverage
    commands: LayerCoverage

    @property
    def all_passing(self) -> bool:
        """所有层是否达标"""
        return all([self.services.is_passing, self.clients.is_passing, self.commands.is_passing])

    @property
    def failing_layers(self) -> list[LayerCoverage]:
        """获取未达标的层"""
        return [layer for layer in [self.services, self.clients, self.commands] if not layer.is_passing]
```

**参考模式**：`src/vibe3/services/metrics_service.py` 中的 `LayerMetrics` 模型。

---

### 2. 新增覆盖率服务 (`src/vibe3/services/coverage_service.py`)

**目的**：运行 pytest 覆盖率检查并解析报告，是质量门禁的核心业务逻辑。

**关键方法**：
```python
class CoverageService:
    def run_coverage_check(self) -> CoverageReport:
        """运行覆盖率检查的主入口

        流程：
        1. 运行 pytest --cov --cov-report=json
        2. 检查测试是否通过（退出码 0）
        3. 解析 coverage.json
        4. 分层统计覆盖率
        5. 返回 CoverageReport

        Raises:
            CoverageError: 测试失败或覆盖率工具错误
        """
        # 运行 pytest
        result = subprocess.run([
            "uv", "run", "pytest",
            "tests/vibe3/",
            "--cov=src/vibe3",
            "--cov-report=json:coverage.json",
            "-q", "--no-cov-on-fail"
        ])

        # 检查测试通过
        if result.returncode != 0:
            raise CoverageError("Tests failed. Fix failing tests first.")

        # 解析 JSON
        with open("coverage.json") as f:
            cov_data = json.load(f)

        # 分层统计
        return self._analyze_coverage(cov_data)

    def _analyze_coverage(self, cov_data: dict) -> CoverageReport:
        """分层统计覆盖率

        遍历 coverage.json 中的 files，按路径前缀分组：
        - src/vibe3/services/ → services 层
        - src/vibe3/clients/ → clients 层
        - src/vibe3/commands/ → commands 层
        """
        # 读取配置
        config = get_config()
        thresholds = config.quality.test_coverage

        # 分别统计每层
        services = self._calculate_layer_coverage(
            cov_data, "src/vibe3/services/", "services", thresholds.services
        )
        # ... clients, commands

        return CoverageReport(services=services, clients=clients, commands=commands)

    def _calculate_layer_coverage(
        self, cov_data: dict, layer_path: str, layer_name: str, threshold: int
    ) -> LayerCoverage:
        """统计单层覆盖率

        累加该层所有文件的:
        - num_statements (总语句数)
        - covered_lines (覆盖行数)

        计算覆盖率 = covered_lines / num_statements * 100
        """
        total_statements = 0
        total_covered = 0

        for file_path, file_data in cov_data["files"].items():
            if file_path.startswith(layer_path):
                total_statements += file_data["summary"]["num_statements"]
                total_covered += file_data["summary"]["covered_lines"]

        coverage_percent = (total_covered / total_statements * 100) if total_statements > 0 else 0.0

        return LayerCoverage(
            layer_name=layer_name,
            covered_lines=total_covered,
            total_lines=total_statements,
            coverage_percent=round(coverage_percent, 1),
            threshold=threshold
        )
```

**参考模式**：
- `src/vibe3/services/metrics_service.py` 的配置读取和限制检查
- `src/vibe3/services/pr_scoring_service.py` 的分数计算和阈值判断

---

### 3. 修改 PR ready 命令 (`src/vibe3/commands/pr.py`)

**修改位置**：`ready()` 函数

**集成方式**：
```python
@app.command()
def ready(
    pr_number: Annotated[int, typer.Argument(help="PR number")],
    yes: Annotated[bool, typer.Option("-y", "--yes", help="跳过交互确认")] = False,
    force: Annotated[bool, typer.Option("--force", help="强制跳过质量门禁检查")] = False,  # 新增
    trace: Annotated[bool, typer.Option("--trace", ...)] = False,
    json_output: Annotated[bool, typer.Option("--json", ...)] = False,
) -> None:
    """Mark PR as ready for review."""
    # 1. 质量门禁检查（除非 --force）
    if not force:
        try:
            coverage_service = CoverageService()
            coverage_report = coverage_service.run_coverage_check()

            if not coverage_report.all_passing:
                render_coverage_check_failed(coverage_report)
                raise typer.Exit(1)

            render_coverage_check_passed(coverage_report)

        except CoverageError as e:
            logger.error("Coverage check failed", error=str(e))
            render_error(str(e))
            raise typer.Exit(1)
    else:
        logger.warning("Skipping quality gate checks (--force)")
        render_warning("Quality gate checks skipped (--force)")

    # 2. 确认操作（除非 --yes）
    if not yes:
        confirmed = typer.confirm(...)
        if not confirmed:
            raise typer.Exit(0)

    # 3. 调用服务标记为 ready
    service = PRService()
    pr = service.mark_ready(pr_number)
    render_pr_ready(pr)
```

**执行流程**：
```
用户执行: vibe pr ready 42
    ↓
1. 质量门禁检查（可被 --force 跳过）
    ├─ 运行 pytest --cov
    ├─ 解析覆盖率报告
    ├─ 判断是否达标
    ├─ 不达标 → 显示失败详情，退出(1)
    └─ 达标 → 显示通过表格，继续
    ↓
2. 用户确认（可被 --yes 跳过）
    ↓
3. 调用 GitHub API 标记为 ready
```

---

### 4. 新增 UI 渲染函数 (`src/vibe3/ui/pr_ui.py`)

**目的**：友好地展示覆盖率检查结果。

**新增函数**：
```python
def render_coverage_check_passed(report: CoverageReport) -> None:
    """渲染成功检查结果

    示例输出：
    ✓ Quality gate checks passed

    Test Coverage
    ┌─────────┬──────────┬───────────┬────────┐
    │ Layer   │ Coverage │ Threshold │ Status │
    ├─────────┼──────────┼───────────┼────────┤
    │ Services│ 82.5%    │ ≥80%      │ ✅     │
    │ Clients │ 73.0%    │ ≥70%      │ ✅     │
    │ Commands│ 65.2%    │ ≥60%      │ ✅     │
    └─────────┴──────────┴───────────┴────────┘
    """
    console.print("\n[green]✓[/] Quality gate checks passed\n")

    table = Table(title="Test Coverage", box=None)
    table.add_column("Layer", style="cyan")
    table.add_column("Coverage", justify="right")
    table.add_column("Threshold", justify="right")
    table.add_column("Status", justify="center")

    for layer in [report.services, report.clients, report.commands]:
        status = "✅" if layer.is_passing else "❌"
        table.add_row(
            layer.layer_name.capitalize(),
            f"{layer.coverage_percent}%",
            f"≥{layer.threshold}%",
            status
        )

    console.print(table)


def render_coverage_check_failed(report: CoverageReport) -> None:
    """渲染失败检查结果

    示例输出：
    ✗ Quality gate checks failed

    Test Coverage (Failed)
    ┌─────────┬──────────┬───────────┬─────────┬────────┐
    │ Layer   │ Coverage │ Threshold │ Gap     │ Status │
    ├─────────┼──────────┼───────────┼─────────┼────────┤
    │ Services│ 57.3%    │ ≥80%      │ +22.7%  │ ❌     │
    │ Clients │ 73.0%    │ ≥70%      │ -       │ ✅     │
    │ Commands│ 65.2%    │ ≥60%      │ -       │ ✅     │
    └─────────┴──────────┴───────────┴─────────┴────────┘

    Action required:
      • Add tests for services layer (need 22.7% more coverage)

    Tip: Use --force to skip quality checks (not recommended)
    """
    console.print("\n[red]✗[/] Quality gate checks failed\n")

    table = Table(title="Test Coverage (Failed)", box=None)
    table.add_column("Layer", style="cyan")
    table.add_column("Coverage", justify="right")
    table.add_column("Threshold", justify="right")
    table.add_column("Gap", justify="right")
    table.add_column("Status", justify="center")

    for layer in [report.services, report.clients, report.commands]:
        status = "✅" if layer.is_passing else "❌"
        gap_str = f"{layer.gap:+.1f}%" if not layer.is_passing else "-"
        table.add_row(
            layer.layer_name.capitalize(),
            f"{layer.coverage_percent}%",
            f"≥{layer.threshold}%",
            gap_str,
            status
        )

    console.print(table)

    # Action guidance
    console.print("\n[yellow]Action required:[/]")
    for layer in report.failing_layers:
        console.print(f"  • Add tests for {layer.layer_name} layer (need {layer.gap:.1f}% more coverage)")

    console.print("\n[dim]Tip: Use --force to skip quality checks (not recommended)[/]\n")
```

**参考模式**：现有的 `render_pr_created()`, `render_pr_details()` 函数。

---

### 5. 新增单元测试 (`tests/vibe3/services/test_coverage_service.py`)

**测试覆盖**：
```python
class TestCoverageService:
    def test_run_coverage_check_success(self):
        """测试成功场景：测试通过，覆盖率达标"""

    def test_run_coverage_check_test_failure(self):
        """测试失败场景：pytest 返回非零退出码"""

    def test_run_coverage_check_coverage_below_threshold(self):
        """测试覆盖率不足场景：测试通过但覆盖率 < 阈值"""

    def test_analyze_coverage_no_code(self):
        """测试边界场景：某层无代码（返回 0%）"""

    def test_calculate_layer_coverage(self):
        """测试单层统计逻辑"""
```

**Mock 策略**：
- 使用 `unittest.mock.patch` Mock `subprocess.run`
- Mock coverage.json 文件内容
- Mock 配置读取

---

## Critical Files to Modify

### 必须新增的文件

1. **`src/vibe3/models/coverage.py`** - 覆盖率数据模型（~50 行）
2. **`src/vibe3/services/coverage_service.py`** - 覆盖率服务核心逻辑（~150 行）
3. **`src/vibe3/ui/pr_ui.py`** - 新增渲染函数（在现有文件中添加 ~100 行）
4. **`tests/vibe3/services/test_coverage_service.py`** - 单元测试（~150 行）

### 必须修改的文件

5. **`src/vibe3/commands/pr.py`** - 修改 `ready()` 命令，集成质量门禁（修改 ~30 行）

---

## Reusable Patterns

### 配置读取
```python
from vibe3.config.loader import get_config

config = get_config()
thresholds = config.quality.test_coverage
# thresholds.services = 80, thresholds.clients = 70, thresholds.commands = 60
```

### 限制检查模式
参考 `src/vibe3/services/metrics_service.py`:
```python
class LayerMetrics(BaseModel):
    @property
    def total_ok(self) -> bool:
        return self.total_loc <= self.limit_total

    @property
    def violations(self) -> list[FileMetrics]:
        return [f for f in self.files if f.loc > self.limit_file]
```

### --yes 跳过确认
参考 `src/vibe3/commands/pr.py` 现有实现：
```python
if not yes:
    confirmed = typer.confirm(...)
    if not confirmed:
        raise typer.Exit(0)
```

### 错误处理
参考 `src/vibe3/services/metrics_service.py`:
```python
class MetricsError(VibeError):
    def __init__(self, details: str) -> None:
        super().__init__(f"Metrics collection failed: {details}", recoverable=False)
```

---

## Verification Plan

### 1. 单元测试验证
```bash
# 运行覆盖率服务测试
uv run pytest tests/vibe3/services/test_coverage_service.py -v

# 期望：所有测试通过
```

### 2. 集成测试（手动）

#### 场景 1：覆盖率达标
```bash
# 1. 确保当前代码覆盖率达标
uv run pytest tests/vibe3/ --cov=src/vibe3 --cov-report=term

# 2. 运行 pr ready（应该通过）
uv run python src/vibe3/cli.py pr ready 42 --yes

# 期望：
# ✓ Quality gate checks passed
# 显示覆盖率表格
# PR 标记为 ready
```

#### 场景 2：覆盖率不足
```bash
# 1. 临时降低配置阈值（修改 config/settings.yaml）
# quality.test_coverage.services: 90  # 提高到 90%

# 2. 运行 pr ready（应该失败）
uv run python src/vibe3/cli.py pr ready 42 --yes

# 期望：
# ✗ Quality gate checks failed
# 显示失败表格和差距
# 提示需要增加多少覆盖率
# 退出码 = 1
```

#### 场景 3：强制跳过
```bash
# 运行 pr ready with --force
uv run python src/vibe3/cli.py pr ready 42 --force --yes

# 期望：
# ⚠️ Quality gate checks skipped (--force)
# PR 标记为 ready（跳过检查）
```

#### 场景 4：测试失败
```bash
# 1. 故意破坏一个测试（让 pytest 失败）

# 2. 运行 pr ready
uv run python src/vibe3/cli.py pr ready 42 --yes

# 期望：
# ERROR: Tests failed (exit code 1). Fix failing tests first.
# 退出码 = 1
```

### 3. 类型检查
```bash
# 运行 mypy 确保类型安全
uv run mypy --strict src/vibe3/

# 期望：无新增类型错误
```

---

## Error Handling

| 错误场景 | 处理方式 | 提示信息 |
|---------|---------|---------|
| pytest 未安装 | `FileNotFoundError` → `CoverageError` | "pytest-cov not found. Install with: uv add --dev pytest-cov" |
| 测试运行失败 | 检查退出码 ≠ 0 | "Tests failed (exit code X). Fix failing tests first." |
| 覆盖率报告未生成 | 检查 coverage.json 是否存在 | "Coverage report not generated. Ensure pytest-cov is installed." |
| 某层无代码 | total_statements = 0 → 覆盖率 0% | 正常处理，显示 0% |
| JSON 解析失败 | `json.JSONDecodeError` → `CoverageError` | "Failed to parse coverage report: invalid JSON" |

---

## Dependencies

**必须已安装**：
- `pytest >= 7.4.0` (已在 dev dependencies)
- `pytest-cov >= 4.0.0` (需确认是否已安装)

**检查命令**：
```bash
uv run pytest --version
uv run pytest-cov --version  # 如果没有，需要添加
```

**添加依赖**（如果缺失）：
```bash
uv add --dev pytest-cov
```

---

## Future Enhancements (Out of Scope)

以下功能在本实现中**不包含**，可作为未来增强：

1. **Commit Status 集成**：在 GitHub 上创建 commit status (success/failure)
2. **详细文件级报告**：显示哪些具体文件覆盖率不足
3. **增量覆盖率检查**：只检查 PR 中修改的文件
4. **覆盖率趋势追踪**：记录历史覆盖率并显示趋势
5. **自定义阈值**：允许在 PR metadata 中指定特定阈值

---

## Summary

本实现通过新增独立的 `CoverageService` 和分层统计逻辑，在 `pr ready` 命令中集成了质量门禁检查，确保只有测试覆盖率达标（services ≥ 80%, clients ≥ 70%, commands ≥ 60%）的 PR 才能标记为 ready，同时通过 `--force` 参数提供强制跳过的灵活性。

**预计工作量**：
- 新增代码：~450 行（含测试）
- 修改代码：~30 行
- 预计时间：2-3 小时

**风险点**：
- pytest-cov JSON 格式可能随版本变化（需测试兼容性）
- 分层统计逻辑需要准确匹配路径前缀
- 大型代码库运行覆盖率可能较慢（可考虑缓存优化）