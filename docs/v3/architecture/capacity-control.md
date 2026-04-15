## CapacityService

### 用途

统一管理所有执行角色的容量控制,解决双层节流问题。

**双层节流问题**:

- StateLabelDispatchService 跟踪 `in_flight_dispatches`
- ManagerExecutor 也跟踪 `in_flight_dispatches`
- 导致容量计算冲突,可能出现超额分发

**解决方案**:

CapacityService 提供单一的容量检查点,结合 live session count 和 in-flight dispatch tracking。

### 容量检查触发路径

系统提供两条容量检查路径:

#### 路径1: Heartbeat 自动调度

- **触发源**: GlobalDispatchCoordinator 通过 heartbeat 定期扫描
- **调度方式**: 自动周期性调度,无需人工干预
- **适用场景**: 持续监控 issue 状态,自动触发 manager/planner/executor/reviewer 分派
- **实现位置**: `src/vibe3/domain/handlers/dispatch.py` → GlobalDispatchCoordinator

#### 路径2: CLI 手动触发

- **触发源**: `vibe3 internal issue-role-sync` CLI 命令
- **调度方式**: 手动触发,用于特定 issue-role 组合
- **适用场景**: 紧急修复、手动干预、测试验证
- **实现位置**: `src/vibe3/execution/issue_role_sync_runner.py`

**关键特性**: 两条路径共享同一个 `_shared_in_flight_dispatches` 类变量,确保容量计数一致,避免重复分派。