---
document_type: reference
title: Vibe Workflow Engine Historical Design
status: archived-reference
author: GPT-5 Codex
created: 2026-03-13
last_updated: 2026-03-13
related_docs:
  - docs/standards/v3/vibe-engine-design.md
  - docs/standards/glossary.md
  - docs/standards/v3/command-standard.md
  - docs/standards/v3/skill-standard.md
  - docs/standards/v3/skill-trigger-standard.md
---

# Vibe Workflow Engine 历史设计参考

本文档保留早期 Vibe Workflow Engine 的完整架构蓝图，供历史背景、设计演化和旧文档考据使用。

它不是现行标准真源。当前正式语义以以下文档为准：

- `docs/standards/glossary.md`
- `docs/standards/v3/command-standard.md`
- `docs/standards/v3/skill-standard.md`
- `docs/standards/v3/skill-trigger-standard.md`

需要特别注意：

- 文中 `Stage 1/2/3/4`、`Execution Gate`、`Review Gate`、`Unified Workflow Orchestrator` 等表述属于历史架构蓝图
- 文中对 `flow` / `worktree` 的叙事不能直接当成现行标准
- 若历史叙事与当前标准冲突，以当前标准为准

---

# Vibe Workflow Engine 架构设计

> 历史说明（2026-03-13）：本文已迁入 `docs/references/`，只作为历史架构设计背景保留，不作为现行标准真源。

> 术语说明：本文保留其架构设计语境，但 `flow`、`workflow`、`Skill 层`、`Shell 能力层`、`执行代理`、`共享状态真源` 等正式术语以 [glossary.md](../standards/glossary.md) 为准。

## 1. 设计初衷与痛点

在 Vibe Center 2.0 中，我们确立了**Model-Spec-Context (MSC) 范式**，旨在用强约束和边界控制收敛 AI 生成的代码质量，防止"凭感觉写出垃圾代码"。然而，我们发现当前系统的**执行入口存在断层**：

- **痛点一：Shell 工具只是空壳**。早期 `bin/vibe flow start` 偏向“切执行现场”而缺少真正的规范驱动，它没有真正拉起 AI Agent 进入验证阶段。`governance.yaml` 中配置的 `flow_hooks` 被记录了，但无人执行。
- **痛点二：Slash 命令缺乏强制约束**。用户可以直接使用 `/vibe-commit` 或直接在对话中提出改代码要求，Agent 会欣然接受，这就绕过了所有的需求验证 (PRD)、代码质量检查 (lint/test) 等 MSC 规范机制。
- **痛点三：工具的认知负面影响**。无论是 openSpec 还是 Serena，这些本该作为隐形护栏的基础工具，反而成了需要用户主动理解并运行的负担。

## 2. 核心架构：统一工作流编排器 (Unified Workflow Orchestrator)

我们的解决思路是：**设计一个统一的工作流引擎，将所有入口（Shell 命令行、Slash 命令、Agent 自然对话）全部打通，并在处理流程中强行嵌入 MSC 拦截门。** 所有的需求变更无论从哪来，都只能通过这条单行道。

### 2.1 任务生命周期与系统闭环 (Task Lifecycle Loop)

在 Vibe Engine 中，一项开发任务的生命周期与底层的 Git branch / flow runtime 和 CLI 命令是严格绑定的：

1. **创建 (Todo)**
   - **触发**: `vibe task add <title>` 或 Agent 识别出新意图。
   - **状态**: 任务已登记在 `registry.json` 中，但尚未创建代码分支，也未指派 AI 角色。
2. **执行 (In Progress)**
   - **触发**: `vibe flow new <slug>`（在当前目录切到新 flow / branch）或 `vibe flow bind <task-id>`（绑定现有工作区）。
   - **状态**: 当前 branch 与 flow runtime 就绪，Agent 身份确认，一切就绪。
   - **循环**: Agent 开始写代码了，这是纯粹的 Execution 阶段，不受干扰。
3. **审计 (In Review / Code Review)**
   - **触发**: `vibe flow review --local` （调用底层大模型进行自动化逻辑与依赖检查）或者 `vibe flow pr` (推送至云端供人类复核)。
   - **状态**: 任务处于冻结待决状态，根据 Codex/Human 的反馈决定退回 *执行* 还是前进到 *完成*。
4. **收尾 (Completed / Closed)**
   - **触发**: `vibe flow done` (人类敲击或 AI 代办)。
   - **状态**: 交付收口。当前特征分支被删除，flow 历史被保留；物理目录是否清理取决于 worktree 生命周期，而不是 flow 本体。
5. **归档 (Archived)**
   - **触发**: `vibe check`。
   - **状态**: `registry.json` 中属于已完结状态的任务，连带的 Markdown 等元信息被永久搬运入 `archive/`。

这个流转关系使得工具不再是散落的拼图，而是：**新建任务 -> 切入 flow/branch 现场 -> 编写代码 -> Codex Review -> 提交 PR -> 结束当前 flow -> 归档记录** 的完美闭环。

### 2.2 三层分离的架构模型

```mermaid
graph TD
    classDef ui fill:#3b82f6,stroke:#1d4ed8,stroke-width:2px,color:#fff;
    classDef engine fill:#10b981,stroke:#047857,stroke-width:2px,color:#fff;
    classDef tool fill:#6366f1,stroke:#4338ca,stroke-width:2px,color:#fff;

    subgraph "Tier 2: Vibe Skills Layer (Skill 层 - 智能包装)"
        A1[bin/vibe flow]:::ui
        A2[/vibe-task / /vibe-flow / /vibe-save]:::ui
        A3[自然语言需求对话]:::ui
    end

    subgraph "Tier 3: Supervisor Layer (引擎编排层 - The Developer Vibe Gate)"
        B1{"Stage 1: Scope Gate<br/>(读 SOUL.md)"}:::engine
        B2{"Stage 2: Plan Gate<br/>(查 PRD/Spec)"}:::engine
        B3{"Stage 3: Execution Gate<br/>(vibe-test-runner)"}:::engine
        B4{"Stage 4: Review Gate<br/>(规则审计 & Metrics)"}:::engine
    end

    subgraph "Tier 1: Shell Layer (Shell 能力层 - 无感知运行)"
        C1[vibe 命令及 alias]:::tool
        C2[bats-core]:::tool
        C3[codex & Shellcheck]:::tool
        C4[OpenSpec & Registry JSON]:::tool
    end

    A1 --> B1
    A2 --> B1
    A3 --> B1

    B1 -- 允许/快速通道 --> B2
    B1 -- 越界 --> 拒绝执行_要求解释SOUL

    B2 -- 已有Plan/小修 --> B3
    B2 -- 无Plan --> 强制生成PRD引导

    B3 -- 测试通过 --> B4
    B3 -- 失败/熔断 --> 报修循环

    B4 -- 全绿 --> 完成_允许Commit
    B4 -- 违规 --> 打回修改

    B3 -.-> C1
    B3 -.-> C2
    B3 -.-> C3
    B2 -.-> C4
```

### 2.3 核心文件分工（绝对清晰的指令集）

为了支撑引擎判断，我们赋予根目录三个文件截然不同的政治地位：

1. **`SOUL.md` (宪法层 / What & Why We Build)**: 界定项目的绝对边界，项目是什么，不是什么。在这个范围内，引擎允许干活。一旦越界，引擎触发"拒绝响应"，只有澄清或修改了宪法，才能复工。
2. **`CLAUDE.md` (法律层 / How We Build)**: 技术约束、物理极限（如 LOC 最大值）、特定语言规范。引擎在这里抓取物理检查项（比如文件大于 300 行就报错）。
3. **`AGENTS.md` (Agent 入口层 / Who Executes)**: AI Agent 的统一入口，定义 Agent 行为准则、工作风格和导航路径。

## 3. 工作流执行机制

在这个统一引擎下，"形式不重要，阶段状态才重要"。任何动作都会被评估它处于哪个 Stage，并触发相应的 Guardrail。

### 3.1 意图与快、慢通道分流
面对用户的命令，引擎第一步是分类：
- **快速通道 (Fast Track)**：例如仅仅是修改一个 README，调整一个变量名，补充一个注释等**不涉及逻辑增减的行为**。这类操作可以在意图核查后直接进入 Execution / Review Gate。
- **慢速通道 (Full Workflow)**：只要是新功能、重构或者逻辑调整。强制过所有的拦截门。

### 3.2 护栏机制详解 (The Gates)

| 阶段名 | 拦截条件 | 控制手段 | 未达标时的表现 |
|--------|----------|----------|----------------|
| **Stage 1: Scope Gate** | 检查需求是否违反 `SOUL.md` 的业务界限 | 文本向量比对 / 大模型常识审核 | ❌ Agent 输出："抱歉，这违反了我们的 SOUL：我们只是 CLI 工具，不能做网页。要继续吗？请讨论修改 SOUL.md。" |
| **Stage 2: Plan Gate** | 对于增加新功能，是否存在 `.agent/plans/` 计划或 PRD？ | 工作流节点审核文件树 | ❌ Agent 输出："我们还没有完成设计，这很容易生产垃圾代码。让我们先确定几个参数，我来起草一个 Spec。" |
| **Stage 3: Execution Gate** | 代码是否能跑通且影响面受控？ | 调用 `vibe-test-runner` | ❌ 直接循环尝试 3 次自动修 Bug，修不好再吐给用户报错面板。 |
| **Stage 4: Review Gate** | 逻辑退化指标与漏洞扫描 | 调用 `vibe flow review --local` (Codex) | ❌ Agent 输出："发现潜在死代码或违规项，请清理垃圾代码后我再打包当前修改。" |

### 3.3 无痛护航 (Pain-Free Tooling)

在这套机制下：
- 用户从来不需要主动命令 Agent 运行 `find_referencing_symbols`（这是 Execution Gate 的潜规则）。
- 用户不需要关心如何把一个逻辑变成 OpenSpec，他们只需要正常问答，Agent 代为沉淀文件。
- Shell 命令和 Agent 对话合流：你在 Shell 敲击 `vibe flow review` 实际上就是调用 `vibe-rules-enforcer` 并把输出和 metrics 丢回 Shell。

## 4. 实施策略

为实现这个蓝图，我们将使用一个"大脑" Skill，串联现有的所有原子级模块：

- 创建新的核心 Skill: `vibe-workflow-orchestrator`，此技能在任何上下文启动时都会被隐式或者显式触发。
- 当 `bin/vibe flow` 相关命令在终端运行时，如果环境有 Agent 环境变量，触发 Agent 代跑流程；没有的话回退为普通输出。

## 5. 终极远景：多智能体管线 (The Agent of Agents Loop)

通过在底座中封装这些不可变的生命周期（如 `vibe flow review`），Vibe Center 最终将演化为能够托管异构 AI 智能体的超管基础设施（Super-Orchestrator），例如借助 `OpenClaw` 或类似底座实现完全自治的开发管线：

1. **架构师 (Gemini)**：擅长无限上下文。负责通读整个代码库与高阶业务需求，在 `docs/plans/` 中输出精确到步骤的系统设计与抽象逻辑 (`plan.md`)。
2. **执行者 (Claude)**：擅长零样本编码。作为无头(Headless)引擎被唤醒（`claude -c -p <plan> --dangerously-skip-permissions`），在当前被分配的 flow / branch 现场中老老实实地落实每一行代码，不去擅自重构项目。
3. **审计员 (Codex)**：擅长挑刺和严谨的静态分析。作为守门员拦截在提交前（`vibe flow review --local`），专门负责代码 review、找 bug 和死代码。如果退回，再发给 Claude 重新修。
4. **总指挥 (OpenClaw / Vibe Flow Auto)**：维持整个 flow 现场流转的编排循环，负责调用上述执行代理，并在需要并行隔离时额外调度 worktree 基础设施。
5. **人类 (Human Approver)**：从打字员解放为终审法官，只需在 Slack/Channel 中查看汇总的 PR 与 Review 报告，点一下 "LGTM" 闭环合码。
