# Design: V3 Process Plane Implementation

## Context

### 背景与当前状态
Vibe Center V2 架构中，provider（OpenSpec、Supervisor、Kiro）的实现分散在多个模块：
- OpenSpec: `openspec/` 目录，管理 change 生命周期
- Supervisor: 六层流程模型（Intake → Scoping → Design → Plan → Execution → Audit/Close）
- Kiro: `.kiro/` 目录，AI 辅助决策
- Manual: 人工降级模式

当前问题：
1. Provider 路由逻辑分散，无统一接口
2. 新增 provider 需要修改多处代码
3. Provider 降级策略不明确
4. Provider 状态无法统一查询

### 约束
- **迁移约束**：V3 阶段仅在 `v3/process-plane/` 目录实现，不修改 V2 代码
- **接口约束**：与控制平面、执行平面的接口必须符合 MASTER-PRD 的契约定义
- **状态约束**：流程平面内部状态不得覆盖控制平面核心状态（todo → in_progress → blocked → done → archived）

### 利益相关者
- **控制平面**：调用流程平面的 route/start/status/complete 接口
- **执行平面**：接收流程平面的执行意图（通过控制平面中转）
- **Provider 开发者**：按照 adapter 模板接入新 provider

## Goals / Non-Goals

### Goals
1. **Provider Router 架构**：建立统一的 provider 路由、启动、状态查询、完成接口
2. **路由策略引擎**：基于任务类型、风险等级、资源配置的智能路由
3. **降级机制**：provider 不可用时自动降级到 manual 模式
4. **Provider Adapter 模板**：标准化的 provider 接入规范
5. **解耦设计**：新增 provider 不影响控制平面 schema

### Non-Goals
1. **不重定义控制平面状态机**：控制平面的核心状态保持不变
2. **不直接执行 worktree/tmux 命令**：这些由执行平面负责
3. **不暴露 provider 内部状态**：只输出聚合状态给控制平面
4. **不删除 V2 代码**：V3 阶段只在 v3/ 目录新增实现

## Decisions

### Decision 1: Provider Router 接口设计

**选择**: 采用 4 个核心接口（route/start/status/complete）

**理由**:
- `route(task)`: 决定使用哪个 provider，职责清晰
- `start(task, context)`: 启动 provider 执行，支持上下文传递
- `status(provider_ref)`: 查询 provider 执行状态，支持异步
- `complete(provider_ref)`: 完成 provider 执行，清理资源

**替代方案**:
- ❌ 单一接口 `execute(task)`: 无法支持异步执行和状态查询
- ❌ 更多接口（如 pause/resume/cancel）: 增加复杂度，当前不需要

**接口定义**:
```bash
# Provider Router 接口
route(task) -> provider_name
start(task, context) -> provider_ref
status(provider_ref) -> {state, metadata}
complete(provider_ref) -> {result, artifacts}
```

### Decision 2: Provider 路由策略

**选择**: 基于规则的策略引擎（任务类型 + 风险等级 + 资源配置）

**理由**:
- 任务类型：OpenSpec 适合 spec-driven 变更，Supervisor 适合复杂流程
- 风险等级：高风险任务优先使用 Supervisor 的六层审核
- 资源配置：Kiro 需要 AI 资源，资源不足时降级

**替代方案**:
- ❌ 硬编码路由：不够灵活，新增 provider 需要修改代码
- ❌ 机器学习路由：过度设计，当前规模不需要

**路由策略矩阵**:
| 任务类型 | 风险等级 | 资源配置 | Provider |
|---------|---------|---------|----------|
| spec-driven | 低 | 充足 | OpenSpec |
| spec-driven | 高 | 充足 | Supervisor |
| spec-driven | - | 不足 | Manual |
| ad-hoc | 低 | 充足 | Kiro |
| ad-hoc | 高 | 充足 | Supervisor |

### Decision 3: Provider Adapter 模式

**选择**: Adapter 模式 + 标准化接口

**理由**:
- 每个 provider 实现统一的 adapter 接口
- 核心路由逻辑不依赖具体 provider 实现
- 新增 provider 只需实现 adapter，无需修改核心代码

**替代方案**:
- ❌ 直接调用 provider: 耦合度高，难以扩展
- ❌ Plugin 模式: 过度设计，增加复杂度

**Adapter 接口**:
```bash
# 每个 Provider 必须实现的接口
provider_adapter() {
  case "$1" in
    route)   # 决定是否处理该任务
    start)   # 启动执行
    status)  # 查询状态
    complete)# 完成清理
  esac
}
```

### Decision 4: 降级策略

**选择**: 自动降级 + 手动恢复

**理由**:
- Provider 不可用时自动降级到 manual 模式
- Manual 模式保证系统基本可用
- 支持手动恢复到高级 provider

**降级路径**:
```
Supervisor → OpenSpec → Kiro → Manual
```

**替代方案**:
- ❌ 无降级：provider 不可用时系统不可用
- ❌ 全自动恢复：复杂度高，容易出错

### Decision 5: 状态聚合策略

**选择**: Provider 状态 → 聚合状态（不暴露内部步骤）

**理由**:
- 控制平面只需要知道 provider 的聚合状态
- Provider 内部步骤（如 Supervisor 六层）不映射为控制平面状态
- 减少跨平面状态耦合

**状态映射**:
```bash
# Provider 内部状态 → 聚合状态
Provider 内部: Intake → Scoping → Design → Plan → Execution → Audit
聚合输出: in_progress → done

# 不暴露的细节
- Supervisor 的 "Scoping" 不映射为控制平面的 "blocked"
- 只有控制平面可以设置 "blocked" 状态
```

## Risks / Trade-offs

### Risk 1: Provider 状态与控制平面状态冲突

**风险**: Provider 内部状态（如 Supervisor 六层）可能与控制平面状态（todo → in_progress → blocked → done → archived）产生语义冲突

**缓解**:
1. 明确接口契约：Process → Control 只输出聚合状态（in_progress/done）
2. 流程平面内部状态不暴露给控制平面
3. 文档清晰说明状态语义

### Risk 2: 路由策略配置复杂

**风险**: 基于规则的路由策略可能配置复杂，难以调试

**缓解**:
1. 提供路由策略可视化工具（后续）
2. 默认策略覆盖 80% 场景
3. 支持路由策略测试（dry-run 模式）

### Risk 3: Provider 降级影响用户体验

**风险**: Provider 自动降级可能影响用户体验（如从 Supervisor 降级到 Manual）

**缓解**:
1. 降级前通知用户
2. 提供手动恢复接口
3. 记录降级日志，便于排查

### Trade-off 1: 灵活性 vs 简洁性

**权衡**: Adapter 模式提供灵活性，但增加了抽象层

**选择理由**:
- 灵活性优先：支持多种 provider 接入
- 抽象层开销可接受：接口简单，性能影响小

### Trade-off 2: 完整性 vs 迁移速度

**权衡**: 完整实现所有 provider vs 快速迁移核心 provider

**选择理由**:
- 迁移速度优先：先实现 OpenSpec + Manual，后续扩展
- 保持接口完整：预留扩展接口

## Migration Plan

### 阶段 1: 核心架构（当前）
1. 实现 Provider Router 核心接口（route/start/status/complete）
2. 实现 OpenSpec adapter（作为参考实现）
3. 实现 Manual adapter（降级兜底）
4. 实现基础路由策略（基于任务类型）

### 阶段 2: 扩展 Provider
1. 实现 Supervisor adapter（六层流程）
2. 实现 Kiro adapter（AI 辅助）
3. 完善路由策略（风险等级 + 资源配置）

### 阶段 3: 优化与监控
1. 实现路由策略可视化
2. 实现 provider 状态监控
3. 实现降级策略优化

### Rollback 策略
- V3 实现在独立目录（v3/process-plane/），不影响 V2 代码
- 如需回滚，只需切换到 V2 接口
- 数据兼容：V3 与 V2 共享数据格式

## Open Questions

1. **Provider 优先级**: 当多个 provider 都可用时，如何确定优先级？
   - 建议：基于历史成功率 + 用户偏好

2. **Provider 并行执行**: 是否支持多个 provider 并行执行？
   - 建议：当前不支持，保持简单；后续可扩展

3. **Provider 状态持久化**: Provider 状态是否需要持久化？
   - 建议：是的，支持跨会话恢复

4. **Provider 资源限制**: 如何限制 provider 的资源使用（如 Kiro 的 AI 调用次数）？
   - 建议：实现 provider 级别的资源配额
