---
name: vibe-task
description: Use when the user wants to inspect RFC, blocked, or epic issues, check dependency chains, or assess milestone readiness. Do not use for roadmap prioritization or issue pool governance.
---

# /vibe-task - RFC / Blocked / Epic 检查与依赖图编排

检查项目中的 RFC、blocked、epic issues 状态，并梳理三类 issue 间的依赖关系。

## 核心原则

- **专注问题 issue**：RFC、blocked、epic
- **基于真源**：只读 shell 输出，不补充字段
- **依赖优先**：梳理依赖链，给出 milestone 可进性判断

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

**依赖图编排**（三类 issue 间的依赖关系）：
- epic → 子 issues（split 产出的依赖关系）
- blocked_by 链（A depends on B depends on C）
- milestone 可进性：某 milestone 是否所有 blocker 已解除

**不看**：
- 正常运行的 issue（由 `vibe-orchestra` 管理）
- 版本规划（由 `vibe-roadmap` 管理）

## Workflow

### Step 1: 运行 CLI

```bash
vibe3 task status
```

### Step 2: 处理 RFC Issues（逐项决策）

对每个 `roadmap/rfc` issue，按以下顺序执行：

**必须逐项处理，不可批量扫描后输出报告。**

#### 2.1 读取 issue 详情

```bash
gh issue view <N>
```

查看 issue 描述和已有 comments，理解 RFC 的具体问题。

**决策前先检查 `docs/decisions/INDEX.md` 中是否有相关 `accepted` ADR**。若有，决策不得违反既有 ADR；如需偏离，必须显式提议 supersede。

#### 2.2 做出决策（三选一）

**方案 1：采纳并推进**
- 移除 `roadmap/rfc` label
- 设置 `state/ready`（或 `state/claimed`）
- 在 comment 写入决策结论

```bash
gh issue comment <N> --body "[decision] 采纳并推进；[reason] <理由>"
gh issue edit <N> --remove-label roadmap/rfc --add-label state/ready
```

**架构级 rfc 结晶为 ADR**（三条全满足时）：
① 跨任务/跨模块的架构选型；② 有真实权衡或反直觉；③ 期望跨 PR/issue 长期有效。

满足时：在 `docs/decisions/INDEX.md` 预留号（`status: proposed`），决策 comment 改为：
```
gh issue comment <N> --body "[decision] 采纳并结晶为 ADR-NNNN；[reason] <理由>"
```
然后给 issue 设 `state/ready`，流入正常执行管线（vibe-new → 分支 → 写 ADR 文件 + 更新 INDEX → PR → 合并 → ADR 转 `accepted`）。

不满足时：维持原有 `[decision]` 评论流程，不产 ADR。

**方案 2：转为依赖等待**
- 明确依赖的 issue 或外部条件
- 保留 `roadmap/rfc` label
- 设置 `state/blocked` 并在 comment 中说明依赖关系

```bash
gh issue comment <N> --body "[decision] 转为依赖等待；[reason] 需要 #<M> 完成后再讨论；[blocked_by] #<M>"
gh issue edit <N> --add-label state/blocked
```

**方案 3：推迟或关闭**
- 在 comment 写入决策理由
- 保留 `roadmap/rfc` label
- 状态不变

```bash
gh issue comment <N> --body "[decision] 推迟处理；[reason] <理由>"
```

#### 2.3 验证决策已落地

决策写入后，验证 comment 是否成功：

```bash
gh issue view <N> --comments | grep "\[decision\]"
```

如果未找到决策标记，重新执行决策写入。

**不允许悬浮结论**：每个 RFC 必须有明确的决策和 action，不能只输出"需要讨论"而没有下一步。只有当前 RFC 决策验证通过后，才处理下一个。

### Step 3: 处理 Blocked Issues（二选一方案）

对每个 `state/blocked` issue，只允许两种操作：

**明确禁止发明中间方案。**

#### 3.1 检查 flow 状态

```bash
vibe3 task status
```

查看 flow 的 `pr_ref` 或 `audit_ref` 是否存在，判断是否有有效产出。

#### 3.2 选择处理方案

**方案 1：恢复阻塞状态**（适用于 agent 已产出有效工作的场景）

```bash
vibe3 task resume <N> --yes
```

效果：
- 保留 worktree 和分支
- 清除 blocked_reason
- 恢复到推断的状态（通常是 `state/ready` 或之前的状态）

**方案 2：完全重建**（适用于 worktree/分支已失效的场景）

```bash
vibe3 flow rebuild <N> --yes
```

效果：
- 删除 worktree 和分支
- 重建新的 worktree
- 清除 blocked_reason
- 恢复到 `state/ready`

**方案 3：移除阻塞恢复**（适用于 agent 已产出有效工作的场景）

```bash
vibe3 task resume <N> --label auto --yes
```

效果：
- 保留 worktree 和分支
- 清除 blocked_reason
- 自动推断状态（优先 review/merge-ready，否则 claimed）

#### 3.3 选择依据

- 如果 flow 的 `pr_ref` 或 `audit_ref` 存在 → 用方案 2（有产出值得保留）
- 如果 flow 已 stale 或无有效产出 → 用方案 1

**禁止选择性保留**：既不完全重置也不按标准方案恢复的操作。

### Step 4: 处理 Epic Issues（依赖图梳理）

对每个 `roadmap/epic` issue，执行依赖图梳理：

#### 4.1 读取 epic 详情

```bash
gh issue view <N>
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

### Step 5: 输出汇总报告

总结三类 issue 的处理结果：

```text
RFC & Blocked & Epic Issues 处理报告

RFC Issues（已逐项处理）
- #123: [decision] 采纳并推进；[reason] 架构方向已明确
- #124: [decision] 推迟处理；[reason] 需要更多技术调研

Blocked Issues（已按方案处理）
- #456: 方案 2 恢复（保留 worktree，已有 PR 产出）
- #457: 方案 1 重置（分支已 stale）

Epic Issues（依赖图梳理）
- #789: 已拆分为 #790, #791, #792
  依赖关系: #789 → #790 → #791, #792
  关键路径: #789 → #790 → #791

依赖图总览
- RFC 已解决: #123 → 解锁 downstream issues
- Blocked 已处理: #456 恢复为 in-progress
- Epic 关键路径: #789 → #790 → #791

下一步建议
- RFC: 监控决策执行情况
- Blocked: 跟踪恢复后的 issues 进度
- Epic: 关注关键路径上的 issues
```

## 与其他 Skills 的区别

- **vibe-task**: 看 RFC、blocked、epic issues（问题 issue）及依赖图
- **vibe-orchestra**: 管理 assignee issue pool（运行中的 issues）
- **vibe-roadmap**: 版本规划 + 治理审查（Layer 3：消化 governance suggest，纠正 pool 决策）

## Restrictions

- **必须逐项处理**：不允许一次扫描完就输出报告
- **RFC 必须落地**：每个 RFC 必须写入 issue comment，不允许悬浮结论
- **Blocked 二选一**：只允许"完全重置"或"移除阻塞恢复"，禁止发明中间方案
- **不处理正常运行 issue**：由 `vibe-orchestra` 管理
- **不做版本规划建议**：由 `vibe-roadmap` 管理
- **不做复杂审计或修复**：只处理 RFC、blocked、epic issues
- **不补充 CLI 未提供的字段**：基于真源，只读 shell 输出
