# Blocked / Dependency 对账标准 — 当前实现缺口清单

**维护者**: Vibe Team
**最后更新**: 2026-06-29
**状态**: Migration Tracker（重构完成后可移除）

> 配套标准: [blocked-dependency-reconciliation-standard.md](blocked-dependency-reconciliation-standard.md)
> 用途: 记录当前代码/文档相对标准 v1.0 的差距，作为分阶段重构 plan 的输入。

---

## 0. 说明

这是一份**迁移快照**：对照 [统一标准](blocked-dependency-reconciliation-standard.md) 逐条列出当前实现的偏离，附证据（`file:line`）、违反的标准章节、严重度。重构 plan 关闭这些缺口后，本文可删除。

严重度：**P0** 直接导致 resume<->block 漂移 / 误派发；**P1** 结构性漂移（修不彻底会复发）；**P2** 一致性/健壮性。

---

## 1. 缺口总表

| # | 缺口 | 违反 | 证据 | 严重度 |
|---|------|------|------|--------|
| G1 | 双（三）轨对账并存：QualifyGate 与 CheckService 规则各写一套 blocked/resume 逻辑 | §1.4, §6 | `queue_operations.py:94`, `dispatch_health.py:83`, `rule_checks.py:148/187` | P0 |
| G2 | 真源方向接反：决策读 label/flow_status，缓存从 label 重建并伪造 reason | §1.1, §1.3, §7 | `rule_checks.py:202`, `qualify_gate_support.py:197`, `rule_checks.py:152` | P0 |
| G3 | `sync_cache_from_truth`（body->缓存）是死代码 | §1.1, §6 | `blocked_state_service.py:336`（零调用） | P1 |
| G4 | 依赖门禁读错字段：读 dead `dependencies`，真正生效的是 `blocked_by` | §8 | `qualify_gate_checks.py:121`, `service.py:388`, `coordination.py:185` | P1 |
| G5 | 依赖只写不清：无任何解除/清理 `flow_issue_links` 的路径 | §1.5, §6.3 | 全仓库无 unlink；`blocked_state_io.py:130` 不碰 links | P0 |
| G6 | 无统一写/清原语：写散落多处，清不一致 | §1.2, §4 | `block_mixin.py:31`, `task/service.py:107`, `blocked_state_io.py:84` | P1 |
| G7 | auto-resume 不做依赖门禁，可清掉仍有未关闭依赖的阻塞 | §6.2 | `qualify_gate.py:113`, `rule_checks.py:148` | P0 |
| G8 | `intake --blocked-reason` 单用静默丢弃 | §5 | `task.py:262`, `orchestrator.py:147` | P2 |
| G9 | 依赖基数不一致：`flow_state.blocked_by_issue` 单值 vs body/links 多值 | §2.1 | `sqlite_schema.py:270`, `resume.py:363` | P2 |
| G10 | 标准文档自相矛盾（三种真源说法） | §0 | 见标准 §0 废止表 | P1 |

---

## 2. 逐项详述

### G1 — 双轨对账（P0，违 §1.4/§6）

服务器上**同时**运行两套独立的 blocked/resume 对齐逻辑，触发条件不同，竞争同一 flow：

- **QualifyGateService**（orchestra 派发）：`run_qualify_gate` / `qualify_blocked_issue`，入口 `queue_operations.py:94`、`dispatch_coordinator.py:336`。
- **CheckService 规则**（周期 + 健康检查）：`rule_stale_blocked_sync`(`rule_checks.py:148`)、`rule_blocked_label_sync`(`rule_checks.py:187`)，入口 `periodic_check_executor.py:52`、`dispatch_health.py:83`。
- 第三者 `orchestra/remote_check.py:39` 做纯 label 卫生（范围不同，但属同类 sprawl）。

标准要求三入口收敛到单一 `reconcile_blocked`（§6），差异仅 `clear_reason`。

### G2 — 真源方向接反（P0，违 §1.1/§1.3/§7）

- `rule_blocked_label_sync` 从 **label** 重建缓存，并**伪造** `reason="Remote state/blocked label detected"`、`blocked_by_issue=None`（`rule_checks.py:202-211`）——真源信息丢失。
- `has_stale_blocked_state` 以 **label 或 DB** 为触发（`qualify_gate_support.py:197-211`）。
- `rule_stale_blocked_sync` 以 `flow_status=="blocked"` + label 变化为触发（`rule_checks.py:152-157`）。

标准要求：判定一律读 body 真源；缓存/label 只能由 reconcile 从 body 重建（§7 禁止用法清单）。

### G3 — body->缓存更新器是死代码（P1，违 §1.1/§6）

`BlockedStateService.sync_cache_from_truth`（`blocked_state_service.py:336`）实现了"从 body 真源重建缓存"，但**零调用**。当前缓存由 G2 的 label 路径拼出。标准的 `rebuild_cache_from_truth`（§6）应以此为基。

### G4 — 依赖门禁读错字段（P1，违 §8）

- `check_dependencies` 读 `truth.dependencies`（`qualify_gate_checks.py:121`）；CheckService 只读依赖检查同样读 `truth.dependencies`（`service.py:388`）。
- `truth.dependencies` 源自 body 托管投影的 `dependencies` 字段（`coordination.py:185-191`），而该字段**无生产写入者（dead）**。
- 真正生效的依赖门禁是 `qualify_blocked_issue` 用 `truth.blocked_by_issues`（body `Blocked by`）（`qualify_gate.py:158`）。

标准：退役 `dependencies` 字段与 `check_dependencies`，统一走 `blocked_by`（§8）。

### G5 — 依赖只写不清（P0，违 §1.5/§6.3）

- 写：`link_issue(role="dependency")` 写 `flow_issue_links`（`task/service.py:107`、`block_mixin.py:76`）。
- 清：**全仓库无任何删除/对齐 `flow_issue_links` 的路径**（grep 确认无 unlink/break）；`unblock`/`clear_database_cache` 不触及它（`blocked_state_io.py:130`）。
- 后果：被依赖 issue 关闭或 body 移除依赖后，`flow_issue_links` 永久残留；degraded 回退时可基于已解决依赖误判。

标准：reconcile 的 `rebuild_cache_from_truth` 必须按 body 真源对齐/清理依赖缓存（§6.3）。

### G6 — 无统一写/清原语（P1，违 §1.2/§4）

- 写：`block_flow`(`block_mixin.py:31`) + `link_issue` + `block_state_only` + `write_body_projection` 多处拼装。
- 清：`clear_body_projection`(`blocked_state_io.py:84`，无条件清 body 全部) + `clear_database_cache`（不碰 links）。
- 无单一 `set_block` / `clear_block` 原语。标准 §4 要求归一。

### G7 — auto-resume 不做依赖门禁（P0，违 §6.2）

- 手工 resume 有依赖门禁 `_check_blocked_by_dependency`（`resume.py:363`，但只查单值 `blocked_by_issue`）。
- auto-resume 两条路径**都不查依赖**：`run_qualify_gate` 的 `has_stale` 路径 -> `auto_resume_blocked`（`qualify_gate.py:113`）；`rule_stale_blocked_sync`（`rule_checks.py:148`）-> `recover(auto=True)`。
- 后果：body 一旦被读成"未阻塞"，会清掉仍有未关闭依赖的阻塞。标准要求 auto 路径与 resume 共用 reconcile，依赖未满足时保持 blocked（§6.2）。

### G8 — intake reason 单用丢弃（P2，违 §5）

`task intake --blocked-reason R`（无 `--blocked-by`）时，placeholder 创建被 `if blocked_by is not None` 门控跳过（`task.py:262`），`bootstrap_issue_flow` 也仅在有依赖时调 `block_flow`（`orchestrator.py:147-200`）-> reason 静默丢弃。标准要求 reason 单用必须生效。

### G9 — 依赖基数不一致（P2，违 §2.1）

`flow_state.blocked_by_issue` 是单值列（`sqlite_schema.py:270`），而 body `Blocked by` 与 `flow_issue_links` 是多值；手工 resume 门禁只查单值（`resume.py:363`）-> 多依赖时只校验其一。标准把多值真源放 body，`blocked_by_issue` 仅作派生主依赖。

### G10 — 标准文档矛盾（P1，违 §0）

三份现有文档对依赖真源给出三种说法（body remote-first / flow_issue_links / 三个真源），见标准 §0 废止表。需按本次裁定回写对齐。

---

## 3. 不在本次范围

- Scope 拆分 / Epic / RFC 语义（[issue-dependency-standard.md](../issue-dependency-standard.md) §3-6 不变）。
- 依赖继承（从被依赖 PR 分支建 worktree，[dependency-handling.md](../../v3/architecture/dependency-handling.md) §3）——保留，仅真源声明对齐。
- 终端状态（done/aborted/review/failed）回收逻辑。

---

## 4. 建议分阶段映射（plan 输入）

| 阶段 | 关闭缺口 | 说明 |
|------|---------|------|
| P-1 统一原语 + 退役死字段 | G6, G4, G3 | 落 `set_block`/`clear_block`/`rebuild_cache_from_truth`；退役 `dependencies`/`check_dependencies` |
| P-2 依赖对账闭环 | G5, G7, G9 | reconcile 清理 `flow_issue_links`；auto 路径加依赖门禁；多值化 |
| P-3 收敛双轨 | G1, G2 | check/orchestra/resume 共用 `reconcile_blocked`，只差 `clear_reason`；flow_status 退回指针 |
| P-4 收尾 | G8, G10 | intake reason 修复；回写对齐其余标准文档 |
| 检查 | 全部 | 端到端回归（含 desk-sync + 未关闭依赖 -> 不放行）+ 全量 CI |

---

## 5. 变更历史

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-06-29 | 1.0 | 初版缺口快照，对照标准 v1.0 |
