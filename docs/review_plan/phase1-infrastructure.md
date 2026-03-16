---
document_type: plan
title: Codex Review Phase 1 - 基础设施搭建
status: draft
author: Claude Sonnet 4.6
created: 2026-03-16
last_updated: 2026-03-16
related_docs:
  - docs/review_plan/codex-auto-review-plan.md
  - docs/references/codex-review.md
  - docs/references/codex-serena-intetration.md
  - docs/standards/serena-usage.md
  - docs/v3/implementation/03-coding-standards.md
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
    total_loc: 3000          # Python 总行数限制
    max_file_loc: 300        # 单文件最大行数
    min_tests: 5             # 最少测试数量

# 审核范围（适配 vibe-center 实际结构）
review_scope:
  critical_paths:            # 关键路径（重点审核）
    - "bin/"                 # CLI 入口
    - "lib/flow"             # Flow 核心逻辑
    - "lib/git"              # Git 操作
    - "lib/github"           # GitHub 集成
    - "scripts/python/vibe3/services/"  # v3 服务层

  public_api_paths:          # 公开 API（兼容性检查）
    - "bin/vibe"             # 主入口
    - "lib/flow.sh"          # Flow 公开接口
    - "scripts/python/vibe3/commands/"  # v3 命令层

# 质量标准
quality:
  test_coverage:
    services: 80             # Services 层 ≥ 80%
    clients: 70              # Clients 层 ≥ 70%
    commands: 60             # Commands 层 ≥ 60%
```

#### 1.2 实现任务

- [ ] 创建 `scripts/python/vibe3/config/settings.py`：
  - 使用 pydantic 定义配置模型
  - `CodeLimitsConfig` - 代码量限制
  - `ReviewScopeConfig` - 审核范围
  - `QualityConfig` - 质量标准
  - `VibeConfig` - 总配置

- [ ] 创建 `scripts/python/vibe3/config/loader.py`：
  - `load_config()` - 从 `.vibe/config.yaml` 加载配置
  - 支持默认值
  - 支持环境变量覆盖

- [ ] 更新 `metrics.sh` 硬编码参数：
  - 从配置读取限制值
  - 不再写死 `7000`、`300`、`20` 等数字

- [ ] 创建配置验证命令：
  - `vibe config check` - 验证配置文件
  - `vibe config show` - 显示当前配置

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

### 2. Serena Service（迁移 `serena_gate.py`）

**目标**: 迁移现有逻辑到 v3 架构，添加日志和错误处理

**现有代码**: `scripts/review-tools/serena_gate.py` (147 行)

**迁移到**: `scripts/python/vibe3/services/serena_service.py`

**改造内容**:
- ✅ 添加 loguru 日志
- ✅ 添加类型注解
- ✅ 统一异常处理
- ✅ 输出标准化（impact.json）

**实现任务**:
- [ ] 创建 `services/serena_service.py`
- [ ] 迁移 `extract_function_names()` 函数
- [ ] 迁移 `count_references()` 函数
- [ ] 封装为 `analyze_file_symbols()` 服务
- [ ] 添加 `logger.bind(domain="review", action="serena_analysis")`
- [ ] 添加异常处理（`logger.exception()`）
- [ ] 编写测试：`tests/services/test_serena_service.py`

---

### 3. Metrics Service（迁移 `metrics.sh`）

**目标**: Shell → Python，使用配置系统，消除硬编码

**现有代码**: `scripts/review-tools/metrics.sh` (186 行)

**迁移到**: `services/metrics_service.py` + `commands/metrics.py`

**改造内容**:
- ✅ 从配置读取限制值（不硬编码）
- ✅ 使用 v3 config 系统
- ✅ 添加日志和异常处理

**实现任务**:
- [ ] 创建 `services/metrics_service.py`
- [ ] 实现 `collect_shell_metrics()` - 从配置读取限制
- [ ] 实现 `collect_python_metrics()` - 从配置读取限制
- [ ] 添加日志和异常处理
- [ ] 创建 `commands/metrics.py` (typer 入口)
- [ ] 编写测试

---

### 4. Structure Service（迁移 `structure_summary.sh`）

**目标**: Shell → Python，添加日志

**现有代码**: `scripts/review-tools/structure_summary.sh` (169 行)

**迁移到**: `services/structure_service.py` + `commands/structure.py`

**实现任务**:
- [ ] 创建 `services/structure_service.py`
- [ ] 实现 `analyze_shell_file()`
- [ ] 实现 `analyze_python_file()`
- [ ] 添加日志和异常处理
- [ ] 创建 `commands/structure.py`
- [ ] 编写测试

---

### 5. DAG Service（新增）

**目标**: 分析模块依赖图，确认影响范围

**位置**: `services/dag_service.py`

**实现任务**:
- [ ] 创建 `services/dag_service.py`
- [ ] 实现 `build_module_graph()` - 解析 import
- [ ] 实现 `expand_impacted_modules()` - 扩展影响模块
- [ ] 添加日志和异常处理
- [ ] 编写测试

---

### 6. PR Scoring Service（新增）

**目标**: 根据 PR 多维度指标计算风险分数

**位置**: `services/pr_scoring_service.py`

**评分维度**（参考资料定义）:
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
- [ ] 创建 `services/pr_scoring_service.py`
- [ ] 实现 `calculate_risk_score()` - 计算风险分数
- [ ] 实现 `determine_risk_level()` - 判定风险等级
- [ ] 实现 `generate_score_report()` - 生成评分报告
- [ ] 添加日志和异常处理
- [ ] 编写测试：`tests/services/test_pr_scoring_service.py`

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

- [ ] 所有 Services 函数 ≤ 50 行
- [ ] 所有文件 ≤ 300 行
- [ ] 强制类型注解（pydantic + mypy）
- [ ] loguru 日志 + context binding
- [ ] 统一异常处理

### 测试覆盖

- [ ] Services 层测试覆盖率 ≥ 80%
- [ ] Clients 层测试覆盖率 ≥ 70%
- [ ] Commands 层测试覆盖率 ≥ 60%
- [ ] 所有测试通过：`pytest tests/`

### 功能验证

- [ ] 配置系统可以正常加载和验证
- [ ] 所有迁移的服务可以正常工作
- [ ] PR 评分系统可以正常计算风险分数
- [ ] 日志输出符合 v3 标准

---

## 迁移统计

| 原工具 | 原行数 | 迁移目标 | 预估行数 | 变化 |
|--------|--------|----------|----------|------|
| 配置系统 | - | `config/settings.py` + `loader.py` | ~200 | 新增 |
| `serena_gate.py` | 147 | `serena_service.py` | ~180 | +日志/类型 |
| `metrics.sh` | 186 | `metrics_service.py` + `commands/metrics.py` | ~280 | Shell→Python |
| `structure_summary.sh` | 169 | `structure_service.py` + `commands/structure.py` | ~260 | Shell→Python |
| 新增 DAG | - | `dag_service.py` | ~150 | 新功能 |
| 新增 Scoring | - | `pr_scoring_service.py` | ~200 | PR 风险评分 |

**总计**: ~1270 行 Python 代码

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
- `vibe inspect --metrics` → metrics_service
- `vibe inspect --structure` → structure_service
- `vibe inspect --symbols` → serena_service
- `vibe inspect pr 42` → serena_service + dag_service + pr_scoring_service

**输出要求**:
- 确定性操作（相同输入 → 相同输出）
- 结构化输出（JSON/YAML）
- 可被 `vibe review` 消费

### `vibe review` - 代码审核
**职责**: 基于 `inspect` 提供的信息，调用 Codex 进行代码审核

**调用关系**:
- `vibe review pr 42` → 调用 `inspect pr 42` → 获取上下文 → Codex review

**实现方式**:
- 通过 subprocess 调用 `vibe inspect` 获取结构化数据
- 构建上下文，传递给 Codex

---

## 实施顺序

Phase 1 完成后，进入 **Phase 2 - 审核流程集成**：
- 创建 `vibe review` 统一命令
- 集成评分系统到审核流程
- 创建审核命令与 GitHub API 集成