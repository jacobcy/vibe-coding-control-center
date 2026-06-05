# Orchestra Configuration Guide

本文档详细说明 Orchestra 调度器的配置选项。

配置真源为 `config/settings.yaml` 中的 `orchestra` 部分。

## 配置概览

Orchestra 配置模型定义在 `src/vibe3/models/orchestra_config.py` 中，包含以下主要配置组：

- **基础配置**：服务启用、端口、轮询间隔等
- **容量控制**：并发限制、熔断器等
- **调度触发**：assignee dispatch、PR review dispatch 等
- **周期性服务**：governance、supervisor、periodic check 等
- **队列管理**：queue_recollect（队列优先级刷新）

## 基础配置

### 核心字段

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| enabled | bool | true | 是否启用 Orchestra 服务 |
| polling_interval | int | 900 | Heartbeat 轮询间隔（秒） |
| debug_polling_interval | int | 60 | Debug 模式下的轮询间隔 |
| debug_max_ticks | int | 10 | Debug 模式最大 tick 数 |
| debug | bool | false | 是否启用 debug 模式 |
| scene_base_ref | str | "origin/main" | 场景基础分支引用 |
| repo | str \| None | None | 目标仓库（格式："owner/repo"） |
| max_concurrent_flows | int | 3 | 最大并发 flow 数量 |
| async_execution | bool | true | 是否异步执行 manager |
| dry_run | bool | false | 试运行模式（不执行实际操作） |
| pid_file | Path | ~/.vibe/orchestra.pid | PID 文件路径 |
| port | int | 8080 | HTTP 服务端口 |
| port_range_max | int \| None | None | 端口自动发现范围上限 |
| bot_username | str \| None | None | Bot 的 GitHub 用户名 |
| manager_usernames | tuple[str, ...] | () | Manager 用户名列表 |
| max_retry_budget | int | 3 | 队列条目最大重试次数 |

### 使用示例

```yaml
orchestra:
  enabled: true
  repo: "owner/repo"
  port: 8080
  polling_interval: 900
  max_concurrent_flows: 5
  manager_usernames:
    - "vibe-manager"
    - "ai-agent"
```

## 容量控制配置

### 并发控制

```yaml
orchestra:
  max_concurrent_flows: 3
  governance_max_concurrent: 1
  supervisor_max_concurrent: 2
```

### 熔断器配置

#### circuit_breaker

熔断器配置，防止连续失败导致系统不稳定。

**字段说明**：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| enabled | bool | true | 是否启用熔断器 |
| failure_threshold | int | 4 | 触发熔断的连续失败次数 |
| cooldown_seconds | int | 300 | 熔断持续时间（秒） |
| half_open_max_tests | int | 1 | 半开状态允许的测试请求数 |

**配置示例**：

```yaml
orchestra:
  circuit_breaker:
    enabled: true
    failure_threshold: 4
    cooldown_seconds: 300
    half_open_max_tests: 1
```

## 调度触发配置

### assignee_dispatch

基于 Issue assignee 触发 manager 执行。

**字段说明**：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| enabled | bool | true | 是否启用 assignee dispatch |
| use_worktree | bool | true | 是否在 worktree 中执行 |
| agent | str \| None | None | Agent 预设名称 |
| backend | str \| None | None | Backend 覆盖 |
| model | str \| None | None | Model 覆盖 |
| timeout_seconds | int | 3600 | 执行超时时间（秒） |
| prompt_template | str | "orchestra.assignee_dispatch.manager" | Prompt 模板路径 |
| token_env | str \| None | "VIBE_MANAGER_GITHUB_TOKEN" | Manager 专用 GitHub token 环境变量 |

**配置示例**：

```yaml
orchestra:
  assignee_dispatch:
    enabled: true
    use_worktree: true
    timeout_seconds: 3600
    token_env: "VIBE_MANAGER_GITHUB_TOKEN"
```

### pr_review_dispatch

基于 PR reviewer 触发 review 执行。

**字段说明**：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| enabled | bool | true | 是否启用 PR review dispatch |
| async_mode | bool | true | 是否异步执行 |
| use_worktree | bool | false | 是否在 worktree 中执行 |

**配置示例**：

```yaml
orchestra:
  pr_review_dispatch:
    enabled: true
    async_mode: true
    use_worktree: false
```

### state_label_dispatch

基于状态标签触发调度。

**字段说明**：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| enabled | bool | true | 是否启用 state label dispatch |

## 周期性服务配置

### governance

周期性治理扫描服务。

**字段说明**：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| enabled | bool | true | 是否启用治理扫描 |
| prompt_template | str | "orchestra.governance.plan" | Prompt 模板路径 |
| dry_run | bool | false | 试运行模式 |
| interval_ticks | int | 4 | 每 N 个 tick 执行一次（约 1 小时） |
| agent | str \| None | None | Agent 预设名称 |
| backend | str \| None | None | Backend 覆盖 |
| model | str \| None | None | Model 覆盖 |

**配置示例**：

```yaml
orchestra:
  governance:
    enabled: true
    interval_ticks: 4
    dry_run: false
```

### supervisor_handoff

Supervisor handoff issue 消费服务。

**字段说明**：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| enabled | bool | true | 是否启用 supervisor handoff |
| issue_label | str | "supervisor" | Supervisor issue 标签 |
| handoff_state_label | str | "" | Handoff 状态标签（空则使用 ConventionResolver） |
| interval_ticks | int | 4 | 每 N 个 tick 执行一次 |
| prompt_template | str | "" | Prompt 模板路径（空则使用 ConventionResolver） |
| agent | str \| None | None | Agent 预设名称 |
| backend | str \| None | None | Backend 覆盖 |
| model | str \| None | None | Model 覆盖 |

**配置示例**：

```yaml
orchestra:
  supervisor_handoff:
    enabled: true
    issue_label: "supervisor"
    interval_ticks: 4
```

### periodic_check

周期性一致性检查和资源清理。

**字段说明**：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| enabled | bool | true | 是否启用周期性检查 |
| interval_ticks | int | 10 | 每 N 个 tick 执行一次（约 2.5 小时） |
| max_age_days | int | 7 | 资源过期天数阈值 |
| enable_worktree_cleanup | bool | true | 是否清理过期 worktree |
| enable_local_branch_cleanup | bool | true | 是否清理本地分支 |
| enable_remote_branch_cleanup | bool | true | 是否清理远程分支 |

**配置示例**：

```yaml
orchestra:
  periodic_check:
    enabled: true
    interval_ticks: 10
    max_age_days: 7
    enable_worktree_cleanup: true
    enable_local_branch_cleanup: true
    enable_remote_branch_cleanup: true
```

## 队列管理配置

### queue_recollect

队列优先级刷新配置，控制 orchestra 定期重建 issue 队列以反映优先级标签的更新。

**字段说明**：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| enabled | bool | true | 是否启用队列优先级刷新 |
| interval_ticks | int | 10 | 每 N 个 heartbeat tick 触发一次队列重建（最小值：1） |

**使用场景**：

当 issue 的优先级标签在运行时被更新时（例如从 `priority/low` 改为 `priority/high`），默认的 "frozen-queue" 策略不会立即反映新优先级。队列优先级刷新功能会定期重建队列，确保高优先级 issue 能够被优先处理。

**配置示例**：

```yaml
orchestra:
  queue_recollect:
    enabled: true
    interval_ticks: 10  # 每 10 个 tick（约 10 秒）刷新一次队列
```

**注意事项**：

1. **性能影响**：队列重建会调用 GitHub API 重新收集 issue，建议间隔不要设置过小（推荐 ≥ 10）
2. **in-flight 保护**：正在处理的 issue（waiting_state 不为 None）会被保留，不会丢失状态
3. **禁用场景**：如果不需要动态优先级调整，可以设置 `enabled: false` 以减少 API 调用

**示例场景**：

```python
# 场景：用户在 GitHub 上将 issue #200 标记为高优先级
# 默认情况：issue #200 在队列中的位置不变，需等待队列为空后重建
# 启用队列刷新：下一个 tick 10 时，队列自动重建，issue #200 移至队列前端

# 配置
config = OrchestraConfig(
    queue_recollect=QueueRecollectConfig(
        enabled=True,
        interval_ticks=10,
    ),
)
```

## 其他配置

### polling

Heartbeat 轮询回退配置。

**字段说明**：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| enabled | bool | true | 是否启用轮询回退 |

**配置示例**：

```yaml
orchestra:
  polling:
    enabled: true
```

## 完整配置示例

```yaml
orchestra:
  # 基础配置
  enabled: true
  repo: "owner/repo"
  port: 8080
  polling_interval: 900
  max_concurrent_flows: 5
  
  # 容量控制
  governance_max_concurrent: 1
  supervisor_max_concurrent: 2
  
  # 熔断器
  circuit_breaker:
    enabled: true
    failure_threshold: 4
    cooldown_seconds: 300
  
  # Assignee dispatch
  assignee_dispatch:
    enabled: true
    use_worktree: true
    timeout_seconds: 3600
  
  # PR review dispatch
  pr_review_dispatch:
    enabled: true
    async_mode: true
  
  # Governance
  governance:
    enabled: true
    interval_ticks: 4
  
  # Supervisor handoff
  supervisor_handoff:
    enabled: true
    interval_ticks: 4
  
  # Periodic check
  periodic_check:
    enabled: true
    interval_ticks: 10
    max_age_days: 7
  
  # Queue recollect
  queue_recollect:
    enabled: true
    interval_ticks: 10
```

## 配置加载

配置通过 `config.loader.get_config()` 加载，加载顺序为：

1. `.vibe/config.yaml` - 项目特定配置
2. `config/settings.yaml` - 默认配置（推荐）
3. `~/.vibe/config.yaml` - 全局配置
4. Pydantic 最小安全默认值 - 降级场景

详细说明见 [configuration-guide.md](../architecture/configuration-guide.md)。

## 相关文档

- [README.md](README.md) - Orchestra 概述
- [runtime-modes.md](runtime-modes.md) - 运行模式说明
- [prd-orchestra-integration.md](prd-orchestra-integration.md) - PRD
- [../architecture/configuration-guide.md](../architecture/configuration-guide.md) - 配置系统总览
