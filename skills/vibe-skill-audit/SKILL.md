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

- `skills/` 是 Vibe 自有 skill 定义的唯一源码；`.agent/skills/` 只是运行时链接层。见 `docs/standards/skill-standard.md`。
- 共享状态相关写入只能通过真实 `bin/vibe` 命令完成；不要在 skill 中直接改 `.git/vibe/*.json`。见 `docs/standards/command-standard.md` 和 `docs/standards/shell-capability-design.md`。
- 术语定义与边界语义只引用真源，不在本 skill 中复述。术语见 `docs/standards/glossary.md`，动作词默认语义见 `docs/standards/action-verbs.md`。
- 触发时机、合理介入范围与相邻 skill 冲突裁决以 `docs/standards/skill-trigger-standard.md` 为准。
- 如果需要的 Shell 能力不存在，结论应为 `Capability Gap`，而不是在 skill 文案中发明 workaround。

## Truth Sources

When the skill touches the corresponding semantic area, cite these files directly:

- `docs/standards/glossary.md`
- `docs/standards/action-verbs.md`
- `docs/standards/skill-standard.md`
- `docs/standards/command-standard.md`
- `docs/standards/shell-capability-design.md`
- `docs/standards/git-workflow-standard.md`
- `docs/standards/worktree-lifecycle-standard.md`

If the target skill only manages local installation or runtime linking, only cite the subset that actually governs that behavior.

引用原则：

- 只引用与当前语义范围直接相关的标准文件。
- 引用标准时优先说“以某标准为准”，不要在 skill 里再展开第二套解释。
- 如果为了说明边界必须举例，例子也只能用于帮助理解，不能取代标准定义。

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
2. Check whether it asks the agent to use real `bin/vibe` commands that exist today.
3. Check whether it turns Shell audit commands into hidden repair commands.
4. Check whether it paraphrases standards so loosely that `roadmap`, `task`, `flow`, `workflow`, `branch`, or `worktree` become ambiguous.
5. Check whether a newer standards file likely invalidates part of the skill text.

## Output Contract

Report findings in four buckets:

- `Blocking`: direct truth-source violation or shared-state bypass
- `Missing Reference`: a required standards citation is absent
- `Capability Gap`: the skill depends on a `bin/vibe` command shape that does not exist
- `Drift Warning`: a cited standards file appears newer than the skill and may require review

When there are no findings, say that explicitly and state which checks were run.
