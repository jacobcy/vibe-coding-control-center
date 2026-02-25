# Project Context: Vibe Center 2.0

Vibe Center 是一个极简的 AI 开发编排工具：管理工具链、密钥、worktree/tmux 工作流，以及 Agent 规则体系。

> Entry note: The canonical root entry is `AGENTS.md`. Use this file for project context and hard rules.

## 技术栈
- 语言：Zsh
- 入口：`bin/vibe`
- 模块：`lib/*.sh`
- Agent 工作区：`.agent/`

## 常用命令
- `bin/vibe check`
- `bin/vibe tool`
- `bin/vibe keys <list|set|get|init>`
- `bin/vibe flow <start|review|pr|done|status|sync>`

## 目录职责
- `bin/`: CLI 分发入口
- `lib/`: Shell 核心逻辑
- `config/`: keys 与 aliases
- `skills/`: 治理与流程技能
- `.agent/`: rules/context/workflows

## HARD RULES
1. `lib/ + bin/` 总行数 <= 1200。
2. 单个 `.sh` 文件 <= 200 行。
3. 零死代码：函数必须有调用方。
4. 不在 shell 层实现排除项（NLP 路由、缓存系统、i18n、自研测试框架等）。
5. 能用现成工具就不用自造轮子（bats/jq/curl/gh）。
6. 新增能力必须符合 SOUL 的“认知优先”原则。
7. PR 说明必须附 LOC Diff（before/after/delta）。

## 开发协议
- 思考英文，输出中文。
- 默认最小差异修改。
- 完成前必须给出验证证据（测试输出或可复现实验步骤）。

## 参考
- `SOUL.md`
- `AGENTS.md`
- `.agent/README.md`
- `.agent/rules/*`
