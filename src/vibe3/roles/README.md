# Roles

角色定义与执行模块，实现各角色的具体执行逻辑。

## 职责

- 角色定义：定义系统中所有角色及其触发条件
- 角色注册表：维护角色与触发标签的映射关系
- 角色执行：实现各角色的具体执行逻辑（manager, plan, run, review, governance, supervisor）
- 请求构建：构建各角色的执行请求和上下文

## 文件列表

统计时间：2026-05-02

### 角色定义文件

| 文件 | 行数 | 职责 |
|------|------|------|
| definitions.py | 76 | 角色定义（TriggerableRoleDefinition） |
| registry.py | 90 | 角色注册表，维护标签到角色的映射 |

### 角色实现文件

| 文件 | 行数 | 职责 |
|------|------|------|
| manager.py | 315 | Manager 角色（状态机、协作调度） |
| plan.py | 376 | Plan 角色（实现方案规划） |
| run.py | 561 | Run 角色（方案执行） |
| review.py | 441 | Review 角色（代码审查） |
| governance.py | 420 | Governance 角色（系统治理建议） |
| supervisor.py | 299 | Supervisor 角色（异常监控与恢复） |

### 辅助文件

| 文件 | 行数 | 职责 |
|------|------|------|
| review_helpers.py | 67 | Review 辅助函数 |
| __init__.py | 6 | 模块导出 |

**总计**：10 文件，2651 行

## 依赖关系

### 依赖

- `execution`：执行协调器、容量服务、执行契约
- `clients`：Git 客户端、GitHub 客户端、SQLite 客户端
- `models`：编排配置、执行请求模型
- `config`：编排配置加载
- `domain`：事件发布、状态机
- `services`：Flow 服务、PR 服务、Task 服务
- `agents`：Agent 后端

### 被依赖

- `domain handlers`：事件处理器触发角色执行
- `commands`：命令层触发角色（如 vibe-run）

## 架构说明

### TriggerableRoleDefinition 设计

每个角色通过 `TriggerableRoleDefinition` 定义其触发条件和行为：

```python
TriggerableRoleDefinition(
    name="plan",
    trigger_labels=["state/claimed"],  # 触发标签
    execute_func=execute_plan,         # 执行函数
    description="规划实现方案"          # 描述
)
```

### Label-based Dispatch

角色通过标签触发，实现松耦合调度：

```
Issue Label Change
    ↓
Registry.lookup(label)
    ↓
TriggerableRoleDefinition
    ↓
Execute Function
```

### 角色分工

- **Manager**：
  - 监控 issue 状态变化
  - 调度其他角色执行
  - 协调跨角色协作

- **Plan**：
  - 分析需求，规划实现方案
  - 输出实现计划（plan_ref）

- **Run**：
  - 执行实现方案
  - 编写代码、测试
  - 输出执行报告（report_ref）

- **Review**：
  - 审查代码变更
  - 评估质量、风险
  - 输出审查裁决（audit_ref）

- **Governance**：
  - 定期扫描系统状态
  - 发现问题并提出建议
  - 触发系统级改进

- **Supervisor**：
  - 监控执行状态
  - 处理异常情况
  - 触发恢复或重试

### 关键设计

1. **标签驱动**：角色通过标签触发，避免硬编码依赖
2. **单一职责**：每个角色专注于一个阶段的工作
3. **状态隔离**：每次执行都在独立的 worktree 和 session 中
4. **可恢复性**：执行失败时保留现场，支持恢复
5. **协作模式**：Manager 协调多个角色协作完成复杂任务