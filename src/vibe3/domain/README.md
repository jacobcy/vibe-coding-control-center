# Domain

事件驱动架构的核心，定义领域事件与处理器。

## 职责

- 事件定义：定义系统中所有领域事件（flow 生命周期、治理决策、supervisor 扫描）
- 事件发布：提供事件发布机制，将事件分发给注册的处理器
- 状态机规则：定义 issue 状态转变规则与事件触发逻辑
- 事件处理器注册：协调多层执行链的事件分发

## 文件列表

统计时间：2026-05-02

### 顶层文件

| 文件 | 行数 | 职责 |
|------|------|------|
| orchestration_facade.py | 327 | 编排门面，协调事件分发与三层执行链 |
| publisher.py | 86 | 事件发布器，管理事件处理器注册与分发 |
| state_machine.py | 45 | 状态机定义，issue 状态转变规则 |

### events/ 子目录

| 文件 | 行数 | 职责 |
|------|------|------|
| __init__.py | 106 | 事件类型导出 |
| flow_lifecycle.py | 143 | Flow 生命周期事件定义 |
| governance.py | 52 | 治理决策事件定义 |
| supervisor_apply.py | 121 | Supervisor 扫描结果应用事件定义 |

### handlers/ 子目录

| 文件 | 行数 | 职责 |
|------|------|------|
| __init__.py | 50 | 处理器导出 |
| _shared.py | 62 | 共享辅助函数 |
| dispatch.py | 274 | 事件分发处理器，协调执行链 |
| flow_lifecycle.py | 87 | Flow 生命周期事件处理器 |
| governance_scan.py | 147 | 治理扫描处理器（L1 层） |
| issue_state_dispatch.py | 179 | Issue 状态转变分发处理器 |
| supervisor_scan.py | 93 | Supervisor 扫描处理器（L2 层） |

**总计**：15 文件，1856 行

## 依赖关系

### 依赖

- `config`：编排配置加载
- `models`：领域模型定义
- `exceptions`：领域异常
- `clients`：GitHub 客户端（事件通知）
- `services`：状态标签分发服务
- `execution`：容量服务、执行协调

### 被依赖

- `execution`：事件触发执行
- `roles`：角色监听事件
- `orchestra`：全局编排协调
- `commands`：命令层触发事件

## 架构说明

### 三层执行链

Domain 模块实现了三层执行链架构，通过事件驱动协调不同层级的执行：

- **L1 治理层（Governance）**：定期扫描，发现系统级问题并触发修复建议
- **L2 监管层（Supervisor）**：扫描执行状态，处理异常情况并触发恢复
- **L3 代理层（Agent）**：执行具体任务，响应 issue 状态变化

### 事件流

```
Issue State Change → Event Publisher → Handlers
                                        ├─ Governance Handler (L1)
                                        ├─ Supervisor Handler (L2)
                                        └─ Agent Dispatch (L3)
```

### 关键设计

1. **事件解耦**：各层通过事件通信，避免直接依赖
2. **优先级队列**：L1 > L2 > L3 的执行优先级
3. **状态机驱动**：issue 状态转变自动触发相应事件
4. **容量控制**：通过 capacity service 控制并发执行数