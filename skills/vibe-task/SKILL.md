---
name: vibe-task
description: Use for handling blocked and RFC issues, making decisions that may form ADRs (Architecture Decision Records). Processes problem issues requiring human judgment, dependency resolution, and architectural decisions. Do not use for routine issue monitoring (use vibe-orchestra) or roadmap planning (use vibe-roadmap).
---

# /vibe-task - Problem Issues & ADR Entry Point

**问题 issue 处理与架构决策入口**，辅助人类处理 RFC、blocked、epic issues，形成架构决策记录（ADR）。

## 权限模型（强制执行）

每一步操作标注了所需的权限级别。Agent **不得**越权执行需要人类确认的操作。

| 标记 | 含义 | Agent 允许的操作 |
|------|------|-----------------|
| `[Agent]` | Agent 可自主执行 | 只读查询、纯信息展示 |
| `[人类确认]` | 必须经人类确认 | **禁止**自主执行写操作（改 label、写 RFC decision comment、重建 flow） |

**伪代码流程**：
```
vibe-task 入口
├── [Agent]      Step 0: 防止重复评论检查
├── [Agent]      Step 1: 运行 vibe3 task status（只读）
├── [Agent]      Step 2: RFC 分析 + vibe3 task show（只读）
│   ├── [人类确认]  Step 2.2: 展示 RFC 摘要 + 建议方案 → 等待人类选择
│   └── [Agent]       Step 2.3: 按人类选择执行（写 comment、改 label）
├── [Agent]      Step 3: Blocked 分析 + vibe3 task show（只读）
│   ├── [Agent]      Step 3.1: PR merge 状态检查（只读）
│   └── [Agent]       Step 3.2-3.3: 执行恢复（使用 vibe3 命令）
└── [Agent]      Step 4-5: Epic 梳理 + 汇总报告
```

**硬约束**：
- `[人类确认]` 步骤中，Agent **必须停下来**，展示分析结果和建议方案，等待人类明确回复后才能执行
- Agent **不得**在未获人类确认的情况下对 RFC issue 执行写操作（改 label、写 `[decision]` comment、关 issue）
- 唯一的写操作例外：Blocked issue 的恢复（Step 3）可由 Agent 自主执行，但必须严格使用 `vibe3` 命令

## 核心职责

1. **RFC 决策辅助**：分析 RFC issues，**向人类提出建议**，由人类做出决策
2. **ADR 形成**：架构级 RFC 结晶为 Architecture Decision Records
3. **Blocked 恢复**：检查现场后选择合适的恢复方案
4. **依赖梳理**：构建 epic/blocked_by 依赖关系图

## 核心原则

- **展示而非决定**：RFC 问题必须向人类展示分析结果和建议，由人类做最终决策
- **先读后写**：写 comment 前必须先用 `vibe3 task show <N>` 查看已有评论，避免重复
- **用 vibe3 命令而非直接操作 GitHub**：state/ 标签的修改必须通过 `vibe3 task resume`、`vibe3 flow rebuild` 等命令，**禁止**用 `gh issue edit` 直接操作 state/ 标签
- **基于真源**：所有信息以 `vibe3 task show` 输出为准
- **检查实际状态**：恢复 blocked 前必须检查 PR merge 状态、worktree 状态等实际现场

## Scope

**只看三类 issue**：

1. **RFC issues** (`roadmap/rfc` label)
   - 需要人类讨论的 issue
   - 目标不明确或需要架构决策

2. **Blocked issues** (`state/blocked` label)
   - 有依赖阻塞的 issue
   - 需要解除阻塞才能继续

3. **Epic issues** (`roadmap/epic` label)
   - scope 过大、需要先拆分的 issue
   - 不可直接执行，需 split 成子 issues
   - 依赖图节点：影响多个 downstream issues 的调度

**不看**：
- 正常运行的 issue（由 `vibe-orchestra` 管理）
- 版本规划（由 `vibe-roadmap` 管理）

## Workflow

### Step 0: 防止重复评论检查 `[Agent]`

**在写任何 comment 之前，必须先检查是否已有同类评论。**

```bash
# 对即将处理的每个 issue，检查已有评论
gh issue view <N> --comments --limit 50 | grep -E "\[decision\]|\[vibe-task\]"
```

```
IF 已有 "[decision]" 标记:
    SKIP 此 RFC issue（已有决策，不重复写入）

IF 已有 "[vibe-task]" 标记（来自同一 session）:
    SKIP 此 issue（已有处理记录，不重复写入）
```

### Step 1: 查看全局状态 `[Agent]`

```bash
vibe3 task status
```

从输出中提取三类 issue 的分布概况，**不急于逐项深入**。先建立全局视图。

### Step 2: 处理 RFC Issues `⚠️ [人类确认]`

**强制约束**：
- 每次只处理一个 RFC issue，**禁止批量处理**
- 发布 `[decision]` comment 前，**必须先向人类汇报分析结果和建议方案**
- **必须等待人类明确回复**后才能执行任何写操作（改 label、写 comment）

对每个 `roadmap/rfc` issue，**必须先分析再向人类展示，获得确认后才能执行**。

#### 2.1 读取 RFC 详情 `[Agent]`

```bash
# 使用 vibe3 task show 查看 issue 全貌（含已有评论、PR、audit）
# 如果有本地 flow，vibe3 task show 会展示 Recent Comments
vibe3 task show <N> --full

# 补充：如果 vibe3 task show 无法使用（无本地 flow），降级为：
gh issue view <N> --comments
```

**检查清单**：
- [ ] 查看已有评论：是否有 `[decision]` 标记？是否有 `[roadmap decision]`？
- [ ] 查看是否有已有的 `[governance suggest]` 评论
- [ ] 查看 issue body 中的依赖声明
- [ ] 读取 `docs/decisions/INDEX.md` 中相关 `accepted` ADR

**如果已有 `[decision]` 标记**：跳过此 RFC，不重复决策。

#### 2.2 向人类展示分析结果 `[人类确认]` ← 关键步骤

**强制流程**：
1. 分析 RFC 内容和相关代码（Read → Grep → Analyze）
2. 向人类汇报分析结果和建议方案
3. **等待人类明确回复**"采纳 A"、"选 B"等确认词
4. 收到确认后才执行对应操作（写 comment、改 label）

**正确示例**：
```
✅ 正确：
→ 我: 读取 RFC #123 内容和相关 ADR
     检查已有评论（无 [decision] 标记）
     分析问题：标题、问题描述、现有评论、相关 ADR
     汇报："=== RFC #123 分析 ===
            标题: ...
            问题: ...
            建议方案: A（采纳并推进）
            理由: ..."
     明确询问："请选择 A/B/C，或提供其他指示"
→ 用户: "选 A"
→ 我: 执行方案 A（写 comment、改 label）
```

**违规示例**：
```
❌ 错误：直接执行不等待确认
→ 我: "分析完成，建议选 A，现在执行..."
→ 用户: (未有机会确认，操作已完成)

❌ 错误：批量处理多个 RFC
→ 我: "分析完 RFC #123、#124、#125，建议分别为 A/B/C，开始执行..."
→ 用户: (无法逐个确认)

❌ 错误：跳过分析直接问
→ 我: "RFC #123 怎么处理？选 A/B/C？"
→ 用户: (未获分析结果，无法判断)
```

**向人类展示**以下内容，**不要直接执行**：

```text
=== RFC #<N> 分析 ===

标题: <title>
问题: <1-2 句话总结 RFC 要解决的问题>
现有评论: 共 <M> 条，最近一条来自 <author>
相关 ADR: <有/无，若有列出编号>

建议方案: <方案 1/2/3>
理由: <1-2 句话>
是否需要 ADR: <是/否>

可选动作:
  A: 采纳并推进（移除 roadmap/rfc，设为 state/ready）
  B: 转为依赖等待（保留 roadmap/rfc，设为 state/blocked）
  C: 推迟或关闭

请选择 A/B/C，或提供其他指示。
```

**Agent 必须等待人类回复**明确选择后才能执行 Step 2.3。**禁止**在未获人类确认的情况下自行决定并执行 RFC 处置。

#### 2.3 执行人类决策 `[Agent]`

**仅当人类已明确选择后**，才执行对应操作：

**人类选 A — 采纳并推进**：
```bash
gh issue comment <N> --body "[decision] 采纳并推进；[reason] <理由>"
gh issue edit <N> --remove-label roadmap/rfc --add-label state/ready
```

**人类选 B — 转为依赖等待**：
```bash
gh issue comment <N> --body "[decision] 转为依赖等待；[reason] 需要 #<M> 完成后再讨论；[blocked_by] #<M>"
gh issue edit <N> --add-label state/blocked
```

**人类选 C — 推迟或关闭**：
```bash
gh issue comment <N> --body "[decision] 推迟处理；[reason] <理由>"
# 保留 roadmap/rfc label，状态不变
```

**ADR 结晶规则**（仅人类选 A 且满足以下全部三条时推动 ADR PR）：
1. 跨任务/跨模块的架构选型
2. 有真实权衡或反直觉
3. 期望跨 PR/issue 长期有效

满足时：在 comment 中指向 ADR PR，不将 ADR 文件和实现改动混在一个 PR 中。

#### 2.4 验证决策已落地 `[Agent]`

```bash
gh issue view <N> --comments | grep "\[decision\]"
```

验证通过后才处理下一个 RFC。

### Step 3: 处理 Blocked Issues `[Agent]`

对每个 `state/blocked` issue，**必须先检查现场**，再选择恢复方案。

#### 3.1 检查现场 `[Agent]`

```bash
# 查看 flow 和 issue 全貌（含已有评论、PR、audit、Recent Comments）
vibe3 task show <N> --full
```

从 `vibe3 task show` 输出中提取关键字段：

| 字段 | 含义 | 判断要点 |
|------|------|---------|
| `PR:` | PR 编号和状态 | `open` → 仍在审查；`merged` → 已合并 |
| `Verdict:` | PASS/FAIL | PASS → 审查已通过 |
| `Blocked Reason:` | 阻塞原因 | 分类依据（见下文） |
| `Recent Comments` | 最近评论 | 检查是否已有 `[vibe-task]` 处理记录 |
| `Latest Work` | 最近产出 | audit/plan/report 是否存在 |

**已有处理记录检查**：
```bash
gh issue view <N> --comments --limit 50 | grep "\[vibe-task\]"
```
如果已存在属于当前 session 的记录 → 跳过此 issue，不重复处理。

**PR merge 状态检查**（关键步骤）：
```bash
# 如果 vibe3 task show 显示有 PR，必须验证是否已 merge
gh pr view <PR_NUMBER> --json state,mergedAt
```

#### 3.2 选择恢复方案 `[Agent]`

根据现场检查结果，选择**仅以下三种方案之一**。

```
IF    pr_ref 存在 AND gh pr view 返回 MERGED:
    → 方案 3: vibe3 task resume <N> --label auto --yes
      （PR 已合并，自动推断为 state/done）

ELIF pr_ref 存在 AND gh pr view 返回 OPEN:
    → 方案 3: vibe3 task resume <N> --label auto --yes
      （有有效 PR 产出，保留 worktree）

ELIF audit_ref 或 report_ref 存在（有产出但无 PR）:
    → 方案 1: vibe3 task resume <N> --yes
      （有有效产出，保留 worktree，清除 blocked_reason）

ELIF blocked_reason 含 "Scope baseline violation":
    → 方案 2: vibe3 flow rebuild <N> --yes
      （分支状态不正确，需要从 main 重建）

ELIF blocked_reason 含 "state unchanged" AND 无 PR AND 无 audit:
    → 方案 2: vibe3 flow rebuild <N> --yes
      （state unchanged 通常意味着无法自动推进，重建）

ELIF flow 不存在（vibe3 task show 显示 "no flow scene"）:
    → 标记为 "需要先 intake 以创建本地 flow"
      （不执行恢复，等待 human intake）

ELSE:
    → 方案 1: vibe3 task resume <N> --yes
      （默认：恢复阻塞状态，保留 worktree）
```

#### 3.3 执行恢复 `[Agent]`

```bash
# 方案 1: 恢复阻塞状态（保留 worktree 和分支）
vibe3 task resume <N> --yes

# 方案 2: 完全重建（删除 worktree 和分支，从 main 重建）
vibe3 flow rebuild <N> --yes

# 方案 3: 移除阻塞恢复（保留 worktree，自动推断状态）
vibe3 task resume <N> --label auto --yes
```

**禁止**：以下操作**一律不得使用**：
- ❌ `gh issue edit <N> --remove-label state/blocked` — 直接移除标签无法解除三源（label/body/cache）的 blocked 状态，**flow 仍然是 blocked**
- ❌ `gh issue edit <N> --add-label state/ready` — 同上，label 改了但 flow state 不变
- ❌ `gh issue edit <N> --add-label state/done` — 同上
- ❌ 任何绕过 `vibe3` 命令直接操作 state/ 标签的行为

#### 3.4 验证恢复结果 `[Agent]`

```bash
# 确认 label 已正确更新
gh issue view <N> --json labels --jq '.labels[].name' | grep "^state/"

# 确认 flow 状态已恢复
vibe3 flow show <N> 2>/dev/null || echo "无本地 flow"
```

### Step 4: 处理 Epic Issues（依赖图梳理）`[Agent]`

#### 4.1 读取 epic 详情

```bash
vibe3 task show <N> --full
```

查看 epic issue body 中的子 issue 列表。

#### 4.2 检查子 issues 状态

确认：
- 子 issues 是否已创建
- 子 issues 的依赖关系是否明确
- 子 issues 的状态（ready/claimed/in-progress/blocked）

#### 4.3 检查 epic 完整性

**如果 epic body 缺少子 issue 列表**：
- 通过 comments 或交叉引用查找已创建的子 issues
- 更新 epic body 添加子 issue 列表

**如果 epic 尚未拆分**：
```bash
gh issue comment <N> --body "[epic] 建议调用 /roadmap 触发拆分流程"
```

#### 4.4 构建依赖图

基于 epic 及其子 issues，构建依赖关系：
- epic → 子 issues（split 产出的依赖关系）
- 子 issues 间的依赖关系
- 识别关键路径和阻塞点

### Step 5: 输出汇总报告 `[Agent]`

总结三类 issue 的处理结果：

```text
RFC & Blocked & Epic Issues 处理报告

RFC Issues（已逐项向人类展示）
- #123: [人类选 A] 采纳并推进
- #124: [等待人类决策] 已展示分析，等待选择

Blocked Issues（已按方案处理）
- #456: 方案 3（保留 worktree，已有 PR 产出，PR 已 MERGED）
- #457: 方案 2（Scope baseline violation，从 main 重建）
- #458: 方案 1（有 audit 产出，保留 worktree）

Epic Issues（依赖图梳理）
- #789: 已拆分为 #790, #791, #792
  依赖关系: #789 → #790 → #791, #792
  关键路径: #789 → #790 → #791

依赖图总览
- RFC 已解决: #123 → 解锁 downstream issues
- Blocked 已处理: #456 恢复为 done
- 依赖链: #2698 (merge-ready) → #2699 → #2700

下一步建议
- RFC: 监控人类确认的执行情况
- Blocked: 跟踪恢复后的 issues 进度
- Epic: 关注关键路径上的 issues
```

## 与其他 Skills 的区别

- **vibe-task**: 看 RFC、blocked、epic issues（问题 issue）及依赖图
- **vibe-orchestra**: 管理 assignee issue pool（运行中的 issues）
- **vibe-roadmap**: 版本规划 + 治理审查（Layer 3：消化 governance suggest，纠正 pool 决策）

## Restrictions

- **必须逐项处理**：不允许一次扫描完就输出报告
- **RFC 必须经人类确认**：禁止 Agent 自主决定 RFC 的处置方案；必须展示分析并等待人类选择
- **Blocked 必须先检查现场**：检查 PR merge 状态、worktree 状态后才能选择方案
- **先读后写**：写 comment 前必须用 `vibe3 task show` 或 `gh issue view --comments` 检查已有评论
- **必须用 vibe3 命令**：禁止直接用 `gh issue edit` 操作 state/ 标签
- **不处理正常运行 issue**：由 `vibe-orchestra` 管理
- **不做版本规划建议**：由 `vibe-roadmap` 管理
- **不补充 CLI 未提供的字段**：基于真源，只读 shell 输出

## 禁止行为清单

| 禁止行为 | 说明 | 正确做法 |
|---------|------|---------|
| `gh issue edit <N> --remove-label state/blocked` | 直接移除标签无法解除三源 blocked 状态，flow 仍然是 blocked | `vibe3 task resume <N> --label auto --yes` |
| `gh issue edit <N> --add-label state/ready` | label 改了但 flow state 和 body projection 不变，造成三源不一致 | `vibe3 task resume <N> --yes` |
| `gh issue edit <N> --add-label state/done` | 同上，不经过三源同步 | `vibe3 task resume <N> --label auto --yes` |
| 未用 `vibe3 task show` 查看已有评论就写 comment | 造成评论污染、重复写入同类内容 | 先用 `vibe3 task show <N> --full` 查看 Recent Comments |
| RFC 不向人类展示就执行决策 | 让 RFC 失去讨论意义 | Step 2.2 展示分析 + 等待人类确认 |
| 恢复 blocked 不检查 PR merge 状态 | 可能对已合并的 PR 做错误恢复 | Step 3.1 执行 `gh pr view <N> --json state,mergedAt` |
| 凭 blocked_reason 文本直接判断不做现场检查 | 描述可能过时，不看实际代码/PR 状态 | Step 3.1 多项现场检查（vibe3 task show + gh pr view） |

## Pre-flow Dependency Rules

> 完整规范见 [roadmap-common.md § Pre-flow Dependency Rules](../supervisor/roadmap-common.md)

vibe-task 在 pre-flow 阶段（issue 无 flow/branch context）的约束：

- ✅ 在 issue body 正文中用自然语言说明依赖：`Blocked by #N`、`Depends on #N`
- ✅ 添加 `roadmap/*`、`priority/*` 规划类 labels
- ❌ 禁止直接添加 `state/blocked` 标签 — pre-flow 无法保证三源（label/body/cache）原子写入，会导致 dispatcher 无法识别
- ❌ 禁止直接写 managed section（`Blocked by:` / `Dependencies:` 结构化字段）
- ❌ 禁止调用 `vibe3 flow blocked / flow bind` — 这两个命令需要 branch 存在

依赖的正式注册（写入 managed section + flow_issue_links）由 manager 入场后完成；pre-flow 只负责把依赖关系说清楚。
