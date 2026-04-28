---
document_type: test-docs
title: Vibe Center Test Suite Documentation
status: active
author: Claude Sonnet 4.5
created: 2026-03-13
last_updated: 2026-04-27
related_docs:
  - docs/standards/doc-text-test-governance.md
---

# Vibe Center Test Suite

## Test Categories

### V3 Test Suite

Tests that verify the primary Python orchestration/runtime in `tests/vibe3/`.

**Location**: `tests/vibe3/`

**Run**:
```bash
# Run all V3 tests
uv run pytest tests/vibe3

# Run focused V3 subsets
uv run pytest tests/vibe3/commands
uv run pytest tests/vibe3/services
```

**Purpose**: Validate the V3 execution chain, shared-state services, orchestration logic, and command behavior.

### Shell Compatibility Tests

Tests that verify shell command behavior, output, exit codes, and side effects for the V2 compatibility layer.

**Location**: `tests/vibe2/`

**Run**:
```bash
# Run all shell compatibility tests
bats tests/vibe2/

# Run specific test suites
bats tests/vibe2/skills/          # Skills behavior tests
bats tests/vibe2/flow/            # Flow command behavior tests
bats tests/vibe2/roadmap/         # Roadmap command behavior tests
bats tests/vibe2/task/            # Task command behavior tests
bats tests/vibe2/contracts/       # Contract tests
bats tests/vibe2/helpers/         # Helper function tests
bats tests/vibe2/integration/     # Integration tests
bats tests/vibe2/tools/           # Tool script tests
```

**Purpose**: Verify that `vibe` shell commands and helpers continue to work as the compatibility surface.

### Documentation Regression Rules

Documentation semantic locks are governed separately. No dedicated checked-in suite is currently present.

**Governance**: See [Doc-Text Test Governance Standard](../docs/standards/doc-text-test-governance.md)

## Running All Tests

```bash
# Run all tests in V3-first order
uv run pytest tests/vibe3
bats tests/vibe2/

# Run a specific V3 test file
uv run pytest tests/vibe3/commands/test_check_command.py

# Run a specific shell test file
bats tests/vibe2/skills/test_skills.bats

# Run with verbose output
uv run pytest -q tests/vibe3/commands/test_check_command.py
```

## Test Structure

```
tests/
├── vibe3/                     # Vibe 3.x test suite (Python)
│   ├── agents/
│   ├── analysis/
│   ├── clients/
│   ├── commands/
│   ├── domain/
│   ├── environment/
│   ├── execution/
│   ├── hooks/
│   ├── integration/
│   ├── manager/
│   ├── models/
│   ├── orchestra/
│   ├── prompts/
│   ├── roles/
│   ├── runtime/
│   ├── services/
│   └── ui/
└── vibe2/                     # Vibe 2.x compatibility suite (shell)
    ├── contracts/             # Contract tests
    │   ├── check_help.sh
    │   ├── test_flow_contract.bats
    │   ├── test_github_project_bootstrap.bats
    │   ├── test_keys_contract.bats
    │   ├── test_roadmap_contract.bats
    │   ├── test_shared_state_contracts.bats
    │   ├── test_vibe_check.bats
    │   ├── test_vibe_contract.bats
    │   └── test_worktree_alias.bats
    ├── flow/                  # Flow command behavior tests
    │   ├── test_flow_bind_done.bats
    │   ├── test_flow_help_runtime.bats
    │   ├── test_flow_lifecycle.bats
    │   ├── test_flow_pr_linking.bats
    │   └── test_flow_pr_review.bats
    ├── helpers/               # Helper function tests
    │   └── test_utils.bats
    ├── integration/           # Integration tests
    │   ├── test_install.bats
    │   ├── test_install_gh_noninteractive.bats
    │   ├── test_serena_gate.bats
    │   └── test_vibe_integration.bats
    ├── roadmap/               # Roadmap command behavior tests
    │   ├── test_roadmap_query.bats
    │   ├── test_roadmap_remote_dependency.bats
    │   ├── test_roadmap_status_render.bats
    │   ├── test_roadmap_sync_intake.bats
    │   ├── test_roadmap_sync_linking.bats
    │   └── test_roadmap_write_audit.bats
    ├── skills/                # Skills behavior tests
    │   ├── test_review_skills.bats
    │   ├── test_skills.bats
    │   └── test_vibe_skill_audit.bats
    ├── task/                  # Task command behavior tests
    │   ├── test_task_core.bats
    │   ├── test_task_count_by_branch.bats
    │   ├── test_task_ops.bats
    │   ├── test_task_render.bats
    │   └── test_task_sync.bats
    └── tools/                 # Tool script tests
        └── test_metrics.bats
```

## Writing New Tests

### V3 Tests

Add to the appropriate `tests/vibe3/` subdirectory based on the layer under test:

- `tests/vibe3/commands/` for CLI behavior
- `tests/vibe3/services/` for orchestration and business logic
- `tests/vibe3/runtime/`, `tests/vibe3/execution/`, `tests/vibe3/orchestra/` for runtime flow behavior

### Shell Compatibility Tests

Add to the appropriate `tests/vibe2/` subdirectory based on the shell surface under test:

- `tests/vibe2/skills/` for skill behavior
- `tests/vibe2/flow/` for flow lifecycle and state transitions
- `tests/vibe2/roadmap/` for roadmap behavior
- `tests/vibe2/task/` for task command behavior
- `tests/vibe2/contracts/` for command contracts and invariants
- `tests/vibe2/helpers/` for utility helpers
- `tests/vibe2/integration/` for install and integration coverage
- `tests/vibe2/tools/` for tool script behavior

### Documentation Regression Rules

If documentation semantic locks are needed in the future, follow [Doc-Text Test Governance Standard](../docs/standards/doc-text-test-governance.md) and place them under `tests/doc-text/`.

## Test Conventions

### Naming Conventions

**V3 Tests**:
- Pattern: `<area> <action> <expected-result>`
- Example: `check command surfaces incomplete state before exit`

**Shell Compatibility Tests**:
- Pattern: `<command> <action> <expected-result>`
- Example: `vibe skills check is repo-rooted even when run from a subdirectory`

### Test Independence

- Each test must be able to run in isolation
- Use `setup()` function to initialize test environment
- Clean up any side effects in `teardown()` if needed
- Do not depend on execution order

### Assertions

- Use `pytest` assertions for V3 tests
- Use Bats assertions for shell compatibility tests: `[ "$status" -eq 0 ]`, `[[ "$output" =~ pattern ]]`
- Prefer specific assertions over generic ones
- Add meaningful failure messages when helpful

## CI Integration

Tests are automatically run in CI:

```yaml
test-v3:
  script:
    - uv run pytest tests/vibe3

test-shell:
  script:
    - bats tests/vibe2/
```

## Troubleshooting

### Common Issues

**V3 test fails with missing dependency**:
- Ensure `uv sync` completed successfully
- Re-run `uv run pytest tests/vibe3`

**Shell compatibility test fails unexpectedly**:
- Check whether the shell surface or invocation path changed
- Re-run the specific Bats file with `bats -t`

**Behavior test fails intermittently**:
- Check for race conditions or timing issues
- Ensure test isolation (no shared state)
- Verify mock data is consistent

### Getting Help

- Review [Doc-Text Test Governance Standard](../docs/standards/doc-text-test-governance.md)
- Consult existing tests for patterns and conventions

## Related Documentation

- [Doc-Text Test Governance Standard](../docs/standards/doc-text-test-governance.md)
- [Project Glossary](../docs/standards/glossary.md)
- [CLAUDE.md - Hard Rule #10](../CLAUDE.md)
