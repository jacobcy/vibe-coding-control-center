---
title: Vibe Workflow Engine 实施计划
date: 2026-02-26
status: planning
---

# Vibe Workflow Engine 实施计划

## 1. 目标与背景

由于当前系统存在"认知脱节"：Shell 命令行虽然创建了工作区环境，但未能有效拉起智能 Agent；而直接在对话里操作又容易让 Agent 脱缰从而写出垃圾代码。

本计划旨在打通 **Shell 命令** 与 **Slash 对话命令**，引入一个全局统一配置和编排的 **Vibe Workflow Engine**。通过统一编排器（Orchestrator），在所有修改代码的行径上建立强制的 "四闸机制" (4-Gates Mechanism)：
1. **Scope Gate**: 审判边界 (SOUL.md)
2. **Plan Gate**: 审判规划 (PRD/Spec)
3. **Execution Gate**: 安全构建与测试 (Serena + Lint + test)
4. **Review Gate**: MSC 度量全绿审查 (Metrics)

## 2. 核心架构调整范围

- **编排器技能**: 创建 `skills/vibe-workflow-orchestrator/SKILL.md`，它将成为统管整个交互闭环的"母技能"。
- **入口改造**:
  - 创建 `.agent/workflows/vibe-new.md` (或整合到 existing ones) 以对外暴露对等于 `vibe flow start` 的智能对话入口。
  - 修改 `bin/vibe` 与 `lib/flow.sh`：如果是通过终端执行，则主动提示"已为您准备好环境，请向 Agent 发送 `/vibe-new` 开启引导"。如果在 Cursor/Trae 里也可以做到通过 IPC 唤起。
- **治理强化**: 调整 `vibe-test-runner` 等子技能的描述，确保它们只能被 Orchestrator 或其它 Gate 调用，而不是让用户去学怎么调工具。

## 3. 具体实施阶段 (Phases)

### Phase 1: 建立核心编排器 (The Orchestrator)

1. **新建技能文件 `skills/vibe-orchestrator/SKILL.md`**:
   - 系统角色定义为"严格的开发向导与路由门卫"。
   - 实现四阶段网关的流转逻辑 (Scope -> Plan -> Execution -> Review)。
   - 实现"快速通道"与"慢速通道"的意图分类逻辑拦截器。
   - 规定拒绝非合规意图的精确回复模板（如"这超出了 SOUL.md 的界限..."）。

2. **定义交互式 Slash 命令入口**:
   - `workflows/vibe-new.md`：用于新功能开始，进入流程慢车道。
   - 改写现有的 `workflows/vibe-commit.md` 确保其受 orchestrator 调用或并入流程尾声。

### Phase 2: Shell 入口与对话入口的合流

1. **改造 `lib/flow.sh`**:
   - 当用户在终端执行 `vibe flow start <feature>` 后。不只是干巴巴创建目录，而是以显眼的方式在控制台上输出一张引导提示 (Onboarding Banner)。
   - 提示语："✅ 工作区已就绪。为了保证不产生垃圾代码，请呼叫您的 AI 助手并输入 `/vibe-new <feature>` 进入自动化功能引导流程。"
  
2. **规范化提示词链**:
   - Orchestrator 需要能读懂 `docs/standards/serena-usage.md` 和 `.github/workflows/ci.yml` 里面约定的东西。
   - 配置它在到达 Execution Phase 的时候，透明、静默地去运行 `scripts/lint.sh`, `scripts/metrics.sh` 并获取输出结果进行 3 次重试。

### Phase 3: "拒绝的艺术"与容错

1. **测试边界防御**:
   - 准备反向测试案例：尝试让 Agent 写一个网页爬虫（越界），观察 Scope Gate 拦截率。
   - 准备跳步测试案例：没写 PRD 直接让它改逻辑（跳步），观察 Plan Gate 拦截率。
2. **提炼与精简 (Refinement)**:
   - 从用户视角观察日志与输出，减去生硬的"机器味"，让引导变成"我们先确定下目标，以免我写出错代码"的高情商话术。

## 4. 依赖模块校验

执行本计划前，需确保以下模块完全健康：
- [x] `bin/vibe flow` 相关的基础 Shell 行为完备
- [x] Serena AST 基本集成跑通
- [x] `scripts/lint.sh` & `scripts/metrics.sh` 双层诊断与度量可用
- [x] Bats 核心代码测试环境支持

## 5. 预期影响

实施本计划后，无论资深开发者还是小白，都将被收拢在**最正确的做事路线上**，极大减少废弃代码和技术债。它将证明我们不仅"造了强大的工具"，更"设计了无法被绕过的高效治理体制"。
