# Services/Issue

Issue 失败处理、Flow 映射、标题缓存、dispatch eligibility 服务。

## 职责

- Issue 失败处理：处理 executor/manager/planner/reviewer 运行失败或无进展
- Flow 映射：issue number ↔ canonical branch name 双向映射
- 标题缓存：统一 issue title 缓存服务（branch-based）
- Dispatch eligibility：判断 issue 是否可被 dispatch（通过 IssueDispatchPolicy）
- Issue body 管理：解析/渲染/合并 issue body 的 managed section（flow-state projection）

## 文件列表

| 文件 | 行数 | 职责 |
|------|------|------|
| failure.py | 360 | Issue fail/block 状态转变函数族 |
| flow.py | 284 | Issue-to-flow 映射服务（branch naming convention） |
| title_cache.py | 335 | Issue title 缓存服务（branch-based） |
| body.py | 125 | Issue body managed section 解析/渲染/合并 |
| context.py | 50 | Issue 上下文加载（load_issue_info） |
| dispatch_policy.py | 33 | Issue dispatch eligibility 判断（IssueDispatchPolicy） |
| collection.py | 38 | Issue collection 服务（re-export） |
| __init__.py | 126 | 公共 API 导出（lazy import） |

截至 2026-06，总计 7 文件，约 1351 行代码（含 `__init__.py`）。不含 `__init__.py` 为 1225 行。

## 架构说明

### Failure 函数族设计

`failure.py` 提供统一的 issue 状态标记接口：

**核心函数**：
- **mark_issue**：统一 fail/block 接口（根据 action 参数选择）
  - `action="fail"`：runtime failures（记录 timeline event，不写 GitHub comment）
  - `action="block"`：business blocks（blocked_reason + label）

**角色映射**（`_ROLE_MAP`）：
- `executor` → `run`
- `reviewer` → `review`
- `planner` → `plan`

**Fail 函数族**：
- `fail_executor_issue`：executor 运行失败
- `fail_manager_issue`：manager 运行失败
- `fail_planner_issue`：planner 运行失败
- `fail_reviewer_issue`：reviewer 运行失败

**Block 函数族**：
- `block_executor_noop_issue`：executor 无进展
- `block_manager_noop_issue`：manager 无进展
- `block_planner_noop_issue`：planner 无进展
- `block_reviewer_noop_issue`：reviewer 无进展
- `block_issue`：通用 block 函数

**依赖方向**：failure → flow（单向，不可反转）

### Branch Naming Convention

`flow.py` 使用 `ConventionResolver` 实现分支命名约定：

**核心方法**：
- `canonical_branch_name(issue_number)`：生成 canonical task branch
  - Example: `task/issue-372`
- `parse_issue_number(branch)`：解析 canonical task branch
  - 仅匹配严格 canonical 格式（如 `task/issue-372`）
  - 不匹配带后缀的分支（如 `task/issue-372-worktree`）
- `parse_issue_number_any(branch)`：解析任意 task/dev issue branch
  - 支持 `task/issue-N` 和 `dev/issue-N`

**设计演进**：
- 早期：hardcoded regex patterns（分散在 manager, orchestra, services）
- 当前：集中到 `IssueFlowService`，使用 `ConventionResolver`

### Title Cache 设计

`title_cache.py` 提供统一 issue title 缓存：

**关键设计决策**：
- **Primary key**：branch（DB 存储使用 branch）
- **参数约定**：所有方法使用 `branch` 作为标准参数
- **Issue number 转换**：仅在 command 层，不在 cache service

**Cache 策略**：
- `get_title(branch)`：仅查缓存
- `get_title_with_fallback(branch)`：cache-first + GitHub API fallback
- `update_title(branch, title)`：更新缓存

**更新时机**：
- flow init
- PR creation
- title fetch

### Issue Body Managed Section

`body.py` 管理 issue body 的 managed section（flow-state projection）：

**Managed Section 标记**：
- Start: `<!-- vibe3-flow-state-start -->`
- End: `<!-- vibe3-flow-state-end -->`

**核心函数**：
- `parse_projection(body)`：从 issue body 解析 `FlowStateProjection`
  - 解析 state、blocked_by、blocked_reason、dependencies
- `render_projection(proj)`：渲染 managed section 文本
- `merge_projection(body, proj)`：合并 projection 到 issue body（替换 managed section）

### Dispatch Eligibility

`dispatch_policy.py` 判断 issue 是否可被 dispatch：

**核心类**：
- **IssueDispatchPolicy**：判断 issue 是否符合 dispatch 条件
- **DispatchExclusion**：记录 dispatch exclusion（不可 dispatch 的原因）

**设计目标**：避免将不符合条件的 issue dispatch 给 agent

### 设计原则

- **参数约定统一**：所有服务使用 `branch` 作为标准参数（title cache）
- **集中化逻辑**：将分散的 branch naming 集中到 `IssueFlowService`
- **Lazy import**：避免循环依赖（`__init__.py`）
- **单向依赖**：failure → flow，避免反转
- **ConventionResolver**：使用约定解析器，支持多 profile

## 公共 API

`__init__.py` 导出以下 21 个符号：

### 服务类

- **IssueFlowService**: Issue-to-flow 映射服务（branch naming）
- **IssueCollectionService**: Issue collection 服务
- **IssueTitleCacheService**: Issue title 缓存服务
- **IssueDispatchPolicy**: Issue dispatch eligibility 判断
- **DispatchExclusion**: Dispatch exclusion 记录

### Body 函数

- **parse_projection**: 解析 issue body managed section
- **render_projection**: 渲染 managed section 文本
- **merge_projection**: 合并 projection 到 issue body

### Failure 函数

- **fail_executor_issue**: Executor 运行失败
- **fail_manager_issue**: Manager 运行失败
- **fail_planner_issue**: Planner 运行失败
- **fail_reviewer_issue**: Reviewer 运行失败
- **fail_issue**: 通用 fail 函数（legacy）

### Block 函数

- **block_executor_noop_issue**: Executor 无进展
- **block_manager_noop_issue**: Manager 无进展
- **block_planner_noop_issue**: Planner 无进展
- **block_reviewer_noop_issue**: Reviewer 无进展
- **block_issue**: 通用 block 函数

### Flow 函数

- **resolve_issue_branch_input**: 解析 issue branch 输入（branch or issue_number）
- **iter_issue_branch_candidates**: 迭代 issue branch candidates（支持 worktree）

### Context 函数

- **load_issue_info**: 加载 issue 上下文（从 GitHub 或缓存）

### 其他

- **mark_issue**: 统一 issue 状态标记接口（fail/block）

## 内部依赖

```
issue/
├── failure.py → flow.py (IssueFlowService) [单向，不可反转]
├── title_cache.py → clients (GitHubClient, SQLiteClient)
├── flow.py → config (ConventionResolver, VibeConfig)
├── flow.py → config (load_orchestra_config)
├── body.py → models (FlowStateProjection)
├── context.py → clients (GitHubClient, SQLiteClient)
└── dispatch_policy.py → models (DispatchExclusion)
```

**循环依赖检查**：✅ 无循环依赖

**跨模块依赖**：
- `failure.py` → `services/issue/flow.py`（IssueFlowService）
- `__init__.py` → `services/shared/branch_resolver.py`（resolve_issue_branch_input, iter_issue_branch_candidates）

## 外部依赖

- **clients/**: GitHubClient（issue 查询）、SQLiteClient（flow_state、context_cache）
- **config/**: VibeConfig、ConventionResolver（branch convention）、load_orchestra_config
- **models/**: FlowStateProjection（projection 模型）、DispatchExclusion、OrchestraConfig
- **exceptions/**: InvalidBranchLinkError
- **services/shared/**: branch_resolver（resolve_issue_branch_input, iter_issue_branch_candidates）

## 被依赖

- **commands/**: task.py、flow_lifecycle.py、flow_status.py、pr_query.py、internal.py、flow_status_helpers.py
- **execution/**: issue_role_sync_runner.py、job_executor.py
- **services/flow/**: status.py、rebuild.py、block_mixin.py、cleanup.py、projection.py、transition.py、blocked_state_io.py、recovery.py、status_resolver.py
- **services/check/**: cleanup.py、service.py、pr_service.py
- **services/orchestra/**: orchestrator.py、coordination.py
- **services/shared/**: status_query.py、branch_resolver.py、labels.py、roles.py
- **domain/**: handlers/dispatch.py、handlers/issue_state_dispatch.py、flow_manager.py、dispatch_coordinator.py、qualify_gate.py、qualify_gate_support.py、dispatch_queue_collection.py
- **roles/**: manager.py、plan.py、review.py、run_request.py、supervisor.py

约 40 个文件引用。

## 架构演变说明

### Failure 系统演进

**早期设计**：分散的 fail/block 函数，无统一接口

**当前设计**：
1. `mark_issue` 提供统一 fail/block 接口
2. 根据 `action` 参数选择行为（fail vs block）
3. Role 映射统一处理（executor → run）
4. 单向依赖 failure → flow（避免循环）

### Branch Naming 集中化

**早期设计**：
- Hardcoded regex patterns 分散在 manager、orchestra、services
- `FlowManager._canonical_task_branch()`
- `StatusQueryService.is_task_branch()`

**当前设计**：
1. `IssueFlowService` 集中所有 branch naming 逻辑
2. 使用 `ConventionResolver` 支持多 profile
3. 提供严格 canonical matching 和宽松 matching 两套方法

### Title Cache 统一化

**设计目标**：避免 title 缓存逻辑分散

**实现方式**：
1. `IssueTitleCacheService` 作为唯一 title 缓存入口
2. Primary key 使用 branch（与 DB 存储一致）
3. 参数约定统一（所有方法使用 `branch`）
4. Issue number 转换仅在 command 层（不在 service 层）

### Body Managed Section

**设计目标**：管理 issue body 的 flow-state projection

**实现方式**：
1. Managed section 通过 HTML comment 标记
2. `parse_projection` / `render_projection` / `merge_projection` 三函数
3. `FlowStateProjection` 模型（state, blocked_by, blocked_reason, dependencies）

## 设计原则

- **参数约定统一**：所有服务使用 `branch` 作为标准参数（title cache）
- **集中化逻辑**：将分散的 branch naming、title cache 集中到统一服务
- **Lazy import**：避免循环依赖（`__init__.py`）
- **单向依赖**：failure → flow（不可反转）
- **ConventionResolver**：使用约定解析器，支持多 profile
- **Managed Section**：issue body 通过 HTML comment 标记管理区域