# Phase 0 Research: ADR Context Recall

**Feature**: 011-adr-recall | **Date**: 2026-07-03 | **Spec**: [spec.md](./spec.md)

本文件记录把 spec 落地为 plan 所需的全部设计决策。每项给出 **Decision / Rationale / Alternatives**。7 轮 brainstorm grill 的宏观决议见 [spec.md §Design Decisions](./spec.md)；此处聚焦实现层的工程选择。

---

## 1. 召回程序的承载形态：独立 skill

**Decision**: 召回程序作为独立 skill `.claude/skills/adr-recall/SKILL.md` 承载，**不**注册为 `.specify/extensions/<ext>/extension.yml` 的生命周期钩子。

**Rationale**:
- 召回由 `supervisor/policies/plan.md` 在 plan 阶段**显式调用**（"运行 adr-recall skill"），不是 spec-kit 生命周期事件（`before_plan`/`after_plan` 等）的自动触发。
- skill 形态最薄：一个 markdown 文件，零扩展注册、零 `extension.yml` 维护、零 HookExecutor 介入。
- 对齐 HARD RULES #16 Skill-First 三问法：(1) 不创造不可替代的原子能力（只是编排读 ADR + 产 artifact）→ 必须是 skill；(2) 编排现有能力（读 INDEX、`vibe3 inspect base`、写 artifact）达 80% 目标 → YES；(3) 非核心管线阶段 → 非命令。
- 命名：项目 spec-kit 集成 skill 前缀为 `speckit-*`，但召回不属于 spec-kit 六阶段（brainstorm/specify/plan/tasks/implement/review），它是**任意 plan 时刻**的横向能力（包括非 spec-kit 的 `/vibe-*` 流程）。故用中性名 `adr-recall`（无 `speckit-` 前缀），表明它是项目级 skill 而非 spec-kit 阶段 skill。

**Alternatives**:
- **A. spec-kit extension（`extension.yml` + `commands/`）**： rejected——需维护扩展注册、版本、hook 元数据，对一个不被生命周期触发的命令是纯开销。仅当未来要接入 `after_plan` 自动注入时才值得升级为 extension。
- **B. 内嵌进 `plan.md` policy 文本**：rejected——policy 应薄（声明"跑召回"），召回的有序 checklist + 自检逻辑有足够复杂度，独立 skill 更可测、可复用（`vibe-task`/`vibe-roadmap` 也要调）。

---

## 2. `decides` 字段：语义与质量判据

**Decision**: `decides` 是 frontmatter 字段，一句话陈述"**决策对象 + 约束**"，<120 字。质量自检规则：须同时含 (a) 决策对象（被约束的实体/机制）与 (b) 约束词（"必须/禁止/仅/不得/MUST/禁止"等指令性动词）。

**Rationale**:
- `decides` 是召回**第一步（语义相关性）**的唯一扫描源；INDEX.md 的 `decides` 列让 agent 一次扫完全部 ADR 的相关性，不必读 body。
- "决策对象 + 约束"形式使语义匹配有抓手：issue 提到的事件边界 → 命中 `decides` 含 "DomainEvent 禁止承担 flow 状态机判断"。
- <120 字强制压缩，避免 `decides` 沦为正文副本（违反 ADR "记录为什么不记录怎么做"）。

**写作示导（入 `_template.md`）**:
- ✅ `decides: "DomainEvent 禁止承担 flow 状态机判断；FlowEvent 仅作 flow-local 审计投影，由 DomainEvent 单向投影产生。"`
- ✅ `decides: "依赖注入必须经 Protocol（BackendProtocol 等），禁止 service 层直接实例化 backend。"`
- ❌ `decides: "我们选了事件驱动。"`（无约束、无对象——低质，自检会标记）
- ❌ `decides: "见正文 Decision 节。"`（无信息量）

**Alternatives**:
- **用 `tags` 刻面**：rejected——tags 是分类，`decides` 是可读的决策摘要，后者对 agent 语义匹配更直接（ADRScope 式刻面搜索留作过阈值后的 follow-up）。
- **不设质量自检，靠人工把关**：rejected——人工把关即现状（INDEX 已有但 agent 不读），自检把质量门槛前移到召回时。

---

## 3. `scope` 字段：语义、与 `related_docs`/`How` 的关系

**Decision**: `scope` 是 frontmatter 字段，值为 **path globs**（仓库相对路径，支持 `*` 通配），指向该 ADR 治理的**代码位置**。召回**第二步（代码相关性）**用 `vibe3 inspect base` 得到的改动文件列表匹配 `scope`。

**与现有字段的关系**（关键澄清，避免职责重叠）:
- `related_docs`：指向**文档**（standards/guides）。已有。
- `How` 段：链接到实现文档 + 当前代码模型文件（如 `src/vibe3/models/domain_events.py`）。已有，且是**人读**的链接清单。
- `scope`（新）：**机器匹配**用的代码 path glob，是召回代码相关性的锚点。它**形式化**了 `How` 段里已经零散存在的代码路径信号（ADR-0004 的 `How` 已指向 `domain_events.py`/`flow.py`），使之可被 glob 匹配。

**Rationale**:
- 召回需要"改动文件 → 命中 ADR"的反向映射；没有 `scope`，只能靠 `decides` 语义猜，假阴性高。
- `scope` glob 与 `How` 链接不冲突：前者是机器锚点（精简 glob），后者是人读上下文（具体文件 + 说明）。

**示例**（ADR-0004 回填）:
```yaml
scope:
  - src/vibe3/models/domain_events.py
  - src/vibe3/models/flow.py
  - src/vibe3/domain/handlers/**
  - src/vibe3/runtime/**
```

**Alternatives**:
- **复用 `related_docs` 承载代码路径**：rejected——语义混淆（doc vs code），且 `related_docs` 无 glob 语义。
- **不设 `scope`，纯靠语义匹配**：rejected——代码相关性假阴性不可接受（事件边界类 ADR 必须靠改动文件命中）。

---

## 4. ADR-Consideration Artifact Schema

**Decision**: artifact 作为 plan.md 的 "ADR Consideration" 节内嵌，schema 见 [contracts/artifact.md](./contracts/artifact.md)。核心字段：

| 字段 | 说明 |
|------|------|
| `adr_snapshot_baseline` | 召回基线（分支 + commit SHA），标记 ADR 快照版本，防"分支陈旧"误判 |
| `evaluated_adrs` | 全部评估过的 accepted ADR（至少读了 `decides` 的） |
| `applicable` | `scope` 命中且语义相关的，读了 body 的 ADR |
| `dismissed` | 评估后判定不适用的 ADR，**每条附理由**（禁止空豁免） |
| `decides_quality_flags` | `decides` 自检标记的低质项（ADR id + 问题） |
| `scope_rot_flags` | `scope` 健康自检标记的腐烂项（路径不存在 / supersede 继承缺口） |
| `supersede_proposals` | 若 plan 需偏离某 accepted ADR，显式提议的 supersede（编号 + 理由） |

**Rationale**:
- `adr_snapshot_baseline` 直击"分支陈旧"edge case（spec Edge Case #5）。
- `dismissed` 强制附理由 + `evaluated_adrs` 记全集，直击"零匹配假阴性"（spec Edge Case #4）：reviewer 可审计"声称零相关"是否成立。
- `scope_rot_flags` 把"腐烂可见"（SC-004）变成 artifact 一等字段，review 必须处理。

**Alternatives**:
- **独立 artifact 文件**（如 `.agent/plans/adr-consideration-<issue>.md`）：rejected——artifact 是 plan 的必要组成（FR-009），内嵌避免分裂真源；reviewer 读 plan 即得。
- **极简 artifact（只列 applicable）**：rejected——无 `dismissed`/`evaluated` 则零匹配无法审计，gate 形同虚设。

---

## 5. Gate 的"牙齿"映射：BLOCK → FailedGate；`roadmap/rfc` 由谁打

**Decision**: review 阶段 ADR 违规的 enforcement 路径：
1. reviewer 审计 artifact，违反 accepted ADR / artifact 不完整 → 给 **BLOCK** verdict（`supervisor/policies/review.md` 裁决标准已有 BLOCK）。
2. BLOCK verdict **喂给现有 FailedGate / block-flow**（`src/vibe3/orchestra/failed_gate.py`、runtime heartbeat），产生 flow 阻断——**不新建 enforcement 管道**。
3. `roadmap/rfc` 标签**不是 reviewer 直接打**：当违规需要人类做 ADR 决策（如是否 supersede）时，reviewer 在 comment 里**建议**打 `roadmap/rfc`（该标签的权威打标路径是 `skills/vibe-roadmap`，reviewer 不越权直打）。

**Rationale**（精确化 spec FR-011，避免凭空发明标注路径）:
- 现状核查：`review.md` 的裁决是 PASS/MAJOR/BLOCK，reviewer 通过 `[review]` marker 的 comment 外发裁决，**本身不打标签**；BLOCK 的强制力来自 FailedGate。
- `roadmap/rfc` 是**单个标签**（带斜线，见 `skills/vibe-roadmap/SKILL.md:74,418`），由 roadmap 流程在"需人类架构决策"时打。reviewer 复用它的语义（"这条要人类拍板 ADR"），但走建议而非直打，避免双打标路径。
- 这是对 HARD RULES #15（最短路径优先）的严格遵守：复用 FailedGate + 复用 `roadmap/rfc` 语义，零新增强制基础设施。

**Alternatives**:
- **reviewer 直接 `gh issue edit --add-label roadmap/rfc`**：rejected——绕过 vibe-roadmap 的打标权限，形成第二打标路径；且 review skill 的 guardrail 明确"不发 PR/不 merge/不 label"。
- **新建 `adr-violation` 标签**：rejected——标签膨胀，且 `roadmap/rfc` 已覆盖"需人类架构决策"语义。

---

## 6. 零匹配的处理（防假阴性）

**Decision**: 召回返回无相关 ADR 时，artifact 仍必须填写 `evaluated_adrs`（全集）+ `dismissed`（每条附"为何不适用"）。reviewer 把"零相关"主张本身作为审计点：若 `evaluated_adrs` 漏列已 accepted ADR，或 `dismissed` 无理由，按 artifact 不完整 → BLOCK。

**Rationale**: spec Edge Case #4 的直接对策。无此规则，"零匹配"成为绕过 gate 的万能口令。

**Alternatives**: 无（这是 gate 有效的必要条件）。

---

## 7. supersede 链的 `scope` 继承检测

**Decision**: `scope` 健康自检包含两条规则：
- **R1 路径存在**：`scope` glob 展开后至少命中一个当前仓库存在的路径；否则标腐烂。
- **R2 继承覆盖**：若 ADR-B `supersedes` ADR-A，则 ADR-B 的 `scope` **必须覆盖** ADR-A 的 `scope`（否则 ADR-A 治理的代码在被取代后无人治理 → 双重漏判）。缺口标腐烂。

**Rationale**: spec Edge Case #2（supersede 漏继承）的直接对策。检测在召回时（读 frontmatter 即可），不需引擎。

**Alternatives**:
- **强制 supersede 时自动复制 scope**：rejected——frontmatter 是人写的，强制自动复制会破坏 ADR 不可变性约定；改为"检测 + 标记 + 人工修"。

---

## 8. constitution.md 增补：semver 策略

**Decision**: 在 `.specify/memory/constitution.md` 新增一节 "Spec ↔ ADR ↔ Principles 三层关系"（FR-013），按 semver **MINOR** bump（1.0.0 → 1.1.0），并更新顶部 Sync Impact Report。

**Rationale**: constitution §Governance 定义：MINOR = 新增 section。本节是**新增**原则关系声明，不改现有 5 原则、不动权限层级 → MINOR。内容遵守原则 II（只声明关系、引用上游，不复述 SOUL/CLAUDE/rules）。

**三层关系（增补节核心）**:
- **Principles**（SOUL/CLAUDE/rules）：常驻、不可变价值观与硬规则——"为什么这样管"。
- **Spec**（`.specify/specs/NNN/`）：per-feature "这个功能做什么"。
- **ADR**（`docs/decisions/`）：cross-cutting "为什么选这个架构决策"，跨 feature 长期有效。
三者互补：spec 引用 principles + 遵守 applicable ADR；ADR 不复述 principles；principles 不规定 per-feature 实现。

**Alternatives**:
- **PATCH（仅措辞）**：rejected——这是新增 section，不是措辞调整。
- **MAJOR**：rejected——未删除/重定义原则，未动权限层级。

---

## 结论

全部 8 项实现决策已落定，无未决项。Phase 1 直接据此产出 data-model / contracts / quickstart。零 Python 约束（FR-014）贯穿所有决策——所有 enforcement 复用现有机制，本特性净增仅为 markdown 数据 + 一个 skill + policy 文本。
