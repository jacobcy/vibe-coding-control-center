---
document_type: plan
title: "Phase 2: GovernanceService + Circuit Breaker — 系统可运行性与健壮性"
phase: 2
status: draft
author: "Claude"
created: "2026-03-30"
depends_on:
  - docs/v3/orchestra/plan-phase1-orchestra-status.md
  - src/vibe3/orchestra/heartbeat.py
  - src/vibe3/orchestra/dispatcher.py
  - src/vibe3/services/codeagent_execution_service.py
  - skills/vibe-orchestra/SKILL.md
  - skills/vibe-roadmap/SKILL.md
---

# Phase 2: GovernanceService + Circuit Breaker

## 目标

1. **GovernanceService**：自动化周期性治理——运行 vibe-orchestra/vibe-roadmap skill
   对 issue 进行 label 调整、优先级排序、依赖分析，然后通过 assignee 机制触发执行
2. **Circuit Breaker**：当 codeagent-wrapper 连续失败（API 错误、token 不足）时，
   自动暂停 heartbeat dispatch，等待恢复后重新启用

## 设计原则

- **利用现有触发链**：GovernanceService 的输出是 label 变更和 assignee 设置，
  这会自然触发现有的 AssigneeDispatchService，不需要新的 dispatch 路径
- **skill 是决策者**：GovernanceService 只负责"什么时候运行 skill"和
  "把 snapshot 喂给 skill"，skill 自己做决策
- **Circuit Breaker 保护全局**：作为 Dispatcher 级别的保护机制，
  而非单个 service 的逻辑

## Part A: Circuit Breaker

### 状态机

```
        success
  CLOSED -------> CLOSED (正常运行)
    |
    | N consecutive failures
    v
   OPEN ---------> HALF_OPEN (cooldown 到期后)
    |                  |
    | (拒绝所有        | test dispatch
    |  dispatch)       |
    |                  +---> success: CLOSED
    |                  +---> failure: OPEN (重置 cooldown)
```

### 配置

```yaml
orchestra:
  circuit_breaker:
    enabled: true
    failure_threshold: 3        # 连续失败 N 次触发 OPEN
    cooldown_seconds: 300       # OPEN 状态持续时间（5 分钟）
    half_open_max_tests: 1      # HALF_OPEN 允许的测试 dispatch 数
```

新增 `CircuitBreakerConfig` 纳入 `OrchestraConfig`：

```python
class CircuitBreakerConfig(BaseModel):
    enabled: bool = True
    failure_threshold: int = Field(default=3, ge=1)
    cooldown_seconds: int = Field(default=300, ge=60)
    half_open_max_tests: int = Field(default=1, ge=1)
```

### 实现

文件：`src/vibe3/orchestra/circuit_breaker.py`

```python
class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

@dataclass
class CircuitBreaker:
    """Dispatch-level circuit breaker.

    Tracks consecutive failures from Dispatcher._run_command().
    When threshold is reached, blocks new dispatches until cooldown expires.
    """
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: float = 0.0
    failure_threshold: int = 3
    cooldown_seconds: int = 300

    def record_success(self) -> None:
        """Reset to CLOSED on any successful dispatch."""
        ...

    def record_failure(self, error_category: str) -> None:
        """Increment failure counter. Transition to OPEN if threshold hit."""
        ...

    def allow_request(self) -> bool:
        """Check if dispatch is allowed.

        CLOSED: always allow
        OPEN: block, check if cooldown expired -> HALF_OPEN
        HALF_OPEN: allow limited test requests
        """
        ...
```

### 错误分类

不是所有失败都应触发 circuit breaker。分类：

- **API/Token 错误**（触发 circuit breaker）：
  - `returncode != 0` 且 stderr 包含 `rate limit`、`token`、`quota`、`API error`、`authentication`
  - 进程 timeout（可能是 API hang）
- **业务错误**（不触发 circuit breaker）：
  - merge conflict、test failure、review rejection
  - 这些是正常业务流程的一部分

```python
def classify_failure(returncode: int, stderr: str, timed_out: bool = False) -> str:
    """Classify dispatch failure for circuit breaker decision.

    Returns:
        "api_error": API/token/rate limit failure -> counts toward breaker
        "business_error": normal business failure -> does not count
        "timeout": process timeout -> counts toward breaker
    """
    if timed_out:
        return "timeout"
    stderr_lower = stderr.lower()
    api_keywords = ("rate limit", "token", "quota", "api error", "authentication",
                    "unauthorized", "forbidden")
    if any(kw in stderr_lower for kw in api_keywords):
        return "api_error"
    return "business_error"
```

### 接入点

在 `Dispatcher._run_command()` 的返回路径上接入：

```python
# dispatcher.py
def _run_command(self, cmd, cwd, label) -> bool:
    if not self._circuit_breaker.allow_request():
        logger.warning("Circuit breaker OPEN, skipping dispatch")
        return False

    timed_out = False
    try:
        result = subprocess.run(...)
        ...
    except subprocess.TimeoutExpired:
        timed_out = True
        ...

    if success:
        self._circuit_breaker.record_success()
    else:
        category = classify_failure(result.returncode, result.stderr, timed_out)
        if category != "business_error":
            self._circuit_breaker.record_failure(category)
    return success
```

CircuitBreaker 通过 `Dispatcher.__init__` 注入（或默认创建）：

```python
def __init__(
    self,
    config: OrchestraConfig,
    dry_run: bool = False,
    repo_path: Path | None = None,
    orchestrator: FlowOrchestrator | None = None,
    circuit_breaker: CircuitBreaker | None = None,
) -> None:
    ...
    self._circuit_breaker = circuit_breaker or CircuitBreaker(
        failure_threshold=config.circuit_breaker.failure_threshold,
        cooldown_seconds=config.circuit_breaker.cooldown_seconds,
    )
```

### 可观测性

CircuitBreaker 状态纳入 OrchestraSnapshot（Phase 1 扩展）：

```python
# OrchestraSnapshot 新增字段
circuit_breaker_state: str   # "closed" | "open" | "half_open"
circuit_breaker_failures: int
circuit_breaker_last_failure: float | None
```

日志策略：
- 状态转换时 `logger.warning("Circuit breaker: CLOSED -> OPEN (failures=3)")`
- OPEN 状态下每次拒绝 dispatch 时 `logger.warning("Circuit breaker OPEN, dispatch blocked")`
- HALF_OPEN 测试 dispatch 时 `logger.info("Circuit breaker HALF_OPEN: allowing test dispatch")`

## Part B: GovernanceService

### 触发时机

GovernanceService 注册为 ServiceBase，在 on_tick() 中按频率运行：

```python
class GovernanceService(ServiceBase):
    """周期性运行 governance skill 进行 issue 治理。"""

    event_types: list[str] = []  # 不处理 webhook 事件，仅通过 tick 触发

    def __init__(
        self,
        config: OrchestraConfig,
        status_service: OrchestraStatusService,  # Phase 1
        executor: ThreadPoolExecutor,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        self._tick_count = 0
        self._governance_interval_ticks = config.governance.interval_ticks  # 默认 4
        ...

    async def on_tick(self) -> None:
        self._tick_count += 1
        if self._tick_count % self._governance_interval_ticks != 0:
            return
        await self._run_governance()
```

默认 polling_interval=900s，interval_ticks=4，即每小时运行一次治理扫描。

### 配置

```yaml
orchestra:
  governance:
    enabled: true
    interval_ticks: 4     # 每 N 个 heartbeat tick 运行一次
    skill: "vibe-orchestra"  # 使用哪个 governance skill
    dry_run: false        # true 时只生成 plan 不执行
```

### 执行方式

GovernanceService 不直接做决策，而是：

1. 从 OrchestraStatusService 获取 snapshot
2. 将 snapshot 格式化为 plan 文件（markdown）
3. 通过 `vibe3 run --plan <governance-plan.md>` 调用 codeagent-wrapper
4. codeagent-wrapper 加载 vibe-orchestra skill，基于上下文做出决策
5. skill 的决策通过 `gh issue edit` 修改 label/assignee，触发现有链路

```python
async def _run_governance(self) -> None:
    # 1. 获取状态快照
    snapshot = self._status_service.snapshot()

    # 2. 检查 circuit breaker（governance 本身也消耗 API token）
    if self._circuit_breaker and not self._circuit_breaker.allow_request():
        logger.bind(domain="orchestra").warning(
            "Governance skipped: circuit breaker OPEN"
        )
        return

    # 3. 构建 governance plan
    plan_content = self._build_governance_plan(snapshot)

    if self._dry_run:
        logger.bind(domain="orchestra").info(
            f"[DRY-RUN] Governance plan:\n{plan_content}"
        )
        return

    # 4. 写入临时 plan 文件（参考 master.py 的 tempfile 模式）
    prompt_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", prefix="governance_plan_", delete=False
        ) as f:
            f.write(plan_content)
            prompt_path = f.name

        cmd = ["uv", "run", "python", "-m", "vibe3", "run", "--plan", prompt_path]
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            self._executor,
            lambda: subprocess.run(cmd, cwd=self._repo_path, timeout=600),
        )
    finally:
        if prompt_path:
            Path(prompt_path).unlink(missing_ok=True)
```

### 上下文构建（Context Builder）

类似 reviewer 为 review agent 提供 structure 信息，GovernanceService 为
governance skill 提供系统全局视图：

```python
def _build_governance_plan(self, snapshot: OrchestraSnapshot) -> str:
    """构建 governance skill 的输入 plan。"""
    issue_lines = []
    for entry in snapshot.active_issues[:20]:  # 限制最多 20 条
        state_str = entry.state.to_label() if entry.state else "state/unknown"
        blocked = f" [blocked_by={entry.blocked_by}]" if entry.blocked_by else ""
        issue_lines.append(
            f"- #{entry.number}: {entry.title[:60]} | {state_str}{blocked}"
        )

    return f"""# Orchestra Governance Scan

## 当前系统状态

- 活跃 issue: {len(snapshot.active_issues)}
- 活跃 flow: {snapshot.active_flows}
- Circuit breaker: {snapshot.circuit_breaker_state}

## Issue 列表

{chr(10).join(issue_lines) or '(无活跃 issue)'}

## 指令

请根据以上状态执行 vibe-orchestra governance：
1. 检查 issue 优先级是否合理（参考 priority/* labels）
2. 检查依赖关系是否已解除（blocked_by 中的 issue 是否已关闭）
3. 对 READY 状态的高优先级 issue，分配给 vibe-manager-agent
4. 对 BLOCKED 状态的 issue，检查 blocker 是否已关闭，如已关闭则推进状态
5. 记录决策原因（通过 issue comment）
"""
```

### 与 PR #378 的区别

PR #378 试图通过 `vibe3 run --skill` 直接运行 skill，但：
- `vibe3 run --skill` 命令不存在
- 缺少上下文（不知道当前系统状态）
- 把 skill 调度逻辑硬编码在 Python 代码中，绕过了 skill 的自主决策能力

Phase 2 的方式：
- 使用现有的 `vibe3 run --plan`（已存在且可工作）
- 通过 plan 文件提供完整系统状态上下文
- skill 决策通过 GitHub API 执行（label/assignee 变更）
- 变更自然触发现有的 `webhook -> AssigneeDispatchService -> dispatch` 链路

## 验收标准

### Circuit Breaker

1. 连续 N 次 API/token 类 dispatch 失败后，新 dispatch 被自动阻止
2. cooldown 到期后自动切换 HALF_OPEN，允许试探性 dispatch
3. 试探成功恢复 CLOSED，试探失败重置 cooldown
4. 业务错误（test failure、conflict）不触发 circuit breaker
5. circuit breaker 状态在 `vibe3 orchestra status` 可见
6. `dry_run=True` 时 circuit breaker 不实际阻止（只记录日志）

### GovernanceService

1. 按配置频率（默认每 4 tick）自动运行 governance 扫描
2. 从 OrchestraStatusService 获取完整上下文并传入 skill via plan 文件
3. skill 的 label/assignee 变更触发现有 dispatch 链路（无新 dispatch 路径）
4. governance 执行本身受 circuit breaker 保护
5. `dry_run=True` 时只输出 plan 内容不执行
6. governance 失败（timeout/error）不影响 heartbeat 继续运行

## 风险

- **Governance 执行本身消耗 API token**：存在循环消耗风险。
  缓解：governance 频率可配置（默认每小时一次），circuit breaker 双重保护
- **Skill 决策错误**：可能错误分配 issue。
  缓解：governance 只能操作 label/assignee，不直接写代码；
  出错可通过手动修改 label 纠正
- **Plan 文件大小**：大量 issue 时 plan 可能很长。
  缓解：限制最多 20 条 issue，按优先级排序取前 20

## 工作量估算

- `CircuitBreaker` + 错误分类（`circuit_breaker.py`）：~120 行
- `CircuitBreakerConfig` + `OrchestraConfig` 扩展：~30 行
- `Dispatcher` 接入 circuit breaker：~40 行
- CircuitBreaker 测试：~150 行
- `GovernanceService`（`services/governance.py`）：~200 行
- Context builder：~80 行
- GovernanceService 测试：~120 行
- 总计：~740 行
