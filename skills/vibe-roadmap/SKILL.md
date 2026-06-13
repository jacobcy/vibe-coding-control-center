---
name: vibe-roadmap
description: Use when the user wants project-level roadmap planning, version goals, backlog triage, governance suggest review, or issue placement decisions. Triggered by "vibe roadmap", "/vibe-roadmap", "版本规划", "roadmap 审查", "消化 governance suggest", "下一个版本做什么", or "这个 issue 放哪一版". Do not use for assignee pool governance (use vibe-orchestra) or single-flow execution.
---

# /vibe-roadmap - 版本规划与治理审查

维护版本路线图，同时作为三层治理架构的 Layer 3 审查者，消化 governance 层的 `[governance suggest][roadmap-intake]` / `[governance suggest][assignee-pool]` 并形成最终 `[roadmap decision]`。

三层架构、标签语义（orchestra-scanned / orchestra-governed / roadmap-reviewed）和三级审查框架（Level 1/2/3）见 @vibe/supervisor/roadmap-common.md（使用 `vibe3 handoff show @vibe/supervisor/roadmap-common.md` 命令读取）。

## 权限模型（强制执行）

| 标记 | 含义 | Agent 允许的操作 |
|------|------|-----------------|
| `[Agent]` | Agent 可自主执行 | 只读查询、治理漏网检查、反模式评分、data-driven 的 close/hold/rfc 判断 |
| `[人类确认]` | 必须经人类确认 | **禁止**自主执行 milestone 分配、版本目标定义、intake 纳入决策 |

**硬约束**：
- `[人类确认]` 步骤中，Agent **必须停下来**，展示分析结果和建议方案，等待人类明确回复后才能执行
- Agent **不得**在未获人类确认的情况下修改 milestone、写 `close` decision、或对非明显的 rfc 做最终判断
- 写 `[roadmap decision]` 前**必须先搜索**是否已有同类 decision，避免重复评论
- 所有 state/ 标签操作必须通过 `vibe3` 命令，**禁止**直接用 `gh issue edit` 操作 state/ 标签

## 核心原则

- **审查纠正 governance 决策**：消化 roadmap-intake / assignee-pool 的分层 `[governance suggest]`，写 `[roadmap decision]`，打 `roadmap-reviewed`
- **GitHub-as-truth**：所有操作通过 GitHub labels
- **先搜后写**：写 `[roadmap decision]` 前必须搜索是否已有同名 decision，避免重复评论
- **用 vibe3 命令操作状态**：需要修改 state/ 标签时，使用 `vibe3 task` 命令，**禁止**直接用 `gh issue edit` 操作 state/ 标签
- **不做执行**：不处理单个 flow 执行
- **manager assignee**：分配 assignee 时使用 `vibe3 task intake <number>`（shell），**禁止手动指定人类用户名**

## Scope

**做**：
- 消化 governance 层的 `[governance suggest][roadmap-intake]` / `[governance suggest][assignee-pool]`（Step 0）
- 治理漏网检查（Step 0.5）
- 版本目标定义与 milestone 分配
- Issue 分类与 roadmap/priority labels 设置
- Intake gate 判断：纳入 / rfc / 建议关闭（Step X）

**不做**：
- Assignee issue pool 实时治理（由 `vibe-orchestra` 负责）
- RFC issues 处理（由 `vibe-task` 负责）
- 根据当前 runtime 现场做即时抢占排序（由 `vibe-orchestra` 负责）

## Workflow

### Step 0: 消化未处理的 governance suggest `[Agent]`

每次 `/vibe-roadmap` 被触发，**必做的第一步**。

**0.0 查看需要处理的 issue**：
```bash
# 使用 vibe3 task status 获取全局视图
vibe3 task status
```

**0.1 找到上次决策锚点**：
```bash
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
gh search issues "repo:$REPO [roadmap decision]" --match comments --limit 20 \
  --json number,updatedAt --jq 'sort_by(.updatedAt) | reverse | .[0] | {number, updatedAt}'
```
若无历史 `[roadmap decision]` 评论（首次运行），锚点设为 7 天前。

**0.2 列出未消化的分层 `[governance suggest]`**（过滤已决策的 issue）：
```bash
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
gh search issues "repo:$REPO [governance suggest]" --match comments --limit 50 \
  --json number,labels,title \
  --jq '.[] | select(.labels | map(.name) | index("roadmap-reviewed") | not)
            | select(.labels | map(.name) | index("roadmap/rfc") | not)
            | {number, title}'
```

**0.3 按 suggest 类型排列决策优先级**：
- 先处理 `needs split`（产出最大）
- 再处理 `Recommend Close`（清积压）
- 再处理 `waiting on #X`（依赖校验）
- 最后处理 `Skipped (needs human)`（判断是 rfc 还是可继续）

**0.4 决策前检查已有评论（防重复）**：
```bash
# 对每个即将处理的 issue，检查是否已有 [roadmap decision]
gh issue view <N> --comments --limit 50 | grep "\[roadmap decision\]"
```
```
IF 已有 "[roadmap decision]" 评论 AND 由当前 agent 在近期写入:
    SKIP 此 issue（已有决策，不重复写入，不重复打 roadmap-reviewed）
```

**0.5 依赖验证（写 `proceed` / `unblock` 决策前必须执行）** `[Agent]`：

当决策意图是解除阻塞（`proceed`、`unblock`）并声称"依赖已解除"时，**必须先验证依赖项的实际状态**，不可仅凭 governance suggest 的描述或 issue body 中的自然语言声明。

**验证方法**：
```bash
# 对每个被引用的依赖 issue，使用 vibe3 task show 检查其状态
vibe3 task show <dep_number> --full

# 补充：检查 GitHub 状态和标签
gh issue view <dep_number> --json state,labels --jq '{state, labels: [.labels[].name]}'
```

**判定标准**（全部满足才可写 `proceed`）：
- 依赖 issue 的 GitHub `state` 为 `CLOSED`，或
- 依赖 issue 带有 `state/done` 或 `state/merge-ready` 标签，或
- 依赖 issue 有已合并的 PR（`gh pr list --search "<dep_number>" --state merged`）

**不满足时**：
- 写 `[roadmap decision] hold: 依赖 #N 未完成（当前状态: <state/label>），不解除阻塞`
- 打 `roadmap-reviewed`
- 不写 `proceed`

**背景**：#2171 被错误解除阻塞的根因是 roadmap decider 声称"依赖 #2169 已完成"，但 #2169 实际仍在 `state/handoff`。此步骤防止同类错误。

**0.6 闭环要求**：处理完每个 suggest 后：
- 写 `[roadmap decision]` 评论（marker 含义见 roadmap-common.md Comment Marker Contract）
- decision 不是 `rfc` → **打 `roadmap-reviewed`**：`gh issue edit <number> --add-label "roadmap-reviewed"`
- decision 是 `rfc` → **不打 `roadmap-reviewed`**，打 `roadmap/rfc`，等人类决策后再处理

**0.7 proceed/unblock 时必须移除 orchestra-scanned** `[Agent]`：

当 decision 是 `proceed` 或 `unblock`（依赖已解除、可以继续推进）时，如果 issue 带有 `orchestra-scanned` 标签，**必须移除**。否则 roadmap-intake 的过滤规则会永久跳过该 issue，即使依赖已解除也无法被重新纳入。

```bash
# 检查是否有 orchestra-scanned
LABELS=$(gh issue view <number> --json labels --jq '[.labels[].name]')
if echo "$LABELS" | grep -q "orchestra-scanned"; then
  gh issue edit <number> --remove-label "orchestra-scanned"
fi
```

**背景**：#2381 被标记为 `orchestra-scanned` 后，即使依赖已解除（#2376、#2380 CLOSED），roadmap-intake 仍无法看到它。roadmap 写了 `proceed` 但没移除标签，导致 issue 被永久跳过。

**适用场景**：
- 依赖解除后的 proceed
- 错误 skip 后的 override
- 任何导致 issue 需要重新进入 pipeline 的 decision

**不适用场景**：
- decision 是 `hold`（保持 blocked）
- decision 是 `close`（关闭 issue）
- decision 是 `rfc`（等待人类决策）

**0.8 推翻 intake skip 时的三步处理** `[Agent]`：

当被审查的 `[governance suggest][roadmap-intake]` 来自 intake 层 skip 决策（issue 带 `orchestra-scanned` 且无 assignee），如果你决定纳入该 issue，**必须显式执行三步**（标签语义见 roadmap-common.md）：

```bash
# 1. 移除 intake 跳过标记
gh issue edit <number> --remove-label "orchestra-scanned"

# 2. 分配 manager assignee，让 issue 进入 assignee-pool（使用 vibe3 命令，不手动操作 state/ 标签）
vibe3 task intake <number> --yes

# 3. 写决策评论 + 打 roadmap-reviewed
gh issue comment <number> --body "[roadmap decision] override intake skip: <理由>"
gh issue edit <number> --add-label "roadmap-reviewed"
```

### Step 0.5: 治理漏网检查 `[Agent]`

Step 0 处理完后，检查两类"漏网" issue：

**类型 A：有 assignee 但缺 state 标签**（通过了 intake 但 pool 还没处理，卡在两层之间）

```bash
vibe3 status
# 从 Manager agents 读取本机 manager，再替换下面的 <manager>
gh issue list --assignee <manager> --limit 50 --json number,title,labels,state \
  --jq '.[] | select(.state == "OPEN")
            | select([.labels[].name] | map(select(startswith("state/"))) | length == 0)
            | {number, title}'
```

对每个漏网 issue：
- 应执行（范围明确、有 priority）→ **使用 `vibe3 task intake <N>`** 补 `state/ready`
- 应关闭（过时/冲突/无价值）→ 写 `[roadmap decision] close` + 打 `roadmap-reviewed`

**禁止**：对漏网 issue 直接使用 `gh issue edit --add-label state/ready`。必须通过 `vibe3 task intake` 命令确保三源同步。

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

### Step 0.6: 反模式检查 `[Agent]`

Step 0.5 处理完后，对候选 issue 执行反模式识别（定义见 roadmap-common.md「反模式 Issue 识别标准」）。

**扫描范围**：
- Step 0 处理完的未决策 governance suggest（已排除 roadmap-reviewed 和 roadmap/rfc）
- Step 0.5 漏网检查中发现的 issue

**评估流程**：

对照 roadmap-common.md 的 5 条反模式特征逐项评分：
1. 无明确痛点
2. 高复杂度低 ROI
3. 与现有能力重叠
4. 违反项目原则
5. 边缘场景驱动

对每个特征，给出具体证据（如："缺少用户场景描述"、"改动涉及 3 个模块但收益仅为边缘场景"）。

**评分 >= 2 的处理**（判定为反模式）：

```bash
# 写决策评论（必须逐条写评分理由）
gh issue comment <number> --body "[roadmap decision] close: 反模式
- #1: <是否满足 + 具体证据>
- #2: <是否满足 + 具体证据>
- ...
评分: <总数> 条，判定为反模式"

# 打审查标签
gh issue edit <number> --add-label "roadmap-reviewed"

# 关闭 issue
gh issue close <number>
```

**评分 < 2 的处理**：

继续走正常 roadmap 流程（Step 1 检查版本目标）。

---

### Step 1: 检查版本目标 `[人类确认]`

```bash
vibe3 task status
gh issue list --limit 50
gh issue list -l "roadmap/p0"
gh issue list -l "roadmap/p1"
```

**向人类展示**当前版本目标状态和建议，由人类决定版本目标。

### Step 1.5: Milestone 健康检查 `[Agent]`

**每次版本规划必须执行**，生成统计报告并选择性处理缺失 milestone 的 issues。

**Step 1.5a: 统计报告** `[Agent]`

检查无 milestone 的 issues 并生成报告：

```bash
# 统计总数
COUNT=$(gh issue list --state open --limit 100 --json milestone --jq '[.[] | select(.milestone == null)] | length')
echo "发现 $COUNT 个 open issues 没有 milestone"

# 按优先级分组统计
echo -e "\n按 roadmap 优先级分布："
gh issue list --state open --limit 100 --json number,title,milestone,labels \
  --jq '.[] | select(.milestone == null) 
        | {number, title, priority: ([.labels[].name | select(startswith("roadmap/p"))] | first // "none")}' \
  | jq -s 'group_by(.priority) | .[] | {priority: .[0].priority, count: length}'
```

**Step 1.5b: 分批处理** `[Agent]`

当发现大量无 milestone issues 时，**不要一次性全部处理**。采用以下策略：

**策略 1: 按优先级分批**
```bash
# 只处理 P0/P1 高优先级 issues（每次最多 5-10 个）
gh issue list --state open --limit 100 --json number,title,milestone,labels \
  --jq '.[] | select(.milestone == null) 
        | select([.labels[].name] | index("roadmap/p0") or index("roadmap/p1"))
        | .number' \
  | head -5 | while read NUM; do
    echo "处理 #$NUM..."
    # 分析并分配 milestone
  done
```

**策略 2: 按标题关键词分批**
```bash
# 处理标题包含 "Phase" 字样的 issues（通常有明确的阶段标识）
gh issue list --state open --limit 100 --json number,title,milestone \
  --jq '.[] | select(.milestone == null) 
        | select(.title | test("Phase [0-9]")) 
        | {number, title}' \
  | head -10
```

**单个 Issue 处理流程**：

1. **分析 issue 内容和 scope**：
   - 使用 `vibe3 task show <N>` 查看标题、body、已有评论、PR 状态
   - 判断属于哪个 feature/阶段
   - 检查是否为 epic issue 或 sub-issue

2. **分配 milestone** `[人类确认]`：

```bash
# 查看现有 milestones
gh api repos/{owner}/{repo}/milestones --paginate -q '.[] | {number, title, open_issues}'

# 分配 milestone（需人类确认后执行）
gh issue edit <number> --milestone "<milestone title>"
```

3. **记录决策**：

```bash
gh issue comment <number> --body "[roadmap decision] milestone assigned: <milestone> (理由: <scope/feature归属>)"
gh issue edit <number> --add-label "roadmap-reviewed"
```

**Milestone 分配原则**：

- **Epic issue** → 放入对应的版本/阶段 milestone（如 "Phase 6: 架构清理与模块化"）
- **Sub-issue** → 与父 epic issue 使用相同 milestone
- **独立小修复** → 根据紧急程度放入当前版本或下一版本 milestone
- **RFC/架构讨论** → 不分配 milestone，等待决策后再归档

### Step 2: 版本规划决策 `[人类确认]`

**场景 A: 没有版本目标**
- 提示用户定义版本目标，展示 backlog issues 供选择

**场景 B: 有版本目标但有新 issues**
- 对新 issues 分类：分配 milestone、添加 roadmap 状态标签、必要时补 `priority/[0-9]`
- 对候选 issues 做 intake gate 判断（见 Step X）

**场景 C: 版本结束**
- 确认下一版本目标，重新评估待分类 Issue，更新 roadmap 状态标签

### Step X: Intake 判断 `[Agent]`

对新进入的 issue 运行三级审查（Level 1/2/3，见 roadmap-common.md）后，选择：

**场景 A: 适合自动化推进**（通过全部三级审查）

先根据 issue 内容判断是否为简单任务：

**简单任务路由**（同时满足以下条件）：
- 只涉及测试文件修改（`tests/`、`test_*.py`、`*_test.py`、测试夹具、测试配置）
- 不涉及业务代码改动（`src/`、`lib/`、核心逻辑文件）
- 预估改动范围 ≤ 5 个文件、≤ 100 行

满足时，路由到 supervisor/apply 快速通道（复用 assignee-pool Step 2.5 的判断标准）：
```bash
# 移除旧 state 标签（如有），添加 supervisor 路由标签
gh issue edit <number> --add-label "supervisor,state/handoff"
gh issue comment <number> --body "[roadmap decision] simple task → supervisor/apply: <判断依据>."
gh issue edit <number> --add-label "roadmap-reviewed"
```

不满足时，走完整 manager intake 路径：
```bash
# 使用 vibe3 命令，确保三源同步
vibe3 task intake <number>
gh issue comment <number> --body "[roadmap decision] Intake completed (scope=<bugfix|feature|refactor>)."
gh issue edit <number> --add-label "roadmap-reviewed"
```

**场景 B: 需要人类讨论** `[人类确认]`（目标不明确/架构方向未定/scope 过大无法判断拆分）
```bash
gh issue comment <number> --body "[roadmap decision] rfc: <具体原因>."
gh issue edit <number> --add-label "roadmap/rfc"
# 不打 roadmap-reviewed，不分配 assignee
```

**架构级 rfc 判据**（见 `docs/decisions/_template.md` 和 ADR 结晶条件）：如果 rfc 满足"跨任务/跨模块架构选型 + 有真实权衡 + 期望长期有效"，不要只要求后续实现 PR 顺手写 ADR；应推动一个小型 ADR PR（只含 ADR 文件、INDEX 更新和必要的最小链接更新），并在决策 comment 中写明 `ADR PR: <url>`。非架构级 rfc 维持现有流程不变。

**场景 C: 建议关闭**（Level 2/3 不通过：依赖已移除/API 废弃/重复）`[Agent]`
```bash
gh issue comment <number> --body "[roadmap decision] close: <关闭原因>."
gh issue edit <number> --add-label "roadmap-reviewed"
# 建议人类关闭 issue（不自动关闭）
```

### Step 3: 应用标签 `[Agent]`

```bash
gh issue edit <issue-number> --milestone "Phase 1: 基础设施"
gh issue edit <issue-number> --add-label "roadmap/p0"
gh issue edit <issue-number> --add-label "priority/5"
```

**注意**：roadmap/ 和 priority/ 标签可通过 `gh issue edit` 操作（非 state/ 标签，不涉及三源同步）。但 state/ 标签的操作必须通过 `vibe3` 命令（见 Step X）。

### Step 4: 输出状态 `[Agent]`

**审查时先参考 `docs/decisions/INDEX.md` 中已有 `accepted` ADR，再读取相关 ADR 正文**。决策不得违反当前有效 ADR；如需偏离，必须显式提议 supersede。

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

## 禁止行为清单

| 禁止行为 | 说明 | 正确做法 |
|---------|------|---------|
| `gh issue edit <N> --add-label state/ready` | 直接操作 state/ 标签无法同步三源 | 用 `vibe3 task intake <N>` 或 `vibe3 task resume <N>` |
| `gh issue edit <N> --remove-label state/blocked` | 同上，label 改了但 flow state 不变 | `vibe3 task resume <N> --label auto --yes` |
| 未搜索已有 `[roadmap decision]` 就写新 decision | 造成重复评论 | Step 0.4 先 `grep "\[roadmap decision\]"` |
| 写 `proceed` 前不验证依赖项的实际状态 | 可能错误解除阻塞（#2171 教训） | Step 0.5 执行 `vibe3 task show <dep>` + `gh issue view <dep>` |
| 不检查 issue body 中的已有 `[governance suggest]` 就写 decision | 覆盖已有分层决策 | Step 0.2 先列出所有未消化的 suggest |
| proceed/unblock 后不移除 `orchestra-scanned` | issue 被永久跳过（#2381 教训） | Step 0.7 检查并移除 orchestra-scanned |
| 对 state/done 但 OPEN 的 issue 只看标签不验证代码 | 标签和实际代码状态可能不一致 | Step 0.5 类型 B: `git log` + `inspect files` |

## 与其他 Skills 的区别

- **vibe-roadmap**: 版本规划、治理审查、governance suggest 消化（Layer 3 decider）
- **vibe-orchestra**: assignee issue pool 治理（人机协作入口，Layer 2）
- **vibe-task**: RFC 和 blocked issues 检查
- **vibe-debug-serve**: vibe3 serve 运行状态与深度调试

## Restrictions

- 不处理执行层管理（转 `vibe-orchestra`）
- 不看 RFC 或 blocked issues（转 `vibe-task`）
- 不根据当前 runtime 现场做即时抢占排序（转 `vibe-orchestra`）
- 所有决策必须写 `[roadmap decision]` marker，**禁止**写 `[governance suggest]`
- **禁止直接用 `gh issue edit` 操作 state/ 标签**
- **写 decision 前必须先搜索已有 decision**
- **写 proceed 前必须先验证依赖项的实际状态（使用 vibe3 task show）**

## Pre-flow Dependency Rules

> 完整规范见 [roadmap-common.md § Pre-flow Dependency Rules](../supervisor/roadmap-common.md)

vibe-roadmap 在 pre-flow 阶段（issue 无 flow/branch context）的约束：

- ✅ 在 issue body 正文中用自然语言说明依赖：`Blocked by #N`、`Depends on #N`
- ✅ 添加 `roadmap/*`、`priority/*` 规划类 labels
- ❌ 禁止直接添加 `state/blocked` 标签 — pre-flow 无法保证三源（label/body/cache）原子写入，会导致 dispatcher 无法识别
- ❌ 禁止直接写 managed section（`Blocked by:` / `Dependencies:` 结构化字段）
- ❌ 禁止调用 `vibe3 flow blocked / flow bind` — 这两个命令需要 branch 存在

依赖的正式注册（写入 managed section + flow_issue_links）由 manager 入场后完成；pre-flow 只负责把依赖关系说清楚。
