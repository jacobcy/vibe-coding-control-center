# Code Review Policy

## Review Focus

This policy guides code review for the vibe-center project.

### Priority Issues

1. **Correctness** - Logic errors, edge cases, data integrity
2. **Regressions** - Breaking changes, API compatibility
3. **Security** - Authentication, authorization, input validation
4. **Performance** - N+1 queries, memory leaks, resource exhaustion

### Context-Specific Checks

#### Critical Paths (lib/flow, lib/git, src/vibe3/services/)

- State management correctness
- Error handling completeness
- Transaction boundary safety
- Resource cleanup guarantees

#### Public API (bin/vibe, src/vibe3/commands/)

- Backward compatibility
- Input validation
- Clear error messages
- Documentation accuracy

### Output Format

```
path/to/file.py:42 [MAJOR] concise issue description
VERDICT: PASS | MAJOR | BLOCK
```

### Verdict Guidelines

- **PASS**: Code is acceptable, only minor suggestions
- **MAJOR**: Significant issues found, review recommended
- **BLOCK**: Critical issues, must fix before merge

### Review Constraints

- Focus on changed code only
- Consider inspect risk score
- Avoid nitpicking style issues
- Prioritize actionable feedback
