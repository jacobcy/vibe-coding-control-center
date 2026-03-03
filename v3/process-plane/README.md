# V3 Process Plane - Provider Router Architecture

## 概述

Process Plane 是 Vibe Center V3 的流程平面，负责 provider 路由与任务执行管理。它提供统一的 provider 接入接口、智能路由策略、自动降级机制，支持多种 provider（OpenSpec、Supervisor、Kiro、Manual）的独立演进。

## 核心组件

### 1. Provider Router (`router.sh`)

统一的 provider 路由器，提供 4 个核心接口：

```bash
# 路由任务到合适的 provider
pp_route(task) -> provider_name

# 启动 provider 执行
pp_start(task, context) -> provider_ref

# 查询 provider 状态
pp_status(provider_ref) -> {state, metadata}

# 完成 provider 执行
pp_complete(provider_ref) -> {result, artifacts}
```

**状态聚合**: Provider 内部状态聚合为 `in_progress`/`done`，不暴露内部步骤。

### 2. Routing Strategy Engine (`strategy.sh`)

智能路由策略引擎，基于以下维度选择 provider：

- **任务类型**: `spec-driven` | `ad-hoc`
- **风险等级**: `low` | `medium` | `high`
- **资源配置**: AI 资源是否充足

**路由策略矩阵**:

| 任务类型 | 风险等级 | 资源配置 | Provider |
|---------|---------|---------|----------|
| spec-driven | 低 | 充足 | OpenSpec |
| spec-driven | 高 | 充足 | Supervisor |
| spec-driven | - | 不足 | Manual |
| ad-hoc | 低 | 充足 | Kiro |
| ad-hoc | 高 | 充足 | Supervisor |

**使用示例**:

```bash
# 路由 spec-driven 低风险任务
TASK='{"type":"spec-driven","risk":"low","id":"task-1"}'
PROVIDER=$(pp_route "$TASK")
# 输出: openspec

# Dry-run 模式（预览路由决策）
RESULT=$(pp_strategy_dry_run "$TASK")
# 输出: {"provider":"openspec","reason":"spec-driven task with low risk","dry_run":true}
```

### 3. Provider Fallback (`fallback.sh`)

自动降级机制，保证系统可用性。

**降级路径**: Supervisor → OpenSpec → Kiro → Manual

**特性**:
- ✅ Provider 不可用时自动降级
- ✅ 降级历史记录
- ✅ 降级循环检测
- ✅ 手动恢复接口

**使用示例**:

```bash
# 查找可用的降级 provider
FALLBACK=$(pp_fallback_find_available "openspec")
# 输出: kiro 或 manual

# 查询降级历史
HISTORY=$(pp_fallback_history 5)
```

### 4. Provider Adapters (`adapters/`)

标准化的 provider 接入规范。所有 providers 实现统一的 adapter 接口。

**已实现的 Adapters**:
- **Manual**: 永远接受任务（降级兜底）
- **OpenSpec**: 接受 spec-driven 任务
- **Supervisor**: 接受高风险任务（六层流程）
- **Kiro**: 接受 ad-hoc 任务且 AI 资源充足

**Adapter 接口**:

每个 adapter 必须实现 4 个方法：

```bash
provider_route(task) -> bool           # 是否接受任务
provider_start(task, context) -> ref   # 启动执行
provider_status(ref) -> {state, meta}  # 查询状态
provider_complete(ref) -> {result}     # 完成清理
```

## 快速开始

### 1. 加载模块

```bash
source v3/process-plane/adapter-loader.sh
source v3/process-plane/strategy.sh
source v3/process-plane/fallback.sh
source v3/process-plane/router.sh
```

### 2. 查看可用的 adapters

```bash
pp_adapter_list
# 输出:
# manual
# openspec
# supervisor
# kiro
```

### 3. 执行任务

```bash
# 定义任务
TASK='{"type":"spec-driven","risk":"low","id":"my-task"}'

# 路由到合适的 provider
PROVIDER=$(pp_route "$TASK")
echo "Selected provider: $PROVIDER"

# 启动执行
REF=$(pp_start "$TASK" '{"context":"data"}')
echo "Provider ref: $REF"

# 查询状态
STATUS=$(pp_status "$REF")
echo "Status: $STATUS"

# 完成执行
RESULT=$(pp_complete "$REF")
echo "Result: $RESULT"
```

## 运行测试

```bash
# 运行综合测试套件
bash tests/process-plane/test-comprehensive.sh

# 运行所有 adapters 测试
bash tests/process-plane/test-all-adapters.sh
```

## 架构亮点

1. **统一接口**: 所有 providers 实现统一的 adapter 接口，新增 provider 无需修改核心代码
2. **智能路由**: 基于任务类型、风险等级、资源配置的智能路由策略
3. **自动降级**: Provider 不可用时自动降级，保证系统可用性
4. **状态聚合**: 不暴露 provider 内部状态，只输出聚合状态（in_progress/done）
5. **可扩展**: Adapter 模式支持快速接入新的 providers

## 文件结构

```
v3/process-plane/
├── router.sh              # Provider Router 核心接口
├── strategy.sh            # 路由策略引擎
├── fallback.sh            # 降级机制
├── adapter-loader.sh      # Adapter 加载器
├── README.md              # 本文档
└── adapters/
    ├── adapter-template.sh    # Adapter 模板
    ├── manual/adapter.sh      # Manual adapter
    ├── openspec/adapter.sh    # OpenSpec adapter
    ├── supervisor/adapter.sh  # Supervisor adapter
    └── kiro/adapter.sh        # Kiro adapter

tests/process-plane/
├── test-comprehensive.sh  # 综合测试套件
├── test-all-adapters.sh   # Adapter 测试
└── test-core-simple.sh    # 核心功能测试
```

## 开发新 Adapter

1. 复制 adapter 模板：

```bash
cp v3/process-plane/adapters/adapter-template.sh \
   v3/process-plane/adapters/my-provider/adapter.sh
```

2. 实现必需的接口：

```bash
provider_route() {
  local task="$1"
  # 实现路由逻辑
  echo "true"  # 或 "false"
}

provider_start() {
  local task="$1"
  local context="$2"
  # 实现启动逻辑
  echo "my-provider:task-id"
}

provider_status() {
  local ref="$1"
  # 实现状态查询
  echo '{"state":"in_progress","metadata":{}}'
}

provider_complete() {
  local ref="$1"
  # 实现完成逻辑
  echo '{"result":"success","artifacts":[]}'
}
```

3. Adapter 会自动被加载器发现和注册。

## 与控制平面的集成

Process Plane 通过明确的接口契约与控制平面交互：

**Control → Process**:
- `provider`: 选中的 provider 名称
- `provider_ref`: provider 执行引用
- `status`: 聚合状态

**Process → Control**:
- `provider_state`: provider 执行状态的聚合结果

## 迁移状态

✅ **核心架构已完成并通过测试**
✅ **所有 4 个 Provider Adapters 已实现**
✅ **核心功能（路由、启动、状态、完成）已验证**

当前实现是一个**可工作的 MVP**，支持：
- ✅ Provider 路由和任务执行
- ✅ 智能路由策略
- ✅ 自动降级机制
- ✅ 状态聚合

## 下一步

- [ ] Supervisor Flow 六层流程的详细实现
- [ ] 完善测试覆盖
- [ ] 集成到控制平面
- [ ] 性能优化和监控

## 参考

- [设计文档](openspec/changes/v3-process-plane-implementation/design.md)
- [提案文档](openspec/changes/v3-process-plane-implementation/proposal.md)
- [规范文档](openspec/changes/v3-process-plane-implementation/specs/)
- [V3 Master PRD](../MASTER-PRD.md)
