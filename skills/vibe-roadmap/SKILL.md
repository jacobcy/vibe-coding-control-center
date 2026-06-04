---
name: vibe-roadmap
description: Use when the user wants project-level roadmap planning, version goals, backlog triage, governance suggest review, or issue placement decisions. Triggered by "vibe roadmap", "/vibe-roadmap", "版本规划", "roadmap 审查", "消化 governance suggest", "下一个版本做什么", or "这个 issue 放哪一版". Do not use for assignee pool governance (use vibe-orchestra) or single-flow execution.
---

# /vibe-roadmap - 版本规划与治理审查

维护版本路线图，同时作为三层治理架构的 Layer 3 审查者，消化 pool 层的 `[governance suggest]` 并形成最终 `[roadmap decision]`。

三层架构、标签语义（orchestra-scanned / orchestra-governed / roadmap-reviewed）和三级审查框架（Level 1/2/3）见 [supervisor/roadmap-common.md](../../supervisor/roadmap-common.md)。

## 核心原则

- **审查纠正 governance 决策**：消化 assignee-pool 的 `[governance suggest]`，写 `[roadmap decision]`，打 `roadmap-reviewed`
- **GitHub-as-truth**：所有操作通过 GitHub labels
- **不做执行**：不处理单个 flow 执行
- **manager assignee**：分配 assignee 时使用 `vibe3 task intake <number>`（shell），**禁止手动指定人类用户名**

## Scope

**做**：
- 消化 pool 层的 `[governance suggest]`（Step 0）
- 治理漏网检查（Step 0.5）
- 版本目标定义与 milestone 分配
- Issue 分类与 roadmap/priority labels 设置
- Intake gate 判断：纳入 / rfc / 建议关闭（Step X）

**不做**：
- Assignee issue pool 实时治理（由 `vibe-orchestra` 负责）
- RFC issues 处理（由 `vibe-task` 负责）
- 根据当前 runtime 现场做即时抢占排序（由 `vibe-orchestra` 负责）

## Workflow

### Step 0: 消化未处理的 governance suggest

每次 `/vibe-roadmap` 被触发，**必做的第一步**。

1. **找到上次决策锚点**：
   ```bash
   REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
   gh search issues "repo:$REPO [roadmap decision]" --match comments --limit 20 \
     --json number,updatedAt --jq 'sort_by(.updatedAt) | reverse | .[0] | {number, updatedAt}'
   ```
   若无历史 `[roadmap decision]` 评论（首次运行），锚点设为 7 天前。

2. **列出未消化的 `[governance suggest]`**（过滤已决策的 issue）：
   ```bash
   REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
   gh search issues "repo:$REPO [governance suggest]" --match comments --limit 50 \
     --json number,labels,title \
     --jq '.[] | select(.labels | map(.name) | index("roadmap-reviewed") | not)
               | select(.labels | map(.name) | index("roadmap/rfc") | not)
               | {number, title}'
   ```

3. **按 suggest 类型排列决策优先级**：
   - 先处理 `needs split`（产出最大）
   - 再处理 `Recommend Close`（清积压）
   - 再处理 `waiting on #X`（依赖校验）
   - 最后处理 `Skipped (needs human)`（判断是 rfc 还是可继续）

4. **闭环要求**：处理完每个 suggest 后：
   - 写 `[roadmap decision]` 评论（marker 含义见 roadmap-common.md Comment Marker Contract）
   - decision 不是 `rfc` → **打 `roadmap-reviewed`**：`gh issue edit <number> --add-label "roadmap-reviewed"`
   - decision 是 `rfc` → **不打 `roadmap-reviewed`**，打 `roadmap/rfc`，等人类决策后再处理

5. **推翻 intake skip 时的三步处理**：

   当被审查的 `[governance suggest]` 来自 intake 层 skip 决策（issue 带 `orchestra-scanned` 且无 assignee），如果你决定纳入该 issue，**必须显式执行三步**（标签语义见 roadmap-common.md）：

   ```bash
   # 1. 移除 intake 跳过标记
   gh issue edit <number> --remove-label "orchestra-scanned"

   # 2. 分配 manager assignee，让 issue 进入 assignee-pool（自动移除旧 assignee）
   vibe3 task intake <number> --yes

   # 3. 写决策评论 + 打 roadmap-reviewed
   gh issue comment <number> --body "[roadmap decision] override intake skip: <理由>"
   gh issue edit <number> --add-label "roadmap-reviewed"
   ```

### Step 0.5: 治理漏网检查

Step 0 处理完后，检查两类"漏网" issue：

**类型 A：有 assignee 但缺 state 标签**（通过了 intake 但 pool 还没处理，卡在两层之间）

```bash
gh issue list --assignee vibe-manager-agent --limit 50 --json number,title,labels \
  --jq '.[] | select(.state == "OPEN")
            | select([.labels[].name] | map(select(startswith("state/"))) | length == 0)
            | {number, title}'
```

对每个漏网 issue：
- 应执行（范围明确、有 priority）→ 补 `state/ready`
- 应关闭（过时/冲突/无价值）→ 写 `[roadmap decision] close` + 打 `roadmap-reviewed`

**类型 B：state/done 但 issue 仍 OPEN**（系统未自动关闭）

```bash
gh issue list --label "state/done" --limit 30 --json number,title \
  --jq '.[] | select(.state == "OPEN") | {number, title}'
```

对每个漏网 issue，**必须代码实际验证**（不能只看标签或 PR 状态）：
```bash
git log --oneline -10 --all --grep="<issue 关键词>"
uv run python src/vibe3/cli.py inspect files <相关路径>
```
- 完成了（代码实际包含改动）→ 关闭 issue，comment 说明代码证据
- 没完成（代码中无改动）→ 关闭当前 issue + 创建新 issue（范围更明确，引用原 issue）

处理完后打 `roadmap-reviewed`，结果写入 `.agent/context/memory.md` 缓存。

---

### Step 1: 检查版本目标

```bash
vibe3 task status
gh issue list --limit 50
gh issue list -l "roadmap/p0"
gh issue list -l "roadmap/p1"
```

### Step 2: 版本规划决策

**场景 A: 没有版本目标**
- 提示用户定义版本目标，展示 backlog issues 供选择

**场景 B: 有版本目标但有新 issues**
- 对新 issues 分类：分配 milestone、添加 roadmap 状态标签、必要时补 `priority/[0-9]`
- 对候选 issues 做 intake gate 判断（见 Step X）

**场景 C: 版本结束**
- 确认下一版本目标，重新评估待分类 Issue，更新 roadmap 状态标签

### Step X: Intake 判断

对新进入的 issue 运行三级审查（Level 1/2/3，见 roadmap-common.md）后，选择：

**场景 A: 适合自动化推进**（通过全部三级审查）
```bash
vibe3 task intake <number>
gh issue comment <number> --body "[roadmap decision] Intake completed (scope=<bugfix|feature|refactor>)."
gh issue edit <number> --add-label "roadmap-reviewed"
```

**场景 B: 需要人类讨论**（目标不明确/架构方向未定/scope 过大无法判断拆分）
```bash
gh issue comment <number> --body "[roadmap decision] rfc: <具体原因>."
gh issue edit <number> --add-label "roadmap/rfc"
# 不打 roadmap-reviewed，不分配 assignee
```

**场景 C: 建议关闭**（Level 2/3 不通过：依赖已移除/API 废弃/重复）
```bash
gh issue comment <number> --body "[roadmap decision] close: <关闭原因>."
gh issue edit <number> --add-label "roadmap-reviewed"
# 建议人类关闭 issue（不自动关闭）
```

### Step 3: 应用标签

```bash
gh issue edit <issue-number> --milestone "Phase 1: 基础设施"
gh issue edit <issue-number> --add-label "roadmap/p0"
gh issue edit <issue-number> --add-label "priority/5"
```

### Step 4: 输出状态

```text
版本规划状态

当前版本: Phase 1: 基础设施

P0 (紧急)
- #36: GitHub Projects 整合 [roadmap/p0, priority/8]

当前版本
- #34: Issue 同步 [roadmap/p1, priority/5]
- #35: save 自动关联 [roadmap/p1, priority/5]

下一个版本
- #37: 智能调度 [roadmap/p2, priority/3]

RFC (需讨论)
- #77: 架构方向未定 [roadmap/rfc]
```

## 与其他 Skills 的区别

- **vibe-roadmap**: 版本规划、治理审查、governance suggest 消化（Layer 3 decider）
- **vibe-orchestra**: assignee issue pool 治理（人机协作入口，Layer 2）
- **vibe-task**: RFC 和 blocked issues 检查
- **vibe-debug-serve**: vibe3 serve 运行状态与深度调试

## Restrictions

- 不处理执行层管理（转 `vibe-orchestra`）
- 不看 RFC 或 blocked issues（转 `vibe-task`）
- 不根据当前 runtime 现场做即时抢占排序（转 `vibe-orchestra`）
- 所有操作通过 GitHub labels，不在本地存储
- 所有决策必须写 `[roadmap decision]` marker，**禁止**写 `[governance suggest]`
