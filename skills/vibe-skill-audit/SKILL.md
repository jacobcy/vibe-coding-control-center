---
name: vibe-skill-audit
description: Use when the user wants to create, update, review, or audit a repo-local Vibe skill under `skills/`, mentions "/vibe-skill-audit", "vibe-skill", "vibe skill", "创建 skill", "审查 skill", "skill 文案", or "自动匹配语义", or needs a Vibe-specific wrapper around `skill-creator` rather than a generic cross-project skill workflow.
---

# /vibe-skill-audit - Vibe Skill Governance

## Overview

Use this skill to govern Vibe-native skills. It wraps generic skill creation with Vibe's stricter rules around Shell boundaries, standards citations, and flow lifecycle semantics.

语义边界：

- 通用、跨项目的 skill 创建方法，以 `skill-creator` 为基线。
- 目标是当前仓库里的 `skills/vibe-*` 时，优先用 `vibe-skill-audit` 做创建、更新、审查和漂移治理；`vibe-skill` 可作为对话层短称。
- `vibe-skills-manager` 只处理 skill 安装、同步、清理与推荐，不负责设计或审查 `skills/vibe-*` 文案。

本 skill 只负责校验和收敛 skill 文案，不负责在这里重新定义 `flow`、`workflow`、`worktree`、`branch`、shared-state 或 Shell 边界语义。相关语义一律引用标准文件。

Read [review-checklist.md](./references/review-checklist.md) before substantial work. Use the checklist both when creating a new skill and when auditing an existing one.

## Hard Boundary

- `skills/` 是 Vibe 自有 skill 定义的唯一源码；`.agent/skills/` 只是运行时链接层。见 `docs/standards/v3/skill-standard.md`。
- 共享状态相关写入只能通过真实 `vibe3` 命令完成；不要在 skill 中直接改 `.git/vibe3/handoff.db`。见 `docs/standards/v3/command-standard.md` 和 `docs/standards/v3/python-capability-design.md`。
- 术语定义与边界语义只引用真源，不在本 skill 中复述。术语见 `docs/standards/glossary.md`，动作词默认语义见 `docs/standards/action-verbs.md`。
- 触发时机、合理介入范围与相邻 skill 冲突裁决以 `docs/standards/v3/skill-trigger-standard.md` 为准。
- 如果需要的 Shell 能力不存在，结论应为 `Capability Gap`，而不是在 skill 文案中发明 workaround。
- 如果 skill 中引用的命令、入口、默认现场读取方式、修复方式已经落后于当前仓库实现，必须视为语义漂移并立即修正文案；不要保留“兼容旧说法”的模糊描述。

## Truth Sources

When the skill touches the corresponding semantic area, cite these files directly:

- `docs/standards/glossary.md`
- `docs/standards/action-verbs.md`
- `docs/standards/v3/skill-standard.md`
- `docs/standards/v3/command-standard.md`
- `docs/standards/v3/python-capability-design.md`
- `docs/standards/v3/git-workflow-standard.md`
- `docs/standards/v3/worktree-lifecycle-standard.md`

If the target skill only manages local installation or runtime linking, only cite the subset that actually governs that behavior.

引用原则：

- 只引用与当前语义范围直接相关的标准文件。
- 引用标准时优先说“以某标准为准”，不要在 skill 里再展开第二套解释。
- 如果为了说明边界必须举例，例子也只能用于帮助理解，不能取代标准定义。

命令对齐原则：

- skill 里写到的 `vibe3` 命令必须与当前 CLI 真实入口一致。
- skill 里写到的“先看现场 / 再审计 / 再修复”顺序必须与当前仓库实际工作流一致。
- 如果仓库已经把某个命令降级成“仅审计”或“仅展示”，skill 不得继续把它写成默认修复入口。
- 如果仓库已经把某个能力迁移到新的命令组，skill 必须直接改成新命令，不保留过时入口作为主路径。

## Semantic Alignment Loop

每次创建、更新或审查 repo-local skill 时，都必须显式执行一轮“skill 与仓库语义对齐”：

1. 找出 skill 里提到的所有 `vibe3` 命令、入口、默认路径、修复动作。
2. 到当前仓库实现核对这些命令是否仍然存在、参数形状是否变化、职责是否迁移。
3. 核对 skill 描述的默认入口是否仍然符合当前推荐工作流。
4. 核对 skill 是否把旧术语、旧命令、旧边界继续当作主路径。
5. 发现漂移就直接改 skill 文案，不要只报 `Drift Warning` 后停下。

这个循环的目标不是“检查 skill 有没有引用标准”，而是“确保 skill 说的话与当前仓库真的一致”。

## Mode 1: Create Or Update A Vibe Skill

1. Confirm the skill belongs under `skills/` and is not just an update to `skills/vibe-skills-manager/`.
2. If creating from scratch, initialize the folder with the shared initializer:
   ```bash
   python3 /Users/jacobcy/.codex/skills/.system/skill-creator/scripts/init_skill.py <skill-name> --path skills --resources scripts,references --interface display_name="..." --interface short_description="..." --interface default_prompt="Use $<skill-name> ..."
   ```
3. Replace template text with Vibe-specific guidance:
   - keep the trigger description precise
   - state Shell boundary explicitly
   - cite the governing standards instead of redefining them
   - when semantics are already defined in standards, replace prose duplication with direct references
   - enumerate every `vibe3` command mentioned in the skill and verify each one against the current repo implementation before keeping it
   - prefer the current default runtime entrypoints rather than preserving old aliases or superseded command flows
4. Add only the minimum supporting resources actually needed. Prefer one checklist/reference file over many thin docs.
5. Validate structure:
   ```bash
   python3 /Users/jacobcy/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/<skill-name>
   ```
6. If the skill contains audit or deterministic checks, add or update automated tests before claiming completion.

## Mode 2: Review Or Audit An Existing Vibe Skill

Run the repository-local audit helper first:

```bash
bash skills/vibe-skill-audit/scripts/audit-skill-references.sh skills/<target>/SKILL.md
```

Then inspect the target skill with this order:

1. Check whether the skill cites the right standards for its semantic scope.
2. Check whether it asks the agent to use real `vibe3` commands that exist today.
3. Check whether those commands still have the same responsibility today, or whether the repo has moved the behavior to another command.
4. Check whether it turns Shell audit commands into hidden repair commands.
5. Check whether it paraphrases standards so loosely that `roadmap`, `task`, `flow`, `workflow`, `branch`, or `worktree` become ambiguous.
6. Check whether a newer standards file or newer command implementation likely invalidates part of the skill text.

重点检查以下漂移类型：

- 过时命令仍被写成主入口
- 展示命令被写成修复命令
- 审计命令被写成自动修复器
- 已迁移的职责仍留在旧 skill 里
- skill 所说的“默认现场读取方式”已经不符合当前仓库习惯

## Output Contract

Report findings in four buckets:

- `Blocking`: direct truth-source violation or shared-state bypass
- `Missing Reference`: a required standards citation is absent
- `Capability Gap`: the skill depends on a `vibe3` command shape that does not exist
- `Drift Warning`: a cited standards file appears newer than the skill and may require review

如果发现的是“skill 继续使用旧命令或旧职责，但当前仓库已有明确新语义”，默认动作不是只报结论，而是直接更新 skill 文案；只有在当前实现本身不清晰时，才保留为 `Drift Warning`。

When there are no findings, say that explicitly and state which checks were run.
