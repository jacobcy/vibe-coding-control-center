# Coding Standards (Supplement)

本文件定义实现细节、工具选择和边界细则。

术语以 [docs/standards/glossary.md](../../docs/standards/glossary.md) 为准，动作词以 [docs/standards/action-verbs.md](../../docs/standards/action-verbs.md) 为准。

治理级总原则见 [SOUL.md](../../SOUL.md)，项目上下文与最小硬规则见 [CLAUDE.md](../../CLAUDE.md)。

## Shell Implementation
- 使用 `#!/usr/bin/env zsh`。
- 可执行脚本使用 `set -e`。
- 变量与路径必须正确引用。
- 共用函数优先复用 `lib/utils.sh`。

## Size And Complexity
- `lib/ + bin/` 总行数不应超过 7000。
- 单文件不应超过 300 行。
- 超过 150 行或包含密集数据转换的非核心逻辑，应优先迁移到 `scripts/`。
- 每个 `.sh` 文件只解决一个基础问题。
- 不允许为了压行数写难读代码。

## Function Style
- 函数命名使用 `snake_case`。
- 内部函数前缀 `_`。
- 公共输出统一走 `log_*` helper。

## Shell And Skill Boundary
- Shell 能力层负责原子操作、确定性状态修改、可验证输出。
- Skill 层负责理解上下文、调度、编排，并调用 Shell。
- 不为已有 Shell 命令再写一套 Skill 等价实现。
- 优先补现有命令能力，不为单一场景新增顶层命令。
- 涉及共享状态时，不直接手改 `.git/vibe/*`，除非当前任务明确要求一次性人工处理运行时数据。

## Tooling Choice
- 优先使用现成工具：`bats`、`jq`、`curl`、`gh`。
- 不自造缓存系统、NLP 路由、自研测试框架、i18n 层等复杂能力。
- 仅允许使用 `npx skills` 管理第三方 Markdown skills。
- 仅修改 `skills/` 中的自有 skill，不修改外部自动生成产物。

## Context And File Hygiene
- 不在终端直接喷大体量内容；优先摘要、截断、过滤。
- 长期共享记忆使用 `.agent/context/memory.md`。
- 当前短期上下文使用 `.agent/context/task.md`。
- 跨 worktree 共享状态写入 `.git/vibe/`。
- 不在项目根目录随意落临时文件。
- 仓库相关的临时脚本、调试输出、scratch 文件统一放 `temp/`，便于追踪并由清理流程统一处理。
- 仅在真正与仓库无关的系统级一次性场景下使用 `/tmp`；用完即删，不作为默认调试落点。

## Delivery Discipline
- 一次提交只做一个逻辑变更。
- 提交前提供可验证证据（测试输出或复现实验步骤）。
- 未过审计门前，不做 `git push` 或 PR 发布。
- 不直接在 `main` 上开发。
