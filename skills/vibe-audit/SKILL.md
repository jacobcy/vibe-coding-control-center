---
name: vibe-audit
description: Use when evaluating whether a project should continue, be refactored, rebuilt, forked, or abandoned — for both own projects and external/third-party codebases
metadata:
  category: discipline
  triggers: evaluate, audit, refactor-or-rebuild, fork-or-build, architecture review,
    code quality, should I use this, is this worth it, project evaluation
---

# Architecture Audit

Project-level viability assessment. NOT code review (style/linting), NOT security audit.

Answers one question: **What should we do with this codebase?**

Two tracks depending on ownership:
- **Track A (自有项目):** Refactor vs Rebuild → produce execution plan
- **Track B (外部项目):** Use / Fork / Extract / Trash → produce adoption plan

Behavioral rules (anti-sycophancy, language, session discipline) are in `~/.agents/AGENTS.md`. This skill does not repeat them.

---

## When to Use

- Evaluating whether your own project's architecture holds up
- Deciding whether to adopt, fork, or ignore a third-party project
- Before committing significant effort to any codebase
- When "sunk cost" pressure is influencing decisions
- Project feels like it's growing without converging

## Execution Flow

```
1. Determine Track (A or B)
2. Quick Scan (5 min, automated, no interaction)
3. Deep Audit (on request, 11 dimensions)
4. Decision + Asset Extraction
5. Output Plan to ~/.agents/plans/
```

---

## Step 1: Determine Track

| Signal | Track |
|---|---|
| "我们的项目"、"这个项目要不要重构" | A — 自有项目 |
| "这个库好不好用"、"要不要 fork"、"评估一下这个开源项目" | B — 外部项目 |
| 不确定 | 问用户 |

---

## Step 2: Quick Scan

Automated. No interaction. Both tracks共用。

**执行步骤:**

1. **读项目身份文件** — README, AGENTS.md, CLAUDE.md, CONTEXT.md（取最先找到的 2-3 个）
2. **度量代码规模** — `find src/ lib/ -name '*.py' -o -name '*.ts' -o -name '*.js' | xargs wc -l`，按目录汇总
3. **扫目录结构** — 层级深度、文件数量、命名一致性
4. **读最大的 3 个源文件** — 判断代码密度和风格
5. **检查 git 活跃度**（如可用）— `git log --oneline --since="6 months ago" | wc -l`，最近贡献者数量
6. **检查依赖文件** — requirements.txt / package.json / go.mod，数依赖数量和版本锁定情况

**Quick Scan 输出格式:**

```
## 基本指标
- 总行数: [X] 行（src/ [Y] 行，tests/ [Z] 行）
- 文件数: [N]
- 依赖数: [M]
- Git 活跃度: [近6月 commits] / [贡献者数]
- 最大文件: [file] ([lines] 行)

## 一句话裁决
[EMOJI] [verdict]

## 三大问题
1. [issue 1]
2. [issue 2]
3. [issue 3]

## 初步建议: [Track A 裁决 or Track B 裁决]
```

---

## Step 3: Deep Audit (按需)

用户确认需要深入分析后执行。逐维度打分。

### 校准基准（MANDATORY FIRST STEP）

> "一个合格工程师从零实现同样功能，大约需要多少行代码？"

没有这个基准，后续所有判断都是直觉，不是工程分析。

### 审计维度

| # | 维度 | 核心问题 | 评级 |
|---|---|---|---|
| 1 | **技术选型** | 语言/框架是否匹配问题规模？换个人会选同样的栈吗？ | 🟢🟡🔴 |
| 2 | **目标偏离** | 文档说的 vs 代码做的，偏离度百分比。>30% 红灯 | 🟢🟡🔴 |
| 3 | **过度工程** | 解决了项目不存在的问题的抽象层有几个？ | 🟢🟡🔴 |
| 4 | **价值密度** | 核心业务逻辑行数 / 总行数。<10% = 全是脚手架 | 🟢🟡🔴 |
| 5 | **文档一致性** | README 承诺的功能，代码实际实现了多少？ | 🟢🟡🔴 |
| 6 | **死代码率** | 没有调用者的函数/模块占比。>20% 红灯 | 🟢🟡🔴 |
| 7 | **依赖健康** | 造轮子 vs 过度依赖的平衡。有无脆弱的自制解析器？ | 🟢🟡🔴 |
| 8 | **测试质量** | 测试在验证行为还是凑覆盖率？ | 🟢🟡🔴 |
| 9 | **复杂度趋势** | git 历史显示收敛还是发散？文件变更频率？ | 🟢🟡🔴 |

---

## Step 4: Decision

### Track A — 自有项目决策矩阵

```
┌──────────────┬──────────────────────────────────────────────────────────┐
│ 裁决          │ 触发条件                                                │
├──────────────┼──────────────────────────────────────────────────────────┤
│ ✅ 继续       │ 膨胀 <2x，偏离 <20%，无致命缺陷                         │
│ ⚠️ 瘦身      │ 膨胀 2-3x，死代码 <15%，核心可用，可定点清除              │
│ 🔧 Fork 改写  │ 核心逻辑可用但分发/接口有问题，改外壳不改引擎             │
│ 🔄 重构       │ 技术选型正确但实现混乱，膨胀 2-4x                        │
│ ❌ 推倒重来   │ 膨胀 >5x，或死代码 >20%，或偏离 >30%                    │
│ 🪦 放弃       │ 问题本身不值得解决，或市场上已有成熟方案                  │
└──────────────┴──────────────────────────────────────────────────────────┘
```

### Track B — 外部项目决策矩阵

```
┌──────────────┬──────────────────────────────────────────────────────────┐
│ 裁决          │ 触发条件                                                │
├──────────────┼──────────────────────────────────────────────────────────┤
│ ✅ 直接使用   │ 活跃维护，API 稳定，文档完善，满足 >80% 需求             │
│ 🔧 Fork 改造  │ 核心好用但缺关键功能/有设计缺陷，维护者不活跃或方向不同  │
│ 📦 提取逻辑   │ 整体不可用但有 1-3 个模块/算法值得复用（标注具体文件行号）│
│ 🪦 代码垃圾   │ 膨胀 >5x，无测试，依赖过时，或核心逻辑本身有缺陷        │
└──────────────┴──────────────────────────────────────────────────────────┘
```

**Track B 额外评估项:**

| 项目 | 检查内容 |
|---|---|
| 维护状态 | 最近 commit 时间、issue 响应速度、release 频率 |
| 许可证 | MIT/Apache 可商用；GPL 传染性；无许可证 = 不可用 |
| API 稳定性 | 是否频繁破坏性变更，是否有 SemVer 纪律 |
| 社区信号 | Star/Fork 比、contributor 数、是否一人项目 |
| 替代方案 | 同类项目中是否有更好选择（必须列出对比） |

---

## Step 5: Asset Extraction（两个 Track 通用）

无论裁决是什么，都必须产出资产清单：

```markdown
## 值得保留的资产

### 可直接复用的文件
- [file] ([lines] 行): [reason]

### 可提取的核心逻辑
- [function/pattern] (~[lines] 行): [what it does]

### 值得保留的设计决策
- [decision]: [why correct]

### 必须丢弃的部分
- [module]: [why — 用数据，不用形容词]
```

---

## Step 6: Output Plan

审计是讨论 session，交付物必须是 plan 文件（见 `~/.agents/AGENTS.md` §3）。

**Plan 保存路径:** `~/.agents/plans/YYYY-MM-DD-audit-<project-slug>.md`

Plan 内容根据裁决不同：

### 裁决 = 继续 / 直接使用

不需要 plan。在回复中给出结论和使用注意事项即可。

### 裁决 = 瘦身

```markdown
# [project] 瘦身计划

## 目标
从 [X] 行减至 ~[Y] 行，保留核心功能 [list]。

## 删除清单（按依赖顺序）
1. 删 [file/module] ([lines] 行) — [reason]
2. 删 [file/module] ([lines] 行) — [reason]
...

## 风险点
- 删 [A] 后 [B] 会断，需要 [fix]

## 验证
- 每步删完跑 [test command]
- 最终验证: [end-to-end command]
```

### 裁决 = Fork 改写

```markdown
# [project] Fork 改写计划

## 目标
在现有代码上改 [分发机制/接口/配置]，核心逻辑零修改。

## 不动的部分
- [module]: [why keep, lines]

## 要改的部分
1. [Task]: 新增/替换 [file] — [what and why]
2. [Task]: 删除 [file] — [reason]
...

## 删除的部分
- [duplicate/dead code] — [lines saved]

## 净变化
+[X] 行, -[Y] 行
```

### 裁决 = 推倒重来

```markdown
# [project] 重建计划

## 重建目标
一句话: [what the rebuilt project should be]

## 从旧项目提取的资产
[asset extraction list, copy-paste ready]

## 约束（防止重蹈覆辙）
1. [constraint]
2. [constraint]
3. [constraint]

## 目标文件结构
[tree, 10-15 files max]

## 实施 Task
[standard task-by-task plan per ~/.agents/skills/writing-plans/]
```

### 裁决 = 提取逻辑

```markdown
# 从 [project] 提取逻辑

## 提取清单
1. [file:L10-L85] → 复制到 [destination] — [what it does]
2. [file:L100-L200] → 改造后用于 [purpose] — [adaptation needed]

## 依赖处理
- 提取的代码依赖 [lib]，需要 [install command]
- [internal dependency] 需要一并提取或替换

## 验证
- 提取后运行 [test]
```

### 裁决 = 代码垃圾 / 放弃

不需要 plan。在回复中给出结论和替代方案建议。

---

## Vibe Coding Economics

传统假设：重建成本 >> 瘦身成本。AI 辅助开发下，**等式反转**。

- **瘦身**: 需要理解每行死代码为什么存在、删后有无副作用 → O(n) 认知成本
- **重建**: 目标已明确、核心逻辑已提炼、AI 加速 → O(1) 执行成本，通常 30min-2h

**判定规则:** 膨胀 >5x 时，瘦身的认知负担（理解数千行垃圾）> 重建的执行成本（写几百行新代码）。此时瘦身是浪费不是节约。

但反过来，膨胀 <3x、核心可用时，重建是浪费——你在重写已经能用的代码。不要因为"重建很酷"而重建。

---

## Agent Self-Check

发现自己有以下行为时立即停止并重写：

- 膨胀 >5x 时建议瘦身（保守偏误）
- 膨胀 <2x 时建议重建（破坏偏误）
- 用"可能"、"也许"、"取决于"代替具体数据
- 评估外部项目时只看 Star 数不读代码
- 跳过校准基准直接给裁决
- 产出报告而非 plan（违反 session 规则）
- 替用户做最终决定——你提供数据和选项，用户决定

## NOT in Scope

- 代码风格审查（交给 linter）
- 安全漏洞扫描（交给安全工具）
- 在审计 session 中写实现代码（审计产出 plan，执行交给新 session）
