---
name: vibe-commit
description: Review-gated commit and PR-slicing workflow for Vibe projects. Use when the user wants to inspect a dirty worktree, decide what should be committed vs stashed vs discarded, group valid changes into conventional commits, judge whether the branch should produce one PR or multiple PRs, and if necessary create a new flow/branch before proposing PR publication.
category: process
trigger: auto
---

# /vibe-commit - Vibe Commit Workflow

`/vibe-commit` 负责认知层编排，不直接替代 shell 的发布规则。涉及术语、动作词、flow 生命周期、提交署名时，以以下真源为准：

- `docs/standards/glossary.md`
- `docs/standards/action-verbs.md`
- `docs/standards/authorship-standard.md`
- `docs/standards/command-standard.md`
- `docs/standards/git-workflow-standard.md`
- `docs/standards/worktree-lifecycle-standard.md`

## Core Role

你是一个提交与 PR 切片助手。你的职责不是“尽快把当前分支发出去”，而是先确认：

1. 当前工作区是否干净
2. 脏改动里哪些应该提交、哪些应该暂存、哪些应该丢弃
3. 已提交历史适合提一个 PR 还是多个 PR
4. 当前分支语义是否仍然匹配这次要发布的交付目标

只有这些问题都过关后，才进入 PR 草案阶段。

## Workflow

### Step 1: Check Worktree Cleanliness First

先运行：

```bash
git status --short
```

如果工作区不干净，继续收集：

```bash
git diff --stat
git diff --cached --stat
git diff --cached
git diff
```

读取 diff 时保持节制，不要把全量 diff 直接喷到终端。

### Step 2: Classify Dirty Changes

把未提交内容分成三类：

- `commit now`: 属于当前交付目标，应该进入这次发布
- `stash`: 本身有效，但不适合进入当前 commit / 当前 PR
- `discard`: 明显实验残留、误改或与当前目标无关

要求：

- `discard` 必须明确向用户说明原因，再执行删除
- `stash` 只用于“暂不进入当前交付切片”的有效工作，不要把不确定内容直接混入 commit
- 若 dirty changes 横跨多个独立交付目标，先判定“需要多个 PR”，不要急于提交

### Step 3: Group Commits

对 `commit now` 的内容做逻辑分组。每组必须只对应一个独立变更目标。

草拟 Conventional Commit 信息时，按 `docs/standards/authorship-standard.md` 追加 `Co-authored-by`。不要依赖过时的固定路径假设；若需要贡献者名册，应从当前项目可用的任务/上下文记录中读取，读取失败时明确说明证据不足。

在任何 `git commit` 执行前，必须先向用户展示：

- 每个分组包含哪些文件
- 哪些内容会被 stash
- 哪些内容会被 discard
- 每条 commit 草案

### Step 4: Inspect Commit History Before PR Draft

只有工作区清理并提交完成后，才检查历史切片是否适合发 PR。

先读取 shell 真源：

```bash
vibe flow pr --help
```

再读取当前分支相对基线的提交历史，例如：

```bash
git log --oneline <base>..HEAD
```

判断：

- 当前提交历史是否只服务一个交付目标
- 当前分支名是否仍然表达这个交付目标
- 是否已经混入多个应拆开的 PR 切片

### Step 5: Decide One PR Or Multiple PRs

如果满足以下条件，可以继续按单 PR 处理：

- 提交历史只服务一个交付目标
- 当前分支语义与这个目标一致
- `git-workflow-standard.md` 下的 flow/PR 关系没有被破坏

如果不满足，或者明显需要多个 PR：

- 不要继续沿用当前分支直接发 PR
<<<<<<< HEAD
- 使用 `vibe flow new <name> --branch <ref>` 创建新的 flow/branch
=======
- 使用 `vibe flow new <name> --branch <ref>` 创建新的 flow/branch
>>>>>>> ee66d77 (docs(commit): add dirty-worktree and PR-slicing flow)
- 在新的 flow 中迁移当前要发布的那一组改动或 commit
- 再由新分支继续提交与发布

### Step 6: Propose PR Publication

只有在以下条件同时满足时，才能提议发 PR：

- 工作区已干净
- 该发的 commit 都已经完成
- 单 PR / 多 PR 判断已完成
- 若单 PR，当前分支语义适合直接发布

此时才向用户展示 PR 草案，并明确责任边界：

- `/vibe-commit`：认知层分组、判断、草案生成
- `vibe flow pr`：shell 层发布入口与 base 校验真源
- `gh pr create`：底层外部工具，不应越过 shell 规则单独充当真源

如果当前分支不是直接面向 `main` 的最小差异分支，不得默认建议“发往 `main`”；要么给出推断的 `--base <ref>`，要么要求显式指定。

## Restrictions

- 必须遵循 Conventional Commits
- 不得在用户确认前静默执行 `git commit`
- 不得把“是否拆多个 PR”的判断偷换成“先发一个再说”
- 不得把 `stash` 当作垃圾桶，也不得把 `discard` 当作默认处理方式
- 对外始终使用中文
