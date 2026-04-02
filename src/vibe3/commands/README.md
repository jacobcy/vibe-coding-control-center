# Commands

CLI 子命令实现层，每个文件对应一个 `vibe3 <cmd>` 子命令。

## 职责

- 解析用户输入（Typer 参数/选项）
- 调用 services/clients 执行业务逻辑
- 通过 ui/ 格式化输出
- 处理错误并显示用户友好信息

## 子命令清单

| 命令 | 文件 | 职责 |
|------|------|------|
| flow | flow.py, flow_lifecycle.py, flow_status.py | Flow 生命周期 |
| task | task.py | Task 绑定与查询 |
| pr | pr.py, pr_create.py, pr_lifecycle.py, pr_query.py | PR 全生命周期 |
| review | review.py | 代码审查 |
| inspect | inspect.py, inspect_*.py | 代码分析 |
| handoff | handoff.py, handoff_read.py, handoff_write.py | 上下文交接 |
| plan | plan.py | Plan 生成 |
| run | run.py | Agent 执行 |
| snapshot | snapshot.py | 代码结构快照 |
| status | status.py | 全局状态面板 |
| check | check.py | 环境检查 |
| roadmap | roadmap.py | 版本路线图 |
| prompt | prompt_check.py | Prompt 调试 |

## 依赖关系

- 依赖: services, clients, models, ui, analysis, agents
- 被依赖: cli.py (路由注册)
