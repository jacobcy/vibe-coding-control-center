---
name: vibe-skill
description: Create, update, review, or audit Vibe project skills under `skills/` when the user wants a Vibe-specific skill workflow rather than a generic skill. Use for: creating a new `vibe-*` skill, tightening an existing skill's Shell boundary, checking whether a skill cites the correct `docs/standards/*` truth sources, verifying referenced `bin/vibe` commands are real, or warning when standards have drifted ahead of a skill.
---

# Vibe Skill

## Overview

Use this skill to govern Vibe-native skills. It wraps generic skill creation with Vibe's stricter rules around Shell boundaries, standards citations, and flow lifecycle semantics.

Read [review-checklist.md](./references/review-checklist.md) before substantial work. Use the checklist both when creating a new skill and when auditing an existing one.

## Hard Boundary

- Treat `skills/` as the only canonical source for Vibe-owned skill definitions.
- Do not treat `.agent/skills/` as editable source; it is runtime linkage only. See `docs/standards/skill-standard.md`.
- Do not edit `.git/vibe/*.json` directly from a skill workflow. Shared-state writes must go through real `bin/vibe` subcommands. See `docs/standards/command-standard.md` and `docs/standards/shell-capability-design.md`.
- Do not restate term definitions that already belong in `docs/standards/glossary.md` or action semantics that belong in `docs/standards/action-verbs.md`.
- If a required Shell capability is missing, report `Capability Gap` instead of inventing a direct-file workaround.

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

## Mode 1: Create Or Update A Vibe Skill

1. Confirm the skill belongs under `skills/` and is not just an update to `skills/vibe-skills/`.
2. If creating from scratch, initialize the folder with the shared initializer:
   ```bash
   python3 /Users/jacobcy/.codex/skills/.system/skill-creator/scripts/init_skill.py <skill-name> --path skills --resources scripts,references --interface display_name="..." --interface short_description="..." --interface default_prompt="Use $<skill-name> ..."
   ```
3. Replace template text with Vibe-specific guidance:
   - keep the trigger description precise
   - state Shell boundary explicitly
   - cite the governing standards instead of redefining them
4. Add only the minimum supporting resources actually needed. Prefer one checklist/reference file over many thin docs.
5. Validate structure:
   ```bash
   python3 /Users/jacobcy/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/<skill-name>
   ```
6. If the skill contains audit or deterministic checks, add or update automated tests before claiming completion.

## Mode 2: Review Or Audit An Existing Vibe Skill

Run the repository-local audit helper first:

```bash
bash skills/vibe-skill/scripts/audit-skill-references.sh skills/<target>/SKILL.md
```

Then inspect the target skill with this order:

1. Check whether the skill cites the right standards for its semantic scope.
2. Check whether it asks the agent to use real `bin/vibe` commands that exist today.
3. Check whether it turns Shell audit commands into hidden repair commands.
4. Check whether it confuses `roadmap`, `task`, `flow`, `workflow`, `branch`, or `worktree`.
5. Check whether a newer standards file likely invalidates part of the skill text.

## Output Contract

Report findings in four buckets:

- `Blocking`: direct truth-source violation or shared-state bypass
- `Missing Reference`: a required standards citation is absent
- `Capability Gap`: the skill depends on a `bin/vibe` command shape that does not exist
- `Drift Warning`: a cited standards file appears newer than the skill and may require review

When there are no findings, say that explicitly and state which checks were run.
