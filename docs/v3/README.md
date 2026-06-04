---
title: Vibe 3.0 Parallel Rebuild - 项目设计入口
date: 2026-03-17
authors:
  - Claude Sonnet 4.6
related_docs:
  - docs/v3/PROMPTS.md
  - SOUL.md
  - CLAUDE.md
status: active
purpose: 作为 Vibe 3.0 重构的导航入口，指向项目设计总依据和各阶段实施文档
---

# Vibe 3.0 Parallel Rebuild

> **设计总依据**: [PROMPTS.md](PROMPTS.md) - 项目设计的权威源，定义实施阶段、强制规则和核心决策

## 核心理念

将 Vibe Center 重构为**确定性、可追踪的 AI 开发编排工具**：

- **统一的基础设施层**（config、logging、error、data）
- **可追踪的命令执行**（每个命令可追踪，每个操作可记录）
- **责任链 handoff 机制**（plan/execute/review 三阶段）
- **可选的 agent 自动编排**（Orchestra，借鉴 Symphony 理念）

---

## 架构设计

Vibe3 采用分层架构与事件驱动机制，确保系统可扩展性与解耦。

- **[模块依赖关系图](architecture/module-dependencies.md)** - **(New)** 定义 22 个模块的依赖方向与风险点
- **[依赖管理机制](architecture/dependency-handling.md)** - 定义 Flow/Issue 之间的物理依赖与阻塞解除逻辑
- **[Infrastructure Guide](architecture/infrastructure-guide.md)** - 基础设施服务使用指南
- **[Capacity Control](architecture/capacity-control.md)** - 并发与容量控制详述

---

## 实施阶段（强制顺序）

按照 [PROMPTS.md](PROMPTS.md) 定义的四阶段实施，不得跳跃：

### Phase 1: Infrastructure（基础设施层）✅ 已完成

**目标**: 建立统一的基础架构，确保代码质量和可维护性

**核心交付物**:
```
src/vibe3/
├── cli.py                    # Typer 入口
├── commands/                 # 命令调度层
├── services/                 # 业务逻辑层
├── clients/                  # 外部依赖封装（Protocol 接口）
├── models/                   # Pydantic 数据模型
├── observability/            # 日志系统 ✅ 已实现
│   ├── logger.py             # 日志配置
│   └── trace.py              # 追踪系统
│   └── audit.py              # 审计系统
├── exceptions/               # 异常定义 ✅ 已实现
├── ui/                       # 展示层（Rich）
├── config/                   # 配置模块
├── adapters/                 # 适配器层（role 集成）
├── agents/                   # Agent 定义
├── analysis/                 # 代码分析
├── domain/                   # 领域事件、发布器、Handler（事件驱动架构核心）
├── environment/              # Worktree/Session 管理
├── execution/                # 执行控制（容量、生命周期、Session）
├── orchestra/                # Orchestra 服务器和调度
├── prompts/                  # 提示词模板
├── roles/                    # Manager/Planner/Executor/Reviewer 角色
├── runtime/                  # 心跳、事件路由
├── server/                   # HTTP/Webhook 服务器
└── utils/                    # 共享工具函数
```

**实施文档**: [infrastructure/](infrastructure/README.md)
- [01-data-standard.md](infrastructure/01-data-standard.md) - 数据标准
- [02-architecture.md](infrastructure/02-architecture.md) - 架构设计
- [03-coding-standards.md](infrastructure/03-coding-standards.md) - 编码标准
- [04-test-standards.md](infrastructure/04-test-standards.md) - 测试标准
- [05-logging.md](infrastructure/05-logging.md) - 日志系统
- [06-error-handling.md](infrastructure/06-error-handling.md) - 异常处理
- [07-command-standards.md](infrastructure/07-command-standards.md) - 命令参数标准
- [08-command-quick-ref.md](infrastructure/08-command-quick-ref.md) - 命令快速参考

**验收标准**:
- ✅ 所有命令包含核心参数集（`--trace`, `-v`, `--json`, `-y`）
- ✅ 所有异常继承 VibeError
- ✅ 日志系统支持 verbose 参数（0=ERROR, 1=INFO, 2=DEBUG）
- ✅ 所有外部调用在 clients/ 中封装
- ✅ 测试覆盖率达标（Services 层核心功能已测试）

---

### Phase 2: Trace（调试追踪层）⏸️ Optional/Pending

**状态**: ⏸️ **Optional/Pending** - 非阻塞阶段，可根据实际需求启动

**设计原则**:
- **调试友好** - 追踪输出人类可读，帮助理解"代码执行到哪一步了"
- **轻量级** - 不引入 OpenTelemetry，使用 `sys.settrace`，开销 < 20%
- **一次性输出** - 追踪结果直接输出到控制台，不持久化存储
- **接口预留** - 为 Phase 4 的记录追踪预留 `TraceCollector` 接口

**实施文档**: [trace/](trace/README.md)
- [codex-auto-review-plan.md](trace/codex-auto-review-plan.md) - 自动审核计划
- [codex-review-phases.md](trace/codex-review-phases.md) - 审核阶段
- [phase1-infrastructure.md](trace/phase1-infrastructure.md) - Phase 1 基础设施
- [phase2-integration.md](trace/phase2-integration.md) - Phase 2 集成
- [phase3-automation.md](trace/phase3-automation.md) - Phase 3 自动化

**验收标准**:
- [ ] `vibe3 review pr 42 --trace` 输出调用链路
- [ ] `vibe3 inspect pr 42 --trace` 输出调用链路
- [ ] 追踪开销 < 20%
- [ ] 不影响命令执行结果

---

### Phase 3: Handoff（责任链层）✅ 已完成

**目标**: 实现 plan/execute/review 三阶段责任链，确保每个操作可记录

**设计原则**:
- **三阶段流程** - Plan → Execute → Review
- **责任清晰** - 每个 agent 的操作可追溯
- **产物引用** - 通过 `*_ref` 字段引用文档，不复制正文

**实施文档**: [handoff/](handoff/README.md)
- [01-command-and-skeleton.md](handoff/01-command-and-skeleton.md) - 命令骨架
- [02-flow-task-foundation.md](handoff/02-flow-task-foundation.md) - Flow/Task 基础
- [03-pr-domain.md](handoff/03-pr-domain.md) - PR 领域
- [04-handoff-and-cutover.md](handoff/04-handoff-and-cutover.md) - Handoff 与切换
- [05-polish-and-cleanup.md](handoff/05-polish-and-cleanup.md) - 优化与清理

**验收标准**:
- [ ] 每个操作记录到 SQLite handoff store
- [ ] 每个 agent 署名（格式：`agent/model`）
- [ ] 产物引用不复制正文
- [ ] `vibe3 flow status` 显示责任链

---

### Phase 4: Orchestra（自动编排层）✅ Active

**状态**: ✅ **Active** - 已实现核心调度功能，治理层（Tier 3）已上线并持续优化中

**目标**: 实现 agent 自动编排，架构上对齐 Tier 3 治理体系（cron-supervisor, roadmap-intake）

**设计理念**:
- **不学习 Symphony 的 agent 模型**（v3 已有更完整的 handoff 体系）
- **实现 Tier 3 治理分层**：
  - L1: Cron-supervisor & Roadmap-intake（无 worktree 观察层）
  - L2: Supervisor Apply（轻量治理执行层）
  - L3: Manager 主链（代码开发层）
- **借鉴 Symphony 的调度工程问题**：
  - 如何让 daemon 安全地并发管理多个 agent 执行
  - 如何保证不重复 dispatch
  - 如何从崩溃恢复

**实施文档**: [orchestra/](orchestra/README.md)
- [prd-orchestra-integration.md](orchestra/prd-orchestra-integration.md) - Orchestra 集成 PRD
- [github-issue-draft.md](orchestra/github-issue-draft.md) - GitHub Issue 草稿

**实施条件**:
- ✅ Phase 1-3 已完成并稳定运行
- ✅ 有明确的 agent 自动编排需求
- 🔄 持续优化调度与容量控制

---

## 强制规则（不可违反）

详见 [PROMPTS.md - 强制规则](PROMPTS.md#强制规则不可违反)

### 核心原则

1. **架构分层** - CLI → Commands → Services → Clients → Models，禁止反向依赖
2. **数据真源** - GitHub 为唯一真源，SQLite handoff store 只记录执行过程
3. **代码复杂度控制** - 文件规模、函数规模、嵌套深度有严格限制
4. **禁止事项** - 不得使用 utils/、argparse、ORM、Any 类型等
5. **幂等性和确定性** - 相同输入相同输出，重新运行不得产生重复副作用

---

## 当前进度

### 实施状态

| Phase | 描述 | 状态 | 完成度 |
|-------|------|------|--------|
| Phase 1 | Infrastructure（基础设施层） | ✅ 已完成 | 100% |
| Phase 2 | Trace（调试追踪层） | ⏸️ 待启动 | 0% |
| Phase 3 | Handoff（责任链层） | ✅ 已完成 | 100% |
| Phase 4 | Orchestra（自动编排层） | ✅ Active | 持续优化 |

### 已完成

- ✅ 目录结构创建（[src/vibe3/](../../src/vibe3/)）
- ✅ Client 隔离（clients/ 包含 GitClient、GitHubClient）
- ✅ Models 定义（models/）
- ✅ Commands 实现（commands/）
- ✅ Services 实现（services/）
- ✅ UI 层（ui/）
- ✅ Config 模块（config/）
- ✅ **observability/** - 日志系统 + degraded mode
- ✅ **exceptions/** - VibeError 层级 + error codes + error tracking
- ✅ 核心参数集（`--trace`, `-v`, `--json`, `-y`）
- ✅ Handoff 责任链系统（SQLite handoff store, HandoffService）
- ✅ Orchestra 自动编排（Manager, dispatcher, ready queue）
- ✅ **Tier 3 Governance** - Cron-supervisor, Roadmap-intake, Supervisor-apply

### 现行 CLI 命令面

```
vibe3
├── flow: update, bind, blocked, show, status, list-deleted, restore
├── task: show, status, resume
├── handoff: show, status, init, append, plan, report, indicate, audit, next, verdict
├── inspect: pr, base, symbols, files, commit
├── review: pr
├── check
├── plan
├── pr
├── scan
├── snapshot
├── serve
├── mcp
├── ask
├── run
└── version
```

> `task status` 是唯一 `vibe3 task` 的聚合入口；`task show` 仅展示轻量摘要。

### Phase 2 验收状态

Phase 2 Trace 层暂未启动，但不阻塞 Orchestra 运行。
Phase 3 Handoff 层已完成所有核心交付物。

### Phase 4 当前状态

Orchestra 已实现核心调度功能：
- ✅ Driver/Tick/Async Child 架构
- ✅ Event-driven dispatch
- ✅ Capacity control (live worker sessions)
- ✅ Health check + circuit breaker
- ✅ Supervisor governance 扫描
- 🔄 持续优化调度稳定性与恢复机制

---

## 执行计划

### Phase 1 执行计划

Phase 1 已完成，后续优先级由 Orchestra 和 supervisor issue 驱动。

### 后续阶段

- Phase 2 执行计划（待制定）
- Phase 3 已交付，无需进一步计划
- Phase 4 持续优化，不制定独立计划

---

## 报告与记录

### 实施报告

- [reports/02-fix-report.md](reports/02-fix-report.md) - 修复报告
- [reports/02-blockers-cleared-report.md](reports/02-blockers-cleared-report.md) - 阻塞清除报告
- [reports/02-manual-review-report.md](reports/02-manual-review-report.md) - 手动审核报告
- [reports/03-fix-report.md](reports/03-fix-report.md) - 后续修复报告
- [reports/test-refactoring-report-2026-03-16.md](reports/test-refactoring-report-2026-03-16.md) - 测试重构报告

---

## 关键决策记录

详见 [PROMPTS.md - 关键决策记录](PROMPTS.md#关键决策记录)

### 核心决策

1. **为什么四阶段？** - Infrastructure → Trace → Handoff → Orchestra，依赖关系明确
2. **为什么 Engine/Runtime 冻结？** - v3 已有更完整的 handoff 体系，DAG 引擎复杂度高
3. **为什么 Trace 分两个阶段？** - Phase 2 调试追踪（现在）+ Phase 4 记录追踪（可选）
4. **为什么不学习 Symphony 的 agent 模型？** - v3 的 handoff 体系更适合多 agent 场景

---

## 参考文档

### 项目宪法
- **[SOUL.md](../../SOUL.md)** - 项目宪法和核心原则
- **[CLAUDE.md](../../CLAUDE.md)** - AI Agent 开发协议
- **[AGENTS.md](../../AGENTS.md)** - AI Agent 入口指南

### 设计文档
- **[PROMPTS.md](PROMPTS.md)** - 项目设计总依据（权威）
- **[infrastructure/README.md](infrastructure/README.md)** - 基础设施层文档入口
- **[handoff/README.md](handoff/README.md)** - Handoff 文档入口
- **[trace/README.md](trace/README.md)** - Trace 文档入口
- **[orchestra/README.md](orchestra/README.md)** - Orchestra 文档入口

### 实施文档
- **[execution_plan/phase_2_execution_plan.md](execution_plan/phase_2_execution_plan.md)** - Phase 2 执行计划
- **[execution_plan/implementation-spec-phase3-draft.md](execution_plan/implementation-spec-phase3-draft.md)** - Phase 3 实施草案

---

**维护者**: Vibe Team
**最后更新**: 2026-05-20
**设计总依据**: [PROMPTS.md](PROMPTS.md)