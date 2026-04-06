---
name: vibe-instruction
description: Use when you need an overview of the Vibe Center project, its implementations (vibe2 shell and vibe3 python), the available commands, and the standard development workflow. This is the meta-skill that orients any agent to the project.
---

# /vibe-instruction - 项目导览

这是所有 agent 的入口导览技能。用于快速了解项目结构、可用命令和开发工作流。

---

## 项目结构概览

Vibe Center 包含**两个并行实现**：

```
vibe-center/
  bin/vibe          # V2 Shell 入口 (重定向到 V3)
  lib/              # V2 Shell 核心逻辑
  config/aliases.sh # V2 alias 定义
  src/vibe3/        # V3 Python 实现 (当前核心)
  skills/           # AI agent 技能集 (Markdown)
  .agent/           # 规则、规范、工作流、Supervisor 上下文
```

---

## V2 Shell 部分（vibe2）

V2 提供底层 alias 和环境工具。

**核心 alias**：

| alias            | 含义                                |
| ---------------- | ----------------------------------- |
| `wtnew <branch>` | 创建新 worktree（git worktree add） |
| `vup`            | 更新主仓库 + 当前 worktree          |

**V2 环境命令**：

```bash
bin/vibe check          # 验证环境 (V2 版)
bin/vibe tool           # 工具管理
bin/vibe keys <list|set|get|init>  # 密钥管理
```

---

## V3 Python 部分（vibe3）

V3 是当前的人机协作编排层，负责 issue / branch / PR 的创联与本地 flow / handoff 协作增强。

**运行方式**：

```bash
# 推荐给 agent / tmux / server 子进程使用仓库真源入口
uv run python src/vibe3/cli.py <command>
# 人类本地交互可以继续使用 alias
vibe3 <command>
```

### 核心命令组

#### status - 全局看板 (主入口)

```bash
uv run python src/vibe3/cli.py task status             # 查看所有活跃 flow、Orchestra 追踪进度及环境状态
uv run python src/vibe3/cli.py task status --all       # 含已完成/中止的历史记录
```

#### flow - 逻辑现场管理

```bash
uv run python src/vibe3/cli.py flow show          # [高频] 查看当前分支绑定的 task、PR、milestone 及 Timeline
uv run python src/vibe3/cli.py flow status        # 仅查看活跃 flow 列表
uv run python src/vibe3/cli.py flow update        # [高频] 注册当前分支为 flow，或更新其 metadata
uv run python src/vibe3/cli.py flow bind <issue>  # [高频] 绑定 issue 到当前 flow (role: task/related/dependency)
uv run python src/vibe3/cli.py flow blocked       # 标记当前 flow 为阻塞，并记录原因
```

#### run - Agent 执行引擎

```bash
uv run python src/vibe3/cli.py run --skill <name> # 派发特定 skill 执行 (推荐使用 --async 后台运行)
uv run python src/vibe3/cli.py run "指令描述"      # 派发自定义指令执行
uv run python src/vibe3/cli.py run --plan <file>  # 执行指定的实现计划
uv run python src/vibe3/cli.py run --worktree     # 在隔离的临时 worktree 中执行 (防止污染当前环境)
```

#### plan - 计划生成

```bash
uv run python src/vibe3/cli.py plan --issue <issue>     # 基于 issue 内容生成实现计划
uv run python src/vibe3/cli.py plan --spec --msg "内容" # 基于语义描述生成实现计划
```

#### handoff - 协作交接记录

```bash
uv run python src/vibe3/cli.py handoff show       # 查看当前分支的 agent 交接链 (Chain of Thought)
uv run python src/vibe3/cli.py handoff append "..." --kind milestone # 记录关键发现或里程碑
uv run python src/vibe3/cli.py handoff plan/report/audit # 记录标准阶段交接
```

#### inspect - 代码智能分析

```bash
vibe3 inspect symbols <file>:<symbol> # 跨文件查找符号引用
vibe3 inspect base origin/main        # 分析当前分支与主干的结构差异
vibe3 inspect files <path>            # 统计文件 LOC、方法数与内部依赖
```

---

## 标准开发工作流

### 1. 启动任务

```bash
# 使用 skill 自动化（推荐）
/vibe-new <feature-description>  # 选/建 issue -> 切到 dev/issue-<id> -> flow update/bind -> 按需创联 PR

# 或手动启动人机协作流
git checkout -b dev/issue-123
uv run python src/vibe3/cli.py flow update
uv run python src/vibe3/cli.py flow bind 123 --role task
uv run python src/vibe3/cli.py pr create --base main --yes   # 按需
```

### 2. 执行与观察

```bash
uv run python src/vibe3/cli.py plan --issue 123   # 生成计划
uv run python src/vibe3/cli.py run --plan --async # 派发执行
uv run python src/vibe3/cli.py flow show          # 轮询 Timeline 观察进度
uv run python src/vibe3/cli.py handoff show       # 阅读 agent 留下的 Findings
```

### 3. 提交与收口

```bash
/vibe-commit                     # 整理变更并推送到 PR
/vibe-integrate                  # 等待 CI 与 Review，直到 merge-ready
/vibe-done                       # PR 进入终态后做 issue / handoff / 现场收口
```

---

## 核心边界与误区

1. **flow ≠ branch**：flow 是绑定在 branch 上的逻辑上下文；branch 生命周期优先由 git / gh 管理。
2. **真源在 `.git/vibe3/handoff.db`**：所有 worktree 共享该 SQLite 数据库，由主仓库的 `git common dir` 承载。
3. **不再有 flow new / flow done / 顶层 status**：V3 只保留最小共享状态入口；branch / issue / PR 常规生命周期优先直接使用 git / gh。
4. **handoff 不是数据库**：`.git/vibe3/handoff/` 存储的是 Markdown 交接文件，用于人机协作；状态流转以 SQLite 库为准。
5. **恢复已有 branch 统一用 `/vibe-continue`**：`/vibe-start` 已不再作为现行入口。
6. **Orchestra 是后台服务**：`vibe3 serve` 启动心跳轮询，自动处理 Webhook 事件，`vibe3 task status` 是它的展示面。

---

## 故障排查

- **状态不一致**：运行 `vibe3 check` 进行审计。
- **环境配置**：查看 `config/settings.yaml`。
- **调用追踪**：任何命令加 `--trace` 可查看内部调用栈。
- **权限/API 错误**：运行 `bin/vibe keys list` 检查 Token 有效性。
