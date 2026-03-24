# Vibe Skill Review Checklist

Use this checklist when creating or auditing any `skills/vibe-*/SKILL.md`.

## 1. Boundary Checks

- Does the skill tell the agent to edit `.git/vibe/*.json` directly?
- Does it treat `.agent/context/task.md` as shared truth instead of local context?
- Does it ask the skill layer to do hidden workflow logic that belongs in Shell or standards?

Any "yes" is `Blocking`.

## 2. Standards Mapping

### Always expected for Vibe governance language

- `docs/standards/glossary.md`
- `docs/standards/action-verbs.md`
- `docs/standards/v3/skill-standard.md`

### Required when the skill invokes `bin/vibe` shared-state commands

- `docs/standards/v3/command-standard.md`
- `docs/standards/v3/python-capability-design.md`

### Required when the skill discusses current delivery flow semantics

- `docs/standards/v3/git-workflow-standard.md`
- `docs/standards/v3/worktree-lifecycle-standard.md`

## 3. Command Reality Checks

- Is every `bin/vibe <domain>` command real in `bin/vibe`?
- If a subcommand is named, does it appear in that domain's help output?
- If an option is named, can the current CLI surface plausibly support it?

If not, report `Capability Gap` instead of improvising.

## 4. Drift Checks

- Is the governing standards file newer than the target skill?
- Is the skill still using older wording such as redefining `flow`, `task`, or `roadmap current`?
- Does the skill cite standards only superficially while still keeping a parallel definition?
- Does the skill use routing phrases that turn `worktree` into the runtime subject, such as “which worktree to enter next”, “进入哪个 worktree”, or “继续当前 worktree 绑定的 task”, instead of describing `flow` as the runtime container and `worktree` only as the physical carrier?

If review is needed but not conclusively broken, report `Drift Warning`.
