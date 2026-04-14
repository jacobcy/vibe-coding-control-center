# Vibe Center 2.0

Vibe Center 是一个面向 AI 协作开发的编排工具箱。它保留 V2 Shell 能力层，也提供 V3 Python 运行时，目标不是替代 `git` 和 `gh`，而是把本地 execution scene、agent handoff、runtime observation 和 skill governance 收敛到一套清晰边界里。

## 当前语义

- `git` 负责 branch 生命周期
- `gh` 负责 issue / PR 的常规远端操作
- `vibe3` 负责本地 flow scene、issue 绑定、handoff、runtime observation
- `skills/` 与 workflows 负责编排，不负责重新发明共享状态模型
- Python 模块只提供现场创建、清理、复用、观察与必需能力，不默认推进业务 workflow

一句话：模块给能力，agent / skill 做判断。

## 双栈结构

### V2 Shell

V2 保留环境工具和基础 shell 能力：

- `vibe tool`
- `vibe check`
- `vibe keys`
- `wtnew` 等 worktree / alias 辅助能力

### V3 Python

V3 是当前的本地运行时与协作主系统，核心能力包括：

- `flow update` / `flow bind` / `flow show` / `flow status`
- `status` 全局总览
- `handoff` 本地协作增强
- `plan` / `run` / `review` agent 执行入口
- `serve` / orchestra / manager 运行时能力

## 快速开始

```bash
# 1. 全局安装；会同步基础文件，并自动对当前项目补跑一次 init
zsh scripts/install.sh

# 2. 重新加载 shell
source ~/.zshrc   # 或你的实际 shell rc

# 3. 启动 Claude / Codex / Gemini 等工具后，优先用引导式入口
/vibe-onboard

# 4. 或手工检查
vibe doctor
vibe keys check

# 5. 手动编辑密钥文件
$EDITOR ~/.vibe/keys.env

# 6. 检查 skills / 能力体系
vibe skills check
/vibe-skills-manager
```

说明：

- `scripts/install.sh` 负责全局安装与命令可用性，并会自动对当前项目补跑一次 `scripts/init.sh`
- `scripts/init.sh` 负责当前项目 / worktree 的初始化（第三方 skills、OpenSpec、symlink、hooks、任务迁移等），不是安装脚本，而且可重复执行
- `wtnew` 与 V3 worktree 创建路径也会自动补跑一次 `scripts/init.sh`
- `vibe doctor` 负责工具与 Claude plugins 的事实检查
- `vibe keys check` 负责认证 / key 来源检查
- `/vibe-onboard` 负责引导用户检查和配置工具、Claude plugins、keys，并介绍项目与下一步
- `vibe skills check` / `/vibe-skills-manager` 负责把 skills 体系梳理清楚，避免 codeagent-wrapper 缺少必要能力
- `~/.vibe/keys.env` 由 `config/keys.template.env` 初始化而来，按需手动编辑
- 如果在安装、初始化或使用过程中遇到任何问题，欢迎向项目开发者提交 issue 说明现场与复现步骤
- skills 体系建议：
  - Superpowers：Claude 用官方 plugin；其他 agent 用 `npx skills`
  - OpenSpec：项目内初始化，按需启用
  - Gstack：用户可选增强，建议全局安装到 `~/.claude/skills/gstack`

## Skills 入门

当 `/vibe-onboard` 和 `/vibe-skills-manager` 帮你把环境与能力体系梳理清楚后，可以从这些入口开始理解 skills：

- Superpowers
  - `/brainstorming`
- Gstack（可选增强）
  - `/office-hours`
- OpenSpec（项目内工具链）
  - `/openspec-onboard`

## 推荐工作方式

```bash
# 新分支
git checkout -b feature/example

# 注册当前现场
uv run python src/vibe3/cli.py flow update

# 绑定 issue
uv run python src/vibe3/cli.py flow bind 123

# 查看当前现场
uv run python src/vibe3/cli.py flow show

# 执行 agent
uv run python src/vibe3/cli.py run --skill vibe-manager --async
```

## 架构边界

### Tier 3: Supervisor / Standards

- `SOUL.md`
- `CLAUDE.md`
- `.agent/`
- `docs/standards/`

这一层定义规则、术语、流程边界和治理原则。

### Tier 2: Skills / Workflows

- `skills/`
- `.agent/workflows/`

这一层负责理解上下文、决定下一步、编排能力调用顺序。

### Tier 1: Capability Layer

- V2: `bin/`, `lib/`, `config/`
- V3: `src/vibe3/`

这一层只负责能力，不负责隐藏 workflow。

## V3 关键模块

- `agents/`: plan / run / review agent pipeline
- `analysis/`: symbol、snapshot、change scope
- `clients/`: Git、GitHub、SQLite、AI 客户端
- `commands/`: CLI 子命令
- `manager/`: 单 flow scene 能力与执行代理
- `orchestra/`: 多 issue / 多 flow 的事实观察、排队与调度入口
- `prompts/`: prompt 组装与 provenance
- `runtime/`: heartbeat、event bus、executor
- `server/`: webhook、MCP、health check
- `services/`: flow / PR / task / handoff 业务服务
- `ui/`: Rich 输出

## 关键原则

- assignee 是 orchestration 启动事实源
- `state/*` label 只反映 flow 实际状态，不做主驱动
- branch / worktree 清理能力属于 manager 模块，但何时清理由 agent / skill 判断
- 常驻 server 和定时巡检只是运行模式差异，不改变模块职责
- **容量限制按 live worker session 计算**：manager、planner、executor、reviewer、governance 的异步 session 都在 runtime_session registry 统一管理。容量 throttle 只看真实 live worker 数（starting/running 且探活成功），不看 active flow 数，不看服务自身 tmux。旧的 `flow_state.manager_session_id` 等字段已 deprecated，只做兼容 fallback。

## 目录速览

- `bin/`, `lib/`: V2 Shell 入口与实现
- `src/vibe3/`: V3 Python 主系统
- `skills/`: repo-local Vibe skills
- `.agent/`: rules、workflows、上下文
- `docs/`: 规范、计划、报告和参考文档
- `tests/`: V2 bats 与 V3 pytest 测试

## 文档入口

- [SOUL.md](SOUL.md): 项目宪法
- [STRUCTURE.md](STRUCTURE.md): 仓库结构与模块职责
- [CLAUDE.md](CLAUDE.md): AI 上下文与硬规则
- [AGENTS.md](AGENTS.md): agent 入口指南
- [DEVELOPER.md](DEVELOPER.md): 开发者工作流
- [docs/README.md](docs/README.md): 文档总览
- [docs/standards/glossary.md](docs/standards/glossary.md): 术语真源
