---
name: vibe-issue
description: Use when the user wants to create or refine a GitHub issue. This is a human-facing intake entrypoint, not an automated workflow.
---

# /vibe-issue - Issue Intake Entrypoint

该技能负责人机协作的 Issue 创建：澄清、查重、规范化。

## Core Principle: Human-Facing Only

**只负责人机交互**：
- 澄清用户意图
- 查重现有 issue
- 规范化内容
- 创建 GitHub issue
- 解释下一步（roadmap 或 new）

**不承担的职责**：
- 不检查 flow/task 状态（那是执行阶段的产物）
- 不决定自动化路径
- 不判断 issue 是否应该进入 workflow

## Workflow

### Step 1: Clarify Intent

- 用户可直接运行 `/vibe-issue` 或 `/vibe-issue create "<标题>"`
- 扫描 `.github/ISSUE_TEMPLATE/*.md`
- 询问 Bug 或 Feature，获取模板 fields

### Step 2: Deduplication Check

```bash
gh issue list --search "<标题>" --state all --json number,title,state
```

- 高相似度：展示重复 Issue，建议合并或评论
- 低相似度：继续创建

### Step 3: Dependency Identification

扫描草稿中的依赖引用（`#<数字>`、`Depends on`）：

- 确认目标 issue 状态
- 引导用户写入 `## Dependencies` section
- 格式：`- Depends on #<id> — <短描述>`

### Step 4: Fill & Polish

- 引导补充缺失信息
- 建议 Labels（`bug`、`enhancement`、`priority/*`）
- **禁止添加 `vibe-task` 标签**（自动镜像）

### Step 4.5: Milestone Assignment

**必须为每个 issue 分配 milestone**，确保版本规划可追踪。

**检查现有 milestones**：

```bash
gh api repos/{owner}/{repo}/milestones --paginate -q '.[] | {number, title, open_issues, closed_issues}'
```

**询问用户**：

> 建议分配到哪个 milestone？
> 
> 当前活跃 milestones：
> - Phase 6: 架构清理与模块化 (5 open)
> - Phase 7: Runtime Kernel 核心能力 (3 open)
> - Phase 8: Runtime Kernel 高级特性 (1 open)
>
> 或创建新 milestone？

**分配原则**：

- **Bug 修复** → 当前版本 milestone（如有活跃修复阶段）或下一版本
- **Feature/Epic** → 根据规划放入对应版本 milestone
- **RFC/讨论** → 暂不分配 milestone，等待决策
- **Sub-issue** → 与父 epic issue 使用相同 milestone

**如果用户不确定**：

提供推荐并说明理由：

```text
建议分配到: Phase 6: 架构清理与模块化
理由: 此 issue 涉及 services/shared 模块重构，属于架构清理范围
```

### Step 5: Scope Check

扫描是否为 epic 候选：
- 标题含：`审查`、`总览`、`清理`、`重构所有`
- Body 含：`>N 个文件`、列出 >3 个子任务

建议拆分为主 issue + sub-issues，或记录 `## Scope estimate`。

### Step 5A: Epic Creation

当 Step 5 识别到 epic 候选时，引导用户创建父 epic issue：

**标签配置**：
- `roadmap/epic` + 用户选择的 `roadmap/p*` + milestone

**Body 必需结构**：

```markdown
## Scope
<整体意图和范围描述>

## Sub-issues
- [ ] #N — <sub-issue 1 title>
- [ ] #M — <sub-issue 2 title>
```

**创建流程**：

```bash
# 创建 epic issue
gh issue create --title "<标题>" --body "$(cat <<'EOF'
## Scope
<整体意图>

## Sub-issues
- [ ] #<placeholder-1> — <sub-issue 1 title>
- [ ] #<placeholder-2> — <sub-issue 2 title>
EOF
)" --label "roadmap/epic,roadmap/p1" --milestone "<milestone title>"
```

**注意**：
- 如果 sub-issues 尚未创建，先使用占位符标题创建 epic
- 创建 sub-issues 后，更新 epic 的 `## Sub-issues` 部分为真实 issue 编号
- 复选框格式 `- [ ] #N` 是 `assignee-pool` 解析所需

### Step 5B: Sub-Issue Creation

为 epic 的每个子任务创建 sub-issue：

**标签配置**：
- `roadmap/p*` + milestone（与父 epic 相同）
- **不要**添加 `state/blocked` 标签（这是 pre-flow 阶段，依赖声明只在 body 中）

**Body 必需结构**：

```markdown
## Parent issue
- Parent: #<epic-id>

## Dependencies
- Depends on #<id> — <简短描述>
- Blocked by #<id> — <简短描述>

## <Task description>
<具体任务内容>
```

**创建命令**：

```bash
gh issue create --title "<标题>" --body "$(cat <<'EOF'
## Parent issue
- Parent: #<epic-id>

## Dependencies
- Depends on #<dependency-id> — <描述>

## <Task section>
<内容>
EOF
)" --label "roadmap/p1" --milestone "<milestone title>"
```

**关键约束**（Pre-flow Dependency Rules）：
- **禁止**写入 `state/blocked` 标签
- **禁止**写入 managed section（`<!-- vibe3-flow-state-start -->`）
- **禁止**调用 `vibe3 flow blocked` / `vibe3 flow bind`（需要 branch context）

创建所有 sub-issues 后，更新 epic 的 `## Sub-issues` 部分为真实 issue 编号。

### Step 5C: Dependency Order Encoding

当 sub-issues 之间存在依赖关系时，使用规范的依赖声明格式：

**依赖声明格式**：

```markdown
## Dependencies
- Depends on #<id> — <简短描述（提供了什么）>
- Blocked by #<id> — <简短描述（为什么阻塞）>
```

**格式规范**：
- 每行一个依赖
- 使用 `- Depends on #N` 或 `- Blocked by #N` 前缀
- 简短描述依赖内容或阻塞原因
- 此格式可被以下工具解析：
  - `vibe-new` Step 5（bootstrap 时提取依赖）
  - `roadmap-intake`（检测 `Blocked by #N` 用于 `--blocked-by` 参数）
  - `assignee-pool`（在 issue body/comments 中查找依赖引用）

**示例**：

```markdown
## Dependencies
- Depends on #123 — 提供认证中间件基础能力
- Blocked by #124 — 等待数据库 schema 设计决策
```

### Step 5D: RFC Routing for Unresolved Design Choices

当 epic 或 sub-issue 存在未解决的架构/设计决策时：

**处理流程**：

1. **添加 RFC 标签**：
   ```bash
   gh issue edit <issue-number> --add-label "roadmap/rfc"
   ```

2. **创建决策请求评论**：
   ```bash
   gh issue comment <issue-number> --body "[decision needed] <具体设计问题>"
   ```

3. **等待决策**：
   - RFC issue 不会进入 dispatch
   - 等待人类通过 `/vibe-task` 决策

4. **决策完成后**：
   - 决策写入 issue comment
   - 移除 `roadmap/rfc` 标签
   - 然后可以创建依赖此决策的 sub-issues

**约束**：
- 不要创建依赖未解决 RFC 决策的 sub-issues
- RFC 问题解决前，相关 issue 保持 blocked 状态

### Boundary: Pre-Flow vs Flow Context

**此 skill 的职责边界**：

**负责**：
- 创建 issue 并在 body 中声明依赖（自然语言，pre-flow）
- 引导用户填写规范的 `## Dependencies` 和 `## Sub-issues` 部分
- 设置正确的标签和 milestone

**不负责**（Pre-flow Dependency Rules）：
- 不写入 `state/blocked` 标签（需要 flow context）
- 不写入 managed section（需要 branch context）
- 不调用 `vibe3 flow blocked` / `vibe3 flow bind` 命令

**依赖声明到执行的转换**：

- **roadmap-intake**：检测 body 中的 `Blocked by #N` → 使用 `vibe3 task intake <M> --blocked-by <N>` 创建 placeholder flow 并设置 `state/blocked`
- **vibe-new Step 5**：在 bootstrap 时读取 `## Dependencies` → 验证并标记未满足的依赖
- **manager**：进入 flow 后读取 body 中的依赖 → 通过 `vibe3 flow blocked --task <N>` 注册到 `flow_issue_links`

### Step 5.5: Anti-Pattern Risk Check

对照以下 5 条反模式特征，检查 issue 是否存在反模式风险（定义详见 [roadmap-common.md](../../supervisor/roadmap-common.md#反模式-issue-识别标准)）：

**检查清单**：

- [ ] **有明确痛点**：描述具体使用场景、痛点和验证依据
- [ ] **复杂度与收益匹配**：修改范围合理，收益不只服务模糊或极小场景
- [ ] **不与现有能力重叠**：确认 CI、skill 或既有流程无法解决
- [ ] **符合项目原则**：最小变更、认知优先、Skill-First、验证优先
- [ ] **不是边缘场景驱动**：需求有通用价值，不能由用户自行处理

**风险评估**：

如果命中 >= 2 条未通过项，向用户展示警告：

> ⚠️ **反模式风险提示**
>
> 此 issue 可能被标记为反模式并关闭。建议补充痛点描述、验证证据，或说明为何现有能力无法满足需求。
>
> 详见 [反模式识别标准](../../supervisor/roadmap-common.md#反模式-issue-识别标准)。

**注意**：此步骤只提供警告，不阻止创建（vibe-issue 是 human-facing，不自动拒绝）。

### Step 6: Create

```bash
# 如果有 milestone
gh issue create --title "<标题>" --body "<内容>" --label "<labels>" --milestone "<milestone title>"

# 如果是 RFC 或用户明确不确定 milestone
gh issue create --title "<标题>" --body "<内容>" --label "<labels>"
```

**重要**：
- 创建后立即确认 milestone 是否正确设置
- 如无 milestone，提醒用户后续需通过 `vibe-roadmap` 补充分配

输出 Issue 链接，建议下一步：
- 版本规划：`vibe-roadmap`
- 人工开工：`vibe-new`
- 只说明已创建，等待规划

## Minimal Stop Points

- Issue created
- Existing issue confirmed
- Insufficient info, blocked
- Ready to handoff

## Design Principles

1. 不读取 flow/task 状态（创建阶段不需要）
2. 只负责人机交互，不定义自动化语义
3. GitHub issue 是真源，不检查本地状态
