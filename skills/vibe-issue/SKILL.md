---
name: vibe-issue
description: Use when the user wants to create, draft, deduplicate, or refine a GitHub issue for this repo, asks for issue intake/governance before roadmap placement, or mentions "/vibe-issue", "创建 issue", "提 issue", "issue 查重", or "补 issue 模板".
---

# /vibe-issue - 智能 Issue 助手

该技能负责引导用户创建高质量的 GitHub Issue，并确保其与项目路线图同步。

语义边界：

- `vibe-issue` 负责 Issue intake、模板补全、查重、标签与创建。
- `vibe-roadmap` 负责 Issue 已存在之后的版本规划与优先级归类。
- `vibe-task` 与 `vibe-check` 不负责 Issue 创建治理。

标准真源：

- 术语与默认动作语义以 `docs/standards/glossary.md`、`docs/standards/action-verbs.md` 为准。
- Skill 与 Shell 边界以 `docs/standards/skill-standard.md`、`docs/standards/command-standard.md`、`docs/standards/shell-capability-design.md` 为准。
- 触发时机与相邻 skill 分流以 `docs/standards/skill-trigger-standard.md` 为准。
- 若涉及 worktree / flow 生命周期语义，以 `docs/standards/git-workflow-standard.md`、`docs/standards/worktree-lifecycle-standard.md` 为准。

## 核心原则

- **不重造轮子**：直接调用 `gh` CLI 和 `vibe roadmap` 命令。
- **治理先行**：创建前必先查重，必先匹配模板。
- **自动对齐**：自动将 Issue 映射为 Roadmap Item。

## 使用逻辑

### Step 1: 确定意图与模板

- 用户可直接运行 `/vibe-issue` 进入引导；若已确定标题，可运行 `/vibe-issue create "<标题>"` 跳过首轮澄清。
- Skill 扫描 `.github/ISSUE_TEMPLATE/*.md`。
- 如果没有指定模板，主动询问用户是 Bug 还是 Feature。
- 获取对应模板的 fields。

### Step 2: 智能查重 (Semantic Check)

- 运行 `gh issue list --search "<标题>" --state all --json number,title,state`。
- 分析搜索结果：
  - **高相似度**：展示重复 Issue，建议用户在原 Issue 下评论或合并。
  - **低相似度**：继续创建流程。

### Step 3: Roadmap 检查

- 运行 `vibe roadmap list` 检查是否有类似的心愿。
- 如果 Issue 标题与某个 Roadmap Item 匹配，自动记录其 ID。

### Step 4: 填充与润饰

- 引导用户补充模板中缺失的关键信息。
- 基于 AI 建议合适的 Labels。
- 为保证 `vibe roadmap sync` 可发现该 Issue，创建时必须包含 `vibe-task`；`bug`、`enhancement` 等业务标签可按模板追加。

### Step 5: 提交与收口

- 执行 `gh issue create --title "<标题>" --body "<润色后的内容>" --label "<labels>"`。
- 创建成功后，如果它不在 Roadmap 中，询问用户或自动执行 `vibe roadmap sync`；默认同步路径依赖前一步已附加 `vibe-task`。
- 输出成功提示及 Issue 链接。

## Failure Handling

- 若 `gh` 未登录：提示用户进行授权。
- 若没有模板文件：使用内置的基础 markdown 结构。
