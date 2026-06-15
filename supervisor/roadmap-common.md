---
document_type: standard
title: 治理三层架构与公共定义
status: active
scope: governance-common
authority:
  - three-layer-architecture
  - label-semantics
  - review-framework
maintainer: Vibe Team
created: 2026-05-28
last_updated: 2026-05-28
related_docs:
  - supervisor/governance/roadmap-intake.md
  - supervisor/governance/assignee-pool.md
  - skills/vibe-roadmap/SKILL.md
  - docs/governance/governance-roadmap-closed-loop.md
---

# 治理三层架构与公共定义

本文档集中定义 Governance 系统的公共架构、标签语义和审查框架，避免分散在多个文件中重复阐述。

## 三层架构

Governance 分为两层，加上上层的 roadmap 审查，共三层。每层有独立的标签实现闭环，防止重复处理。

### 架构流程

```
broader repo --> Layer 1: roadmap-intake (入口层)
                    扫描范围: 无 assignee 的 issue
                    过滤: 无 orchestra-scanned（自闭环）
                          + 无 roadmap/rfc / roadmap/epic
                    注意: no-assignee + orchestra-governed 不能被当作可信跳过条件
                    接受 -> 分配 assignee -> 流入 Layer 2
                    跳过 -> 打 orchestra-scanned -> 不再看
                          |
                          v
                 Layer 2: assignee-pool (入池前/池内准入决策层)
                    扫描范围: 分配给本机 manager 的 issue
                    过滤: 无 orchestra-governed
                    例外: roadmap/epic 收口检查每次独立扫描，不受 governed 过滤
                    高置信度决策(close/split/rfc/epic/ready/resume) -> 直接执行/打闭环标签
                    低置信度 -> roadmap/rfc 交人类
                          |
                          v
                 Layer 3: vibe-roadmap (上层审查/纠偏层)
                    扫描范围: 所有 [governance suggest][roadmap-intake] / [governance suggest][assignee-pool] 评论
                    过滤: 无 roadmap-reviewed 且无 roadmap/rfc
                    审查 -> 打 roadmap-reviewed -> 写入 memory.md
```

### 角色分工

| 角色 | 文件 | Marker | 职责 | 标签 |
|------|------|--------|------|------|
| **roadmap-intake** | supervisor/governance/roadmap-intake.md | `[governance suggest][roadmap-intake]` | 入口观察者：扫描 broader repo，决定是否纳入 pool | 跳过时打 `orchestra-scanned` |
| **assignee-pool** | supervisor/governance/assignee-pool.md | `[governance suggest][assignee-pool]` / `[governance decide][assignee-pool]` | 入池前/池内准入 decider：对本机 manager pool 中 issue 做 rfc/epic/ready/close 决策 | 决策后打 `orchestra-governed`，高置信度 close 直接终局 |
| **vibe-roadmap** | skills/vibe-roadmap/SKILL.md | `[roadmap decision]` | 上层审查者：审查 governance 决策，纠正和补全 | 审查后打 `roadmap-reviewed` |
| **vibe-task** | skills/vibe-task/SKILL.md | 无（human-facing，不写 marker） | 人机协作规划辅助：帮助人类处理 blocked/RFC/epic issues，整理依赖关系说明，pre-flow 阶段仅写 issue body 自然语言 | 不操作 `state/*` 标签，不写 managed section |

---

## Priority Scale

优先级标签语义详见 [label-semantics.md](../docs/standards/label-semantics.md)。

**关键规则**：
- `priority/[0-9]`：数字越大优先级越高（9 = 最高，0 = 最低）
- `roadmap/p0-p2`：数字越小越紧急（p0 = 当前版本，最紧急）
- **两者语义相反，勿混淆**

---

## 三标签语义

### 1. orchestra-scanned（入口层闭环）

**谁打**：roadmap-intake
**何时打**：审查后**决定不接受**（不分配 assignee）时
**不打的情况**：接受并分配 assignee 时——assignee 本身就是信号，issue 自然流入 assignee-pool
**Level 0 联动**：`.claude/`/`.codex/` 机械阻塞 skip 时，除 `orchestra-scanned` 外**同时打 `roadmap/rfc`**，使其命中 task-status Rule 1 被 `/vibe-task` surface（详见 [governance-roadmap-closed-loop.md](../docs/governance/governance-roadmap-closed-loop.md) 的 "Level 0 闭环"）

**语义**："已审查，不纳入"（intake 层的结论，后续层可推翻）

**被后续层推翻时的处理**：
vibe-roadmap 审查时如果决定推翻 intake 的 skip 判断（见角色分工表中的"上层审查者：纠正和补全"），应同时：
- 移除 `orchestra-scanned` 标签
- 分配 assignee
- 打 `roadmap-reviewed` 标签

**当前共识**：`orchestra-scanned` 与 assignee 共存是遗留痕迹（roadmap 推翻了 intake 但未清理标签），不影响功能（intake 扫描会同时过滤 assignee 和 scanned 标签），但长期应清理。

**命令**：
```bash
gh issue edit <issue-number> --add-label "orchestra-scanned"
```

**颜色**：FF9933（橙色）

**过滤逻辑**：
```
intake 扫描 -> 跳过有 orchestra-scanned 的 issue（自闭环）
intake 扫描 -> 跳过有 roadmap/rfc 或 roadmap/epic 的 issue（已路由）
intake 扫描 -> 跳过有 assignee 的 issue（已在 pool 中）
intake 扫描 -> 不信任 no-assignee + orchestra-governed，重新评估
```

**stale governed 说明**：
`orchestra-governed` 是 assignee-pool 层闭环标签。若 issue 当前无 assignee，它不再证明 issue 仍在 pool 中；roadmap-intake 不把它当作可信跳过条件。

---

### 2. orchestra-governed（池内层闭环）

**谁打**：assignee-pool
**何时打**：完成普通 pool 决策后（rfc、epic、ready、close）。高置信度 close 直接关闭；低置信度打 `roadmap/rfc` 交人类，不把 close 建议留给 manager 反复判断。

**语义**："已决策，不再重复检查"。它不能替代 issue close，也不能用于 completed epic 的半闭环；completed epic 应直接关闭。

**命令**：
```bash
gh issue edit <issue-number> --add-label "orchestra-governed"
```

**颜色**：9933FF（蓝紫色）

**过滤逻辑**：
```
pool 扫描 -> 跳过有 orchestra-governed 的 issue
pool 扫描 -> 跳过无 assignee 的 issue（不在 pool 中，由 intake 负责）
```

---

### 3. roadmap-reviewed（审查层闭环）

**谁打**：vibe-roadmap
**何时打**：写完 `[roadmap decision]` 评论后，**但 decision 不是 `rfc` 时**
**不打的情况**：decision 是 `rfc` 时——rfc 表示需要人类决策，未完成决策闭环

**语义**："已审查，下次 Step 0 跳过"

**与 `roadmap/rfc` 的互斥规则**：
- `roadmap/rfc` 和 `roadmap-reviewed` **不能共存**
- 带 `roadmap/rfc` 的 issue 表示"未完成决策"，不应打 `roadmap-reviewed`
- 人类移除 `roadmap/rfc` 后，下次 roadmap 扫描会重新捡起该 issue，完成审查后打 `roadmap-reviewed`

**命令**：
```bash
gh issue edit <issue-number> --add-label "roadmap-reviewed"
```

**过滤逻辑**：
```
Step 0 搜索 -> 过滤掉有 roadmap-reviewed 的 issue
Step 0 搜索 -> 过滤掉有 roadmap/rfc 的 issue（等待人类决策）
```

**颜色**：CC99FF（淡紫色）

---

## 三级审查框架

### Level 1: 基础条件

- 问题边界明确、验收口径清楚、无需额外产品讨论
- 改动范围可控、依赖关系简单
- 允许存在若干实现选项；只要目标清楚、边界稳定、可由 manager 在执行中收敛，就不算人类阻塞

### Level 2: 架构一致性

- 依赖的模块/函数仍存在
- 引用的 API 未废弃
- 涉及的配置/架构未变更
- 有明确的代码执行路径
- **依赖项状态已验证**：issue body/comments 中声明的依赖项（如 "Depends on #N"）必须通过 GitHub API 验证实际状态（`state` + `labels`），不可仅凭 governance suggest 的描述或 issue body 中的自然语言声明判断"依赖已解除"。验证标准：依赖 issue 的 GitHub state 为 CLOSED，或带有 `state/done` / `state/merge-ready` 标签，或有已合并的 PR

### Level 3: 生命周期检查

- Issue 未过时（非依赖已移除）
- 非重复已关闭 issue
- 不需要先关闭其他依赖 issue

---

## 反模式 Issue 识别标准

### 定义

反模式 issue 指看似符合治理规范但实际不应纳入开发的问题，特征如下：

1. **无明确痛点**：缺少具体使用场景、缺少真实用户反馈、无法回答"谁在什么场景下遇到什么困难"
2. **高复杂度低 ROI**：改动范围大（跨模块/重构级）但收益模糊或仅解决边缘场景
3. **与现有能力重叠**：已有 CI/skill 可解决但未验证现有能力是否真的无法满足
4. **违反项目原则**：违背最小正确改动、认知优先（SOUL.md）或最小变更、Skill-First、验证先于声称完成（CLAUDE.md）
5. **边缘场景驱动**：只为极少数场景服务，无通用价值或可由用户自行处理
6. **代码层补偿 Agent 行为错误**：问题真源在 agent 读的 prompt material（governance material / SKILL / role material），但 issue 提议在代码中写死检查规则或自动修复逻辑。违反 manager.md §代码层不补偿原则

### 评分规则

- 满足 **任意 2 条及以上** 即判定为反模式
- 每条特征需给出具体证据（如：缺少痛点描述的具体缺失项、违反原则的具体条款）
- 典型案例：#1757（高复杂度低 ROI + 违反最小变更原则）

### 各层处理方式

#### Intake 层（入口层）

- **动作**：skip + 打 `orchestra-scanned`
- **suggest 内容**：注明反模式原因及评分项（如："反模式：满足 #2 高复杂度低 ROI、#5 边缘场景驱动"）
- **边界**：intake 不执行 close，只做 skip 并注明原因，由 pool/roadmap 后续决策

#### Pool 层（入池前/池内决策层）

- **高置信度**（评分 >= 3 或证据充分）：直接 close + 打 `orchestra-governed`
- **低置信度**（评分 = 2 或证据不足）：打 `roadmap/rfc` 交人类或 roadmap 决策
- **边界**：pool 可执行 close，但需在 comment 中写明反模式评分理由

#### Roadmap 层（审查纠正层）

- **动作**：写 `[roadmap decision] close: 反模式 — <逐条评分理由>` + 打 `roadmap-reviewed` + close
- **格式**：
  ```text
  [roadmap decision] close: 反模式
  - #1: <是否满足 + 证据>
  - #2: <是否满足 + 证据>
  - ...
  评分: <总数> 条，判定为反模式
  ```
- **边界**：roadmap 是反模式检查的最终决策者，close 动作遵循 Comment Marker Contract

---

## Comment Marker Contract

### 角色定位

vibe-roadmap 是治理-决策双轨中的**决策者**，不是 observer。marker 必须明确区分：

| 角色 | Marker | 性质 |
|---|---|---|
| roadmap-intake / assignee-pool（observer） | `[governance suggest][roadmap-intake]` / `[governance suggest][assignee-pool]` | 观察者意见，无强制力 |
| **vibe-roadmap（decider）** | `[roadmap decision]` | 决策者结论，覆盖 governance 建议 |

### 强制规则

1. vibe-roadmap 的**所有**决策动作必须写 `[roadmap decision] <动作>: <理由>` comment
2. **禁止** vibe-roadmap 写 `[governance suggest]`（marker 必须区分 observer / decider）
3. `[roadmap decision]` marker 同时作为 cron-supervisor / 下次 vibe-roadmap 自身判断"上次审查时间"的锚点
4. **自动打 `roadmap-reviewed` 标签**：
   - 写完 `[roadmap decision]` 评论后，如果 decision 不是 `rfc`，**必须**打 `roadmap-reviewed` 标签
   - 如果 decision 是 `rfc`，**不打** `roadmap-reviewed`（保留 `roadmap/rfc` 标签等待人类决策）
   - 目的：标记已决策，避免 Step 0 重复扫描
   - 命令：`gh issue edit <number> --add-label "roadmap-reviewed"`
5. 格式：
   ```text
   [roadmap decision] <动作动词>: <简要理由>
   ```
   动作动词统一使用：`split`, `continue`, `close`, `hold`, `rfc`, `assign`, `unblock`

### 示例

```
[roadmap decision] split epic into #42, #43, #44; reason: 3 modules, ~800 LOC, exceeds single-iteration threshold.
[roadmap decision] continue #78; reason: bounded to one module and manager can plan within the existing issue.
[roadmap decision] close #99; reason: dependency removed in #123, API deprecated.
[roadmap decision] hold #55 until #56 completes; reason: #56 provides core infrastructure #55 depends on.
[roadmap decision] rfc #77; reason: needs human decision on architecture direction.
```

---

## 各层职责边界

### Roadmap Intake（入口层）

**决策范围**：**只决定 accept（分配 assignee）或 skip（打 scanned）**
**检查**：生命周期、依赖、API、模块（含 Level 0：`.claude/`/`.codex/` 目录机械检查）
**输出**：`[governance suggest][roadmap-intake]` 建议纳入或跳过，附带原因
**标签**：不设 `roadmap/*`、`priority/*` 标签。**唯一例外**——Level 0 机械阻塞 skip 时直接打 `roadmap/rfc`：这是路由一个确定性硬阻塞（diff 是否碰 `.claude/`/`.codex/`，yes/no 机械可判），不是 intake 自称 decider。理由：Level 0 issue 无 assignee，pool 永远扫不到；只有 intake 打 `roadmap/rfc` 才能命中 task-status Rule 1 被 `/vibe-task` surface（否则落入 Rule 4 永久隐藏）。
**边界**：intake 不自称 decider；除 Level 0 机械例外外，跳过原因写在 suggest 中，由 pool 或 roadmap 做进一步决策

### Assignee Pool（池内决策层）

**决策范围**：`roadmap/*`(rfc/epic/p0/p1/p2)、`priority/*`、close（明确冲突/重复/已完成）、`roadmap/rfc`（低置信度或不确定）、resume（明确可恢复）、split（清晰分界）
**标签**：普通决策完成后打 `orchestra-governed`；completed epic 直接 close，不依赖 `orchestra-governed` 防重复
**边界**：pool 是入池前/池内准入 decider；manager 是入池后的执行 decider。pool 不把低置信度判断交给 manager 循环复核，而是 `roadmap/rfc` 交人类。

### Vibe Roadmap（审查纠正层）

**审查范围**：`roadmap/rfc`、`state/blocked`、未 reviewed 的 issue
**权限**：可覆盖 pool 的决策（rfc → continue、epic → split 等）
**标签**：审查完打 `roadmap-reviewed`，写 memory.md

### Vibe Task（人机协作规划辅助）

**职责**：human-facing skill，帮助人类处理 blocked/RFC/epic 问题类 issue，整理依赖关系，监控 epic 进度
**操作权限**：
- ✅ 读取 issue/flow/task 现场信息
- ✅ 在 issue body 正文中用自然语言说明依赖关系（"Blocked by #N", "Depends on #N"）
- ✅ 添加 `roadmap/*`、`priority/*` 规划类 labels
- ❌ 不操作 `state/*` 标签（blocked/ready/handoff 等均不允许）
- ❌ 不直接写 managed section（`<!-- vibe3-flow-state-start -->` 块）
- ❌ 不调用 `vibe3 flow blocked / flow bind` 命令（需要 flow context，pre-flow 阶段不存在）
**与 governance 层的边界**：vibe-task 是人类规划阶段的辅助工具，不参与自动化 governance 循环；它写入的依赖说明由 manager 入场后转化为正式 flow_issue_links

---

## Pre-flow Dependency Rules

**适用范围**：所有在 pre-flow 阶段操作的角色（vibe-task、vibe-roadmap、roadmap-intake、assignee-pool）

pre-flow 阶段指 issue 尚未进入执行池、无 branch、无 flow context 的状态。此阶段的核心约束：

**Allowed**:
- issue body 中用自然语言说明依赖关系：`Blocked by #N`、`Depends on #N`、`依赖 #N 完成后推进`
- 添加 `roadmap/*`、`priority/*` 等规划类 labels

**Forbidden**:
- ❌ 直接添加 `state/blocked` 标签
- ❌ 直接写 managed section（`<!-- vibe3-flow-state-start --> ... <!-- vibe3-flow-state-end -->` 块中的 `Blocked by:`/`Dependencies:` 等结构化字段）
- ❌ 调用 `vibe3 flow blocked`、`vibe3 flow bind` 命令

**理由**：
1. pre-flow 阶段无 flow context，`flow blocked / flow bind` 命令需要 branch 存在才能执行
2. 直接添加 `state/blocked` 标签而不写 managed section，会导致三源（label/body/local cache）不一致，orchestra dispatcher 无法正确识别和清除
3. 依赖关系的正式注册（写入 managed section + flow_issue_links）由 **manager 入场后**通过 `vibe3 flow blocked --task <N>` 完成；pre-flow 只需写清楚依赖关系的自然语言描述即可

**Manager 的衔接职责**：manager 入场时须读取 issue body 中的依赖声明，与 flow_issue_links 比对，补全未注册的依赖。

---

## 引用指南

各治理文件应引用本文档，而不是重复定义：

```markdown
三层架构、标签语义和三级审查框架详见 [roadmap-common.md](../roadmap-common.md)。
```

各文件只保留自身特有的执行逻辑和决策规则。
