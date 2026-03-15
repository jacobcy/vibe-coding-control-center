---
document_type: plan
title: Phase 01 - CLI Skeleton & Contract
status: draft
author: Claude Sonnet 4.6
created: 2026-03-15
last_updated: 2026-03-15
related_docs:
  - docs/v3/plans/v3-rewrite-plan.md
  - docs/v3/implementation/02-architecture.md
  - docs/v3/implementation/03-coding-standards.md
---

# Phase 01: CLI Skeleton & Contract

**Goal**: Establish the `vibe3` entry point and the dispatching logic to domain managers.

## 1. Context Anchor (Optional)
If you require more than technical scope, refer to the [Vibe 3.0 Master Plan](v3-rewrite-plan.md).

## 2. Pre-requisites (Executor Entry)
- [ ] Working Directory is the project root.
- [ ] No `bin/vibe3` processes are running in the background.

## 2. Directory Structure

```text
bin/vibe3 (Executable Shell)
├── lib3/vibe.sh (Router Logic)
└── scripts/python/vibe_core.py (Python Entry)
```

## 2. CLI Contract Requirements

### Domain Dispatching
Must support the following subcommands with `--help` output:
- `vibe3 flow {new|bind|show|status}`
- `vibe3 task {list|show|link}`
- `vibe3 pr {draft|show|ready|merge}`

### Global Flags
- `--json`: Force JSON output to STDOUT.
- `-y / --yes`: Skip all interactive prompts.

## 3. Technical Implementation

- **Shell Layer**: `bin/vibe3` should proxy arguments to `lib3/vibe.sh`.
- **Python Bridge**: Use `argparse` in `vibe_core.py` to handle nested subcommands.
- **Error Codes**: Use standard Unix exit codes (0 for success, non-zero for errors).

## 4. Acceptance Criteria (Command-Only)

- [ ] `vibe3 flow --help` exit code is 0.
- [ ] `vibe3 task --help` exit code is 0.
- [ ] `vibe3 --json flow status` returns a valid JSON object (even if empty).
- [ ] `mypy scripts/python/vibe_core.py --strict` passes.

## 5. Handoff for Executor 02
- [ ] Ensure `scripts/python/vibe_core.py` contains basic `argparse` stubs for `flow`, `task`, and `pr`.
- [ ] Log the completion status in `.agent/context/task.md` (or equivalent).
