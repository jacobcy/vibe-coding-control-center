---
document_type: plan
title: Codex Review Phase 1 - 基础设施搭建
status: done
author: Claude Sonnet 4.6
created: 2026-03-16
last_updated: 2026-03-17
related_docs:
  - docs/v3/trace/codex-auto-review-plan.md
  - docs/references/codex-review.md
  - docs/references/codex-serena-intetration.md
  - docs/standards/serena-usage.md
  - docs/v3/infrastructure/03-coding-standards.md
  - docs/v3/infrastructure/07-command-standards.md
---

# Codex Review Phase 1 - 基础设施搭建

> [!NOTE]
> 本阶段创建 v3 配置管理系统，并将现有工具迁移到 v3 分层架构。
>
> **技术标准**: 所有 Python 代码必须遵守 v3 标准（编码、测试、日志、错误处理）。

---

## 目标

1. **创建 v3 统一配置管理系统** - 消除硬编码参数，提供配置验证
2. **迁移现有工具** - 将 Shell/Python 工具迁移到 v3 分层架构
3. **添加日志与错误处理** - 符合 v3 标准的日志和异常处理
4. **编写测试** - Services 层测试覆盖率 ≥ 80%
5. **支持命令分层** - Services 同时支持 `vibe inspect` 和 `vibe review`

---

## 任务清单

### 1. v3 配置管理系统

**目标**: 创建 pydantic 配置模型，消除硬编码参数

#### 1.1 配置文件设计

**位置**: `config/setting.yaml`

**结构**:
```yaml
# 代码量控制
code_limits:
  v2_shell:
    total_loc: 7000          # Shell 总行数限制
    max_file_loc: 300        # 单文件最大行数
    min_tests: 20            # 最少测试数量

  v3_python:
    total_loc:           # Python 总行数限制
    max_file_loc: 300        # 单文件最大行数
    min_tests: 5             # 最少测试数量

# 审核范围（适配 vibe-center 实际结构）
review_scope:
  critical_paths:            # 关键路径（重点审核）
    - "bin/"                 # CLI 入口
    - "lib/flow"             # Flow 核心逻辑
    - "lib/git"              # Git 操作
    - "lib/github"           # GitHub 集成
    - "src/vibe3/services/"  # v3 服务层

  public_api_paths:          # 公开 API（兼容性检查）
    - "bin/vibe"             # 主入口
    - "lib/flow.sh"          # Flow 公开接口
    - "src/vibe3/commands/"  # v3 命令层

# 质量标准
quality:
  test_coverage:
    services: 80             # Services 层 ≥ 80%
    clients: 70              # Clients 层 ≥ 70%
    commands: 60             # Commands 层 ≥ 60%
```

#### 1.2 实现任务

- [x] 创建 `src/vibe3/config/settings.py`：
  - 使用 pydantic 定义配置模型
  - `CodeLimitsConfig` - 代码量限制
  - `ReviewScopeConfig` - 审核范围
  - `QualityConfig` - 质量标准
  - `VibeConfig` - 总配置

- [x] 创建 `src/vibe3/config/loader.py`：
  - `load_config()` - 从 `.vibe/config.yaml` 加载配置
  - 支持默认值
  - 支持环境变量覆盖

- [ ] 更新 `metrics.sh` 硬编码参数：
  - 从配置读取限制值
  - 不再写死 `7000`、`300`、`20` 等数字（Python 层已实现，Shell 层待处理）

- [ ] 创建配置验证命令：
  - `vibe config check` - 验证配置文件
  - `vibe config show` - 显示当前配置（Phase 2 范围）

#### 1.3 配置使用示例

**metrics_service.py**:
```python
from vibe3.config import load_config

def check_shell_metrics() -> dict:
    config = load_config()
    limit = config.code_limits.v2_shell.total_loc
    # 使用配置的 limit，不是硬编码 7000
```

---

### 2. 改动分析架构（统一设计）

**目标**: 建立统一的改动分析架构，支持 PR/Commit/Branch/Uncommitted 四种改动源

**设计文档**: [change-analysis-architecture.md](references/change-analysis-architecture.md)

**核心要点**:
- 统一改动源抽象（`ChangeSource` 类型）
- Git Client 统一接口（`get_changed_files(source)`）
- Serena Service 统一分析入口（`analyze_changes(source)`）

**实现任务**（详见设计文档）:
- [x] 创建 `models/change_source.py` - 定义改动源类型
- [x] 扩展 `clients/git_client.py` - 实现统一接口
- [x] 扩展 `services/serena_service.py` - 支持统一改动分析

**目标**: 迁移现有逻辑到 v3 架构，支持统一改动分析

**现有代码**: `scripts/tools/serena_gate.py` (147 行)

**架构分层**:
- `clients/serena_client.py` - 封装 Serena agent 操作
- `services/serena_service.py` - 薄编排层，业务逻辑协调

**代码质量要求**:
- ✅ Service 文件 ≤ 300 行，函数 ≤ 100 行
- ✅ Client 文件无限制，但函数 ≤ 150 行
- ✅ 所有函数添加类型注解
- ✅ 禁止使用 `Any` 类型
- ✅ loguru 日志 + `logger.bind(domain="review", action="serena_analysis")`
- ✅ 统一异常处理（SerenaClientError）
- ✅ 输出标准化（JSON）

**实现任务**（详见设计文档）:
- [x] 创建 `clients/serena_client.py`
- [x] 创建 `services/serena_service.py`
- [x] 扩展 `services/serena_service.py` - 支持统一改动分析
- [x] 添加日志和异常处理

#### 2.3 Git Client 扩展

**目标**: 提供统一的改动获取接口

**位置**: `clients/git_client.py`（已存在，需扩展）

**核心接口**（详见设计文档）:
- `get_changed_files(source: ChangeSource)` - 统一改动文件获取
- `get_diff(source: ChangeSource)` - 统一 diff 获取

**代码质量要求**:
- ✅ Client 文件函数 ≤ 150 行
- ✅ 所有函数添加类型注解
- ✅ loguru 日志
- ✅ 统一异常处理（GitClientError）

**实现任务**（详见设计文档）:
- [x] 扩展 `clients/git_client.py` - 实现统一接口

#### 2.4 与 Phase 2 的衔接

**详见**: [phase1-phase2-integration.md](references/phase1-phase2-integration.md)

Phase 1 提供的能力层将通过统一接口被 Phase 2 的编排层调用。

---

### 3. Metrics Service（迁移 `metrics.sh`）

**目标**: Shell → Python，使用配置系统，消除硬编码

**现有代码**: `scripts/tools/metrics.sh` (186 行)

**架构分层**:
- `services/metrics_service.py` - 业务逻辑，从配置读取限制
- `commands/metrics.py` - typer CLI 入口

**代码质量要求**:
- ✅ Service 文件 ≤ 300 行，函数 ≤ 100 行
- ✅ Command 文件 ≤ 150 行，函数 ≤ 50 行
- ✅ 从配置读取限制值（禁止硬编码）
- ✅ 所有函数添加类型注解
- ✅ loguru 日志 + context binding
- ✅ 统一异常处理

**实现任务**:
- [x] 创建 `services/metrics_service.py`
  - `collect_shell_metrics()` - 收集 Shell 代码指标
  - `collect_python_metrics()` - 收集 Python 代码指标
  - 使用 `vibe3.config.get_config()` 读取配置
- [x] 创建 `commands/metrics.py` (typer 入口)
- [x] 添加日志和异常处理
- [x] 编写测试

**目标**: Shell → Python，添加日志

**现有代码**: `scripts/tools/structure_summary.sh` (169 行)

**架构分层**:
- `services/structure_service.py` - 分析文件结构
- `commands/structure.py` - typer CLI 入口

**代码质量要求**:
- ✅ Service 文件 ≤ 300 行，函数 ≤ 100 行
- ✅ Command 文件 ≤ 150 行，函数 ≤ 50 行
- ✅ 所有函数添加类型注解
- ✅ loguru 日志 + context binding
- ✅ 统一异常处理

**实现任务**:
- [x] 创建 `services/structure_service.py`
  - `analyze_shell_file()` - 分析 Shell 文件结构
  - `analyze_python_file()` - 分析 Python 文件结构
- [x] 创建 `commands/structure.py`
- [x] 添加日志和异常处理
- [x] 编写测试

---

### 5. DAG Service（新增）

**目标**: 分析模块依赖图，确认影响范围

**位置**: `services/dag_service.py`

**代码质量要求**:
- ✅ Service 文件 ≤ 300 行，函数 ≤ 100 行
- ✅ 所有函数添加类型注解
- ✅ loguru 日志 + context binding
- ✅ 统一异常处理
- ✅ 嵌套不超过 3 层

**实现任务**:
- [x] 创建 `services/dag_service.py`
  - `build_module_graph()` - 解析 import 构建依赖图
  - `expand_impacted_modules()` - 从 seed 模块扩展影响范围
- [x] 添加日志和异常处理
- [x] 编写测试

---

### 6. 命令调用链路分析服务（Command Analyzer）

**目标**: 提供命令的静态结构分析，支持代码学习和调试

**设计文档**: [symbol-vs-command-design.md](references/symbol-vs-command-design.md)

**核心能力**:
- **静态分析**: 解析 AST 提取函数调用关系
- **不执行代码**: 只分析代码结构，不运行命令

**使用场景**:
```bash
# 查看 vibe review pr 的静态调用链路（不执行）
vibe inspect commands review pr
```

**注意**: 运行时追踪（`vibe review pr --trace`）在 Phase 2 的 Command 层实现。

**实现任务**（详见设计文档）:
- [x] 创建 `services/command_analyzer.py` - 实现静态分析

---

### 7. PR Scoring Service（新增）

**目标**: 根据 PR 多维度指标计算风险分数

**位置**: `services/pr_scoring_service.py`

**代码质量要求**:
- ✅ Service 文件 ≤ 300 行，函数 ≤ 100 行
- ✅ 所有函数添加类型注解
- ✅ 禁止硬编码权重，从配置读取
- ✅ loguru 日志 + context binding
- ✅ 统一异常处理
- ✅ 使用 pydantic 模型定义评分结果

**评分维度**（从配置读取）:
1. **changed_lines** - 改动行数权重
2. **changed_files** - 改动文件数权重
3. **impacted_modules** - 影响模块数权重
4. **critical_path_touch** - 是否触及关键路径
5. **public_api_touch** - 是否触及公开 API
6. **cross_module_symbol_change** - 是否跨模块符号改动
7. **codex_major/critical** - Codex 审核结果权重

**风险等级**:
- LOW (0-2 分)
- MEDIUM (3-5 分)
- HIGH (6-8 分)
- CRITICAL (≥9 分)

**实现任务**:
- [x] 创建 `services/pr_scoring_service.py`
  - `calculate_risk_score()` - 计算风险分数（从配置读取权重）
  - `determine_risk_level()` - 判定风险等级（从配置读取阈值）
  - `generate_score_report()` - 生成评分报告
- [x] 使用 pydantic 定义 `RiskScore` 模型
- [x] 添加日志和异常处理
- [x] 编写测试：`tests/vibe3/services/test_pr_scoring_service.py`

**配置扩展** (`.vibe/config.yaml`):
```yaml
pr_scoring:
  weights:
    changed_lines:
      small: 0         # <50 行
      medium: 1        # 50-200 行
      large: 2         # 200-500 行
      xlarge: 3        # >500 行
    changed_files:
      small: 0         # 1-3 文件
      medium: 1        # 4-10 文件
      large: 2         # >10 文件
    impacted_modules:
      small: 0         # 1 模块
      medium: 1        # 2-4 模块
      large: 2         # ≥5 模块
    critical_path_touch: 2
    public_api_touch: 2
    cross_module_symbol_change: 2
    codex_major: 3
    codex_critical: 5

  thresholds:
    medium: 3
    high: 6
    critical: 9

  merge_gate:
    block_on_score_at_or_above: 9
    block_on_verdict:
      - "BLOCK"
```

---

## 验收标准

### 代码质量

#### 代码规模（强制）

- [x] **Services 层**: 所有文件 ≤ 300 行，函数 ≤ 100 行
- [x] **Clients 层**: 函数 ≤ 150 行（文件无限制，但应保持合理）
- [x] **Commands 层**: 所有文件 ≤ 150 行，函数 ≤ 50 行
- [x] **CLI 入口**: 文件 ≤ 50 行，函数 ≤ 20 行

#### 类型安全（强制）

- [x] 所有公共函数必须有类型注解
- [x] 使用 Python 3.10+ 类型语法（`str | None` 而非 `Optional[str]`）
- [x] **禁止使用 `Any` 类型**
- [ ] 通过 `mypy --strict` 检查（Phase 2 统一验证）

#### 日志规范（强制）

- [x] 使用 loguru，禁止 `print()`
- [x] 关键操作必须记录日志
- [x] 使用 `logger.bind(domain="...", action="...")` 添加上下文
- [x] 错误日志必须包含异常信息和上下文
- [x] **调用链路追踪**: 每个方法调用必须记录：
  - 调用来源（哪个文件、哪个方法）
  - 调用目标（调用哪个 Client 方法）
  - 关键参数和返回值

#### 异常处理（强制）

- [x] 禁止裸 `except`
- [x] 捕获具体异常类型
- [x] 使用异常链：`raise NewError() from e`
- [x] 自定义异常继承自明确的基类

#### 分层职责（强制）

- [x] **Service 层**: 薄编排，只做业务逻辑协调
- [x] **Client 层**: 封装外部依赖（API、工具）
- [x] **Command 层**: 参数验证 + 调用 Service
- [x] 禁止跨层调用（Command 不能直接调用 Client）

#### 代码复杂度（强制）

- [x] 嵌套不超过 3 层
- [x] 单个函数不超过 10 个参数
- [x] 循环复杂度 ≤ 10

### 调用链路追踪（强制）

**目标**: 记录命令的完整调用链路，方便调试和排查错误

**设计文档**: [call-tracing-vs-dag.md](references/call-tracing-vs-dag.md)

- [x] 所有 Client 方法添加日志
  - 记录方法调用、参数、返回值
  - 使用 `logger.bind(domain="...", action="...")` 绑定上下文
- [x] 所有 Service 方法添加日志
  - 记录调用 Client（`calling="client.method"`）
  - 记录中间结果
- [ ] 所有 Command 添加 `--trace` 参数（gap-report P0，Phase 1 补丁范围）
  - 同时启用 DEBUG 级别日志和调用链路追踪
  - 输出详细调用链路
- [x] 错误追踪
  - 记录异常类型、异常消息
  - 记录完整的调用栈

**验证方式**:
```bash
vibe inspect pr 42 --trace
# 应该输出完整的调用链路日志
```

### 测试覆盖

- [x] Services 层测试覆盖率 ≥ 80%（93 tests passed）
- [x] Clients 层测试覆盖率 ≥ 70%
- [ ] Commands 层测试覆盖率 ≥ 60%（gap-report P1，待补）
- [x] 所有测试通过：`uv run pytest tests/vibe3/`（93 passed）
- [x] 使用 Mock 隔离外部依赖

### 功能验证

- [x] 配置系统可以正常加载和验证
- [x] 所有迁移的服务可以正常工作
- [x] PR 评分系统可以正常计算风险分数
- [x] 日志输出符合 v3 标准
- [ ] 调用链路可以完整追踪（依赖 `--trace` 接入命令层，gap-report P0）

### 验证命令

```bash
# 类型检查
uv run mypy --strict src/vibe3/

# 代码检查
uv run ruff check src/

# 测试覆盖率
uv run pytest tests/ --cov=src/vibe3 --cov-report=term-missing

# 代码行数统计
find src/vibe3 -name "*.py" -exec wc -l {} \;

# 调用链路追踪验证
vibe inspect pr 42 --trace 2>&1 | grep -E "domain|action|calling"
```

---

## 迁移统计

| 原工具 | 原行数 | 迁移目标 | 预估行数 | 架构分层 |
|--------|--------|----------|----------|----------|
| 配置系统 | - | `config/settings.py` + `config/loader.py` | ~200 | Config |
| 改动源抽象 | - | `models/change_source.py` | ~80 | Model |
| `serena_gate.py` | 147 | `clients/serena_client.py` (190行) + `services/serena_service.py` (150行) | ~340 | Client + Service |
| Git Client 扩展 | - | `clients/git_client.py` | +150 | Client |
| `metrics.sh` | 186 | `services/metrics_service.py` + `commands/metrics.py` | ~280 | Service + Command |
| `structure_summary.sh` | 169 | `services/structure_service.py` + `commands/structure.py` | ~260 | Service + Command |
| 新增 DAG | - | `services/dag_service.py` | ~150 | Service |
| 新增 Scoring | - | `services/pr_scoring_service.py` | ~200 | Service |
| 新增 Command Analyzer | - | `services/command_analyzer.py` | ~180 | Service |

**总计**: ~1840 行 Python 代码

**架构说明**：
- **统一改动源抽象**：支持 PR/Commit/Branch/Uncommitted 四种场景
- **Git Client 统一接口**：`get_changed_files(source)` 和 `get_diff(source)`
- **Service 层薄编排**：`analyze_changes(source)` 统一分析入口
- **调用链路分析**：`command_analyzer` 支持命令调试和错误排查
- 所有 Service 文件 ≤ 300 行，Client 函数 ≤ 150 行
- 严格遵循 v3 分层架构，禁止跨层调用

---

## 参考资料

本实施计划基于以下参考资料的核心逻辑：

### 1. 架构对齐

**参考资料架构**（codex-serena-intetration.md）:
```
PR diff
  ↓
python_structure_summary.sh
  ↓
Serena adapter（抽取 changed symbols / references）
  ↓
Review DAG（只保留受影响模块）
  ↓
Risk scoring（给 PR 量化风险）
  ↓
Codex review（基于 policy + context）
  ↓
PR summary comment
  ↓
可选：inline review comments
  ↓
可选：merge gate
```

**实施计划对应**:
- `python_structure_summary.sh` → Structure Service
- `Serena adapter` → Serena Service
- `Review DAG` → DAG Service
- `Risk scoring` → PR Scoring Service
- `Codex review` → Codex CLI
- `PR summary comment` → GitHub Client

### 2. 职责边界

**Serena 层职责**（参考资料明确）:
- 提供事实层（符号和引用关系）
- 不是"让 Serena 替 Codex 审查"
- 而是"让 Serena 给 Codex 提供结构化证据"

**DAG 层职责**:
- 缩小上下文（只看影响面）
- seed → 改动涉及的模块
- 向上扩展 → 所有依赖这些模块的上游模块
- 最终只把 impacted modules 相关上下文喂给 Codex

**Scoring 层职责**:
- 决定风险级别（量化）
- score 决定"这 PR 危不危险"
- codex review 决定"具体危险在哪"

---

## 服务层职责说明

本阶段实现的服务层需要同时支持两个命令：

### `vibe inspect` - 信息提供
**职责**: 提供代码分析信息，输出结构化数据（JSON/YAML）

**调用关系**:
- `vibe inspect metrics` → metrics_service
- `vibe inspect structure` → structure_service
- `vibe inspect symbols [file]` → serena_service
- `vibe inspect commands [cmd]` → command_analyzer
- `vibe inspect pr 42` → serena_service + dag_service + pr_scoring_service

**输出要求**:
- 确定性操作（相同输入 → 相同输出）
- 结构化输出（JSON/YAML）
- 可被 `vibe review` 消费

**参数标准**: 所有子命令支持核心参数集（`--trace`, `--json`, `-y/--yes`），详见 [v3 命令参数标准](../v3/infrastructure/07-command-standards.md)

### `vibe review` - 代码审核
**职责**: 基于 `inspect` 提供的信息，调用 Codex 进行代码审核

**调用关系**:
- `vibe review pr 42` → 调用 `inspect pr 42` → 获取上下文 → Codex review

**实现方式**:
- 通过 subprocess 调用 `vibe inspect` 获取结构化数据
- 构建上下文，传递给 Codex

**参数标准**: 所有子命令支持核心参数集（`--trace`, `--json`, `-y/--yes`），详见 [v3 命令参数标准](../v3/infrastructure/07-command-standards.md)

---

## 实施顺序

Phase 1 完成后，进入 **Phase 2 - 审核流程集成**：
- 创建 `vibe review` 统一命令
- 集成评分系统到审核流程
- 创建审核命令与 GitHub API 集成