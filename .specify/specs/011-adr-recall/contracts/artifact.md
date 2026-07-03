# Contract: ADR-Consideration Artifact

**Feature**: 011-adr-recall | **Data model**: [data-model.md](../data-model.md)

本契约定义召回产出物 "ADR-Consideration Artifact" 的 schema。该 artifact 内嵌于 plan.md 的 "ADR Consideration" 节，是 review gate 的审计对象。

---

## 位置

- **载体**: plan.md 的 `## ADR Consideration` 节（内嵌，非独立文件）。
- **触发**: 非平凡变更的 plan 必含（FR-009）；平凡变更（纯文档错字、依赖升版）可附"本变更非平凡性说明 + 无需 ADR 召回"声明豁免，由 reviewer 判定。

---

## Schema

```markdown
## ADR Consideration

**Baseline**: branch=<branch>, commit=<short_sha>
**Changed files**: (来自 vibe3 inspect base) <file list 或摘要>

### Evaluated ADRs
- ADR-0001 — <decides 摘要>
- ADR-0002 — <decides 摘要>
- ...（全部 accepted ADR，至少读了 decides 的）

### Applicable（scope 命中 + 语义相关，已读 body）
- **ADR-0004** — 适用：本改动触及 <path>，须遵守 <约束要点>
  - 影响评估：<plan 如何遵守 / 哪里体现>
- （无则写"无 applicable ADR"，并见 Dismissed 审计）

### Dismissed（评估后不适用，须附理由）
- ADR-0001 — 不适用：<理由，如"本改动不涉及 RFC→ADR 闭环流程">
- ADR-0003 — 不适用：<理由>
- ...

### Self-Check Flags
- **decides quality**: 无低质 / [ADR-0005: missing_constraint]
- **scope rot**: 无腐烂 / [ADR-0004: missing_path — src/vibe3/runtime/ 已迁移]

### Supersede Proposals（若需偏离 accepted ADR）
- 无 / 提议 ADR-0006 取代 ADR-0004，理由：<...>
```

---

## 字段约束（review 审计依据）

| 字段 | 约束 | 违反后果（review） |
|------|------|---------------------|
| `Baseline` | 必填 branch + commit | 缺失 → BLOCK（无法审计分支陈旧） |
| `Evaluated ADRs` | 必须含全部当前 accepted ADR | 漏列 → BLOCK（artifact 不完整） |
| `Applicable ∪ Dismissed` | 必须等于 accepted ADR 全集 | 不等 → BLOCK |
| `Dismissed.reason` | 每条必填 | 空豁免 → BLOCK |
| `Self-Check Flags` | 必须反映召回自检结果 | 漏报已知腐烂 → BLOCK |
| `Supersede Proposals` | plan 实现违反 accepted ADR 时必填 | 违反且未提议 → BLOCK |

---

## 零匹配（Zero-Match）强制规范

当召回判定无 applicable ADR（`Applicable` 为空）时：
- `Evaluated ADRs` 仍必须列全部 accepted ADR。
- `Dismissed` 必须含全部 accepted ADR，每条附"为何 scope/语义不匹配"理由。
- reviewer 把"零相关"主张本身作为审计点：若理由不成立（如某 ADR scope 显然命中改动文件却被 dismiss），→ BLOCK。

**理由**: 零匹配是绕过 gate 的天然口令；强制全集 + 逐条理由让假阴性可被审计（spec Edge Case #4）。

---

## 豁免（平凡变更）

纯文档错字、依赖版本升级、CI 配置微调等不触及代码语义的变更，plan 可写：

```markdown
## ADR Consideration

本变更为平凡变更（<类型：错字/依赖升版/...>），不触及任何 ADR 治理的代码语义，故豁免召回。
若 reviewer 判定非平凡，须补跑召回。
```

reviewer 拥有豁免否决权：若判定实际非平凡，按 artifact 缺失 → BLOCK。
