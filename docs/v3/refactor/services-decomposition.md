# V3 Services 模块拆分方案

> 注：本文是早期拆分草案。当前主线已经完成部分迁移：
> - `ai_service.py` 已迁到 `clients/ai_suggestion_client.py`
> - GitHub label CRUD 已迁到 `clients/github_labels.py`
> - label 状态机规则已迁到 `domain/state_machine.py`
> 阅读本文件时请以仓库当前代码结构为准。

**状态**: Ready
**目标**: 将 services/ 从 47 个平铺文件（7398 行）瘦身为职责清晰的结构，提升可读性
**原则**: 不破坏现有接口，不追求完美结构，最小风险逐步推进

---

## 背景

### 当前架构分层

```
commands/    <- CLI 入口（4544 行，37 个文件）
agents/      <- Agent 执行和 Pipeline（1456 行，13 个文件）
orchestra/   <- 工作流调度引擎（3677 行，22 个文件）
prompts/     <- 提示词渲染系统（878 行，9 个文件）
services/    <- 业务逻辑（7398 行，47 个文件）  <-- 问题所在
models/      <- 数据模型（1550 行，17 个文件）
```

### 现有问题

1. **规模失控**：services/ 是最大模块，混合了代码分析工具、业务逻辑、prompt 组装器
2. **无层次导航**：47 个文件平铺，新人难以定位
3. **职责混杂**：`check_service.py`（3 个 class）、`pr_scoring_service.py`（4 个 class）等
4. **Mixin 滥用**：check 系列有 2 个 mixin，继承链深

### 提取判断标准

> **只有当模块的依赖图不再指向 services/ 内部时，提取才有意义。**

- `analysis/`：纯工具，无业务耦合 → **值得提取**
- `check/`：依赖 flow/pr/handoff 数据 → 留在 services/
- `handoff/`：依赖 signature_service（被 flow/task/pr 共用）→ 留在 services/
- `context_builder*`：直接调用方是对应 agent → **并入 agents/**

---

## 最终方案

**只做两件事**，其余不动：

```
变动前                        变动后
services/ 47 个文件  -->      services/ ~19 个文件（核心业务）
                              analysis/ 15 个文件（代码分析工具）

agents/   13 个文件  -->      agents/   17 个文件（+4 个 prompt 组装器）
```

---

## 分步实施

每步独立 commit，可单步 revert。迁移期间用 shim 保持向后兼容。

---

### Step 1: 创建 `analysis/` 模块骨架

新建 `src/vibe3/analysis/__init__.py`，验证可导入。

---

### Step 2: 迁移代码分析工具至 `analysis/`

**迁移文件（15 个）**：

```
src/vibe3/analysis/
  __init__.py
  dag_service.py               <- services/dag_service.py
  structure_service.py         <- services/structure_service.py
  change_scope_service.py      <- services/change_scope_service.py
  serena_service.py            <- services/serena_service.py
  serena_file_analyzer.py      <- services/serena_file_analyzer.py
  command_analyzer.py          <- services/command_analyzer.py
  command_analyzer_helpers.py  <- services/command_analyzer_helpers.py
  coverage_service.py          <- services/coverage_service.py
  snapshot_service.py          <- services/snapshot_service.py
  snapshot_diff.py             <- services/snapshot_diff.py
  snapshot_diff_section.py     <- services/snapshot_diff_section.py
  inspect_output_adapter.py    <- services/inspect_output_adapter.py
  pre_push_test_selector.py    <- services/pre_push_test_selector.py
  pre_push_inspect_summary.py  <- services/pre_push_inspect_summary.py
  pre_push_scope.py            <- services/pre_push_scope.py
```

**迁移步骤**：
1. 逐文件复制至 `analysis/`，内部 import 路径改为 `vibe3.analysis.*`
2. `services/` 原路径留 shim（re-export）
3. 更新 `commands/inspect*.py`、`commands/pre_push*.py` 的 import 为 `vibe3.analysis.*`
4. 验证：`uv run mypy src/vibe3/analysis/ && uv run pytest tests/vibe3/analysis/ -q`

**对应测试文件同步移动**（`tests/vibe3/services/` → `tests/vibe3/analysis/`）：

```
test_dag_service.py
test_change_scope_service.py
test_command_analyzer.py
test_coverage_service.py
test_inspect_output_adapter.py
```

---

### Step 3: 迁移 prompt 组装器至 `agents/`

**背景**：

- `prompts/` = 渲染**机制**（PromptAssembler、变量注册表）
- `services/context_builder*` = 业务**内容**（为具体 agent 拼装 prompt 各节）

这 3 个文件的唯一直接调用方是对应的 agent：

```
agents/plan_agent.py   -> services/plan_context_builder.py
agents/run_agent.py    -> services/run_context_builder.py
agents/review_agent.py -> services/context_builder.py
```

**迁移文件（4 个）**：

```
src/vibe3/agents/
  plan_prompt.py           <- services/plan_context_builder.py（重命名）
  run_prompt.py            <- services/run_context_builder.py（重命名）
  review_prompt.py         <- services/context_builder.py（重命名，消除歧义）
  review_pipeline_helpers.py <- services/review_pipeline_helpers.py
```

`spec_ref_service.py` 和 `ai_service.py` 留在 `services/`（多处调用，属通用工具）。

**迁移步骤**：
1. 将 4 个文件移至 `agents/`，重命名
2. `services/` 原路径留 shim
3. 更新 `agents/plan_agent.py`、`agents/run_agent.py`、`agents/review_agent.py` 内部 import
4. 验证无循环依赖（agents/ -> services/ 方向，不反向）
5. 验证：`uv run mypy src/vibe3/agents/ && uv run pytest tests/vibe3/agents/ -q`

**对应测试文件同步移动**（`tests/vibe3/services/` → `tests/vibe3/agents/`）：

```
test_context_builder.py        -> test_review_prompt.py
test_plan_context_builder.py   -> test_plan_prompt.py
test_plan_run_context_builder.py -> test_run_prompt.py
```

---

### Step 4: check_service mixin flatten

**不迁移模块**，仅在 `services/` 内部整理：

- 将 `check_execute_mixin.py`（176 行）inline 进 `check_service.py`
- `check_remote_index_mixin.py` 视内容决定是否 inline
- 从 3 个文件缩为 1-2 个，消除无意义的 mixin 层

**验证**：`uv run pytest tests/vibe3/services/ -k check -q`

---

### Step 5: 清理 shim 文件

在前 4 步全部通过后，删除所有 shim：

从 `services/` 删除（已移至 `analysis/`）：
- `dag_service.py`、`structure_service.py`、`change_scope_service.py`
- `serena_service.py`、`serena_file_analyzer.py`
- `command_analyzer.py`、`command_analyzer_helpers.py`
- `coverage_service.py`
- `snapshot_service.py`、`snapshot_diff.py`、`snapshot_diff_section.py`
- `inspect_output_adapter.py`
- `pre_push_test_selector.py`、`pre_push_inspect_summary.py`、`pre_push_scope.py`

从 `services/` 删除（已移至 `agents/`）：
- `context_builder.py`、`plan_context_builder.py`、`run_context_builder.py`
- `review_pipeline_helpers.py`

**验收**：`uv run mypy src/vibe3` 零错误，`uv run pytest` 全部通过。

---

## 迁移后目录对比

**services/ 保留文件（~19 个）**：

```
services/
  flow_service.py              # 核心状态机
  flow_lifecycle.py            # FlowService lifecycle mixin
  flow_query_mixin.py          # FlowService query mixin
  flow_projection_service.py   # 流程投影聚合
  task_service.py              # 任务 CRUD
  task_usecase.py              # 任务 usecase
  task_binding_guard.py        # 任务绑定守卫
  handoff_service.py           # handoff 持久化
  handoff_recorder_unified.py  # 统一记录
  signature_service.py         # 签名计算（跨 service 共用）
  pr_service.py                # PR 核心操作
  pr_utils.py                  # PR 工具函数
  pr_scoring_service.py        # PR 风险评分
  label_service.py             # GitHub label 状态机
  state_sync_ports.py          # 状态同步 port 定义
  milestone_service.py         # milestone 操作
  version_service.py           # 版本计算
  async_execution_service.py   # 异步执行
  execution_lifecycle.py       # 执行生命周期
  check_service.py             # 一致性检查（mixin flatten 后）
  ai_service.py                # 文本生成（通用工具）
  spec_ref_service.py          # spec 引用解析（通用工具）
```

**tests/ 同步迁移**：

```
tests/vibe3/
  services/    <- 保留核心业务测试（flow/task/pr/handoff/check）
  analysis/    <- 新增，代码分析工具测试（从 services/ 移来）
  agents/      <- 已有，扩充 prompt 组装器测试（从 services/ 移来）
```

---

## 风险评估

| 步骤 | 风险 | 缓解措施 |
|------|------|---------|
| Step 1 骨架 | 无 | - |
| Step 2 analysis 迁移 | 低（工具性，无业务耦合） | shim 过渡 |
| Step 3 prompt 迁移入 agents/ | 中（rename + 移动，需验证无循环依赖） | shim 过渡 + mypy |
| Step 4 mixin flatten | 低（服务内部整理） | 测试覆盖先行 |
| Step 5 清理 shim | 中（需确认无遗漏 import） | mypy + 全量测试 |

---

## 验收标准

- `uv run mypy src/vibe3` 零错误
- `uv run pytest` 全部通过
- `services/` 文件数 <= 22
- `analysis/` 可独立导入，无循环依赖
- `agents/` 依赖方向保持单向（agents -> services，不反向）
- 无业务逻辑改动（纯结构重组）
