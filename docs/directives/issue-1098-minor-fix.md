[manager] MINOR verdict fix required

## Quality Review Summary

**Audit Ref**: (audit report not created — MINOR fix scope)
**Verdict**: MINOR

### Finding

Step 3.5 in `skills/vibe-issue/SKILL.md` conflates two different scenarios:
- "issue不存在" (issue doesn't exist in database)
- "issue已关闭" (issue is closed/completed)

Both cases use the same message: "提示用户该依赖已解决或无效,不必登记"

These are **semantically different**:
- **Closed issue**: Dependency already satisfied (positive state, completed work)
- **Non-existent issue**: Invalid reference (error state, should alert user)

### Fix Required

Modify the dependency handling logic to distinguish these cases:

```markdown
# Current (conflated):
- 如果 issue 不存在或已关闭:
  - 提示用户"该依赖已解决或无效,不必登记"

# Expected (distinguished):
- 如果 issue 不存在:
  - 提示用户"依赖引用无效: #<number> 不存在,请检查编号是否正确"
- 如果 issue 已关闭:
  - 提示用户"依赖已满足: #<number> 已完成,不必重复登记"
```

### Execution Instructions

1. Read current implementation: `skills/vibe-issue/SKILL.md` Step 3.5 dependency handling
2. Split the conditional logic into two separate cases
3. Update user messages to distinguish semantics
4. Verify the change doesn't break step ordering
5. Write brief report in handoff

### Scope

- **Files to modify**: `skills/vibe-issue/SKILL.md` only
- **Lines**: Step 3.5 dependency handling (approximately 2-4 lines changed)
- **No other changes needed**: All other aspects pass review

### Quality Criteria

- Two distinct messages for two different scenarios
- Messages clearly communicate the semantic difference
- User experience improved (less confusion)
- No change to overall logic flow
