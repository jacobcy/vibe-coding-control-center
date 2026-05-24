---
name: vibe-issue
description: Use when the user wants to create, draft, deduplicate, or refine a GitHub issue for this repo, asks for issue intake/governance before roadmap placement, or mentions "/vibe-issue", "创建 issue", "提 issue", "issue 查重", or "补 issue 模板".
---

# /vibe-issue - 智能 Issue 助手

该技能负责引导用户创建高质量的 GitHub Issue，并在进入 roadmap 规划前完成 intake 治理。

语义边界：

- `vibe-issue` 负责 Issue intake、模板补全、查重、标签与创建。
- `vibe-issue` 不决定 roadmap 排期，不负责判断“下一个做哪个 issue”，也不创建 flow / task 现场。
- `vibe-roadmap` 负责 Issue 已存在之后的版本规划与版本窗口归类。
- `vibe-orchestra` 负责在运行中根据当前现场建议“下一个值得处理的 issue”。
- `vibe-task` 与 `vibe-check` 不负责 Issue 创建治理。

> 项目命令参考见 `skills/vibe-instruction/SKILL.md`

## 核心原则

- **不重造轮子**：直接调用 `gh` CLI 以及最小必要的 `vibe3 task status` 命令。
- **治理先行**：创建前必先查重，必先匹配模板。
- **署名必须**：Issue 创建后必须记录创建者信息，符合 [署名规范](../../docs/standards/authorship-standard.md)。
- **先读 shell 输出**：先读取 `gh` / `vibe3` 输出，再做编排判断。
- **只做 intake，不做排期**：Issue 创建后是否进入规划、何时进入版本窗口，由 `vibe-roadmap` 决定。
- **自动队列只解释，不在此决策**：若用户追问”它之后会不会被自动处理、排在什么位置”，可以读取 `uv run python src/vibe3/cli.py task status` 解释当前 ready queue 事实，但不在 `vibe-issue` 中决定顺位。
- **进入执行现场属于后续阶段**：创建完成后，若要做版本规划转给 `vibe-roadmap`；若用户已明确要人工开工，则转给 `vibe-new`。
- **范围先定义**：若采用主 issue / sub-issue 结构，必须先写清主 issue 的治理母题与范围边界。
- **依赖必须显式**：草稿中出现的依赖引用必须解析并标准化到 `## Dependencies` section。
- **Scope 必须自检**：命中 epic 信号的 issue 必须触发拆分询问或写入 `## Scope estimate`。

## 使用逻辑

### Step 1: 确定意图与模板

- 用户可直接运行 `/vibe-issue` 进入引导；若已确定标题，可运行 `/vibe-issue create "<标题>"` 跳过首轮澄清。
- Skill 扫描 `.github/ISSUE_TEMPLATE/*.md`。
- 如果没有指定模板，主动询问用户是 Bug 还是 Feature。
- 获取对应模板的 fields。

### Step 2: 智能查重 (Semantic Check)

- 运行 `gh issue list --search "<标题>" --state all  number,title,state`。
- 分析搜索结果：
  - **高相似度**：展示重复 Issue，建议用户在原 Issue 下评论或合并。
  - **低相似度**：继续创建流程。

### Step 3: 上下文检查

- 必须先运行 `uv run python src/vibe3/cli.py task status --all --check` 检查是否已有相关的活跃 flow / task 绑定。
- 如果 Issue 标题与某个 Task 匹配，只记录上下文供后续参考。
- task 只解释为执行记录，不把 issue 直接当作本地 task，也不在这里决定排期。

### Step 3.5: 依赖识别

扫描用户草稿/输入中潜在的依赖引用，识别模式包括：
- `#<数字>`（如 `#1097`、`#42`）
- 关键词：`Depends on`、`blocked by`、`基于`、`依赖`、`依赖 #`、`depends on #`

若发现潜在依赖：
1. 用 `gh issue view <issue_number> --json number,title,state` 确认目标 issue 状态
2. 若 issue 不存在：
   - 提示用户「依赖引用无效: #<number> 不存在，请检查编号是否正确」
3. 若 issue 已关闭：
   - 提示用户「依赖已满足: #<number> 已完成，不必重复登记」
4. 若 issue 存在且 open：引导用户把依赖标准化写入 issue body 的 `## Dependencies` section
   - 格式：一行一条 `- Depends on #<id> — <短描述>`
   - 示例：`- Depends on #1097 — 统一依赖语义`

若草稿中未提及任何依赖，跳过此步骤。

> **注意**: 不在此阶段写 `flow_issue_links`，那是 `vibe3 flow bind --role dependency` 的职责。这里只确保 issue body 有标准化的 `## Dependencies` section 供下游读取。

### Step 4: 填充与润饰

- 引导用户补充模板中缺失的关键信息。
- 基于 AI 建议合适的 Labels。
- 为保证后续 intake 链路可识别该 Issue，按当前仓库约定补充最小必要标签；`bug`、`enhancement`、`vibe-task` 等标签按模板和场景决定。
- intake 标签不等于已完成 roadmap placement；是否进入版本窗口、如何排序，仍由 `vibe-roadmap` / `vibe-orchestra` 在后续阶段处理。

### Step 4.5: Scope 自检与主/子 Issue 结构判断

#### Scope 自检触发条件

扫描标题和 body，任一命中即视为 epic 候选：

**标题信号**（包含以下任一聚合词）：
- `审查`、`总览`、`清理`、`统一`、`重构所有`、`重构.*模块`、`全面`、`全量`

**Body 信号**：
- 提到 `>N 个文件`、`>M 个模块`、`N+ 个`、`全量` 等量化范围描述
- body 列出 >= 3 个独立子任务（编号列表或 checkbox 列表项 >= 3）

**命中后的行为**：
1. 明确询问用户：「这个 issue 看起来 scope 较大，建议拆为主 issue + sub-issues 结构。是否要建主/子结构？」
2. 若用户确认拆分：
   - 当前 issue 作为主 issue，建议添加 `roadmap/rfc` 标签
   - body 写入 `## Sub-issues` section（留空模板，格式见下方「标准 Section」）
   - 引导用户单独触发 `/vibe-issue` 创建每个 sub-issue
3. 若用户坚持单 issue：
   - body 写入 `## Scope estimate` section，记录范围预估（文件数/模块数/预期工作量）
   - 便于 roadmap-intake 后续判断

#### 现有主/子结构判断

若当前仓库已存在主 issue / sub-issue 结构，先确认主 issue 是否已经表达：
- 治理母题
- 范围边界
- 哪类问题允许继续追加

若新问题仍属于该治理母题，且没有超出原范围，可继续作为 sub-issue 追加。
若新问题已经超出原范围，必须新建独立 issue，不得无限挂靠在旧主 issue 下。

这一步属于 skill/workflow 判断，不属于 shell runtime、`vibe flow bind` 或 execution record 逻辑。

### Step 5: 提交与收口

- 执行 `gh issue create --title "<标题>" --body "<润色后的内容>" --label "<labels>"`。
- 创建成功后，输出 Issue 链接与建议下一步。
- 若需要进入版本规划，交给 `vibe-roadmap` 继续处理。
- 若用户已经明确要人工接手当前 issue，则转给 `vibe-new` 进入执行现场。
- 若用户只是在问自动治理下它将如何被消费，可以补充读取 `uv run python src/vibe3/cli.py task status` 来解释当前 queue 事实，但不在这里决定最终顺位。
- 输出成功提示及 Issue 链接。

## Issue Body 标准 Section

以下 section 由 `vibe-issue` 维护，是下游 agent（roadmap-intake / manager / dispatcher）消费的真源：

### `## Dependencies`

记录跨 issue 依赖关系。

- **格式**: 一行一条 `- Depends on #<id> — <短描述>`
- **写入者**: `vibe-issue` 在 Step 3.5 引导用户确认并写入
- **消费者**: roadmap-intake 读取依赖关系，dispatcher 用于依赖方向判断
- **示例**:
  ```markdown
  ## Dependencies
  - Depends on #1097 — 统一依赖语义
  - Depends on #1050 — 基础架构重构
  ```

### `## Sub-issues`

记录主 issue 下的子任务清单。

- **格式**: 一行一条 `- [ ] #<id> — <子任务短描述>`（checkbox 格式）
- **写入者**: 用户确认拆分后，`vibe-issue` 写入空模板；sub-issue 创建后回填
- **消费者**: manager 读取子任务完成进度，roadmap-intake 判断主 issue scope
- **示例**:
  ```markdown
  ## Sub-issues
  - [ ] #1099 — 子任务 A：核心逻辑重构
  - [ ] #1100 — 子任务 B：测试覆盖更新
  ```

### `## Scope estimate`

记录 scope 自检结果（仅单 issue 模式写入）。

- **格式**: 自由文本，建议包含预估文件数/模块数/工作量级别
- **写入者**: 用户拒绝拆分但 issue 命中 epic 信号时，`vibe-issue` 引导用户填写
- **消费者**: roadmap-intake 用于判断是否应在 intake 阶段拦截过大 scope
- **示例**:
  ```markdown
  ## Scope estimate
  - 预估影响: ~15 个文件, 3 个模块
  - 工作量: 中等（预计 2-3 个 flow）
  ```

**注意**: 这些 section 是 issue body 的一部分，不由 `flow_issue_links` 或任何本地存储替代。
下游 agent 应通过 `gh issue view <id> --json body` 读取。

## 对象边界

- `GitHub issue`: 需求来源与讨论入口
- `task`: 执行记录语义，由 `vibe-task` / shell 流程负责，通过 `uv run python src/vibe3/cli.py task status --all --check` 等命令观察
- `flow`: execution record 的运行时现场，不属于 `vibe-issue` 直接管理范围

## Failure Handling

- 若 `gh` 未登录：提示用户进行授权。
- 若没有模板文件：使用内置的基础 markdown 结构。

## Handoff 记录

若发现问题，运行 `vibe3 handoff append` 记录：

```bash
uv run python src/vibe3/cli.py handoff append "vibe-issue: Issue created" --actor vibe-issue --kind milestone
```

```markdown
## Issues Found

- type: <flow|doc|command|other>
- severity: <low|medium|high>
- description: <问题描述>
- context: <发现场景>
- suggestion: <改进建议（可选）>
```

详细规则见 `docs/standards/v3/handoff-governance-standard.md` 第 6 节。
