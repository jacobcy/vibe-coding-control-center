---
name: vibe-issue
description: Use when the user wants to create, refine, or deduplicate a GitHub issue. This is a human-facing intake entrypoint for issue creation governance, not an automated workflow.
---

# /vibe-issue - Human-Facing Issue Intake Entrypoint

该技能是人机协作的 Issue intake 入口，负责澄清、查重、规范化并创建 GitHub Issue。

## Core Principle: Human-Facing Interaction Only

**`vibe-issue` 只负责人机交互**：
- 澄清用户意图
- 查重现有 issue
- 规范化标题、描述、标签
- 在需要时创建可追踪 issue
- 解释后续如何进入执行链，但不承担执行现场 bootstrap

**`vibe-issue` 不承担的职责**（由基础设施承接）：
- 不决定什么时候自动进入 flow
- 不决定什么时候绑定 task
- 不定义"issue 已经等于进入执行 workflow"的语义
- 不定义 issue intake 后的自动化路径

这些执行链语义由 `vibe3 flow bind`、`vibe3 task status` 等基础设施承接。

## Semantic Boundary

- **vibe-issue**: Issue intake 治理（创建、查重、规范化）
- **vibe-roadmap**: Issue 已存在后的版本规划与窗口归类
- **vibe-orchestra**: 运行时根据现场建议下一个 issue
- **vibe-new**: 进入执行现场的 bootstrap 入口
- **vibe3 flow/task**: 执行链基础设施，承接 issue → flow → task 绑定语义

**vibe-issue 不等于 vibe-new**：
- `vibe-issue` 只负责把模糊需求转成可追踪 issue
- `vibe-new` 负责创建 flow/worktree/workflow 现场

## Human-Facing Workflow

该 workflow 只描述人机交互步骤，不隐含自动化执行链语义。

### Step 1: Clarify Intent

- 用户可直接运行 `/vibe-issue` 进入引导
- 若已确定标题，可运行 `/vibe-issue create "<标题>"` 跳过首轮澄清
- Skill 扫描 `.github/ISSUE_TEMPLATE/*.md`
- 询问用户是 Bug 还是 Feature，获取对应模板的 fields

### Step 2: Deduplication Check

- 运行 `gh issue list --search "<标题>" --state all --json number,title,state`
- 分析相似度：
  - **高相似度**：展示重复 Issue，建议在原 Issue 下评论或合并
  - **低相似度**：继续创建流程

### Step 3: Flow Context Check (Lightweight)

- 使用 `vibe3 flow status` 检查是否已有活跃 flow 绑定到相关 issue
- 该命令读取本地状态，必要时获取远端信息（issue titles、PR 映射等）
- 若发现已绑定 flow，记录上下文供后续参考，**不阻止 issue 创建**

> **注意**: 这一步只提供事实，不隐含"应该阻止创建"或"应该自动进入已存在 flow"的判断。后续选择由用户或下游 workflow 决定。

### Step 4: Dependency Identification

扫描草稿中潜在的依赖引用，识别模式：
- `#<数字>`（如 `#1097`、`#42`）
- 关键词：`Depends on`、`blocked by`、`基于`、`依赖`、`depends on #`

若发现潜在依赖：
1. 用 `gh issue view <issue_number> --json number,title,state` 确认目标状态
2. 若 issue 不存在：提示「依赖引用无效: #<number> 不存在」
3. 若 issue 已关闭：提示「依赖已满足: #<number> 已完成」
4. 若 issue 存在且 open：引导用户把依赖写入 `## Dependencies` section
   - 格式：`- Depends on #<id> — <短描述>`

> **注意**: 不在此阶段写 `flow_issue_links`，那是 `vibe3 flow bind --role dependency` 的职责。这里只确保 issue body 有标准化的 `## Dependencies` section。

### Step 5: Fill & Polish

- 引导用户补充模板缺失信息
- 基于 AI 建议合适的 Labels（`bug`、`enhancement`、`priority/*`）
- **禁止添加 `vibe-task` 标签**：该标签是 `vibe3 flow bind` 成功后的自动镜像，不应手动添加

> **注意**: intake 标签不等于已完成 roadmap placement。是否进入版本窗口、如何排序，由 `vibe-roadmap` / `vibe-orchestra` 在后续阶段处理。

### Step 6: Scope Self-Check & Sub-issue Structure

**Scope 自检触发条件**：

扫描标题和 body，任一命中即视为 epic 候选：
- 标题含：`审查`、`总览`、`清理`、`统一`、`重构所有`、`全面`、`全量`
- Body 含：`>N 个文件`、`>M 个模块`、`N+ 个`、列出 >3 个独立子任务

**命中后的行为**：
1. 提示用户：「这个 issue scope 较大，建议拆为主 issue + sub-issues 结构」
2. 若用户确认拆分：
   - 当前 issue 作为主 issue，建议添加 `roadmap/epic` 标签
   - body 写入 `## Sub-issues` section（留空模板）
   - 引导用户单独触发 `/vibe-issue` 创建每个 sub-issue
3. 若用户坚持单 issue：
   - body 写入 `## Scope estimate` section，记录范围预估

> **注意**: 这一步属于人机 scope 判断，不属于自动化执行链。

### Step 7: Create & Handoff

- 执行 `gh issue create --title "<标题>" --body "<润色后的内容>" --label "<labels>"`
- 创建成功后，输出 Issue 链接与建议下一步
- 若需要版本规划，交给 `vibe-roadmap`
- 若用户明确要人工开工，转给 `vibe-new`
- 若用户问自动治理下如何消费，可读取 `vibe3 task status` 解释当前 queue 事实，**但不决定顺位**

## Minimal Stop Points

该 skill 的最小停点：
- Issue created
- Existing issue confirmed
- Insufficient info, blocked with explanation
- Ready to hand off to `vibe-roadmap` or `vibe-new`

## Issue Body Standard Sections

以下 section 由 `vibe-issue` 维护，是下游消费的真源：

### `## Dependencies`

- **格式**: 一行一条 `- Depends on #<id> — <短描述>`
- **写入者**: `vibe-issue` 在 Step 4 引导用户确认并写入
- **消费者**: `CoordinationResolver` 解析 issue body 同步到 `flow_issue_links`
- **示例**:
  ```markdown
  ## Dependencies
  - Depends on #1097 — 统一依赖语义
  - Depends on #1050 — 基础架构重构
  ```

### `## Sub-issues`

- **格式**: 一行一条 `- [ ] #<id> — <子任务短描述>`（checkbox 格式）
- **写入者**: 用户确认拆分后维护
- **消费者**: manager 读取子任务进度
- **示例**:
  ```markdown
  ## Sub-issues
  - [ ] #1099 — 子任务 A：核心逻辑重构
  - [ ] #1100 — 子任务 B：测试覆盖更新
  ```

### `## Scope estimate`

- **格式**: 自由文本，建议包含预估文件数/模块数/工作量级别
- **写入者**: issue 继续保持单 issue 模式时写入
- **消费者**: roadmap-intake / vibe-roadmap / manager 用于判断
- **示例**:
  ```markdown
  ## Scope estimate
  - 预估影响: ~15 个文件, 3 个模块
  - 工作量: 中等（预计 2-3 个 flow）
  ```

**注意**: 这些 section 是 issue body 的一部分，应由 `gh issue view <id> --json body` 读取。

## Design Principles

1. `vibe-issue` 只负责人机交互，不定义执行链语义
2. 创建完成后可 handoff 给 `vibe-roadmap` 或 `vibe-new`，但不强制
3. 不在 skill 文本中隐含自动化 workflow 的判断或触发条件
