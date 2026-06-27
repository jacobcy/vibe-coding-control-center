# PR Service Module

> **Module**: `vibe3.services.pr` | **Epic**: #3178 | **Phase**: 3/10 — 服务层 A
> **Last Updated**: 2026-06-27

## 核心职责

PR Service 模块负责管理 PR 的完整生命周期，包括：

- **PR 创建**：创建 PR、构建 PR body、解析 base 分支
- **PR 评分**：风险评分、critical files 分析、commit count 统计
- **PR 合并**：合并检查、冲突检测、merge 操作
- **PR Ready**：Ready 检查、状态验证
- **风险分析**：变更影响分析、风险等级判定
- **裁决服务**：Review 裁决、merge 裁决、audit 引用检查

## 文件列表

### 核心服务文件

| 文件 | 行数 | 职责 |
|------|------|------|
| `service.py` | 603 | PR 主服务（CRUD、merge、状态同步） |
| `create.py` | 242 | PR 创建用例编排（create PR flow） |
| `ready.py` | 45 | PR ready 用例（ready check） |

### 分析与评分

| 文件 | 行数 | 职责 |
|------|------|------|
| `analysis.py` | 242 | 变更影响分析（critical files、risk score、commit count） |

### 分支解析

| 文件 | 行数 | 职责 |
|------|------|------|
| `base_resolution.py` | 194 | Base 分支解析（resolve base branch） |
| `resolver.py` | 194 | 分支解析工具（resolve command branch、resolve from PR） |

### Review 与裁决

| 文件 | 行数 | 职责 |
|------|------|------|
| `review.py` | 144 | Review briefing 编排（构建 review briefing） |
| `verdict_service.py` | 185 | 裁决服务（review verdict、merge verdict） |
| `verdict_policy.py` | 34 | 裁决策略函数（passes_review、blocks_merge、requires_audit_ref） |

### 辅助服务

| 文件 | 行数 | 职责 |
|------|------|------|
| `loc_comment.py` | 94 | LOC 摘要评论服务（生成 LOC comment） |
| `utils.py` | 198 | 构建辅助（build PR body、metadata、冲突检查） |

**总计**: 2,322 行（含 `__init__.py`）

## 公开 API

### Core Service

- `PRService` — 主服务入口（CRUD、merge、状态同步）
- `PRCreateUsecase` — PR 创建用例
- `PRCreateResult` — PR 创建结果
- `PrReadyUsecase` — PR ready 用例
- `PrReadyAbortedError` — PR ready 中止异常

### Usecases

- `BaseResolutionUsecase` — Base 分支解析用例

### Analysis

- `analyze_critical_files` — 分析关键文件
- `build_pr_analysis` — 构建 PR 分析
- `calculate_pr_risk_score` — 计算 PR 风险评分
- `filter_critical_files` — 过滤关键文件
- `get_pr_changed_files` — 获取 PR 变更文件列表
- `get_pr_commit_count` — 获取 PR commit 数量
- `get_recent_commits` — 获取最近 commits

### Resolution

- `resolve_command_branch` — 解析命令行分支参数
- `resolve_branch_from_pr` — 从 PR 解析分支

### Verdict

- `VerdictService` — 裁决服务
- `passes_review` — 判断是否通过 review
- `blocks_merge` — 判断是否阻塞 merge
- `requires_audit_ref` — 判断是否需要 audit 引用

### Risk Analysis Types (Passthrough from `vibe3.analysis`)

- `PRDimensions` — PR 维度类型
- `RiskLevel` — 风险等级枚举
- `RiskScore` — 风险评分类型
- `calculate_risk_score` — 计算风险评分
- `determine_risk_level` — 确定风险等级
- `generate_score_report` — 生成评分报告

### Utilities

- `PRLocCommentService` — LOC 评论服务
- `PRReviewBriefingService` — Review briefing 服务
- `build_pr_body` — 构建 PR body
- `check_upstream_conflicts` — 检查上游冲突
- `get_metadata_from_flow` — 从 flow 获取 metadata

### Broken Reference ⚠️

- `PRScoringError` — **FINDING**: 声明在 `_SYMBOL_MODULES` 中指向不存在的 `vibe3.services.pr.scoring` 模块。实际定义位于 `vibe3.analysis.pr_scoring.py`，且已通过 `vibe3.analysis` 正确导出。这是 **双重导出 + broken module reference** 反模式。

## 依赖关系

### 该模块依赖

- **analysis 层**: `vibe3.analysis` (PR 评分、风险分析)
- **domain 层**: `vibe3.domain.pr` (PR 聚合根)
- **models 层**: `vibe3.models` (数据模型)
- **clients 层**: `vibe3.clients.github` (GitHub API 客户端)
- **config 层**: `vibe3.config` (配置管理)
- **services 层内部**:
  - `services.flow` (Flow 状态检查)
  - `services.issue` (Issue 服务)
  - `services.task` (Task 服务)

### 被依赖

- **commands 层**: `commands.pr_create`、`commands.pr_merge`、`commands.pr_ready` 等命令入口
- **roles 层**: `roles.run` (PR 创建和合并)、`roles.review` (PR review)
- **services 层内部**:
  - `services.check` (Check 服务调用 PR 创建)
  - `services.flow` (Flow 状态检查时调用 PR 查询)

## 与服务层其他模块的关系

### 协作模式

1. **与 flow 模块**:
   - PR 创建依赖 Flow 状态 (PRCreateUsecase 检查 flow ready)
   - PR merge 触发 Flow 状态转变 (merge → flow done)
   - PR ready 检查 Flow 是否 ready

2. **与 task 模块**:
   - PR 关联 Task (PR body 包含 task 信息)
   - PR merge 更新 Task 状态

3. **与 issue 模块**:
   - PR 关联 Issue (PR body 包含 issue 信息)
   - PR merge 触发 Issue 状态更新

4. **与 analysis 模块**:
   - PR 评分使用 `vibe3.analysis` 模块
   - Passthrough re-export 6 个 analysis 符号（PRDimensions、RiskLevel、RiskScore、calculate_risk_score、determine_risk_level、generate_score_report）

## 架构约束

- **Lazy import**: 使用 `__getattr__` 避免循环依赖
- **Usecase 编排**: PR 创建流程使用 usecase 层编排（PRCreateUsecase、BaseResolutionUsecase）
- **Passthrough re-export**: 从 `vibe3.analysis` 穿透重导出 6 个符号（有意设计，方便上层使用）

## 已知问题

### Broken Module Reference ⚠️

- `PRScoringError` 在 `_SYMBOL_MODULES` 中指向 `vibe3.services.pr.scoring`（不存在）
- 实际定义位于 `vibe3.analysis.pr_scoring.py`，已正确导出
- **Dual export + broken reference** 反模式
- **Impact**: `from vibe3.services.pr import *` 会抛出 `ModuleNotFoundError`
- **建议**: 从 `services/pr/__all__` 移除 `PRScoringError`，或创建正确的穿透重导出路径

### Passthrough Re-export (有意设计)

- 6 个 analysis 符号（PRDimensions、RiskLevel、RiskScore 等）从 `vibe3.analysis` 穿透重导出
- 这是有意设计，让上层无需直接依赖 `analysis` 模块
- 外部引用验证：有 3 个外部文件引用这些符号（合理）

---

**参考**: 基础层 README (#3179)、外部对接层 README (#3180)