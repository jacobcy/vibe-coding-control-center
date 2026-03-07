## Why

当前 `vibe check` 只能做静态检查（文件存在、状态一致、僵尸分支），无法检测外部事件（PR merged、Issue closed）来判断任务是否应该标记为完成。任务状态完全依赖人工判断，容易导致状态过期和不一致。

需要将 `vibe check` 从"静态检查工具"升级为"智能状态同步工具"，能够：
- 检测 PR merged 等外部事件
- 通过 AI 分析判断任务完成度
- 提示用户确认后自动修正状态

## What Changes

1. **新增智能状态同步能力**
   - 检测已 merged 的 PR，判断关联任务是否完成
   - 支持多任务场景的智能分析（Subagent 分析 PR 内容）
   - 基于置信度的分级处理（高置信度 AI 决定、中置信度用户确认、低置信度跳过）

2. **扩展 vibe flow 命令族**
   - `vibe flow list --pr`: 查询最近 10 个有 PR 的分支
   - `vibe flow list --keywords <text>`: 按关键字查找分支
   - `vibe flow status <branch>`: 返回 task 绑定信息 + PR 状态
   - `vibe flow review <branch> --json`: 返回 PR 详细数据（描述、评论、commits）

3. **增强 vibe check 检查流程**
   - Phase 1: 静态检查（已实现）
   - Phase 2: Git 状态检查（新增）- 检测 PR merged 状态
   - Phase 3: 智能分析（新增）- Subagent 分析任务完成度
   - Phase 4: 用户确认并执行修正

4. **数据策略**
   - 实时查询 `gh` 命令，不同步本地 PR 记录
   - 复用 gh 的缓存机制，避免过度工程化

## Capabilities

### New Capabilities

- `smart-task-sync`: 智能任务状态同步能力，检测外部事件（PR merged）、分析任务完成度、提示用户确认后自动修正状态

### Modified Capabilities

- `cli-commands`: 扩展 `vibe flow` 命令族，新增 `--pr`、`--keywords` 参数和 JSON 输出支持
- `vibe-check`: 从静态检查升级为智能状态同步，新增 Git 状态检查和智能分析流程

## Impact

**修改文件**：
- `lib/check.sh`: 新增 Phase 2/3 检查流程，调用 Skill 层进行智能分析
- `lib/flow.sh`: 扩展 `_flow_list` 支持 `--pr` 和 `--keywords` 参数
- `lib/flow_status.sh`: 增强 `vibe flow status` 输出 PR 信息
- `lib/flow_help.sh`: 更新帮助文档

**新增文件**：
- `skills/vibe-check/SKILL.md`: 升级 Skill 定义，增加 Subagent 调用逻辑

**依赖**：
- 需要 `gh` CLI 工具和 GitHub API 访问权限
- API 限流：5000 requests/hour（充足）

**数据影响**：
- 不新增本地数据存储
- 实时查询 GitHub API
- 复用现有的 registry.json 和 worktrees.json