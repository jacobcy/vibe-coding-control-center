# AutoHarness Learning Loop Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把 AutoHarness 落地为一个可追踪、可分析、可沉淀、可提升的学习机制，而不是一组写死的拦截规则；让每次 flow 执行都能反哺下一次 flow。

**Architecture:** 采用“极薄 runtime harness + flow telemetry + handoff findings + replay evaluation + harness promotion”方案。runtime harness 只负责记录和最小约束，不承担最终治理智能；真正的价值来自执行后的 trace 分析、finding 沉淀和下一轮 harness 迭代。

**Tech Stack:** Python 3.10+, Typer, SQLite handoff store, flow events, handoff service, YAML, existing `run/review/flow/handoff` chain

---

## Core Correction

第一版设计把 AutoHarness 写成了静态 policy gate，这不符合本需求重点。

本需求真正要落的是：

1. 记录 agent 在 flow 中做了什么
2. 判断哪些动作是坏动作、误拦截、低效动作、越界动作
3. 识别这些动作是否暴露了仓库层问题，例如错误语义、设计缺口、契约漂移和疑似 bug
4. 把这些问题沉淀成 finding 和 evidence
5. 在 flow done 或周期性审计时回顾
6. 用这些样本修正 harness
7. 通过 replay 验证新 harness 是否更好

因此，AutoHarness 的重点不是“拦住”，而是“学会更好地约束”。

---

## Why It Fits This Repo

当前仓库已经具备学习闭环需要的三个关键基础：

1. **flow timeline**
   - `flow_events` 已支持 `refs`
   - `flow show` 已能展示时间线

2. **handoff chain**
   - `plan_ref / report_ref / audit_ref`
   - `current.md` 允许记录 findings、blockers、evidence refs

3. **agent execution chain**
   - `run/review` 已统一经过 `review_runner.py`
   - 适合在 repo-owned 边界记录 runtime trace

所以最自然的落地不是另起炉灶，而是把：

`agent operation -> flow event -> handoff finding -> audit review -> harness refinement`

打通成同一条学习链。

---

## Design Principle

### 1. Runtime Harness Must Stay Thin

runtime harness 只做四件事：

- 观察 action
- 做最小 allow / rewrite / block
- 记录 decision 和 evidence
- 把 trace 送入 flow/handoff 链

它不是规则中心，也不是最终智能来源。

### 2. Findings Matter More Than Immediate Blocking

如果只做阻断，不做记录，后续无法优化。

因此每次命中 harness 时，必须尽量产出：

- `action`
- `decision`
- `reason`
- `context`
- `impact`
- `was_this_helpful`
- `did_this_reveal_repo_problem`

### 3. Flow Done Is a Review Point, Not Just an End State

`flow done` 不应只是结束动作。

它应该成为一个回顾点，用来回答：

- 本 flow 中 agent 经常卡在哪些动作
- 哪些 rule 误伤了正常任务
- 哪些违规动作没有被识别
- 哪些 trace 其实指向了仓库本身的语义问题或真实 bug
- 下次应该怎样调整 harness

### 4. Harness Improves by Replay, Not by Intuition

新 harness 不能凭主观判断替换旧 harness。

必须用历史样本回放，比较：

- 非法动作漏检率
- 合法动作误拦截率
- rewrite 后任务成功率
- flow 完成率

---

## Target Files

### Create

- `src/vibe3/governance/harness_models.py`
- `src/vibe3/governance/harness_trace_store.py`
- `src/vibe3/services/agent_runtime_harness.py`
- `src/vibe3/services/harness_replay.py`
- `src/vibe3/services/harness_findings.py`
- `tests/vibe3/governance/test_harness_trace_store.py`
- `tests/vibe3/services/test_agent_runtime_harness.py`
- `tests/vibe3/services/test_harness_replay.py`

### Modify

- `src/vibe3/services/review_runner.py`
- `src/vibe3/services/handoff_service.py`
- `src/vibe3/services/handoff_recorder.py`
- `src/vibe3/commands/run.py`
- `src/vibe3/commands/review.py`
- `src/vibe3/commands/flow.py` if `flow done` gains review hooks
- `.agent/governance/policies/autoharness.yaml`

### Existing Source of Truth to Reuse

- `src/vibe3/clients/sqlite_client.py`
- `src/vibe3/clients/sqlite_schema.py`
- `src/vibe3/models/flow.py`
- `src/vibe3/services/handoff_service.py`
- `docs/standards/v3/handoff-store-standard.md`

---

## V1 Runtime Shape

### Not This

```text
action -> giant blocker -> stop
```

### This

```text
action
  -> thin harness
  -> decision: allow | rewrite | block
  -> trace event
  -> handoff finding if notable
  -> replay corpus
  -> later synthesis and promotion
```

---

## Phase 1: Define the Trace Contract

### Task 1: Introduce a stable harness trace record

**Files:**
- Create: `src/vibe3/governance/harness_models.py`
- Create: `tests/vibe3/governance/test_harness_trace_store.py`
- Modify: `.agent/governance/policies/autoharness.yaml`

**Intent:**
先固定“记录什么”，再讨论“如何学习”。没有稳定 trace contract，后续 replay 和 synthesis 都会漂。

**Required trace fields in v1:**
- `flow_branch`
- `session_actor`
- `phase`
- `action_family`
- `action_payload`
- `decision`
- `reason`
- `evidence`
- `trace_ref`
- `created_at`

**Recommended optional fields:**
- `was_retried`
- `rewrite_payload`
- `task_outcome_hint`
- `is_false_positive`
- `is_false_negative`

**Exit condition:**
trace contract 可以稳定表达一次 agent action 与 harness decision。

---

## Phase 2: Persist Traces Into Flow Context

### Task 2: Connect runtime traces to flow events

**Files:**
- Create: `src/vibe3/governance/harness_trace_store.py`
- Modify: `src/vibe3/services/review_runner.py`
- Modify: `src/vibe3/clients/sqlite_client.py`
- Test: `tests/vibe3/services/test_agent_runtime_harness.py`

**Intent:**
让 runtime harness 不再是黑盒，而是正式进入 flow timeline。

**Recommended write path:**
- 结构化 trace 文件写入 `.git/vibe3/handoff/<branch>/`
- `flow_events` 增加 `handoff_trace` 或 `harness_trace` 事件
- `refs` 中保存：
  - `trace_ref`
  - `phase`
  - `decision`
  - `action_family`

**Reasoning:**
当前 `flow_events.refs` 已支持 JSON，适合承载 trace 引用而不是复制正文。

**Exit condition:**
每次 notable harness decision 都能在 flow timeline 中看到证据入口。

---

## Phase 3: Turn Important Traces Into Handoff Findings

### Task 3: Promote selected traces into handoff findings

**Files:**
- Create: `src/vibe3/services/harness_findings.py`
- Modify: `src/vibe3/services/handoff_service.py`
- Modify: `src/vibe3/services/handoff_recorder.py`
- Test: `tests/vibe3/services/test_agent_runtime_harness.py`

**Intent:**
不是每条 trace 都值得进入 handoff；需要把“有学习价值的 trace”转成 findings。

**Promotion candidates:**
- block 导致任务停滞
- rewrite 后仍失败
- 重复出现的同类违规动作
- 人类确认属于误拦截
- 本应阻断但最终未阻断的坏动作
- trace 暴露了错误语义、设计缺口、契约漂移或真实 bug

**Finding categories in v1:**
- `behavior_violation`
- `false_positive`
- `false_negative`
- `semantic_conflict`
- `contract_drift`
- `suspected_bug`
- `improvement_opportunity`

**Recommended handoff append kinds:**
- `finding`
- `blocker`
- `next`
- `note`

**Recommended finding shape in `current.md`:**
- what happened
- why harness decided so
- why this was useful or harmful
- whether it indicates a repo-level defect
- next harness improvement suggestion
- evidence ref

**Exit condition:**
高价值 trace 能沉淀为 handoff findings，而不是淹没在原始日志中。

---

## Phase 4: Build a Replay Corpus

### Task 4: Create replayable harness examples

**Files:**
- Create: `src/vibe3/services/harness_replay.py`
- Create: `tests/vibe3/services/test_harness_replay.py`
- Possibly create: `.agent/reports/` fixtures or `tests/fixtures/harness/`

**Intent:**
让 harness 的优化基于历史样本，而不是凭感觉改规则。

**Replay input should include:**
- original action
- runtime context
- old decision
- expected decision
- expected impact

**Replay output should measure:**
- false positive reduction
- false negative reduction
- task continuation rate
- evidence completeness
- repo-level finding recall

**Exit condition:**
至少能对一组历史 trace 回放新 harness，输出比较结果。

---

## Phase 5: Add a Harness Review Step to Flow Completion

### Task 5: Treat `flow done` as a learning checkpoint

**Files:**
- Modify: `src/vibe3/commands/flow.py`
- Modify: `src/vibe3/services/handoff_service.py`
- Possibly create: `src/vibe3/services/harness_review.py`

**Intent:**
flow 完成时不仅关闭现场，还要回顾 harness 是否帮助了任务。

**Review questions at flow done:**
- 本 flow 中有哪些反复出现的坏动作
- 哪些 decision 被证明是误伤
- 哪些 trace 应提升为长期样本
- 哪些 trace 指向仓库设计、语义或代码层的问题
- 是否建议更新 harness

**Recommended outputs:**
- `handoff_audit` with harness review summary
- flow event pointing to review artifact
- suggestion for next harness iteration

**Exit condition:**
每次 `flow done` 都能形成一次最小的 harness retrospective。

---

## Phase 6: Separate Stable Policy Seeds From Learned Harness Logic

### Task 6: Re-scope `autoharness.yaml`

**Files:**
- Modify: `.agent/governance/policies/autoharness.yaml`

**Intent:**
把 YAML 从“静态拦截规则表”降级为：

- 治理目标
- 稳定边界
- 评估指标
- harness seed hints

**YAML should define:**
- stable invariants
- trace requirements
- replay metrics
- promotion criteria

**YAML should not pretend to define:**
- every exact rewrite
- every exact blocked command
- the final learned harness itself

**Exit condition:**
`autoharness.yaml` 成为学习机制的配置入口，而不是全部逻辑本体。

---

## Phase 7: Harness Synthesis Loop

### Task 7: Add a controlled refinement loop

**Files:**
- Possibly create: `src/vibe3/services/harness_synthesis.py`
- Possibly create: `docs/reports/` templates for synthesis review

**Intent:**
让 harness 可以根据 accumulated findings 被修正，但不能未经验证直接替换。

**Loop shape:**
1. 收集 trace corpus
2. 聚类常见失败模式
3. 区分“agent behavior problem”与“repo defect signal”
4. 生成 harness patch
5. replay against corpus
6. compare old vs new
7. human review or supervised promotion

**Key rule:**
只有通过 replay 的 harness 才能晋升。

**Exit condition:**
仓库具备“记录 -> 分析 -> 修改 -> 回放 -> 晋升”的最小闭环。

---

## Validation Strategy

### Unit tests

- trace model tests
- trace persistence tests
- finding promotion tests
- replay comparison tests

### Integration checks

- `run/review` 过程中可写 harness trace
- `flow show` 时间线能看到 trace evidence
- `handoff current.md` 可看到高价值 findings
- `flow done` 能输出 harness retrospective summary

### Success metrics

- trace completeness
- finding usefulness
- false positive rate
- false negative rate
- flow completion rate
- repo defect discovery usefulness

---

## Risks and Constraints

### Constraint 1: Over-logging creates noise

所以必须区分 raw trace 和 promoted finding，不能所有动作都直接写入 handoff narrative。

### Constraint 2: Learned harness can regress

所以 replay evaluation 是强制的，不能直接用最新 patch 替换。

### Constraint 3: Flow/handoff are evidence layers, not the learned policy itself

它们用于沉淀经验和回顾，不应承载全部 runtime 逻辑。

---

## Deliverable of This Plan

完成后，仓库将拥有：

1. 一套稳定的 harness trace contract
2. flow 事件中可追溯的 agent action evidence
3. handoff 中可沉淀的 harness findings
4. 基于历史样本的 replay corpus
5. 一个以 `flow done` 为回顾点的 harness 学习闭环
