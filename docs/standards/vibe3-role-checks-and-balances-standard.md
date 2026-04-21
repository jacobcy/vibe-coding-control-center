# Vibe3 Role Checks and Balances Standard

状态: Active

## 1. 目的

本文档定义 Vibe3 多角色 Agent 架构的制衡关系，回答以下问题:

- Governance / Supervisor / Apply 与 Manager / Plan / Run / Review 之间是何种协作关系
- 各角色的权力边界、覆盖能力与被覆盖机制
- 该架构是否构成对抗性编程，以及真正的风险点在哪

本文档是理解 Vibe3 角色体系的入口。各角色的具体 Permission Contract 以各自的角色材料为准:

- `supervisor/governance/assignee-pool.md` — Governance 角色材料
- `supervisor/apply.md` — Apply 角色材料
- `supervisor/manager.md` — Manager 角色材料
- `.agent/policies/plan.md` — Plan 模式策略
- `.agent/policies/run.md` — Run 模式策略
- `.agent/policies/review.md` — Review 模式策略

角色层级与 worktree 所有权定义见 `vibe3-worktree-ownership-standard.md`。
事件驱动语义见 `vibe3-event-driven-standard.md`。

## 2. 核心判断

### 2.1 这不是对抗性编程

对抗性编程通常指:

- 两个团队维护独立代码库，API 不兼容
- 一方故意写测试破坏另一方实现
- 缺乏共同目标，互相推诿责任

Vibe3 的架构是**协作式制衡**:

- 共同目标分层: Governance (L1) 负责 assignee issue pool 的观察与排序；Manager/Plan/Run/Review (L3) 负责把 assignee issue 从 ready 推进到 done；Supervisor/Apply (L2) 负责 supervisor issue 的治理执行。三者不是同一条执行链
- 边界清晰: 每个角色有明确的 Allowed / Forbidden list
- 有分层真源: assignee issue 的状态由 flow 状态管理，supervisor issue 由 supervisor/apply 管理，`state/*` 标签仅为可选镜像
- 有仲裁机制: 人类评论 > Orchestra 系统 > 各角色

### 2.2 这是"三权分立"的制衡架构

| 分支 | 对应角色 | 权力 | 制衡机制 |
|------|----------|------|----------|
| 立法 / 观察 | Governance (L1) | 观察 assignee pool、建议、写 `[governance suggest]` | 无强制执行权，只能通过建议影响 Manager |
| 治理执行 | Supervisor/Apply (L2) | 处理 supervisor issue、close/recreate 治理 issue | Manager 不干预 supervisor issue；人类可 override |
| 行政 / 执行 | Manager + Plan / Run (L3) | 状态机推进、代码实现、PR 产出 | Review 可 BLOCK; Orchestra 系统可强制回退 |
| 司法 / 审计 | Review (L3) | PASS / MAJOR / BLOCK 裁决 | Manager 可覆盖 UNKNOWN / 判定 review 不可信 |

## 3. 权力结构

### 3.1 层级与否决链

```
人类评论（绝对否决权）
        |
Orchestra 系统层（L0）
Progress Contract + Fallback Matrix
强制回退真源 owner
        |
Manager（L3）状态机控制者
可 block / claimed / review
可覆盖 review UNKNOWN verdict
可判定 review 不可信
        |
   +--------+--------+--------+
   |        |        |        |
  Plan     Run    Review   Governance
  (L3)    (L3)    (L3)      (L1)
  产出    产出   PASS/     [governance suggest]
plan_ref report  MAJOR/     纯建议，无强制权
                 BLOCK
                           |
                     Manager "应优先采纳"
                     人类 > governance > manager 自主
```

### 3.2 各角色权力对照

```yaml
governance:
  worktree: NONE (L1)
  can_override: []  # 无直接覆盖能力
  can_be_overridden_by:
    - manager: 可自主判断是否采纳
    - human: 冲突时优先
  teeth: advisory_only

apply:
  worktree: TEMPORARY (L2)
  can_override:
    - issue: 可 close / recreate 治理 issue
    - label: 可读写（限 supervisor label issue）
  can_be_overridden_by:
    - human: comment 指导
  teeth: limited_execution

manager:
  worktree: DEDICATED (L3)
  can_override:
    - plan: 可改 plan_ref，可要求重做
    - run: 可打回 in-progress
    - review: 可覆盖 UNKNOWN，可判定不可信
    - governance: 可自主采纳或忽略建议
  can_be_overridden_by:
    - human: 绝对优先
    - orchestra_system: Fallback Matrix 强制回退
    - loop_guard: 3+ 轮未 merge-ready 必须终局判断
  teeth: high

review:
  worktree: DEDICATED (L3)
  can_override:
    - run: MAJOR/BLOCK 可阻塞 merge
  can_be_overridden_by:
    - manager: 可判定不可信，可覆盖 UNKNOWN
    - human: 绝对优先
  teeth: conditional_blocking
```

## 4. 三个真正的张力点

### 4.1 Governance "没牙齿"

**现状**: Governance 只能写 `[governance suggest]`，Manager "应优先采纳"但最终由 Manager 决定。

**风险**: 如果 Manager 长期忽略 governance 建议，系统没有自动升级机制。

**缓解**: Governance 目前定位正确（L1 轻量扫描不应有强制执行权）。如需增强，建议增加 escalation 机制: 连续 N 个 tick 建议未处理时，自动加 `governance/escalated` label 提醒人类，而非直接修改 state。

### 4.2 Manager 可覆盖 Review

**现状**: Review 给出 BLOCK，Manager 可以说"review 不可信"并覆盖。

**风险**: Manager 可能因急于推进而滥用覆盖权。

**缓解**:

- Manager 覆盖 Review 时，必须在 handoff 中**明确记录覆盖理由和具体证据**
- Orchestra 系统应将"Manager 覆盖 BLOCK verdict"作为 observability event 记录，供人类审计
- 覆盖条件已在 `supervisor/manager.md` 中限定: "review 内容空洞、与 diff 矛盾"

### 4.3 Apply 与 Manager 的边界串扰风险

**现状**:

- Apply 处理 `supervisor` label issue，可 close / recreate
- Manager 处理 assignee issue，推进主执行闭环
- 两者都可能操作 issue labels / comments，但对象池应分离

**风险**: 如果治理 issue 与 assignee issue 分类错误，或同一个 issue 同时被当成 `supervisor issue` 和 assignee issue，两条链会出现串扰。

**缓解**:

- 明确 issue pool 分离规则：`supervisor issue` 不进入 Manager 主链，assignee issue 不交给 Apply
- `supervisor` label issue 不应同时作为 Manager 正在推进的 assignee issue
- 如果发现分类错误，应由 governance/roadmap 或人工纠正 issue 类型，而不是让两条链同时处理

## 5. 风险矩阵

| 风险 | 表现 | 当前缓解 | 建议增强 |
|------|------|----------|----------|
| Governance 被系统性忽略 | 长期无响应 issue 堆积 | 人类可手动介入 | 增加 escalation counter |
| Manager 滥用 Review 覆盖 | 低质量代码频繁通过 | 覆盖条件限定 | 强制 handoff 记录 + observability event |
| Apply 误关开发 issue | Apply close 影响 Manager 现场 | 标签区分（supervisor vs dev） | 明确标签互斥规则 |
| 角色材料自相矛盾 | 各 supervisor/*.md 定义不一致 | 人工 review | 定期角色材料一致性审计 |

## 6. 与其他标准的关系

```
vibe3-role-checks-and-balances-standard.md (本文件)
        |
        +-- vibe3-worktree-ownership-standard.md  (层级定义)
        +-- vibe3-event-driven-standard.md        (事件链语义)
        +-- vibe3-state-sync-standard.md          (state/* 标签语义)
        +-- agent-workflow-standard.md            (Agent 工作流规范)
        |
        +-- supervisor/governance/assignee-pool.md (Governance 角色)
        +-- supervisor/apply.md                     (Apply 角色)
        +-- supervisor/manager.md                   (Manager 角色)
        +-- .agent/policies/plan.md                 (Plan 策略)
        +-- .agent/policies/run.md                  (Run 策略)
        +-- .agent/policies/review.md               (Review 策略)
```

## 7. 修订历史

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-04-21 | v1 | 初始版本，定义角色制衡关系与风险矩阵 |
