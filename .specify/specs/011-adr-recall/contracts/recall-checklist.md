# Contract: Recall Procedure (Behavioral)

**Feature**: 011-adr-recall | **Skill**: `.claude/skills/adr-recall/SKILL.md`

本契约定义召回程序（`adr-recall` skill）的有序步骤、每步输入/输出/失败模式。是无状态行为契约——每次调用从头执行，产出一份 artifact。

---

## 触发与上下文

- **触发方**: `supervisor/policies/plan.md`（plan 阶段）、`skills/vibe-task`、`skills/vibe-roadmap`，通过显式指令"运行 adr-recall skill"调用。
- **输入上下文**:
  - 当前 issue（标题 + 描述 + comments）——语义相关性的人读锚点
  - 改动文件清单——来自 `vibe3 inspect base`（既有命令，只读消费）
  - ADR 全集——来自 `docs/decisions/INDEX.md` + 各 ADR frontmatter
- **输出**: 写入 plan.md 的 `## ADR Consideration` 节（schema 见 [artifact.md](./artifact.md)）。

---

## 有序步骤（State Machine）

### S1 — 语义相关性（读 `decides` 列）

- **输入**: INDEX.md 的 `decides` 摘要列 + issue 语义
- **动作**: 扫描全部 accepted ADR 的 `decides`，标出与 issue 语义相关的候选集
- **输出**: 候选 adr_id 集
- **失败模式**: `decides` 缺失/低质 → 该 ADR 仍进候选（保守），但 S3 标记

### S2 — 代码相关性（`scope` 匹配改动文件）

- **输入**: 候选集 + 改动文件清单（`vibe3 inspect base`）+ 各 ADR `scope` glob
- **动作**: 改动文件路径匹配候选 ADR 的 `scope` glob，命中则升为 applicable 候选
- **输出**: applicable 候选 adr_id 集（S1 候选 ∩ scope 命中）
- **失败模式**: ADR 无 `scope` → 仅靠 S1 语义判定（保守纳入），S4 标记

### S3 — `decides` 质量自检

- **输入**: 全部 accepted ADR 的 `decides`
- **动作**: 按 [adr-frontmatter.md §质量判据](./adr-frontmatter.md) 检查对象/约束/长度
- **输出**: `decides_quality_flags`
- **失败模式**: 标记低质，不阻塞

### S4 — `scope` 健康自检

- **输入**: 全部 accepted ADR 的 `scope` + supersede 链（`supersedes`/`superseded_by`）
- **动作**: R1 路径存在（glob 展开 ≥1 现存路径）；R2 supersede 继承覆盖（successor scope ⊇ predecessor scope）
- **输出**: `scope_rot_flags`（kind = missing_path / supersede_gap）
- **失败模式**: 标记腐烂，不阻塞；reviewer 决定是否先修 ADR

### S5 — 读命中项 body

- **输入**: applicable 候选 adr_id 集
- **动作**: **仅**读这些 ADR 的正文（Context/Decision/Consequences），抽取对当前改动的约束要点
- **输出**: per-ADR 适用性判断 + 约束摘要
- **关键**: 选择性——未命中项**不读 body**（SC-001），只读 `decides`

### S6 — 产 artifact

- **输入**: S1-S5 全部结果
- **动作**: 填 plan.md `## ADR Consideration` 节（schema 见 [artifact.md](./artifact.md)）
- **输出**: 完整 artifact（baseline / evaluated / applicable / dismissed+reason / flags / supersede_proposals）
- **失败模式**: artifact 字段不全 → 视为召回未完成，plan 不应进入 review

---

## 不变量（Invariants）

1. **选择性**: 读取的 ADR body 数 ≤ accepted ADR 总数（仅 applicable 候选读 body）。违反 → 召回退化为全量读，失去价值。
2. **全集审计**: `evaluated_adrs` 必须等于当前 accepted ADR 全集（不论是否命中）。违反 → artifact 不完整，review BLOCK。
3. **无空豁免**: 每个 `dismissed` 必须附理由。
4. **基线可追溯**: artifact 必含 `adr_snapshot_baseline`（branch + commit）。
5. **腐烂可见**: S3/S4 的 flags 必须反映到 artifact，不得静默吞掉。

---

## 与既有命令的关系（只读复用）

| 既有能力 | 召回中的用途 | 是否修改 |
|----------|--------------|----------|
| `vibe3 inspect base` | S2 提供改动文件清单 | 否（只读） |
| `docs/decisions/INDEX.md` | S1 提供 `decides` 列 | 否（数据层回填后只读） |
| `gh issue view` / `vibe3 task show` | 提供当前 issue 语义上下文 | 否（只读） |
| plan.md 结构 | S6 写入 "ADR Consideration" 节 | 新增节，不改既有节 |

召回程序**不调用任何新 Python 命令**，全部通过既有命令 + frontmatter 解析 + agent 判断完成（FR-014）。
