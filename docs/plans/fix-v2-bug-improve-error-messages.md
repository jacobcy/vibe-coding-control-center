# Fix V2 Bug: Improve Error Messages and Help Text

**Issue**: #181
**Type**: Bug Fix
**Scope**: v2 only (minimal changes, no flow changes)

## Goal

Fix 4 usability issues in v2 commands to improve user experience:

1. `vibe task add --spec-standard` - Improve error messages
2. `vibe flow bind --agent` - Relax validation
3. `vibe task add` - Clarify error messages
4. `vibe-start` skill documentation - Update to match reality

## Constraints

- ✅ Only improve help text and error messages
- ✅ Only relax parameter validation
- ❌ Do NOT change workflows or processes
- ❌ Do NOT add new features
- ❌ Do NOT refactor architecture

## Fix Plan

### 1. `vibe task add --spec-standard`

**File**: `lib/task.sh`

**Changes**:
- [ ] Update help text to list supported values
- [ ] Improve error message to show supported values

**Implementation**:
```bash
# Before
✗ Invalid spec standard:

# After
✗ Invalid spec standard: plan
  支持的值: openspec, kiro, superpowers, supervisor
```

---

### 2. `vibe flow bind --agent`

**File**: `lib/flow.sh`

**Changes**:
- [ ] Relax validation to accept any string
- [ ] Or improve error message to show supported values

**Implementation**:
```bash
# Option 1: Accept any string (recommended)
--agent <name>  Accept any string value

# Option 2: Show supported values in error
✗ Unsupported agent: "Claude Sonnet 4.6"
  支持的预定义值: claude, codex, human
  或者不指定 --agent 参数
```

---

### 3. `vibe task add` error message

**File**: `lib/task.sh`

**Changes**:
- [ ] Clarify that users can skip roadmap item and use plan directly
- [ ] Show both options in error message

**Implementation**:
```bash
# Before
✗ Task creation requires a plan binding. Create or select a roadmap item...

# After
✗ Task creation requires a plan binding.

  选项 1: 从已有 plan 创建（推荐）
    vibe task add "Test" --issue 180 \
      --spec-standard openspec \
      --spec-ref docs/plans/example.md

  选项 2: 从 roadmap item 创建
    vibe roadmap add "Test" --issue 180
    vibe task add "Test" --spec-standard openspec --spec-ref <plan-path>
```

---

### 4. `vibe-start` skill documentation

**File**: `skills/vibe-start/SKILL.md`

**Changes**:
- [ ] Add "Prerequisites" section
- [ ] Clarify manual steps required before execution
- [ ] Update workflow to match reality

**Implementation**:
```markdown
## Prerequisites

Before running vibe-start, ensure:

1. ✅ Roadmap item exists (`vibe roadmap add`)
2. ✅ Plan document exists
3. ✅ Task is created (`vibe task add --spec-standard --spec-ref`)
4. ✅ Task is bound to flow (`vibe task update --bind-current`)

## Workflow

### Step 0: Check Prerequisites

If any prerequisite is missing:
- Suggest user to create it manually
- Or ask if user wants automatic creation (future enhancement)
```

---

## Testing

- [ ] Test `vibe task add --help` shows supported spec-standard values
- [ ] Test `vibe task add --spec-standard invalid` shows helpful error
- [ ] Test `vibe flow bind --agent "Custom Agent"` accepts custom value
- [ ] Test `vibe task add` error message shows both options
- [ ] Review `vibe-start` skill documentation

## Acceptance Criteria

- [ ] All 4 fixes implemented
- [ ] No workflow/process changes
- [ ] Help text is clear and helpful
- [ ] Error messages guide users to correct usage

## Estimated Time

- Implementation: 30 minutes
- Testing: 15 minutes
- Total: 45 minutes