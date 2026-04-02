# 仓库语义清理 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 清理仓库语义，使入口文件、模块 README、skill 文档和标准文档与 PR #412 重构后的实际代码一致。

**Architecture:** 分三阶段执行：Phase 1 建立模块 README（自下而上定义语义），Phase 2 更新入口文件和标准文档（将模块语义传播到顶层），Phase 3 清理 skill 文档（确保用户面向文档与代码一致）。

**Tech Stack:** Markdown docs, Python (Pydantic models, Typer CLI, FastAPI), Git

---

## 背景

PR #412 完成了 orchestra 拆分，引入了 `manager/` 模块并重新划分了 `orchestra/`、`runtime/`、`server/` 的职责。但入口文件（STRUCTURE.md, CLAUDE.md）和 skill 文档仍引用旧的模块结构，且 16 个 Python 模块中只有 2 个（observability, orchestra）有 README。

## 当前模块实际职责（经代码验证）

| 模块 | 职责 |
|------|------|
| agents/ | AI Agent 调用层（plan/review/run pipeline + pluggable backends） |
| analysis/ | 代码智能（symbol 分析、结构快照、变更范围、依赖 DAG） |
| clients/ | 外部系统客户端（Git, GitHub, AI/LiteLLM, Serena, SQLite） |
| commands/ | CLI 子命令实现（vibe3 各 Typer 路由） |
| config/ | 配置加载与 schema（YAML → Pydantic 验证） |
| exceptions/ | 统一异常层级（VibeError → UserError/GitError/...） |
| manager/ | Orchestra 执行代理（issue→flow 映射、命令构建、worktree 管理、结果处理） |
| models/ | 领域数据模型（flow, PR, snapshot, trace, review） |
| observability/ | 日志 + 链路追踪 + 审计（loguru, Tracer） |
| orchestra/ | 编排中枢（issue 分诊、事件调度、circuit breaker） |
| prompts/ | Prompt 模板组装（Jinja2 变量解析 + provenance） |
| runtime/ | 事件驱动运行时（EventBus, HeartbeatServer, 子进程执行） |
| server/ | HTTP 服务层（FastAPI webhook, MCP, health check） |
| services/ | 核心业务逻辑（flow/PR/task/handoff/check/scoring） |
| ui/ | CLI 输出格式化（Rich 渲染，agent-friendly） |
| utils/ | 通用工具函数（branch/issue ref 解析、git 路径） |

---

## Phase 1: 模块 README（14 个文件）

为每个缺少 README.md 的 src/vibe3 子模块创建 README。格式统一：

```markdown
# <Module Name>

<一句话职责>

## 职责

- 要点 1
- 要点 2

## 关键组件

| 文件 | 职责 |
|------|------|
| file.py | 做什么 |

## 依赖关系

- 依赖: models, clients
- 被依赖: commands, services
```

### Task 1: agents/ README

**Files:**
- Create: `src/vibe3/agents/README.md`

**Step 1: 创建 README**

```markdown
# Agents

AI Agent 调用层，提供 plan/review/run 三条执行 pipeline 和可插拔 backend。

## 职责

- 定义 AgentBackend 协议（pluggable agent 接口）
- 实现 plan agent（生成实现计划）
- 实现 review agent（代码审查）
- 实现 run agent（通用任务执行）
- 管理 agent session 生命周期

## 关键组件

| 文件 | 职责 |
|------|------|
| base.py | AgentBackend 协议定义 |
| backends/ | 具体 backend 实现（CodeagentBackend） |
| pipeline.py | 执行 pipeline 抽象 |
| plan_agent.py | Plan 生成 agent |
| review_agent.py | Code review agent |
| run_agent.py | 通用执行 agent |
| runner.py | Agent 执行器（统一调度入口） |
| session_service.py | Session 持久化 |

## 依赖关系

- 依赖: models (AgentOptions/AgentResult), prompts (模板组装), clients (AI client)
- 被依赖: commands/run, commands/review, commands/plan, manager
```

**Step 2: Commit**

```bash
git add src/vibe3/agents/README.md
git commit -m "docs(agents): add module README"
```

### Task 2: analysis/ README

**Files:**
- Create: `src/vibe3/analysis/README.md`

**Step 1: 创建 README**

```markdown
# Analysis

代码智能层，提供 symbol 分析、结构快照、变更范围评估和依赖 DAG。

## 职责

- 基于 Serena 的符号引用分析
- 代码结构快照与 diff
- 变更范围评估（pre-push scope）
- 依赖 DAG 构建
- 测试选择器（pre-push test selector）
- coverage 数据整合

## 关键组件

| 文件 | 职责 |
|------|------|
| serena_service.py | Serena 符号分析服务 |
| snapshot_service.py | 代码结构快照 |
| snapshot_diff.py | 快照差异比较 |
| structure_service.py | AST 结构分析 |
| dag_service.py | 依赖 DAG |
| change_scope_service.py | 变更影响范围 |
| pre_push_scope.py | Pre-push 范围评估 |
| pre_push_test_selector.py | 变更驱动的测试选择 |
| coverage_service.py | Coverage 数据 |
| command_analyzer.py | CLI 命令静态分析 |

## 依赖关系

- 依赖: clients (SerenaClient, GitClient), models (snapshot/inspection models)
- 被依赖: commands/inspect, services/check_service, prompts (context builder)
```

**Step 2: Commit**

```bash
git add src/vibe3/analysis/README.md
git commit -m "docs(analysis): add module README"
```

### Task 3: clients/ README

**Files:**
- Create: `src/vibe3/clients/README.md`

**Step 1: 创建 README**

```markdown
# Clients

外部系统客户端层，为 Git, GitHub, AI, Serena, SQLite 提供最小包装。

## 职责

- Git 操作（branch, diff, status, worktree）
- GitHub API（PR, issue, review, comment）
- AI 文本生成（LiteLLM 多模型支持）
- Serena 符号查询
- SQLite 本地状态持久化

## 关键组件

| 文件 | 职责 |
|------|------|
| git_client.py | Git 操作主入口 |
| git_branch_ops.py | 分支操作 |
| git_diff_hunks.py | Diff 解析 |
| git_status_ops.py | Status 查询 |
| git_worktree_ops.py | Worktree 操作 |
| github_client.py | GitHub API 主入口 |
| github_client_base.py | GitHub 基础客户端 |
| github_pr_ops.py | PR 操作 |
| github_issues_ops.py | Issue 操作 |
| github_review_ops.py | Review 操作 |
| ai_client.py | AI 调用（LiteLLM） |
| serena_client.py | Serena 符号分析 |
| sqlite_client.py | SQLite 持久化 |
| protocols.py | 客户端接口协议 |

## 依赖关系

- 依赖: models, config, exceptions
- 被依赖: services, analysis, agents, commands, manager, orchestra
```

**Step 2: Commit**

```bash
git add src/vibe3/clients/README.md
git commit -m "docs(clients): add module README"
```

### Task 4: commands/ README

**Files:**
- Create: `src/vibe3/commands/README.md`

**Step 1: 创建 README**

```markdown
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
```

**Step 2: Commit**

```bash
git add src/vibe3/commands/README.md
git commit -m "docs(commands): add module README"
```

### Task 5: config/ README

**Files:**
- Create: `src/vibe3/config/README.md`

**Step 1: 创建 README**

```markdown
# Config

配置加载与 schema 验证层，从 YAML 文件加载配置并通过 Pydantic 验证。

## 职责

- 加载 config/settings.yaml 配置文件
- Pydantic schema 验证和类型安全
- 运行时配置访问 (get_config/reload_config)
- 子配置域：Orchestra, PR, AI, Code Limits

## 关键组件

| 文件 | 职责 |
|------|------|
| settings.py | 主配置 schema (VibeConfig) |
| settings_orchestra.py | Orchestra 子配置 |
| settings_pr.py | PR quality gate 子配置 |
| loader.py | YAML 加载逻辑 |
| get.py | 全局配置访问入口 |

## 注意

配置 YAML 文件位于仓库根目录 `config/settings.yaml`，不在 `src/vibe3/config/` 下。
本模块（`src/vibe3/config/`）负责**加载和验证**，不存储配置文件本身。

## 依赖关系

- 依赖: (无内部依赖，读取仓库根 config/settings.yaml)
- 被依赖: 几乎所有模块
```

**Step 2: Commit**

```bash
git add src/vibe3/config/README.md
git commit -m "docs(config): add module README"
```

### Task 6: exceptions/ README

**Files:**
- Create: `src/vibe3/exceptions/README.md`

**Step 1: 创建 README**

```markdown
# Exceptions

统一异常层级，所有 vibe3 异常从 VibeError 派生。

## 职责

- 定义异常基类 VibeError（含 recoverable 标志）
- 分类异常：UserError, ConfigError, GitError, GitHubError, SerenaError, SystemError
- 支持 CLI 层统一错误展示

## 异常层级

```
VibeError (base, recoverable=True)
+-- UserError          用户操作不符
+-- ConfigError        配置错误
+-- GitError           Git 操作失败
+-- GitHubError        GitHub API 错误
+-- SerenaError        Serena 分析失败
+-- SystemError        系统故障(recoverable=False)
```

## 依赖关系

- 依赖: (无)
- 被依赖: 所有模块
```

**Step 2: Commit**

```bash
git add src/vibe3/exceptions/README.md
git commit -m "docs(exceptions): add module README"
```

### Task 7: manager/ README

**Files:**
- Create: `src/vibe3/manager/README.md`

**Step 1: 创建 README**

```markdown
# Manager

Orchestra 的执行代理层，负责将 issue 映射到 flow，构建和执行 agent 命令，管理 worktree 生命周期。

## 职责

- Issue → Flow 映射与创建
- Agent 命令构建（plan/review/run）
- Worktree 生命周期管理（创建、复用、回收）
- 命令执行与事件记录
- 执行结果处理

## 关键组件

| 文件 | 职责 |
|------|------|
| flow_manager.py | Issue-to-flow 映射和 flow 创建 |
| command_builder.py | 构建可执行的 agent 命令 |
| manager_executor.py | 命令执行 + 事件日志 |
| worktree_manager.py | Worktree 创建/查找/回收 |
| result_handler.py | Agent 执行结果处理 |
| prompts.py | Manager 专用 prompt 构建 |

## 与 orchestra 的关系

- **orchestra**: 决策层 — 决定对 issue 做什么（分诊、调度）
- **manager**: 执行层 — 执行 orchestra 的决策（创建 flow、跑 agent、管 worktree）

## 依赖关系

- 依赖: services (FlowService), clients (Git/GitHub), agents, models, config
- 被依赖: orchestra (dispatcher 调用 manager)
```

**Step 2: Commit**

```bash
git add src/vibe3/manager/README.md
git commit -m "docs(manager): add module README"
```

### Task 8: models/ README

**Files:**
- Create: `src/vibe3/models/README.md`

**Step 1: 创建 README**

```markdown
# Models

Pydantic 领域数据模型，定义系统中流转的核心数据结构。

## 职责

- 定义 Flow 状态模型（FlowState, ExecutionStatus）
- 定义 PR 模型（CreatePRRequest, PRResponse）
- 定义代码分析模型（FileSnapshot, StructureDiff, CallNode）
- 定义执行追踪模型（ExecutionStep, TraceOutput）
- 定义 Review/Agent 模型（AgentOptions, AgentResult）

## 关键组件

| 文件 | 职责 |
|------|------|
| flow.py | Flow 状态、执行状态 |
| pr.py | PR 请求/响应 |
| snapshot.py | 代码结构快照 |
| inspection.py | 代码分析结果 |
| trace.py | 执行追踪 |
| review.py | Review 模型 |
| review_runner.py | Agent 选项/结果 |
| orchestration.py | IssueInfo 编排模型 |
| plan.py | Plan 模型 |
| change_source.py | 变更源元数据 |
| coverage.py | Coverage 数据 |
| project_item.py | GitHub Project item |
| task_bridge.py | Task-review 桥接 |

## 依赖关系

- 依赖: (无内部依赖，纯数据定义)
- 被依赖: 几乎所有模块
```

**Step 2: Commit**

```bash
git add src/vibe3/models/README.md
git commit -m "docs(models): add module README"
```

### Task 9: prompts/ README

**Files:**
- Create: `src/vibe3/prompts/README.md`

**Step 1: 创建 README**

```markdown
# Prompts

Prompt 模板组装层，加载模板、解析变量、记录 provenance。

## 职责

- 加载 Jinja2/文本模板（config/prompts.yaml）
- 注册和解析变量 provider（code/git/config 来源）
- 组装最终 prompt（变量替换 + 段落拼接）
- 记录变量 provenance（用于审计追踪）
- 模板验证

## 关键组件

| 文件 | 职责 |
|------|------|
| assembler.py | PromptAssembler 主拼装器 |
| recipe_service.py | Recipe 加载与管理 |
| template_loader.py | 模板文件加载 |
| builtin_providers.py | 内置变量 provider |
| provider_registry.py | Provider 注册中心 |
| context_builder.py | 运行时上下文构建 |
| models.py | PromptRecipe, PromptRenderResult |
| validation.py | 模板校验 |

## 依赖关系

- 依赖: clients (GitClient, 获取 git 上下文), config, analysis
- 被依赖: agents (prompt 构建), manager (manager prompts)
```

**Step 2: Commit**

```bash
git add src/vibe3/prompts/README.md
git commit -m "docs(prompts): add module README"
```

### Task 10: runtime/ README

**Files:**
- Create: `src/vibe3/runtime/README.md`

**Step 1: 创建 README**

```markdown
# Runtime

事件驱动运行时基础设施，提供事件总线、心跳轮询和子进程执行能力。

## 职责

- EventBus 事件模型和服务接口（ServiceBase）
- HeartbeatServer 轮询循环和事件路由
- 子进程执行器（timeout/capture）
- CircuitBreaker 失败分类和熔断

## 关键组件

| 文件 | 职责 |
|------|------|
| event_bus.py | GitHubEvent 模型 + ServiceBase 接口 |
| heartbeat.py | HeartbeatServer 轮询 + 事件分发 |
| executor.py | run_command 子进程执行 |
| circuit_breaker.py | 失败率追踪和服务熔断 |

## 与 server/orchestra 的关系

- **server**: HTTP 入口 — 接收 webhook，转为 GitHubEvent
- **runtime**: 事件调度 — HeartbeatServer 轮询事件，路由到 services
- **orchestra**: 业务编排 — 注册为 runtime service，处理 issue 事件

## 依赖关系

- 依赖: models, config
- 被依赖: server (启动 heartbeat), orchestra (注册 services)
```

**Step 2: Commit**

```bash
git add src/vibe3/runtime/README.md
git commit -m "docs(runtime): add module README"
```

### Task 11: server/ README

**Files:**
- Create: `src/vibe3/server/README.md`

**Step 1: 创建 README**

```markdown
# Server

HTTP 服务层，提供 GitHub webhook 接收、MCP 服务和健康检查。

## 职责

- FastAPI webhook 接收和签名验证
- vibe3 serve CLI（start/stop/status）
- MCP (Model Context Protocol) 服务
- Health check 端点
- Tailscale 网络集成

## 关键组件

| 文件 | 职责 |
|------|------|
| app.py | FastAPI app + webhook 路由 + CLI |
| mcp.py | MCP 服务集成 |
| registry.py | 服务初始化 + Tailscale 设置 |

## 依赖关系

- 依赖: runtime (HeartbeatServer), orchestra (服务注册), config
- 被依赖: (顶层入口，不被其他模块依赖)
```

**Step 2: Commit**

```bash
git add src/vibe3/server/README.md
git commit -m "docs(server): add module README"
```

### Task 12: services/ README

**Files:**
- Create: `src/vibe3/services/README.md`

**Step 1: 创建 README**

```markdown
# Services

核心业务逻辑层，实现 flow/PR/task/handoff 等工作流。

## 职责

- Flow 生命周期管理（创建、状态转变、查询、投影）
- PR 全生命周期（创建、评分、merge、ready）
- Task 绑定与管理
- Handoff 记录与恢复
- Pre-push 检查
- Label/Milestone 管理
- 版本管理

## 关键组件

| 文件 | 职责 |
|------|------|
| flow_service.py | Flow CRUD + 状态转变 |
| flow_lifecycle.py | Flow 生命周期 mixin |
| flow_query_mixin.py | Flow 查询 mixin |
| flow_projection_service.py | Flow 状态投影 |
| pr_service.py | PR 主服务 |
| pr_create_usecase.py | PR 创建用例 |
| pr_ready_usecase.py | PR ready 用例 |
| pr_scoring_service.py | PR 质量评分 |
| task_service.py | Task 绑定管理 |
| task_usecase.py | Task 用例 |
| handoff_service.py | Handoff 记录服务 |
| handoff_recorder_unified.py | 统一 handoff 记录器 |
| check_service.py | Pre-push 检查 |
| label_service.py | GitHub label 管理 |
| milestone_service.py | Milestone 管理 |
| version_service.py | 版本号管理 |
| ai_service.py | AI 辅助决策 |
| signature_service.py | Flow 签名验证 |
| spec_ref_service.py | OpenSpec 集成 |

## 依赖关系

- 依赖: clients (Git/GitHub/SQLite), models, config, exceptions
- 被依赖: commands, manager, orchestra
```

**Step 2: Commit**

```bash
git add src/vibe3/services/README.md
git commit -m "docs(services): add module README"
```

### Task 13: ui/ README

**Files:**
- Create: `src/vibe3/ui/README.md`

**Step 1: 创建 README**

```markdown
# UI

CLI 输出格式化层，使用 Rich 渲染 flow/task/PR 等状态展示。

## 职责

- Rich Console 实例管理（agent-friendly，highlight=False）
- Flow 状态渲染（表格、时间线）
- PR 状态渲染
- Task 状态渲染
- Handoff 记录展示
- Orchestra 状态展示

## 关键组件

| 文件 | 职责 |
|------|------|
| console.py | 共享 Rich Console 实例 |
| flow_ui.py | Flow 状态展示 |
| flow_ui_timeline.py | Flow 时间线可视化 |
| pr_ui.py | PR 状态展示 |
| task_ui.py | Task 状态展示 |
| handoff_ui.py | Handoff 记录展示 |
| orchestra_ui.py | Orchestra 状态展示 |

## 依赖关系

- 依赖: models (渲染数据结构)
- 被依赖: commands (输出格式化)
```

**Step 2: Commit**

```bash
git add src/vibe3/ui/README.md
git commit -m "docs(ui): add module README"
```

### Task 14: utils/ README

**Files:**
- Create: `src/vibe3/utils/README.md`

**Step 1: 创建 README**

```markdown
# Utils

通用工具函数，提供 branch 解析、issue 引用解析、git 路径计算等基础能力。

## 关键组件

| 文件 | 职责 |
|------|------|
| branch_utils.py | Branch 名称解析与验证 |
| git_helpers.py | Git 目录和 handoff 路径计算 |
| issue_ref.py | Issue 引用解析（#123, owner/repo#123） |
| trace.py | Trace 工具函数 |

## 依赖关系

- 依赖: (无内部依赖)
- 被依赖: services, commands, clients
```

**Step 2: Commit**

```bash
git add src/vibe3/utils/README.md
git commit -m "docs(utils): add module README"
```

---

## Phase 2: 入口文件更新

### Task 15: 更新 STRUCTURE.md 模块清单

**Files:**
- Modify: `STRUCTURE.md` (约第 160-175 行 "主要模块" 部分)

**Step 1: 替换 src/vibe3 模块列表**

将现有的模块列表：
```
- `cli.py` - CLI 主入口
- `commands/` - 命令实现
- `runtime/` - 运行时核心
- `server/` - 服务器逻辑
- `manager/` - 编排管理
- `services/` - 业务逻辑层
- `clients/` - 外部客户端
- `models/` - 数据模型
- `utils/` - 工具函数
- `observability/` - 可观测性
```

替换为完整的 16 模块清单：
```
- `cli.py` - CLI 主入口（Typer 路由分发）
- `agents/` - AI Agent 调用层（plan/review/run pipeline + backends）
- `analysis/` - 代码智能（symbol 分析、结构快照、变更范围）
- `clients/` - 外部系统客户端（Git, GitHub, AI, Serena, SQLite）
- `commands/` - CLI 子命令实现
- `config/` - 配置加载与 Pydantic schema 验证
- `exceptions/` - 统一异常层级
- `manager/` - Orchestra 执行代理（flow 映射、命令构建、worktree）
- `models/` - Pydantic 领域数据模型
- `observability/` - 日志、链路追踪、审计
- `orchestra/` - 编排中枢（issue 分诊、事件调度）
- `prompts/` - Prompt 模板组装与变量解析
- `runtime/` - 事件驱动运行时（EventBus, Heartbeat）
- `server/` - HTTP 服务层（webhook, MCP, health check）
- `services/` - 核心业务逻辑（flow/PR/task/handoff/check）
- `ui/` - CLI 输出格式化（Rich 渲染）
- `utils/` - 通用工具函数
```

**Step 2: Commit**

```bash
git add STRUCTURE.md
git commit -m "docs(structure): update vibe3 module catalog to match post-#412 reality"
```

### Task 16: 更新 CLAUDE.md 模块描述

**Files:**
- Modify: `CLAUDE.md` (V3 Python 模块描述 + 架构分层)

**Step 1: 在 V3 Python 部分补充完整模块清单**

在 CLAUDE.md 的 V3 部分（"目录职责"一节），将现有简略描述更新为与 STRUCTURE.md 一致的 16 模块清单。

**Step 2: 更新架构分层描述**

检查 CLAUDE.md 的 Tier 1/2/3 分层，显式验证：
- Tier 1 (Shell 能力层) 不应包含 Python 模块引用
- Tier 2 (Skill 层) 包含 orchestra/ 作为编排入口
- Tier 1 附注中，V3 manager/ 被明确为执行代理
- runtime/server 归属明确：server → HTTP 入口，runtime → 事件调度

**Step 3: 验证 inspect 命令描述仍准确**

确认 CLAUDE.md 中 `vibe3 inspect` 系列命令描述未引用已改名/删除的模块路径。

**Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude): sync module descriptions with post-#412 architecture"
```

### Task 17: 更新 AGENTS.md 快速入口

**Files:**
- Modify: `AGENTS.md`

**Step 1: 运行 Quick Start 命令验证**

```bash
uv run python src/vibe3/cli.py flow show 2>&1 | head -5
uv run python src/vibe3/cli.py status 2>&1 | head -5
```

预期：两个命令均不报 import 错误或 command not found。

**Step 2: 检查 AGENTS.md 中模块引用**

```bash
grep -n "orchestra\|manager\|runtime\|server" AGENTS.md
```

如有过时引用，更新为重构后的正确描述。

**Step 3: Commit（如有变更）**

```bash
git add AGENTS.md
git commit -m "docs(agents): update quick start references"
```

---

## Phase 3: Skill 文档与标准文档审计

### Task 18: 审计 skills/ 目录

**Files:**
- Review: 所有 `skills/*/SKILL.md`（20 个文件）
- 重点: `skills/vibe-orchestra/SKILL.md`, `skills/vibe-manager/SKILL.md`

**Step 1: 全量搜索模块引用**

```bash
for skill in skills/*/SKILL.md; do
  matches=$(grep -c "orchestra\|manager\|agents\|analysis\|runtime\|server" "$skill" 2>/dev/null)
  if [ "$matches" -gt 0 ]; then
    echo "$skill: $matches matches"
  fi
done
```

**Step 2: 检查 vibe-orchestra SKILL.md**

确认描述反映拆分后的职责：分诊 + 调度（不包含 manager 执行逻辑）。

**Step 3: 检查 vibe-manager SKILL.md**

确认描述正确：issue→flow 映射、命令构建、worktree 管理。

**Step 4: 交叉检查 vibe-orchestra 和 vibe-manager**

两个 SKILL.md 的职责描述不应有重叠或矛盾。

**Step 5: 修复其他 skill 中的过时引用**

将 Step 1 找到的不一致引用逐一修复。

**Step 6: Commit**

```bash
git add skills/
git commit -m "docs(skills): align SKILL.md descriptions with post-#412 module split"
```

### Task 19: 审计 .agent/rules/ 引用

**Files:**
- Review: `.agent/rules/coding-standards.md`
- Review: `.agent/rules/python-standards.md`
- Review: `.agent/rules/patterns.md`
- Review: `.agent/rules/common.md`

**Step 1: 搜索规则文档中对模块的引用**

```bash
grep -rn "orchestra\|manager\|runtime\|server" .agent/rules/
```

**Step 2: 确认引用路径和职责描述与实际一致**

**Step 3: 修复发现的不一致**

**Step 4: Commit**

```bash
git add .agent/rules/
git commit -m "docs(rules): align module references with post-#412 structure"
```

---

## Phase 4: 验证

### Task 20: 全局验证

**Step 1: 确认所有 README 存在**

```bash
for dir in agents analysis clients commands config exceptions manager models prompts runtime server services ui utils; do
  test -f "src/vibe3/$dir/README.md" && echo "OK: $dir" || echo "MISSING: $dir"
done
```

预期：14 个 OK + 已有的 observability 和 orchestra = 全部 16 个模块

**Step 2: README 依赖关系交叉验证**

每个 README 的"依赖/被依赖"声明应双向一致。例如：
- agents/README 说 "被依赖: commands" → commands/README 应说 "依赖: agents"
- 不要求完美对称，但关键依赖链不能遗漏

```bash
grep -h "依赖:" src/vibe3/*/README.md | sort
```

**Step 3: 检查无 broken links**

```bash
grep -rn '\[.*\](.*\.md)' STRUCTURE.md CLAUDE.md AGENTS.md | head -20
```

**Step 4: 运行 lint 确认无格式问题**

```bash
uv run ruff check src && uv run black --check src tests/vibe3
```

**Step 5: 最终 commit（如有修复）**

---

## 交付清单

| 交付物 | 数量 | 状态 |
|--------|------|------|
| 模块 README.md | 14 个新建 | Phase 1 |
| STRUCTURE.md 更新 | 1 个修改 | Phase 2 |
| CLAUDE.md 更新 | 1 个修改 | Phase 2 |
| AGENTS.md 审查 | 1 个审查/可能修改 | Phase 2 |
| Skill SKILL.md 审计 | 20 个审查/修复 | Phase 3 |
| .agent/rules/ 审计 | 4+ 个审查/修复 | Phase 3 |
| 依赖交叉验证 | 1 次 | Phase 4 |

**预估 commit 数**：~18-20 个

## 风险与注意事项

1. **config/ 路径混淆**：`src/vibe3/config/` 是加载器，`config/` (仓库根) 是配置文件存储，README 需明确区分
2. **runtime vs server 重叠**：两者都涉及事件处理，README 需通过"与 X 的关系"段落明确边界
3. **orchestra vs manager 重叠**：circuit_breaker.py 在两个模块中都存在，需在 README 中说明各自用途差异
