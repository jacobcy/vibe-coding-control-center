---
document_type: standard
title: Plugin Setup Standard
status: active
scope: project-wide
author: Claude Sonnet 4.6
created: 2026-07-07
last_updated: 2026-07-07
related_docs:
  - CLAUDE.md
  - docs/standards/glossary.md
  - docs/standards/configuration-standard.md
  - docs/v3/mcp-server-setup.md
---

# Plugin Setup Standard

本文件定义本项目使用的全部 Claude Code 工具链的安装配置流程。

## 目录

- [记忆系统: claude-mem](#claude-mem)
- [上下文压缩: rtk + caveman](#rtk)
- [知识图谱: graphify](#graphify)
- [项目标准化: spec-kit + superspec](#spec-kit)
- [编排技能: superpowers](#superpowers)
- [第三方代码审查: codex](#codex)
- [状态悬浮栏: claude-hud](#claude-hud)
- [工具链部署: openspec + opsx](#openspec--opsx)
- [项目技能: vibe-*](#vibe-)

---

## 总览

| 工具 | 类型 | 版本 | Codex 兼容 | 安装方式 | 状态 |
|------|------|------|------------|---------|------|
| claude-mem | plugin | 13.10.2 | ✅ | `npx claude-mem install` / `claude plugin install` | ✅ |
| rtk | CLI | 0.42.4 | N/A (独立 CLI) | brew/npm/cargo | ✅ |
| caveman | plugin | 0.1.0 | ✅ | `npx skills add JuliusBrussee/caveman -a codex` | ✅ |
| graphify | CLI + skill | 0.9.8 | ✅ | `uv tool install graphifyy` | ✅ |
| spec-kit (specify) | CLI + skill | 0.12.4 | ✅ | `uv tool install specify-cli` | ✅ |
| superpowers | plugin skill | 6.0.3 | ✅ | `claude plugin install` / 各平台独立安装 | ✅ |
| codex | plugin | 1.0.2 | - | `claude plugin install` | ✅ |
| claude-hud | plugin | 0.3.0 | ❌ Claude Code only | `claude plugin install` | ✅ |
| openspec/opsx | npm + skills | - | ✅ | `npm install -g @fission-ai/openspec` | ✅ |
| vibe skills | skills | - | ❌ 项目特有 | `scripts/init.sh` | ✅ |
| exa search | MCP server | 3.3.9 | ✅ | `mcpServers` config | ✅ |
| context7 | plugin | unknown | ❌ Claude Code only | `claude plugin install` | ✅ |

---

## Codex 兼容说明

Codex CLI 使用 `$` 前缀而非 `/` 调用命令。安装技能时需要指定 `-a codex`。

| 安装方式 | Claude Code | Codex |
|---------|-------------|-------|
| 调用技能前缀 | `/skill-name` | `$skill-name` |
| npx skills add | `-a claude-code` | `-a codex` |
| MCP server 配置 | `mcpServers` in settings.json | `codex mcp add <name>` |
| 多 agent 安装 | 自动发现 | `npx skills add <repo> -a codex` |

---

## claude-mem

跨会话持久记忆系统。自动捕获 observations，支持知识库查询。

### 安装

```bash
claude plugin marketplace add thedotmack/claude-mem
claude plugin install claude-mem
```

### marketplace 配置

```bash
# settings.json 中已注册
thedotmack: { source: "github", repo: "thedotmack/claude-mem" }
```

### 使用

| 命令 | 用途 |
|------|------|
| `/claude-mem:mem-search "query"` | 搜索跨会话记忆 |
| `/claude-mem:knowledge-agent` | 构建知识库并提问 |
| `/claude-mem:make-plan` | 创建实现计划 |
| `/claude-mem:timeline-report` | 项目历史时间线报告 |

### Codex 兼容

```bash
npx claude-mem install --ide codex-cli
```
支持下全部查询命令，前缀从 `/` 改为 `$`（如 `$claude-mem:mem-search "query"`）。

### 验证

```bash
claude plugin list | grep claude-mem
# 版本: 13.8.1
```

---

## RTK

Rust Token Killer — 命令行代理，减少 60-90% tokens。

### 安装

```bash
# brew
brew install rtk  # 或对应包管理器
```

### Hook 配置

`~/.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "~/.claude/hooks/rtk-rewrite.sh" }
        ]
      }
    ]
  }
}
```

### 验证

```bash
rtk --version        # → 0.42.4
rtk gain             # 显示 token 节省统计
```

---

## Caveman

极简输出模式，减少 65% 输出 tokens。

### 安装

官方一键安装（自动检测所有 agent）：

```bash
curl -fsSL https://raw.githubusercontent.com/JuliusBrussee/caveman/main/install.sh | bash
```

Claude Code 插件市场：

```bash
claude plugin marketplace add JuliusBrussee/caveman
claude plugin install caveman
```

Codex 安装：

```bash
npx skills add JuliusBrussee/caveman -a codex
```

### 激活

Session 中通过 `/caveman` 启用：

| 命令 | 模式 | 说明 |
|------|------|------|
| `/caveman` | full | 默认，省略冠词，碎片句 |
| `/caveman lite` | lite | 去掉客套话，句子完整 |
| `/caveman ultra` | ultra | 极限压缩 |
| `/caveman wenyan` | wenyan | 文言文模式 |

### 子技能

| 技能 | 用途 |
|------|------|
| `/caveman:caveman-commit` | 极简 commit 信息生成 |
| `/caveman:caveman-review` | 一行式代码审查 |
| `/caveman:caveman-stats` | Token 节省统计 |
| `/caveman:cavecrew` | 压缩 subagent 分配指南 |

### Statusline Badge

显示当前模式 `[CAVEMAN]` / `[CAVEMAN:ULTRA]`。

已配置 combined statusline (`~/.claude/hooks/statusline.sh`)，与 claude-hud 共用，详见 [claude-hud combined statusline](#combined-statusline)。

---

## graphify

代码知识图谱。AST 提取 + 社区检测 + 可查询图。

### 安装

```bash
uv tool install graphifyy
```

### 使用

```bash
# 构建知识图谱（当前目录）
/graphify .

# 查询已有图
/graphify query "How does X work?"

# 增量更新（只处理改动文件）
/graphify . --update

# 路径分析
/graphify path "ModuleA" "ModuleB"

# 概念解释
/graphify explain "ServiceX"
```

### Git Hooks

graphify 自动安装 `post-commit` 和 `post-checkout` hooks 到仓库共享 hooks 目录：

```
<项目根>/hooks/
├── post-commit      # 提交后后台重建图谱
├── post-checkout    # 切换分支后重建
```

hooks 位置由 git worktree `--git-common-dir` 决定，所有 worktree 共享。

### CLI 配置

```bash
# 注册 skill（同时为 Claude Code 和 Codex 安装）
graphify install
graphify install --platform codex   # Codex 专用

# 手动安装 hooks
graphify hook install

# 写入 CLAUDE.md 集成
graphify claude install

# 查看 hook 状态
graphify hook status
```

### Codex 兼容

- Codex 使用 `$graphify` 而非 `/graphify`
- 需在 `~/.codex/config.toml` 的 `[features]` 中设置 `multi_agent = true`（支持并行提取）
- 技能前缀：`$graphify query "..."`

### 验证

```bash
graphify --version   # → 0.9.8
ls graphify-out/graph.json  # 构建成功则有此文件
```

---

## spec-kit

Spec-driven development 工具链。包括 `specify` CLI + `speckit-*` skills + `superspec` extension。

### 安装 specify CLI

```bash
uv tool install specify-cli
```

### 初始化项目

```bash
specify init  # 创建 .specify/ 目录
```

### 集成安装

```bash
# 安装 Claude 集成（物化 speckit-* skills）
specify integration install claude --force

# 安装 superspec 扩展
specify extension add superspec

# 检查集成状态
specify integration status
```

### 技能列表

安装后，15 个 `speckit-*` skills 出现在 `.agents/skills/`：

| 技能 | 用途 |
|------|------|
| `speckit-specify` | 创建/更新 feature spec |
| `speckit-clarify` | 识别未明确的需求 |
| `speckit-plan` | 生成实现计划 |
| `speckit-tasks` | 生成任务分解 |
| `speckit-taskstoissues` | 任务转 GitHub issues |
| `speckit-implement` | 执行实现计划 |
| `speckit-converge` | 评估完成度并追加任务 |
| `speckit-analyze` | 跨工件质量分析 |
| `speckit-checklist` | 生成检查清单 |
| `speckit-constitution` | 创建/更新项目章程 |
| `speckit-superspec-brainstorm` | Superpowers 头脑风暴 |
| `speckit-superspec-execute` | Superpowers TDD 执行 |
| `speckit-superspec-review` | Superpowers 审查 |
| `speckit-superspec-status` | Superpowers 状态 |
| `speckit-superspec-tasks` | Superpowers 任务 |

### superspec 扩展

`.specify/extensions/superspec/` 提供 TDD 纪律检查点：

- `after_tasks`: 验证任务覆盖后执行 `speckit.superspec.tasks`
- `before_implement`: TDD 纪律检查后执行 `speckit.superspec.execute`
- `after_implement`: 审查完成后执行 `speckit.superspec.review`

### 验证

```bash
specify --version      # → 0.12.4
specify integration status  # → OK
specify integration list    # 查看所有支持的平台
ls .agents/skills/speckit-*/SKILL.md | wc -l  # → 15
```

### Codex 兼容

- Codex 使用 `$speckit-<command>` 前缀（如 `$speckit-specify`）
- 通过 `specify integration list` 查看是否已注册 Codex 集成
- 如果未安装：`specify integration install codex --force`

---

## superpowers

编排技能集，包含 brainstorming、TDD、代码审查、plan 执行等 13 个技能。

### 安装

Claude Code：

```bash
claude plugin install superpowers
# 或通过 skills.json 由 init.sh 自动安装
npx skills add obra/superpowers -g --skill <skills...>
```

Codex 安装：在 Codex App 插件商店搜索 `Superpowers` 安装。Codex CLI 通过 `/plugins` 界面安装。

### 核心技能

| 技能 | 用途 |
|------|------|
| `brainstorming` | 创意/设计前的用户意图探索 |
| `test-driven-development` | 测试先行开发 |
| `writing-plans` | 多步骤任务计划编写 |
| `executing-plans` | 隔离 session 执行计划 |
| `requesting-code-review` | 完成前请求审查 |
| `receiving-code-review` | 接收反馈并验证 |
| `systematic-debugging` | 系统化调试 |
| `verification-before-completion` | 完成前验证 |
| `using-git-worktrees` | 隔离工作空间 |
| `dispatching-parallel-agents` | 并行任务分配 |
| `subagent-driven-development` | 子 agent 驱动开发 |
| `writing-skills` | 创建/编辑技能 |
| `finishing-a-development-branch` | 分支完成处理 |

---

## codex

第三方代码审查和调查 agent。使用 GPT-5.4 提供替代视角。

### 安装

```bash
claude plugin marketplace add openai/codex-plugin-cc
claude plugin install codex
```

### 使用

| 命令 | 用途 |
|------|------|
| `codex:rescue` | 调查代缺陷/复杂 issue |
| `codex:setup` | 检查 Codex CLI 就绪状态 |

### 验证

```bash
claude plugin list | grep codex
# 版本: 1.0.2
```

---

## claude-hud

悬浮 HUD 状态栏，显示 token 用量、活动工具、agent 状态等。

### 安装

```bash
claude plugin marketplace add jarrodwatts/claude-hud
claude plugin install claude-hud
```

### 配置 (macOS + bun)

生成 statusLine 命令并写入 `~/.claude/settings.json`：

```json
{
  "statusLine": {
    "type": "command",
    "command": "bash -c 'cols=${COLUMNS:-}; ... exec <runtime> <plugin_dir>src/index.ts'"
  }
}
```

**macOS + bun runtime** 使用 `--env-file /dev/null` 防自动加载 `.env`。

### 可选显示

`~/.claude/plugins/claude-hud/config.json`：

```json
{
  "display": {
    "showTools": true,
    "showAgents": true,
    "showTodos": true,
    "showDuration": false,
    "showConfigCounts": false,
    "showSessionName": false
  }
}
```

### 验证

```bash
# 测试命令
bash -c '<statusLine.command>' 2>&1
# → [claude-hud] Initializing...
```

### 注意

- 配置后需重启 Claude Code 生效
- `/dev/tty: Device not configured` 在非 TTY 环境正常

### Combined Statusline

与 caveman badge 共用 statusline。wrapper 脚本 `~/.claude/hooks/statusline.sh`：

```bash
# 先输出 caveman 模式 badge
# 再输出 claude-hud HUD
# 由 settings.json 的 statusLine.command 调用
```

```json
{
  "statusLine": {
    "type": "command",
    "command": "bash ~/.claude/hooks/statusline.sh"
  }
}
```

---

## openspec / opsx

实验性 OpenSpec 变更工作流。openspec-* 和 opsx-* 两套命名空间。

### 安装

官方方式（npm 全局安装）：

```bash
npm install -g @fission-ai/openspec@latest
cd your-project
openspec init
```

升级：

```bash
npm install -g @fission-ai/openspec@latest
openspec update
```

项目通过 `scripts/init.sh` 的 skills.json 安装 skills。

### openspec-* 技能

| 技能 | 用途 |
|------|------|
| `openspec-explore` | 探索模式，澄清需求 |
| `openspec-new-change` | 创建新变更 |
| `openspec-ff-change` | 快速创建所有 artifacts |
| `openspec-continue-change` | 继续已有变更 |
| `openspec-apply-change` | 执行实现 |
| `openspec-verify-change` | 验证实现匹配 spec |
| `openspec-archive-change` | 归档已完成变更 |
| `openspec-sync-specs` | 同步 delta spec 到主 spec |
| `openspec-onboard` | 引导式上手指南 |

---

## vibe-* 项目技能

项目自有技能，由 `scripts/init.sh` symlink 到 `.claude/skills/`。

### 安装

```bash
scripts/init.sh
# Symlink skills/vibe-* → .claude/skills/vibe-*
```

### 技能列表

完整列表见 `skills/` 目录。核心技能：

| 技能 | 用途 |
|------|------|
| `vibe-new` | 新建开发分支和 flow |
| `vibe-continue` | 继续已有分支工作 |
| `vibe-commit` | 分类脏改动并创建 commits |
| `vibe-check` | 运行时审计和修复 |
| `vibe-done` | 分支完结清理 |
| `vibe-issue` | 创建/完善 GitHub issue |
| `vibe-save` | 保存 session handoff |
| `vibe-roadmap` | 项目路线图规划 |
| `vibe-review-code` | 结构化代码审查 |
| `vibe-orchestra` | Issue 池治理巡检 |
| `vibe-task` | 单 flow 深入诊断 |

---

## 第三方 CLI 工具

### uv（Python 包管理器）

```bash
# 安装
curl -LsSf https://astral.sh/uv/install.sh | sh
# 验证
uv --version
```

### bun / node

```bash
# bun
curl -fsSL https://bun.sh/install | bash
# 验证
bun --version
```

---

## MCP 服务器

### exa search

通过 HTTP MCP server 提供 Web 搜索和内容提取。

#### 配置

**Claude Code** — 在 `~/.claude/settings.json` 中配置（非 plugin 方式）：

```json
{
  "mcpServers": {
    "exa": {
      "type": "http",
      "url": "https://mcp.exa.ai/mcp",
      "headers": {
        "x-exa-api-key": "${EXA_API_KEY}"
      }
    }
  }
}
```

API key 从环境变量读取，在 `settings.json` 的 `env` 字段设置：

```json
{
  "env": {
    "EXA_API_KEY": "<your-key>"
  }
}
```

**npm 包方式**（备选，需要 API key）：

```json
{
  "mcpServers": {
    "exa": {
      "command": "npx",
      "args": ["-y", "exa-mcp-server"],
      "env": { "EXA_API_KEY": "<your-key>" }
    }
  }
}
```

**Codex** 使用 CLI 命令配置：

```bash
codex mcp add exa --url https://mcp.exa.ai/mcp
```

#### 优势

- HTTP MCP server 方式使用 API key 验证
- 插件方式每次 session 需要 OAuth 交互验证，不推荐

#### 验证

MCP server 启动后，tools 列表中应出现 `web_search_exa` 和 `web_fetch_exa`。

---

### context7

编程库文档查询。通过 Claude Code plugin 激活。

#### 配置

已在 `enabledPlugins` 中启用 `context7@claude-plugins-official`。

#### 使用

```bash
# 先解析库 ID
resolve-library-id <libraryName> <query>
# 再查询文档
query-docs <libraryId> <query>
```

---

## Git 配置注意事项

### remote fetch 配置

bare repo + worktree 设置中，确保 `remote.origin.fetch` 为 `+refs/heads/*:refs/remotes/origin/*`（拉取全部分支），而非默认的 `HEAD`。

```bash
git config remote.origin.fetch "+refs/heads/*:refs/remotes/origin/*"
```

### Hook 目录

worktree 的 hooks 位于 shared `core.hooksPath` 或默认 git common dir 下。graphify 自动管理 `post-commit` 和 `post-checkout`。

---

## 清理说明

### extraKnownMarketplaces

`settings.json` 中 `extraKnownMarketplaces` 的条目会自动同步到 `known_marketplaces.json`。如果已通过 `claude plugin marketplace add` 安装过，`extraKnownMarketplaces` 中的声明是冗余的，可以删除。

```json
// 可以删除的条目（已存在于 known_marketplaces.json）
"caveman": { "source": { "source": "github", "repo": "JuliusBrussee/caveman" } },
"claude-hud": { "source": { "source": "github", "repo": "jarrodwatts/claude-hud" } }
```

### blocklist

`code-review@claude-plugins-official` 在 blocklist 中标记为 test，不影响功能。

---

## 关联文档

- [CLAUDE.md](../../CLAUDE.md) — 项目上下文与硬规则
- [glossary.md](glossary.md) — 术语真源
- [configuration-standard.md](configuration-standard.md) — 配置标准
- [MCP Server Setup](../../docs/v3/mcp-server-setup.md) — MCP 服务配置

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-07-07 | 初始版本（claude-hud + caveman） |
| 2026-07-07 | 扩展至全部 10+ 工具链 |
| 2026-07-07 | 增加 Codex 兼容说明、官方安装命令、跨平台配置 |