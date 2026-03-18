---
document_type: test-docs
title: Vibe Center Test Suite Documentation
status: active
author: Claude Sonnet 4.5
created: 2026-03-13
last_updated: 2026-03-14
related_docs:
  - docs/standards/doc-text-test-governance.md
  - tests/doc-text/README.md
---

# Vibe Center Test Suite

## Test Categories

### Behavior Tests

Tests that verify shell command behavior, output, exit codes, and side effects.

**Location**: `tests/` (excluding `tests/doc-text/`)

**Run**:
```bash
# Run all behavior tests
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

**Purpose**: Verify that `vibe` commands and shell functions work correctly.

### Doc-Text Regression Tests

Tests that lock critical documentation semantics and prevent concept drift.

**Location**: `tests/doc-text/`

**Run**:
```bash
# Run all doc-text tests
bats tests/doc-text/

# Run specific test files
bats tests/doc-text/test_terminology_locks.bats
bats tests/doc-text/test_workflow_constraints.bats
```

**Purpose**: Lock critical terminology definitions and workflow constraints in documentation.

**Governance**: See [Doc-Text Test Governance Standard](../docs/standards/doc-text-test-governance.md)

## Running All Tests

```bash
# Run all tests
bats tests/vibe2/

# Run only behavior tests (vibe2)
bats tests/vibe2/

# Run only doc-text tests
bats tests/vibe2/doc-text/

# Run specific test file
bats tests/vibe2/skills/test_skills.bats

# Run with verbose output
bats -t tests/vibe2/skills/test_skills.bats
```

## Test Structure

```
tests/
├── vibe2/                     # Vibe 2.x test suite (shell)
│   ├── contracts/             # Contract tests
│   │   ├── check_help.sh
│   │   ├── test_flow_contract.bats
│   │   ├── test_github_project_bootstrap.bats
│   │   ├── test_keys_contract.bats
│   │   ├── test_roadmap_contract.bats
│   │   ├── test_shared_state_contracts.bats
│   │   ├── test_vibe_check.bats
│   │   ├── test_vibe_contract.bats
│   │   └── test_worktree_alias.bats
│   ├── doc-text/              # Doc-text regression tests (isolated)
│   │   ├── README.md
│   │   ├── test_terminology_locks.bats
│   │   └── test_workflow_constraints.bats
│   ├── flow/                  # Flow command behavior tests
│   │   ├── test_flow_bind_done.bats
│   │   ├── test_flow_help_runtime.bats
│   │   ├── test_flow_lifecycle.bats
│   │   ├── test_flow_pr_linking.bats
│   │   └── test_flow_pr_review.bats
│   ├── helpers/               # Helper function tests
│   │   └── test_utils.bats
│   ├── integration/           # Integration tests
│   │   ├── test_install.bats
│   │   ├── test_install_gh_noninteractive.bats
│   │   ├── test_serena_gate.bats
│   │   └── test_vibe_integration.bats
│   ├── roadmap/               # Roadmap command behavior tests
│   │   ├── test_roadmap_query.bats
│   │   ├── test_roadmap_remote_dependency.bats
│   │   ├── test_roadmap_status_render.bats
│   │   ├── test_roadmap_sync_intake.bats
│   │   ├── test_roadmap_sync_linking.bats
│   │   └── test_roadmap_write_audit.bats
│   ├── skills/                # Skills behavior tests
│   │   ├── test_review_skills.bats
│   │   ├── test_skills.bats
│   │   └── test_vibe_skill_audit.bats
│   ├── task/                  # Task command behavior tests
│   │   ├── test_task_core.bats
│   │   ├── test_task_count_by_branch.bats
│   │   ├── test_task_ops.bats
│   │   ├── test_task_render.bats
│   │   └── test_task_sync.bats
│   └── tools/                 # Tool script tests
│       └── test_metrics.bats
└── vibe3/                     # Vibe 3.x test suite (Python)
    ├── clients/
    └── services/
```

## Writing New Tests

### Behavior Tests

Add to appropriate directory based on tested component:

**Skills Tests** (`tests/vibe2/skills/`):
- Test `vibe skills` command behavior
- Test skill synchronization behavior
- Test skill execution effects

**Flow Tests** (`tests/vibe2/flow/`):
- Test `vibe flow` command behavior
- Test flow lifecycle and state transitions
- Test flow binding and unbinding

**Roadmap Tests** (`tests/vibe2/roadmap/`):
- Test `vibe roadmap` command behavior
- Test roadmap query and status rendering
- Test roadmap sync and intake

**Task Tests** (`tests/vibe2/task/`):
- Test `vibe task` command behavior
- Test task operations and rendering
- Test task synchronization

**Contract Tests** (`tests/vibe2/contracts/`):
- Test command contracts and invariants
- Test shared state contracts
- Test GitHub Project integration contracts
- Test keys, vibe, worktree alias contracts

**Helper Tests** (`tests/vibe2/helpers/`):
- Test utility function behavior
- Test logging functions
- Test helper functions required by aliases

**Integration Tests** (`tests/vibe2/integration/`):
- Test installation scripts
- Test serena gate integration
- Test vibe command integration

**Tools Tests** (`tests/vibe2/tools/`):
- Test metrics script behavior
- Test other tool scripts

### Doc-Text Tests

**Before adding**, ensure you meet entry criteria in [Doc-Text Test Governance Standard](../docs/standards/doc-text-test-governance.md).

Add to `tests/vibe2/doc-text/` with appropriate file name:
- `test_terminology_locks.bats` for terminology definitions
- `test_workflow_constraints.bats` for workflow constraint text
- New files only if justified and within budget (10 files max)

**Must include** in each test:
- Reason comment explaining why this text needs locking
- Entry criterion citation (which scenario from §4.1)
- Alternative considered statement (why not behavior test?)

**Example**:
```bash
# Reason: Lock critical terminology definition to prevent drift
# Entry Criterion: §4.1.1 - Key semantic freeze (terminology definitions)
# Alternative Considered: Behavior test via vibe commands, but terminology
#                         is documentation-level contract, not command behavior
@test "doc-text: glossary.md locks 'repo issue' as GitHub issue term" {
  run rg -n "repo issue.*特指.*GitHub repository issue" "$REPO_ROOT/docs/standards/glossary.md"
  [ "$status" -eq 0 ]
}
```

## Test Conventions

### Naming Conventions

**Behavior Tests**:
- Pattern: `<command> <action> <expected-result>`
- Example: `vibe skills check is repo-rooted even when run from a subdirectory`

**Doc-Text Tests**:
- Pattern: `doc-text: <document-path> locks <semantic-concept>`
- Example: `doc-text: glossary.md locks 'repo issue' as GitHub issue term`

### Test Independence

- Each test must be able to run in isolation
- Use `setup()` function to initialize test environment
- Clean up any side effects in `teardown()` if needed
- Do not depend on execution order

### Assertions

- Use Bats assertions: `[ "$status" -eq 0 ]`, `[[ "$output" =~ pattern ]]`
- Prefer specific assertions over generic ones
- Add meaningful failure messages when helpful

## CI Integration

Tests are automatically run in CI:

```yaml
# Example CI configuration
test-behavior:
  script:
    - bats tests/ --filter '!^tests/doc-text/'

test-doc-text:
  script:
    - bats tests/doc-text/
```

## Troubleshooting

### Common Issues

**Test fails with "command not found"**:
- Ensure `vibe` is in PATH
- Run `source ~/.zshrc` or restart shell

**Doc-text test fails unexpectedly**:
- Check if documentation was modified
- Verify regex pattern matches actual text
- Review if semantic meaning has changed

**Behavior test fails intermittently**:
- Check for race conditions or timing issues
- Ensure test isolation (no shared state)
- Verify mock data is consistent

### Getting Help

- Check [tests/doc-text/README.md](doc-text/README.md) for doc-text test guidelines
- Review [Doc-Text Test Governance Standard](../docs/standards/doc-text-test-governance.md)
- Consult existing tests for patterns and conventions

## Related Documentation

- [Doc-Text Test Governance Standard](../docs/standards/doc-text-test-governance.md)
- [Doc-Text Tests README](doc-text/README.md)
- [Project Glossary](../docs/standards/glossary.md)
- [CLAUDE.md - Hard Rule #10](../CLAUDE.md)