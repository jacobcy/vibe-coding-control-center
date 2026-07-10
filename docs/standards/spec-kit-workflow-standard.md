# Spec-Kit 工作流规范（双轨模型）

> **文档定位**：定义 spec-kit 与 vibe3 flow 的双轨关系、桥接机制与选用决策
> **适用范围**：所有 spec-driven 或 issue-driven 的开发工作
> **权威性**：本标准为 spec-kit 工作流的权威依据。spec-kit 内部约定（feature 编号、目录、扩展）以 [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md) 为准；vibe3 plan/run/review 流程以 [agent-workflow-standard.md](agent-workflow-standard.md) 为准。

---

## 概述

本项目有**两条并行工作流轨**，经 `after_*` hooks 桥接，**不互相驱动**：

- **spec-kit 轨**（spec-driven，人机协作）：`brainstorm → specify → plan → tasks → implement → review`，经 `/speckit-*` skills 或 `specify workflow run speckit` 推进
- **vibe3 flow 轨**（issue-driven，自动化）：`plan → run → review` agents，针对 issue body 已明确的任务

这条划分对齐用户架构指令（2026-07-07，见 [#3332 rescope](https://github.com/jacobcy/vibe-coding-control-center/issues/3332)）：**自动化适用于 spec 已明确的任务**，spec/explore 阶段保持人机协作，不让 orchestra 全自动驱动六阶段。

---

## 一、spec-kit 轨（spec-driven，人机协作）

| 属性 | 说明 |
|---|---|
| 触发 | 人机协作入口 `/vibe-new` + `/speckit-*` skills |
| 推进器 | `specify workflow run speckit`（`.specify/workflows/speckit/workflow.yml`）|
| 阶段 | `specify → review-spec(gate) → plan → review-plan(gate) → tasks → implement`；brainstorm 与最终 review 经 `/speckit-superspec-brainstorm` / `/speckit-superspec-review` 手动触发 |
| 产物 | `.specify/specs/NNN-<slug>/{spec,plan,tasks}.md` |
| review gate | workflow 内 `gate` 步骤（review-spec / review-plan），人工 approve/reject |

`specify workflow run speckit` 是 spec-kit 自带的**阶段推进器**（非单纯事件回调）：它顺序执行 six-phase 的核心命令，gate 步骤插入人工 review 关卡。`specify workflow list` 可查已安装 workflow。

---

## 二、vibe3 flow 轨（issue-driven，自动化）

| 属性 | 说明 |
|---|---|
| 触发 | `vibe3 plan / run / review`（label 驱动自动化，或 `/vibe-new` + `/vibe-continue` 人机协作）|
| 推进器 | `vibe3` flow/task state machine |
| 适用 | **spec 已明确的任务**，任务语义经 issue body 注入 plan prompt |
| 产物 | handoff refs（`spec_ref` / `plan_ref` / `report_ref` / `audit_ref`）|

详见 [agent-workflow-standard.md](agent-workflow-standard.md)。

---

## 三、桥接（after_* hooks）

两轨的**唯一耦合**是 `vibe-spec-bridge` extension 的 lifecycle hooks：

| spec-kit hook | 发布到 vibe3 handoff |
|---|---|
| `after_specify` | `spec_ref`（`vibe3 handoff spec`）|
| `after_plan` | `plan_ref`（`vibe3 handoff plan`）|
| `after_implement` | `report_ref`（`vibe3 handoff report`）|
| `after_review` | `audit_ref`（`vibe3 handoff audit`）|

边界：

- spec-kit 轨**不驱动** vibe3 flow state（不改 label / flow_status）
- vibe3 flow **不驱动** spec-kit 阶段（不自动触发下一个 `/speckit-*`）
- reviewer 经 `vibe3 handoff show @spec / @plan` 读取 spec-kit 产物，做 spec 完成度（review policy §0f）+ ADR 合规（§0e）对账

即：spec-kit 负责**生成** spec/plan/report/audit artifacts，vibe3 负责**消费**这些 refs 做自动化执行与审查。生成与消费解耦，hooks 是单向发布通道。

---

## 四、选用决策

| 场景 | 用哪条轨 | 入口 |
|---|---|---|
| 新 feature，需 spec 设计 | spec-kit 轨 | `/speckit-*` 或 `specify workflow run speckit` |
| issue 已明确，直接实现 | vibe3 flow 轨 | `/vibe-new <issue>` + `vibe3 plan/run/review` |
| spec-kit 产物需审查对账 | vibe3 review | `vibe3 review`（读 `@spec` / `@plan` refs）|
| 纯文档/拼写/小修 | vibe3 flow 轨（快速） | feature branch + PR |

非平凡变更 SHOULD 先走 spec-kit 轨产出 spec，再视情况切 vibe3 flow 轨执行。琐碎变更直接 vibe3 flow 轨。

---

## 五、superspec 可用性

**superspec 是 local-dev 依赖，非 CI 依赖**：

- superspec 是外部 clone 的 extension（`.gitignore` 忽略 `.specify/extensions/*`，仅保留 project-owned 的 vibe-spec-bridge / vibe-explore）
- worktree bootstrap 经 `scripts/init.sh` 自动安装（`specify extension add`，#3301）；失败非阻塞
- **CI 不跑 spec-kit**（`.github/workflows/ci.yml` 只跑 LOC / lint / ruff / black / mypy / pytest），故 superspec 在 CI 缺失不影响任何 CI 步骤
- 测试（`tests/vibe3/extensions/test_spec_kit_bridge.py`）已为 superspec 缺失设计：断言外部源不被触碰（FR-014）、direct exit path 可达（FR-017）、hook additive 不冲突

结论：**无需 vendored fallback**。fresh clone 经 `init.sh` 获得 superspec；CI 环境不需要它。

---

## 六、自动化指令对齐

本双轨模型落实以下架构指令（ADR-0007 / #3332 rescope）：

1. **自动化适用于 spec 已明确的任务**：vibe3 plan/run/review 通过 issue body 注入任务语义，不自己推导 spec
2. **spec/explore 保持人机协作**：`/vibe-new` + `/speckit-*` 经人类决策推进，不全自动
3. **agent 自用工具收集上下文**：plan prompt 不预注入 spec_ref / memory（ADR-0007）；agent 按本 standard + supervisor/policies/plan.md 自行调 spec-kit / graphify / mem-search / context7
4. **全权委托自动化已实践，效果不好**：故**撤回** "orchestra 全自动驱动 spec-kit 六阶段" 目标（#3332 原始目标），orchestra 不驱动 `specify workflow run`

---

## 参考

- [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md) — spec-kit 内部约定真源（feature 编号、目录、扩展、Explore Before Spec）
- [agent-workflow-standard.md](agent-workflow-standard.md) — vibe3 plan/run/review 权威流程
- [ADR-0006](../decisions/0006-spec-artifact-handoff-contract.md) — Spec Artifact 与 Handoff 统一契约
- [ADR-0007](../decisions/0007-plan-no-context-injection.md) — Plan Prompt 不预注入上下文
- [.specify/workflows/speckit/workflow.yml](../../.specify/workflows/speckit/workflow.yml) — Full SDD Cycle workflow 定义
- [#3327](https://github.com/jacobcy/vibe-coding-control-center/issues/3327) / [#3329](https://github.com/jacobcy/vibe-coding-control-center/issues/3329) / [#3331](https://github.com/jacobcy/vibe-coding-control-center/issues/3331) / [#3333](https://github.com/jacobcy/vibe-coding-control-center/issues/3333) — 桥接闭环 follow-up
