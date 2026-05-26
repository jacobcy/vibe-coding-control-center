# Execution Directive: Issue #1445

## Context

- **Issue**: #1445 系统改进：强化 PR comment sorting 测试断言
- **Branch**: task/issue-1445
- **Type**: Test enhancement (no production code changes)
- **Priority**: Low
- **Risk**: Very low

## Plan Reference

`docs/plans/issue-1445-strengthen-comment-sorting-assertions.md`

## Execution Summary

Add 6 targeted assertions to 2 existing test functions:
1. **test_none_timestamp_does_not_crash**: 3 position assertions for None-timestamp sorting
2. **test_reviews_sorted_chronologically**: 3 state value assertions for review ordering

## Implementation Steps

Follow the plan exactly:

### Step 1: None-timestamp position assertions
**File**: `tests/vibe3/commands/test_pr_show_sorting.py`
**Test**: `test_none_timestamp_does_not_crash` (lines 167-224)
**Action**: Add 3 assertions after line 223

```python
# Verify None-timestamp entries sort to end
assert result.output.find("None timestamp") > result.output.find("Valid timestamp")
assert result.output.find("None review comment") > result.output.find("Valid review comment")
assert result.output.find("None review") > result.output.find("Valid review")
```

**Validate**: `uv run pytest tests/vibe3/commands/test_pr_show_sorting.py::TestPRShowCommentSorting::test_none_timestamp_does_not_crash -v`

### Step 2: Review state value assertions
**File**: `tests/vibe3/commands/test_pr_show_sorting.py`
**Test**: `test_reviews_sorted_chronologically` (lines 130-166)
**Action**: Add 3 state value assertions after line 165

```python
# Verify review state values are rendered and in chronological order
assert result.output.find("CHANGES_REQUESTED") < result.output.find("COMMENTED")
assert result.output.find("COMMENTED") < result.output.find("APPROVED")
# Verify each review state co-locates with its reviewer
assert result.output.find("reviewer_a") < result.output.find("CHANGES_REQUESTED")
assert result.output.find("reviewer_b") < result.output.find("COMMENTED")
assert result.output.find("reviewer_c") < result.output.find("APPROVED")
```

**Validate**: `uv run pytest tests/vibe3/commands/test_pr_show_sorting.py::TestPRShowCommentSorting::test_reviews_sorted_chronologically -v`

### Step 3: Full validation

Run the complete test suite:
```bash
uv run pytest tests/vibe3/commands/test_pr_show_sorting.py tests/vibe3/commands/test_pr_show.py -v
```

## Quality Requirements

1. **Test execution**: All new and existing tests must pass
2. **No production code**: Do NOT modify any files under `src/vibe3/`
3. **Exact assertions**: Copy the assertions from the plan exactly as written
4. **Line placement**: Add assertions at the exact lines specified in the plan

## Known Limitations

- **Color verification**: The plan correctly notes that full Rich markup color verification is not possible through CliRunner's non-TTY output. The state value assertions provide a practical proxy. This is acceptable and out of scope for this micro-improvement.

## Success Criteria

- All 6 new assertions pass
- All existing tests continue to pass
- No production code modified
- Test coverage improved for comment sorting behavior

## After Implementation

Run tests and verify all pass. Then report completion with:
- Test execution output
- Confirmation that no production code was modified
- Any deviations from the plan (should be none)
