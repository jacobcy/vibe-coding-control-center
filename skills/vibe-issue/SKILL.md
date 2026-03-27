---
name: vibe-issue
description: Use when the user wants to create, draft, deduplicate, or refine a GitHub issue for this repo, asks for issue intake/governance before roadmap placement, or mentions "/vibe-issue", "创建 issue", "提 issue", "issue 查重", or "补 issue 模板".
---

# /vibe-issue - 智能 Issue 助手

该技能负责引导用户创建高质量的 GitHub Issue，并在进入 roadmap 规划前完成 intake 治理。

语义边界：

- `vibe-issue` 负责 Issue intake、模板补全、查重、标签与创建。
- `vibe-issue` 不决定 roadmap 排期，也不创建 task。
- `vibe-roadmap` 负责 Issue 已存在之后的版本规划与优先级归类。
- `vibe-task` 与 `vibe-check` 不负责 Issue 创建治理。

标准真源：

- 术语与默认动作语义以 `docs/standards/glossary.md`、`docs/standards/action-verbs.md` 为准。
- Skill 与 Shell 边界以 `docs/standards/v3/skill-standard.md` 为准。

相关标准文档目录：`docs/standards/`

## 核心原则

- **不重造轮子**：直接调用 `gh` CLI 和 `uv run python src/vibe3/cli.py task` 命令。
- **治理先行**：创建前必先查重，必先匹配模板。
- **先读 shell 输出**：先读取 `gh` / `vibe3` 输出，再做编排判断。
- **只做 intake，不做排期**：Issue 创建后是否进入规划、何时进入版本窗口，由 `vibe-roadmap` 决定。
- **候选资格需要显式同步**：`vibe-task` 表示该 issue 具备进入流程的候选资格；创建后通过 `uv run python src/vibe3/cli.py flow bind` 绑定到 flow，而不是直接变成 execution record。
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

- 必须先运行 `uv run python src/vibe3/cli.py task list` 检查是否已有相关的 task。
- 如果 Issue 标题与某个 Task 匹配，只记录上下文供后续参考。
- task 只解释为执行记录，不把 issue 直接当作本地 task，也不在这里决定排期。

### Step 4: 填充与润饰

- 引导用户补充模板中缺失的关键信息。
- 基于 AI 建议合适的 Labels。
- 为保证后续 intake 链路可识别该 Issue，创建时必须包含 `vibe-task`；`bug`、`enhancement` 等业务标签可按模板追加。
- 附加 `vibe-task` 不等于已完成 roadmap placement；是否推入 GitHub Project、何时纳入版本窗口，仍由 `vibe-roadmap` 决定。

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
- 创建成功后，输出 Issue 链接与建议下一步；若需要进入 roadmap 规划，交给 `vibe-roadmap` 继续处理。
- 输出成功提示及 Issue 链接。

## 对象边界

- `repo issue`: 需求来源与讨论入口
- `task`: execution record，由 `vibe-task` / shell 流程负责，通过 `uv run python src/vibe3/cli.py task` 管理
- `flow`: execution record 的运行时现场，通过 `uv run python src/vibe3/cli.py flow` 管理

## Failure Handling

- 若 `gh` 未登录：提示用户进行授权。
- 若没有模板文件：使用内置的基础 markdown 结构。

## Handoff 记录

完成当前 skill 后，若发现流程、文档或命令问题，需在 `.agent/context/task.md` 记录：

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
