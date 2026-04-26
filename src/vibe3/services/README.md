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

## 关键组件

| 文件 | 职责 |
|------|------|
| flow_service.py | Flow CRUD + 状态转变 |
| flow_lifecycle.py | Flow 生命周期 mixin |
| flow_projection_service.py | Flow 状态投影 |
| pr_service.py | PR 主服务 |
| pr_create_usecase.py | PR 创建用例 |
| pr_ready_usecase.py | PR ready 用例 |
| pr_scoring_service.py | PR 质量评分 |
| pr_analysis_service.py | PR 变更影响分析 |
| pr_review_briefing_service.py | PR review briefing 编排 |
| task_service.py | Task 绑定管理 |
| task_resume_usecase.py | 失败任务恢复入口 |
| task_resume_candidates.py | 恢复候选发现 |
| task_resume_operations.py | 恢复动作执行 |
| handoff_service.py | Handoff 记录服务 |
| handoff_recorder_unified.py | Agent 输出到 handoff 工件的转换与记录 |
| check_service.py | Pre-push 检查 |
| label_service.py | 状态标签编排（规则委托给 domain，CRUD 委托给 clients） |
| issue_failure_service.py | Issue failed/blocked 状态处理 |
| issue_flow_service.py | Issue 与 flow 映射 |
| orchestra_status_service.py | 编排状态聚合查询 |
| version_service.py | 版本号管理 |
| signature_service.py | Flow 签名验证 |
| spec_ref_service.py | OpenSpec 集成 |
| flow_reader.py | Flow 只读查询辅助 |
| abandon_flow_service.py | 放弃 flow 编排 |
| base_resolution_usecase.py | base 分支解析 |
| task_binding_guard.py | task/flow 绑定校验 |
| pr_utils.py | PR 构建辅助 |
| check_remote.py | 远程检查辅助 |

## 依赖关系

- 依赖: clients, domain, models, config, exceptions
- 被依赖: commands, execution, domain handlers, orchestra
