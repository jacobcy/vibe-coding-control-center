# vibe-team-review

多 agent 协作审查 skill，支持 PR 审查、代码审查、架构决策等多种场景。

## 结构

| 文件 | 职责 |
|------|------|
| `SKILL.md` | 主执行文档（Phase 0-5 流程） |
| `references/usage.md` | 事件规格和脚本用法 |
| `references/execution-reference.md` | 消息样例和诊断命令 |
| `references/recovery-playbook.md` | 异常恢复流程 |
| `references/debug-guide.md` | 调试指南 |
| `runtime/agents.sh` | Agent 清单（名称、类型） |
| `scripts/lib.sh` | 公共函数库 |
| `scripts/agent-exist.sh` | Agent 存在性检查 |
| `scripts/agent-event.sh` | Agent 事件列表 |
| `scripts/agent-report.sh` | Agent 报告提取 |

## 设计原则

- **报告在 inbox，不在 backlog**。agent 报告存在 team-lead.json，不通过 TaskCreate metadata 传递
- **下游 agent 自己读上游**。Phase 2 agent 自己跑 `agent-report.sh` 读 Phase 1 报告。codex 是外部 plugin（通过 codex:rescue 调用），fix-executor 接收 Phase 4 修复指令。team-lead 不转发、不注入。
- **脚本做验证**。agent-exist/event/report.sh 提供事实，不由 lead 口头判断
- **简化握手**。无 polling/poking/spawned/isActive 等概念，握手即存活检测

## 版本历史

- **v4 (2026-05-13)**: 重写，删除 backlog 参数传递、meta-task 模式、复杂握手协议。下游 agent 直接读前序报告。
- **v3 (2026-05-12)**: PR #842 fix alignment — Phase number alignment + handshake reuse
- **v2 (2026-05-09)**: PR #831 四步握手+POLLING 协议
- **v1 (2026-04)**: 原始实现
