# Services/Check

Pre-push 检查、一致性验证、自动修复、分支清理服务。

## 职责

- Pre-push 检查：验证 handoff store 一致性
- 一致性验证：检查 flow state、PR state、issue state、label constraints
- 自动修复：修复不一致的状态（label、flow status）
- 分支清理：清理 terminal flows（done/aborted）和过期资源（worktrees、branches）
- PR 状态处理：检测 PR merged/closed，触发 flow 状态转变
- Remote index 同步：从 GitHub PR 初始化 flow_state（back-filling task_issue_number）

## 文件列表

| 文件 | 行数 | 职责 |
|------|------|------|
| pr_service.py | 743 | PR 状态变更处理（merged/closed → flow status） |
| service.py | 668 | 主检查服务（verify、auto-fix、rule chain） |
| cleanup.py | 600 | Terminal flow 清理（done/aborted）和过期资源清理 |
| rule_checks.py | 520 | 检查规则（从 _check_branch 提取的独立规则） |
| label_constraints.py | 193 | 数据驱动的 label 约束系统 |
| remote.py | 171 | Remote index 同步（init_remote_index） |
| lock.py | 69 | Branch-level lock（防止并发 check） |
| state_label_recovery.py | 22 | State label 恢复辅助 |
| __init__.py | 55 | 公共 API 导出（lazy import） |

截至 2026-06，总计 8 文件，约 2986 行代码（不含 `__init__.py`）。

## 架构说明

### Check Pipeline 设计

Check 模块采用 pipeline 架构，按以下顺序执行：

```
check_lock (acquire)
    ↓
verify (branch consistency)
    ↓
auto-fix (label、flow status)
    ↓
cleanup (terminal flows、expired resources)
    ↓
check_lock (release)
```

**Pipeline 阶段**：

1. **Lock**：`lock.py` 提供分支级锁，防止并发 check
   - 使用 `fcntl.flock`（非阻塞）
   - Lock file: `.git/vibe3/locks/check-<branch>.lock`
   - 自动释放（process exit）

2. **Verify**：`service.py` 验证分支一致性
   - PR terminal state（merged/closed）
   - Closed task issue
   - Orphaned flow
   - Missing state label
   - Label constraints

3. **Auto-fix**：自动修复不一致
   - Label constraints violations
   - Missing state labels
   - Flow status mismatches

4. **Cleanup**：`cleanup.py` 清理资源
   - Terminal flows（done/aborted）
   - Expired agent worktrees（> 7 days）
   - Expired remote branches（> 7 days）
   - Expired local branches（> 7 days）

### Rule Chain Pattern

`rule_checks.py` 实现规则链模式，从 `_check_branch` 提取独立规则：

**核心规则**：
- `rule_pr_terminal_state`：PR merged/closed → mark flow aborted
- `rule_closed_issue_sync`：Closed task issue → mark flow aborted
- `rule_orphaned_flow`：Orphaned flow（> 100 commits behind main）→ mark aborted
- `rule_missing_state_label`：Missing state label → recover or warn
- `rule_label_constraints`：Label constraints violations → auto-fix

**执行方式**：
- 每个规则返回 `CheckResult | None`
- 返回 `CheckResult` 表示 handled（short-circuit）
- 返回 `None` 表示 continue to next rule

**CheckContext**：
- 共享状态对象，传递给所有规则
- 包含 branch、flow_data、issue_labels 等信息

### Data-Driven Label Constraints

`label_constraints.py` 实现数据驱动的 label 约束系统：

**LabelConstraint 结构**：
- `name`：约束标识符
- `description`：人类可读描述
- `when`：触发条件（Python expression string）
- `forbidden_groups`：禁止的 label groups（支持 `state/*` 通配符）
- `max_from_group`：每组最多允许的 label 数量
- `action`：违反约束时的操作

**约束示例**：
- `single_state_label`：最多一个 `state/*` label
- `no_state_without_assignee`：无 assignee 时禁止 `state/*`
- `scanned_forbids_state`：`orchestra-scanned` 禁止 `state/*`
- `ready_requires_assignee`：`state/ready` 需要 assignee

**验证方式**：
- `check_constraints()` 验证 issue labels
- 支持 glob-style group names（`state/*`）

### PR State Change Detection

`pr_service.py` 处理 PR 状态变更：

**核心职责**：
- 检测 PR merged/closed 状态变更
- 处理 merged PR：mark flow done，auto-close linked issues
- 处理 closed PR：reset issue to READY，clean up flow scene
- 幂等性保护：避免重复处理

**幂等性实现**：
- `_already_handled_pr_closed()` 检查是否已处理
- 比较 `flow_state.updated_at` 和 `pr.closed_at`
- 通过 `initiated_by` 字段判断

### Terminal Flow Cleanup

`cleanup.py` 清理 terminal flows（done/aborted）：

**done vs aborted**：
- **done**：清理物理资源，soft-delete flow record
- **aborted**：清理所有内容（包括 flow record），允许 issue 重启

**清理操作**：
- Worktree deletion
- Local branch deletion
- Remote branch deletion
- Flow record removal

**Live session 保护**：
- 跳过有 live session 的分支
- `_get_branches_with_live_sessions()` 批量查询

### Branch-Level Locking

`lock.py` 实现分支级锁：

**设计目标**：防止同一分支的并发 check 操作

**实现方式**：
- 使用 `fcntl.flock`（非阻塞）
- Lock file: `.git/vibe3/locks/check-<branch>.lock`
- Context manager：自动释放

**限制**：
- 不支持 Windows（`fcntl.flock`）
- Lock 在 process exit 时自动释放

### 设计原则

- **Rule chain**：从 `_check_branch` 提取独立规则，short-circuit 执行
- **Data-driven constraints**：label 约束以数据形式定义，易于扩展
- **幂等性保护**：PR state change 检测避免重复处理
- **Live session 保护**：cleanup 跳过有 live session 的分支
- **Branch-level lock**：防止并发 check，避免竞态条件

## 公共 API

`__init__.py` 导出以下 5 个符号：

### 服务类

- **CheckService**: 主检查服务（verify、auto-fix、rule chain）
- **CheckCleanupService**: Terminal flow 清理和过期资源清理
- **CheckPRService**: PR 状态变更处理

### 结果类型

- **CheckResult**: 检查结果（is_valid、issues、warnings、branch）
- **InitResult**: Remote index 初始化结果（total_flows、updated、skipped、unresolvable）

## 内部依赖

```
check/
├── service.py → pr_service.py (CheckPRService)
├── service.py → lock.py (check_lock)
├── service.py → remote.py (CheckRemote, issue_state_from_payload)
├── service.py → rule_checks.py (rules)
├── cleanup.py → flow/cleanup.py (FlowCleanupService)
├── cleanup.py → orchestra/cleanup.py (ExpiredResourceCleanupService)
├── pr_service.py → flow/status.py (FlowStatusService)
├── pr_service.py → task (TaskService)
└── label_constraints.py → 无外部依赖（纯数据驱动）
```

**循环依赖检查**：✅ 无循环依赖

**跨模块依赖**：
- `service.py` → `services/flow/status.py`（FlowStatusService）
- `service.py` → `services/pr/service.py`（PRService）
- `cleanup.py` → `services/flow/cleanup.py`（FlowCleanupService）
- `cleanup.py` → `services/orchestra/cleanup.py`（ExpiredResourceCleanupService）

## 外部依赖

- **clients/**: GitClient（branch/worktree 操作）、GitHubClient（PR/issue 查询）、SQLiteClient（flow_state）、load_sync_rules
- **config/**: VibeConfig（protected branches、check_cleanup config）
- **models/**: CheckResult、IssueState、PRState、PRResponse、IssueLink
- **services/flow/**: FlowStatusService、FlowCleanupService
- **services/pr/**: PRService
- **services/task/**: TaskService、TaskResumeOperations
- **services/shared/**: labels（normalize_labels）

## 被依赖

- **commands/**: check.py、check_support.py、common.py
- **orchestra/**: dispatch_coordinator_factory.py、domain_types.py、protocols.py、remote_check.py
- **runtime/**: protocols.py、periodic_check_executor.py
- **domain/**: dispatch_coordinator.py、dispatch_health.py、dispatch_queue_maintenance.py
- **server/**: registry.py
- **clients/**: sync_rules.py

约 15 个文件引用。

## 架构演变说明

### Rule Extraction from _check_branch

**早期设计**：`_check_branch` 包含所有检查逻辑（monolithic）

**当前设计**：
1. 提取独立规则到 `rule_checks.py`
2. 每个规则返回 `CheckResult | None`
3. Short-circuit 执行（handled 则停止）
4. `CheckContext` 共享状态

### Data-Driven Label Constraints

**设计目标**：避免 hard-coded label 检查逻辑

**实现方式**：
1. `LabelConstraint` 数据结构定义约束
2. `check_constraints()` 验证 labels
3. 支持 glob-style group names（`state/*`）
4. 约束以数据形式定义，易于扩展和测试

### Terminal Flow Cleanup 演进

**早期设计**：仅清理 done flows

**当前设计**：
1. done 和 aborted 都清理物理资源
2. aborted 额外删除 flow record（允许 issue 重启）
3. 集成 expired resource cleanup（worktrees、branches）
4. Live session 保护

### PR State Change 检测设计

**设计目标**：检测 PR merged/closed 并触发 flow 状态转变

**实现方式**：
1. `CheckPRService` 处理 PR state changes
2. 幂等性保护（避免重复处理）
3. Merged → mark done + auto-close issues
4. Closed → abort + cleanup

## 设计原则

- **Rule chain pattern**：从 monolithic `_check_branch` 提取独立规则
- **Data-driven constraints**：label 约束以数据形式定义，易于扩展
- **幂等性保护**：PR state change 检测避免重复处理
- **Live session 保护**：cleanup 跳过有 live session 的分支
- **Branch-level lock**：防止并发 check，避免竞态条件
- **Pipeline 架构**：lock → verify → auto-fix → cleanup
- **Short-circuit execution**：规则 handled 后停止执行