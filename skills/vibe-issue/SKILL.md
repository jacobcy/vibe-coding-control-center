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

### Step 4: 填充与润饰

- 引导用户补充模板中缺失的关键信息。
- 基于 AI 建议合适的 Labels。
- 为保证后续 intake 链路可识别该 Issue，按当前仓库约定补充最小必要标签；`bug`、`enhancement`、`vibe-task` 等标签按模板和场景决定。
- intake 标签不等于已完成 roadmap placement；是否进入版本窗口、如何排序，仍由 `vibe-roadmap` / `vibe-orchestra` 在后续阶段处理。

### Step 4.5: 判断是否继续挂在现有主 issue 下

- 若当前仓库已存在主 issue / sub-issue 结构，先确认主 issue 是否已经表达：
  - 治理母题
  - 范围边界
  - 哪类问题允许继续追加
- 若新问题仍属于该治理母题，且没有超出原范围，可继续作为 sub-issue 追加。
- 若新问题已经超出原范围，必须新建独立 issue，不得无限挂靠在旧主 issue 下。
- 这一步属于 skill/workflow 判断，不属于 shell runtime、`vibe flow bind` 或 execution record 逻辑。

### Step 5: 提交与收口

- 执行 `gh issue create --title "<标题>" --body "<润色后的内容>" --label "<labels>"`。
- 创建成功后，输出 Issue 链接与建议下一步。
- 若需要进入版本规划，交给 `vibe-roadmap` 继续处理。
- 若用户已经明确要人工接手当前 issue，则转给 `vibe-new` 进入执行现场。
- 若用户只是在问自动治理下它将如何被消费，可以补充读取 `uv run python src/vibe3/cli.py task status` 来解释当前 queue 事实，但不在这里决定最终顺位。
- 输出成功提示及 Issue 链接。

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
