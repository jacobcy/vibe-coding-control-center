# Services

核心业务逻辑层，实现 flow/PR/task/handoff 等工作流。

## 职责

- Flow 生命周期管理（创建、状态转变、查询、投影）
- PR 全生命周期（创建、评分、merge、ready）
- Task 绑定与管理
- Handoff 记录与恢复
- Pre-push 检查
- Label 状态编排
- 版本管理
- Issue 失败处理
- 编排状态聚合

## 文件列表

统计时间：2026-05-02

### Flow 管理文件

| 文件 | 行数 | 职责 |
|------|------|------|
| flow_service.py | 51 | Flow CRUD + 状态转变 |
| flow_transition.py | 293 | Flow 状态转变逻辑 |
| flow_write_mixin.py | 238 | Flow 写操作 mixin |
| flow_read_mixin.py | 154 | Flow 读操作 mixin |
| flow_block_mixin.py | 181 | Flow 阻塞操作 mixin |
| flow_projection_service.py | 151 | Flow 状态投影 |
| flow_cleanup_service.py | 319 | Flow 清理服务 |
| flow_classifier.py | 82 | Flow 分类器 |
| flow_resume_resolver.py | 52 | Flow 恢复解析器 |
| flow_reader.py | 25 | Flow 只读查询辅助 |

### PR 管理文件

| 文件 | 行数 | 职责 |
|------|------|------|
| pr_service.py | 380 | PR 主服务 |
| pr_create_usecase.py | 130 | PR 创建用例 |
| pr_ready_usecase.py | 45 | PR ready 用例 |
| pr_scoring_service.py | 239 | PR 质量评分 |
| pr_analysis_service.py | 230 | PR 变更影响分析 |
| pr_review_briefing_service.py | 144 | PR review briefing 编排 |
| pr_utils.py | 147 | PR 构建辅助 |
| pr_status_checker.py | 117 | PR 状态检查 |

### Task 管理文件

| 文件 | 行数 | 职责 |
|------|------|------|
| task_service.py | 405 | Task 绑定管理 |
| task_resume_usecase.py | 345 | 失败任务恢复入口 |
| task_resume_candidates.py | 391 | 恢复候选发现 |
| task_resume_operations.py | 360 | 恢复动作执行 |
| task_show_service.py | 356 | Task 展示服务 |
| task_status_classifier.py | 52 | Task 状态分类器 |
| task_binding_guard.py | 45 | task/flow 绑定校验 |

### Handoff 管理文件

| 文件 | 行数 | 职责 |
|------|------|------|
| handoff_service.py | 483 | Handoff 记录服务 |
| handoff_storage.py | 224 | Handoff 存储服务 |
| handoff_validation.py | 57 | Handoff 验证服务 |

### Check 管理文件

| 文件 | 行数 | 职责 |
|------|------|------|
| check_service.py | 602 | Pre-push 检查 |
| check_cleanup_service.py | 268 | Check 清理服务 |
| check_ownership_service.py | 89 | Check 所有权服务 |
| check_remote.py | 165 | 远程检查辅助 |

### Issue 管理文件

| 文件 | 行数 | 职责 |
|------|------|------|
| issue_failure_service.py | 464 | Issue failed/blocked 状态处理 |
| issue_flow_service.py | 191 | Issue 与 flow 映射 |
| issue_title_cache_service.py | 286 | Issue 标题缓存服务 |

### Label 管理文件

| 文件 | 行数 | 职责 |
|------|------|------|
| label_service.py | 210 | 状态标签编排（规则委托给 domain，CRUD 委托给 clients） |

### 编排状态文件

| 文件 | 行数 | 职责 |
|------|------|------|
| orchestra_status_service.py | 423 | 编排状态聚合查询 |
| status_query_service.py | 421 | 状态查询服务 |

### 其他文件

| 文件 | 行数 | 职责 |
|------|------|------|
| version_service.py | 121 | 版本号管理 |
| signature_service.py | 146 | Flow 签名验证 |
| spec_ref_service.py | 277 | OpenSpec 集成 |
| abandon_flow_service.py | 156 | 放弃 flow 编排 |
| base_resolution_usecase.py | 129 | base 分支解析 |
| verdict_service.py | 184 | 裁决服务 |
| worktree_ownership_guard.py | 177 | Worktree 所有权守卫 |
| external_events.py | 196 | 外部事件处理 |
| artifact_parser.py | 82 | 工件解析器 |
| __init__.py | 5 | 模块导出 |

**总计**：46 文件，10288 行

## 依赖关系

### 依赖

- `clients`：Git 客户端、GitHub 客户端、SQLite 客户端、AI 客户端
- `domain`：事件发布、状态机规则
- `models`：领域模型定义
- `config`：编排配置加载
- `exceptions`：业务异常
- `analysis`：代码分析服务

### 被依赖

- `commands`：命令层调用服务
- `execution`：执行器调用服务
- `domain handlers`：事件处理器调用服务
- `orchestra`：全局编排调用服务

## 架构说明

### Flow 生命周期

Flow 是编排的核心概念，代表一次完整的任务执行流程：

```
Created → Claimed → In-Progress → Merge-Ready → Merged
                ↓           ↓
            Handoff    Blocked/Failed
                ↓           ↓
              Resume     Recovery
```

### Task 恢复机制

当任务执行失败时，系统提供恢复机制：

1. **候选发现**：`task_resume_candidates.py` 发现可恢复的任务
2. **恢复解析**：`task_resume_resolver.py` 解析恢复路径
3. **恢复执行**：`task_resume_operations.py` 执行恢复动作

### Handoff 机制

Handoff 用于跨 agent 传递上下文：

- **记录**：`handoff_service.py` 记录 agent 输出
- **验证**：`handoff_validation.py` 验证 handoff 完整性
- **存储**：`handoff_storage.py` 管理 handoff 工件

### 关键设计

1. **服务分层**：按职责分为 Flow、PR、Task、Handoff 等服务层
2. **用例模式**：复杂业务逻辑通过 usecase 封装
3. **Mixin 复用**：通过 mixin 共享 Flow 操作逻辑
4. **验证分离**：业务验证逻辑独立于 CRUD 操作
5. **状态机驱动**：Flow 状态转变通过状态机规则控制
