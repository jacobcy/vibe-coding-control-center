# Merge Directive: Issue #2022

## Task
Prepare commit message and create PR for the test selector fix.

## Commit Guidelines
- Title: `fix(analysis): exclude __init__.py from test selection in pre-push hook`
- Body should explain:
  - Problem: test selector incorrectly included __init__.py files
  - Solution: Added exclusion in both code paths (is_v3_test_file + source-to-test mapping)
  - Impact: Eliminates misleading "no tests ran" warning
- Reference: Closes #2022

## PR Requirements
- Base branch: main
- Title: Same as commit title
- Body should include:
  - Summary of the fix
  - Test results (129 analysis tests pass)
  - Reference to issue #2022

## Quality Checks
- All tests already pass (verified in execution phase)
- Type checking clean (mypy)
- Linting clean (ruff)
- No additional changes needed

## Scope
- Single focused fix
- Low risk
- No breaking changes
