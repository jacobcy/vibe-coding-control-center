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
# 1. 安装依赖
zsh scripts/install.sh

# 2. 同步 Python 依赖
uv sync --dev

# 3. 基础检查
vibe check
uv run python src/vibe3/cli.py status
```

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
