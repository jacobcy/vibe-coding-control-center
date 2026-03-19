---
title: Vibe 3.0 - 项目设计总依据
date: 2026-03-17
authors:
  - Claude Sonnet 4.6
related_docs:
  - docs/v3/infrastructure/02-architecture.md
  - docs/v3/handoff/v3-rewrite-plan.md
  - SOUL.md
status: active
purpose: 定义 Vibe 3.0 重构的核心理念、实施阶段和关键决策（权威）
---

# 目标

将 Vibe Center 重构为**确定性、可追踪的 AI 开发编排工具**：

- **统一的基础设施层**（config、logging、error、data）
- **可追踪的命令执行**（每个命令可追踪，每个操作可记录）
- **责任链 handoff 机制**（plan/execute/review 三阶段）
- **可选的 agent 自动编排**（Orchestra，借鉴 Symphony 理念）

---

# 实施阶段（强制顺序，不得跳跃）

## Phase 1: Infrastructure（基础设施层）✅ 当前阶段

**目标**：建立统一的基础架构，确保代码质量和可维护性

**交付物**：
```
src/vibe3/
├── cli.py                    # Typer 入口
├── commands/                 # 命令调度层
├── services/                 # 业务逻辑层
├── clients/                  # 外部依赖封装（Protocol 接口）
├── models/                   # Pydantic 数据模型
├── observability/            # 日志系统 + 追踪系统
│   ├── logger.py             # 日志配置
│   └── trace.py              # 追踪系统（Phase 2）
├── exceptions/               # 异常定义
├── ui/                       # 展示层（Rich）
└── config/                   # 配置模块
```

**实施文档**：[infrastructure/](infrastructure/README.md)

**验收标准**：
- [ ] 所有命令包含核心参数集（`--trace`, `-v`, `--json`, `-y`）
- [ ] 所有异常继承 VibeError
- [ ] 日志系统支持 verbose 参数（0=ERROR, 1=INFO, 2=DEBUG）
- [ ] 所有外部调用在 clients/ 中封装
- [ ] 测试覆盖率 >= 80%（Services 层）

---

## Phase 2: Trace（调试追踪层）⏸️ 下一步

**目标**：实现 `--trace` 参数，帮助 agent 在开发和 review 过程中获得明确上下文

**设计原则**：
- **调试友好** - 追踪输出人类可读，帮助理解"代码执行到哪一步了"
- **轻量级** - 不引入 OpenTelemetry，使用 `sys.settrace`，开销 < 20%
- **一次性输出** - 追踪结果直接输出到控制台，不持久化存储
- **接口预留** - 为 Phase 4 的记录追踪预留 `TraceCollector` 接口

**实施文档**：[trace/](trace/README.md)

**验收标准**：
- [ ] `vibe review pr 42 --trace` 输出调用链路
- [ ] 追踪开销 < 20%
- [ ] 不影响命令执行结果

**关键设计**：Phase 2 预留 `TraceCollector` 接口，Phase 4 只需实现 `DatabaseTraceCollector`，无需修改核心逻辑。

---

## Phase 3: Handoff（责任链层）⏸️ 待启动

**目标**：实现 plan/execute/review 三阶段责任链，确保每个操作可记录

**设计原则**：
- **三阶段流程** - Plan → Execute → Review
- **责任清晰** - 每个 agent 的操作可追溯（格式：`agent/model`）
- **产物引用** - 通过 `*_ref` 字段引用文档，不复制正文

**交付物**：
- `services/handoff_service.py` - Handoff 记录服务
- `clients/store_client.py` - SQLite 客户端
- 数据库迁移脚本

**实施文档**：[handoff/](handoff/README.md)

**验收标准**：
- [ ] 每个操作记录到 SQLite handoff store
- [ ] 每个 agent 署名（格式：`agent/model`）
- [ ] `vibe flow status` 显示责任链

---

## Phase 4: Orchestra（自动编排层）⏸️ 冻结

**状态**: ⏸️ **冻结** - 面向未来设计，当前不实施

**目标**：实现 agent 自动编排，借鉴 Symphony 的调度理念

**设计理念**：
- **不学习 Symphony 的 agent 模型**（v3 已有更完整的 handoff 体系）
- **借鉴 Symphony 的调度工程问题**：如何安全地并发管理多个 agent 执行、如何保证不重复 dispatch、如何从崩溃恢复

**实施文档**：[orchestra/](orchestra/README.md)

**实施条件**：Phase 1-3 完成并稳定运行，且有明确的 agent 自动编排需求。

**实施优先级**：
1. 记录追踪（`DatabaseTraceCollector`） - 优先级最高，复用 Phase 2 接口
2. DAG 引擎 - 优先级中，需要明确的业务场景
3. 自动编排 - 优先级低，复杂度高

---

# 强制规则（不可违反）

## 1. 架构分层

**依赖流向**：CLI → Commands → Services → Clients → Models

**禁止反向依赖**：高层不依赖低层具体实现。

**详细职责边界**：见 [infrastructure/02-architecture.md](infrastructure/02-architecture.md)

---

## 2. 数据真源

**GitHub 为唯一真源**，SQLite handoff store 只做责任链索引。

**详细标准**：见 [infrastructure/01-data-standard.md](infrastructure/01-data-standard.md)

---

## 3. 代码复杂度控制

**强制限制**：文件规模、函数规模、嵌套深度、循环复杂度。

**具体阈值**：见 [infrastructure/03-coding-standards.md](infrastructure/03-coding-standards.md)

---

## 4. 禁止事项

1. ❌ **CLI/commands 中包含业务逻辑**（参数验证除外）
2. ❌ **clients/ 之外有外部调用**
3. ❌ **使用 print()**（用 logger 或 rich）
4. ❌ **本地持久化 roadmap**（GitHub 为唯一真源）
5. ❌ **创建 "utils/" 目录**
6. ❌ **使用 argparse**（用 typer）
7. ❌ **使用 ORM**（SQLAlchemy, peewee）
8. ❌ **使用 Any 类型**

---

## 5. 幂等性和确定性

- **幂等性**（Phase 3）：重新运行流程不得创建重复 PR/提交，每个步骤必须检查现有状态
- **确定性**：相同输入 → 相同输出，无显式种子时不得有随机性

---

# 核心设计

## 1. 日志系统（Agent-Centric）

**核心理念**：结构化语义、可追踪性、精准定位、控制台美化。

**详细设计**：见 [infrastructure/05-logging.md](infrastructure/05-logging.md)

---

## 2. 异常体系

**核心理念**：统一异常基类，区分 UserError 和 SystemError。

**详细设计**：见 [infrastructure/06-error-handling.md](infrastructure/06-error-handling.md)

---

## 3. Client 隔离

**包装原则**：
- 所有外部系统调用（Git、GitHub、SQLite）封装在 clients/
- 提供 Protocol 接口，支持单元测试 Mock
- 包含所有 subprocess 调用

详见：[infrastructure/02-architecture.md](infrastructure/02-architecture.md)

---

## 4. 配置管理

**配置来源优先级**：命令行参数 > 环境变量（`VIBE_*`） > 配置文件（`~/.vibe/config.yaml`） > 默认值

详见：[infrastructure/01-data-standard.md](infrastructure/01-data-standard.md)

---

## 5. 追踪机制

**Phase 2（调试追踪）**：
- 实时输出调用链路，人类可读（树状结构）
- 不存储（一次性），轻量级（开销 < 20%）
- 使用 `sys.settrace`，只追踪关键路径
- **预留接口**：`TraceCollector` 为 Phase 4 的记录追踪做准备

**Phase 4（记录追踪）- 冻结**：
- 持久化追踪事件，支持执行重放和历史审计
- 复用 Phase 2 的 `TraceCollector` 接口，实现 `DatabaseTraceCollector`

详见：[trace/README.md](trace/README.md)

---

## 6. Handoff 机制（Phase 3）

**三阶段流程**：Plan → Execute → Review

**设计目标**：
- ✅ 每个 agent 的操作可追溯
- ✅ 每个阶段的产物可引用（`plan_ref`, `report_ref`）
- ✅ 责任链清晰（谁做了什么）

详见：[handoff/README.md](handoff/README.md)

---

# 验证标准

## Phase 1 验证
- [ ] 所有命令包含核心参数集
- [ ] 所有异常继承 VibeError
- [ ] 日志系统支持 verbose 参数
- [ ] 所有外部调用在 clients/ 中封装
- [ ] 测试覆盖率 >= 80%

## Phase 2 验证
- [ ] `vibe review pr 42 --trace` 输出调用链路
- [ ] 追踪开销 < 20%
- [ ] 不影响命令执行结果

## Phase 3 验证
- [ ] 每个操作记录到 SQLite handoff store
- [ ] 每个 agent 署名（格式：`agent/model`）
- [ ] `vibe flow status` 显示责任链

---

# 失败条件

**基础设施失败**：
- ❌ 引入 utils/ / 混合层次 / 在 clients/ 外留下直接 subprocess 调用
- ❌ 使用非结构化日志 / 使用 Any 类型 / 测试覆盖率 < 80%

**跳跃实施失败**：
- ❌ 未完成 Phase 1 就开始 Phase 2
- ❌ 未完成 Phase 2 就开始 Phase 3
- ❌ 未完成 Phase 3 就开始 Phase 4

---

# 执行不变性（强制）

1. **确定性**：相同输入 → 相同输出
2. **幂等性**（Phase 3）：重新运行流程不得产生重复副作用
3. **可追踪性**（Phase 2）：每个命令必须可追踪
4. **契约化设计**：所有模块必须定义显式接口
5. **无隐式状态**：GitHub 为唯一真源

---

# 关键决策记录

## 决策 1：为什么四阶段？

**理由**：
1. **Infrastructure** - 打地基，确保代码质量
2. **Trace** - 建立追踪能力，支持调试
3. **Handoff** - 建立责任链，支持追责
4. **Orchestra** - 可选，根据需求决定是否实施

**不跳跃的原因**：Phase 2 依赖 Phase 1 的日志系统，Phase 3 依赖 Phase 2 的追踪能力，Phase 4 依赖 Phase 1-3 的完整基础设施。

---

## 决策 2：为什么 Engine/Runtime 冻结？

**理由**：
1. **v3 已有更完整的 handoff 体系** - planner/executor/reviewer 责任链
2. **DAG 引擎复杂度高** - 需要明确的业务场景驱动
3. **优先级低** - 先保证基础设施稳定

**冻结策略**：✅ 预留接口定义 / ❌ 不实现具体逻辑 / ❌ 不编写详细的实施文档

---

## 决策 3：为什么 Trace 分两个阶段？

| 维度 | Phase 2（调试追踪） | Phase 4（记录追踪） |
|------|-----------------|------------------|
| **目标** | 调试友好 | 可重现性 |
| **输出** | 实时树状日志 | 结构化事件（JSON） |
| **存储** | 不存储（一次性） | 持久化到数据库 |
| **使用场景** | 开发调试 | 执行重放、审计 |
| **实现** | `sys.settrace` | OpenTelemetry |
| **复杂度** | 低 | 高 |
| **优先级** | Phase 2（现在） | Phase 4（可选） |

**关键设计**：Phase 2 预留 `TraceCollector` 接口，Phase 4 只需实现 `DatabaseTraceCollector`，无需修改核心逻辑。

---

## 决策 4：为什么不学习 Symphony 的 agent 模型？

**理由**：
- **v3 的 handoff 体系更完整** - 三阶段责任链已覆盖 agent 协作
- **Symphony 是单 agent 模型** - 不适合 v3 的多 agent 场景

**借鉴点**：✅ 调度工程问题（如何安全地并发管理多个 agent） / ✅ 状态机设计（如何从崩溃恢复） / ❌ agent 模型（v3 已有更好的方案）

---

# 参考文档

## 项目宪法
- **[SOUL.md](../../SOUL.md)** - 项目宪法和核心原则
- **[CLAUDE.md](../../CLAUDE.md)** - AI Agent 开发协议
- **[AGENTS.md](../../AGENTS.md)** - AI Agent 入口指南

## 实施文档
- **[infrastructure/README.md](infrastructure/README.md)** - 基础设施层文档入口
- **[handoff/README.md](handoff/README.md)** - Handoff 文档入口
- **[trace/README.md](trace/README.md)** - Trace 文档入口
- **[orchestra/README.md](orchestra/README.md)** - Orchestra 文档入口

## 外部参考
- **Symphony** - agent 自动编排理念（仅借鉴调度工程问题）

---

**维护者**：Vibe Team
**最后更新**：2026-03-17