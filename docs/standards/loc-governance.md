# LOC Governance Standard

## Purpose

Define clear, enforceable limits for file size to maintain codebase health, readability, and maintainability.

## Configuration Semantics

### Two-Threshold System

LOC governance uses a two-threshold system with different enforcement levels:

| Threshold | Value | Local Execution | CI Execution |
|-----------|-------|-----------------|--------------|
| `warning_threshold` | 300 lines | Advisory (suggestion) | Allowed (pass) |
| `ci_block_threshold` | 400 lines | Advisory (warning) | **Blocking (fail)** |

### Semantic Definitions

**`warning_threshold: 300`**
- **Purpose**: Advisory limit for maintainability
- **Local**: Shows warning, allows push
- **CI**: Allows merge (does not block)
- **Intent**: "Consider refactoring this file"

**`ci_block_threshold: 400`**
- **Purpose**: Hard limit for CI enforcement
- **Local**: Shows warning, allows push
- **CI**: **Blocks merge** (pipeline fails)
- **Intent**: "This file must be refactored or granted exception"

### Execution Environment Differences

**Local Development (pre-commit/pre-push hooks)**
- Both thresholds are advisory
- Warnings shown but push allowed
- Goal: Provide early feedback without blocking workflow

**CI Environment (GitHub Actions)**
- `warning_threshold`: Allowed (CI passes)
- `ci_block_threshold`: **Enforced** (CI fails).
- Goal: Prevent large files from merging without explicit exception

### Configuration Location

Defined in `config/loc_limits.yaml`:

```yaml
code_limits:
  single_file_loc:
    warning_threshold: 300    # Advisory in local and CI
    ci_block_threshold: 400   # Blocks CI, advisory in local
```

## Exception Management

### When to Request Exception

Files may exceed limits with documented justification:

1. **Core aggregation points** (service orchestration, state machines)
2. **Strongly coupled test suites** (shared fixtures, related scenarios)
3. **External compatibility layers** (API facades, legacy adapters)

### How to Request Exception

Add entry to `config/loc_limits.yaml`:

```yaml
exceptions:
  - path: "src/vibe3/services/example.py"
    limit: 500
    reason: "Clear justification for why this file cannot be split"
```

**Review Process**:
- PR author documents reason in config
- Reviewer evaluates if refactoring is feasible
- If approved, exception is merged with the PR

### Exception Maintenance

- Exceptions should be reviewed periodically
- If file is later refactored, remove exception
- Exceptions are not permanent; they indicate "deferred refactoring"

## Best Practices

### Refactoring Strategies

**When file approaches 300 lines**:
- Extract utilities to separate modules
- Use composition over inheritance
- Split by responsibility (SRP)

**When file exceeds 400 lines**:
- **Must refactor or request exception**
- Identify cohesive subsets that can be extracted
- Consider if file has multiple responsibilities

### Code Organization Principles

1. **Single Responsibility**: Each file should have one clear purpose
2. **Cohesion**: Related functions belong together
3. **Coupling**: Minimize dependencies between files

### Test File Considerations

Test files often need more flexibility:
- Shared fixtures and setup code
- Multiple test scenarios for same component
- Test-specific helpers

Apply same thresholds but consider test-specific exceptions when justified.

## Alignment with Governance Budget

This LOC governance aligns with `.agent/governance.yaml` budget:

```yaml
budgets:
  file_max: 300  # Maps to warning_threshold
```

The `ci_block_threshold: 400` provides buffer for exceptions while maintaining the governance goal of `file_max: 300`.

## Monitoring and Metrics

### Tracking LOC Trends

- Pre-commit hooks provide immediate feedback
- CI enforcement prevents regression
- Periodic audits identify growing files

### Quality Indicators

- **Files under 300 lines**: ✅ Ideal
- **Files between 300-400 lines**: ⚠️ Review for refactoring
- **Files over 400 lines**: ❌ Must refactor or document exception

## References

- Configuration: `config/loc_limits.yaml`
- Hook scripts: `scripts/hooks/check-per-file-loc.sh`, `check-test-file-loc.sh`
- Parser: `scripts/hooks/loc_settings.py`
- Governance budget: `.agent/governance.yaml`
