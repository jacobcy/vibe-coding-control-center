---
document_type: standard
title: GitHub Remote Call Standard
status: proposed
scope: github-remote-calls
authority:
  - github-cli-boundary
  - graphql-boundary
  - github-auth-preflight
  - github-project-write-rules
author: GPT-5 Codex
created: 2026-03-14
last_updated: 2026-03-14
related_docs:
  - docs/standards/v3/command-standard.md
  - docs/standards/vibe3-handoff-store-standard.md
  - docs/prds/vibe-session-governance.md
  - .agent/plans/2026-03-14-vibe3-data-model-design.md
---

# GitHub Remote Call Standard

本文档定义 Vibe 3.0 与 GitHub 远端交互时的最小调用标准。

目标不是覆盖所有 GitHub API，而是锁定执行器最容易猜错的几件事：

- 什么时候用 `gh issue` / `gh pr`
- 什么时候用 `gh api graphql`
- GitHub Project 字段更新的合法边界
- 鉴权检查、错误处理、dry-run 与输出规则

## 1. Core Rule

Vibe 3.0 的远端调用固定遵循：

- **优先 `gh` CLI**
- **优先 GitHub 一等命令**
- **ProjectV2 和复杂字段更新才进入 GraphQL**

禁止执行器直接自行发明：

- 未记录在标准中的 GraphQL 对象写入路径
- 随意 `curl` GitHub API 替代 `gh`
- 把 GitHub 响应原样长期缓存到本地业务 JSON

## 2. Auth Preflight

所有远端写操作前，必须先检查：

```bash
gh auth status --hostname github.com
```

最小要求：

- 已登录有效账号
- 当前 host 为 `github.com`
- token scope 至少覆盖当前操作所需权限

推荐做法：

- 所有写命令先跑 auth preflight
- 失败时直接报错退出
- 不在脚本里临时触发交互式 `gh auth login`

## 3. Command Selection

### 3.1 Issue

以下操作优先使用 `gh issue`：

- 查看 issue
- 创建 issue comment
- 读取 issue 基本字段

推荐命令：

```bash
gh issue view <number> --json number,title,body,state,url
gh issue comment <number> --body "..."
```

### 3.2 Pull Request

以下操作优先使用 `gh pr`：

- 查看 PR
- 查看 PR diff
- 评论 PR
- review PR

推荐命令：

```bash
gh pr view <number|branch> --json number,title,body,state,headRefName,baseRefName
gh pr diff <number|branch>
gh pr comment <number|branch> --body "..."
gh pr review <number|branch> --comment -b "..."
```

### 3.3 ProjectV2

以下操作优先使用 `gh api graphql`：

- 查询 ProjectV2 items
- 查询 item field values
- 更新 ProjectV2 自定义字段
- 读取项目字段定义

原因：

- GitHub Projects 的自动化主接口是 GraphQL
- ProjectV2 item / field value 更新不适合靠 `gh issue` / `gh pr` 完成

推荐入口：

```bash
gh api graphql -f query='...'
```

## 4. GraphQL Boundary

### 4.1 Allowed GraphQL Reads

允许执行器通过 GraphQL 读取：

- ProjectV2 items
- ProjectV2 fieldValues
- Issue dependency graph
- Project custom field definitions

### 4.2 Allowed GraphQL Writes

允许执行器通过 GraphQL 写入：

- `updateProjectV2ItemFieldValue`
- issue dependency 相关 mutation

### 4.3 Prohibited GraphQL Assumptions

执行器不得假设：

- 所有 Project 字段都能通过 `updateProjectV2ItemFieldValue` 更新
- Assignees / Labels / Milestone / Repository 也能按普通 field value 一样写

明确约束：

- `updateProjectV2ItemFieldValue` 只用于支持的字段类型
- 对于 Assignees、Labels、Milestone、Repository 这类字段，必须改用 GitHub 官方对应 mutation 或 `gh issue` / `gh pr` 一等命令

## 5. Project Field Rules

V3 当前只要求执行器明确区分两类字段：

### 5.1 Official GitHub Fields

只读或按 GitHub 官方对象语义维护：

- item identity
- content type
- issue / pull request 原生字段

这些字段不能被本地 workflow 语义改写。

### 5.2 Vibe Extension Fields

允许写入 Project custom fields 的扩展字段，必须是轻量桥接语义，例如：

- `task_issue`
- `spec_ref`
- `planner`
- `executor`
- `reviewer`
- `next`
- `blocked_by`

约束：

- 这些字段只作为远端可见桥接
- 不能把本地 handoff store 全量投影回 Project
- 不允许把 `plan/report/audit` 正文写入 Project 字段

## 6. Repository Resolution

默认仓库上下文来自当前 git 仓库。

允许使用：

- 当前目录自动推导 repo
- `GH_REPO`

若脚本显式传 repo，则必须优先显式参数。

对于 `gh api` 的 endpoint placeholder：

- `{owner}`
- `{repo}`
- `{branch}`

应按 GitHub CLI 规则解析，不要自行拼装重复逻辑。

## 7. Output Rules

所有远端调用命令必须满足：

- 成功输出可读摘要
- `--json` 输出机器可读结果
- 错误输出到 stderr
- 不允许空回复

远端失败时最少要说明：

- 哪个命令失败
- 失败阶段：auth / lookup / mutation / verify
- 下一步建议：重试、检查登录、检查字段、人工修复

## 8. Dry-Run And Apply

所有会写远端状态的批量或结构化操作，必须支持：

- `--dry-run`
- `--apply`

约束：

- `--dry-run` 只输出 proposal，不写远端
- `--apply` 前必须已完成 auth preflight
- 若操作会批量更新 Project 字段，必须先生成 preview

## 9. Verification Rule

远端写操作结束后，不允许仅凭 mutation 成功就声称完成。

至少应做一次回读验证：

- issue 重新读取
- PR 重新读取
- Project item 重新查询 fieldValues

V3 中推荐由：

- `vibe check`
- 或命令内最小 verify 步骤

完成这层回读确认。

## 10. Minimal Execution Matrix

| 场景 | 推荐命令 | 备注 |
|---|---|---|
| 读取 issue | `gh issue view` | 不走 GraphQL |
| 评论 issue | `gh issue comment` | 不走 GraphQL |
| 读取 PR | `gh pr view` | 不走 GraphQL |
| 评论/审查 PR | `gh pr comment` / `gh pr review` | 不走 GraphQL |
| 查看 PR diff | `gh pr diff` | 不走 GraphQL |
| 读取 ProjectV2 items | `gh api graphql` | Project 读主路径 |
| 更新 Project custom field | `gh api graphql` | 用 `updateProjectV2ItemFieldValue` |
| 更新 assignees/labels/milestone | 官方对应 mutation 或 `gh issue/pr` | 不得误用 field update |
| issue dependency 图 | `gh api graphql` | 复杂关系建议走 GraphQL |

## 11. Sources

本标准关键点基于 GitHub 官方文档：

- GitHub Docs: Projects API / GraphQL automation docs
- GitHub CLI manual: `gh api`, `gh auth status`, `gh issue comment`, `gh pr review`, `gh pr diff`
