# Doc-Text Regression Tests Governance Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Isolate documentation text regression tests from behavior tests, establish governance model, and cap unlimited growth.

**Architecture:** Create separate test suite for doc-text regressions, define clear entry criteria and budget limits, establish new standards document, and migrate existing text tests to new structure.

**Tech Stack:** Bats (Bash Automated Testing System), Ripgrep (rg), Zsh

---

## Background

Issue #134 identifies that `tests/skills/test_skills.bats` contains growing text-based tests that check for specific phrases in documentation files. These are mixed with actual behavior tests, creating confusion about TDD applicability and encouraging unlimited expansion.

**Current Problems:**
- Text tests and behavior tests mixed in same file (13 text tests in test_skills.bats)
- No entry criteria for adding new text tests
- No budget/limit constraints
- Risk of treating doc text changes as requiring TDD

**Solution:**
- Separate text regression tests into dedicated test suite
- Define clear governance standard with entry criteria and budget
- Create migration path for existing text tests
- Document when text tests are appropriate vs. when to avoid them

---

## Task 1: Create Doc-Text Test Governance Standard

**Files:**
- Create: `docs/standards/doc-text-test-governance.md`

**Step 1: Write the governance standard document**

Create comprehensive standard defining:
- Doc-text test vs behavior test definitions
- Separation principle (physical file separation required)
- Entry criteria (when to add, when NOT to add)
- Budget limits (10 files max, 20 tests per file)
- Test structure and naming conventions
- Quarterly review process

See content in previous message (too long to repeat).

**Step 2: Run verification**

Run: `ls -la docs/standards/doc-text-test-governance.md`
Expected: File exists with correct permissions

**Step 3: Commit**

```bash
git add docs/standards/doc-text-test-governance.md
git commit -m "docs(standards): add doc-text regression test governance standard

Establishes entry criteria, budget limits, and separation principle
for doc-text regression tests.

Relates: #134"
```

---

## Task 2: Create Doc-Text Test Directory Structure

**Files:**
- Create: `tests/doc-text/.gitkeep`
- Create: `tests/doc-text/README.md`

**Step 1: Create directory**

```bash
mkdir -p tests/doc-text
touch tests/doc-text/.gitkeep
```

**Step 2: Write README**

Create `tests/doc-text/README.md`:

```markdown
# Doc-Text Regression Tests

本目录包含文档文本回归测试，用于锁定关键语义和防止概念漂移。

## 定义

Doc-text regression tests 通过文本匹配检查文档内容，不测试 Shell 行为。

## 与 Behavior Tests 的区别

- **Doc-text tests**: 检查文档中的文本是否存在、是否符合预期模式
- **Behavior tests**: 测试命令行为、输出、退出码、副作用

## 何时添加测试

**必须满足准入标准**（见 `docs/standards/doc-text-test-governance.md`）:

1. 关键语义冻结（如术语定义）
2. 高风险承诺文本（如 agent 触发条件）
3. 历史漂移问题

## 何时不添加测试

- 低风险润色
- 可被行为测试覆盖
- 重复断言
- 非真源文档

## 运行测试

```bash
# 执行所有 doc-text tests
bats tests/doc-text/

# 执行特定文件
bats tests/doc-text/test_terminology_locks.bats
```

## 预算限制

- 文件数量上限: 10 个文件
- 单文件测试数量上限: 20 个测试
- 超出前必须优先整合而非扩容

## 检查清单

添加新测试前必须填写:

```
Doc-Text Test Entry Checklist:
- [ ] 满足准入标准第 X 条
- [ ] 无法被行为测试替代
- [ ] 无法复用现有 doc-text test
- [ ] 未超出数量预算
```

## 参见

- [Doc-Text Test Governance Standard](../../docs/standards/doc-text-test-governance.md)
- [Issue #134](https://github.com/jacobcy/vibe-coding-control-center/issues/134)
```

**Step 3: Commit**

```bash
git add tests/doc-text/
git commit -m "test(doc-text): create dedicated test directory structure

Prepare isolated test suite for doc-text regression tests.

Relates: #134"
```

---

## Task 3: Migrate Existing Doc-Text Tests (Part 1)

**Files:**
- Create: `tests/doc-text/test_terminology_locks.bats`
- Modify: `tests/skills/test_skills.bats` (extract tests)

**Step 1: Analyze existing text tests**

Run: `grep -n "@test" tests/skills/test_skills.bats | grep -E "(docs|terminology|workflow|standard|skill.*SKILL)"`

Expected: List of 13 text-based tests

**Step 2: Create terminology locks test file**

Create `tests/doc-text/test_terminology_locks.bats`:

```bash
#!/usr/bin/env bats

# Reason: Lock critical terminology definitions to prevent drift
# Entry Criterion: §4.1.1 - Key semantic freeze (terminology definitions)
# Alternative Considered: Behavior tests via `vibe` commands, but terminology
#                         is documentation-level contract, not command behavior

setup() {
  export REPO_ROOT="$BATS_TEST_DIRNAME/../.."
}

@test "doc-text: glossary.md locks 'repo issue' as GitHub issue term" {
  run rg -n "repo issue.*特指.*GitHub repository issue" "$REPO_ROOT/docs/standards/glossary.md"
  [ "$status" -eq 0 ]
}

@test "doc-text: glossary.md locks 'roadmap item' as mirrored GitHub Project item" {
  run rg -n "roadmap item.*mirrored.*GitHub Project item" "$REPO_ROOT/docs/standards/glossary.md"
  [ "$status" -eq 0 ]
}

@test "doc-text: glossary.md locks 'task' as execution record" {
  run rg -n "task.*execution record" "$REPO_ROOT/docs/standards/glossary.md"
  [ "$status" -eq 0 ]
}

@test "doc-text: glossary.md locks 'flow' as runtime container" {
  run rg -n "flow.*运行时容器|flow.*runtime container" "$REPO_ROOT/docs/standards/glossary.md"
  [ "$status" -eq 0 ]
}

@test "doc-text: skill-standard.md locks skill layer responsibilities" {
  run rg -n "Skill 层.*理解上下文.*调度.*编排" "$REPO_ROOT/docs/standards/skill-standard.md"
  [ "$status" -eq 0 ]
}
```

**Step 3: Run the new test**

Run: `bats tests/doc-text/test_terminology_locks.bats`
Expected: All tests pass

**Step 4: Commit**

```bash
git add tests/doc-text/test_terminology_locks.bats
git commit -m "test(doc-text): migrate terminology lock tests

Extract terminology definition locks from test_skills.bats.

Doc-Text Test Entry Checklist:
- [x] 满足准入标准第 1 条 (关键语义冻结)
- [x] 无法被行为测试替代
- [x] 无法复用现有 doc-text test
- [x] 未超出数量预算

Relates: #134"
```

---

## Task 4: Migrate Existing Doc-Text Tests (Part 2)

**Files:**
- Create: `tests/doc-text/test_workflow_constraints.bats`

**Step 1: Create workflow constraints test file**

Create `tests/doc-text/test_workflow_constraints.bats`:

```bash
#!/usr/bin/env bats

# Reason: Lock high-risk workflow constraint text that guides agent behavior
# Entry Criterion: §4.1.2 - High-risk commitment text (workflow constraints)
# Alternative Considered: Behavior tests for workflow execution, but text
#                         constraints are the contract definition, not execution

setup() {
  export REPO_ROOT="$BATS_TEST_DIRNAME/../.."
}

@test "doc-text: workflow docs preserve github project orchestration terminology" {
  run rg -nH \
    "roadmap item.*GitHub Project item mirror|Roadmap Item: mirrored GitHub Project item|task.*execution record|Task: execution record" \
    "$REPO_ROOT/.agent/workflows" \
    "$REPO_ROOT/skills/vibe-roadmap/SKILL.md" \
    "$REPO_ROOT/skills/vibe-task/SKILL.md"

  [ "$status" -eq 0 ]
  [[ "$output" =~ "vibe:new-flow.md" ]]
  [[ "$output" =~ "vibe-roadmap/SKILL.md" ]]
  [[ "$output" =~ "vibe-task/SKILL.md" ]]
}

@test "doc-text: task save and check docs treat spec_standard and spec_ref as extension fields" {
  run rg -nH \
    "spec_standard|spec_ref|扩展桥接字段|extension field|execution spec" \
    "$REPO_ROOT/.agent/workflows/vibe:save.md" \
    "$REPO_ROOT/.agent/workflows/vibe:check.md" \
    "$REPO_ROOT/skills/vibe-task/SKILL.md" \
    "$REPO_ROOT/skills/vibe-save/SKILL.md" \
    "$REPO_ROOT/skills/vibe-check/SKILL.md"

  [ "$status" -eq 0 ]
  [[ "$output" =~ "spec_standard" ]]
  [[ "$output" =~ "spec_ref" ]]
}

@test "doc-text: orchestration docs require reading shell output before semantic decisions" {
  run rg -nH \
    "先读 shell 输出|先运行 \`vibe|必须先运行 \`vibe|read shell output" \
    "$REPO_ROOT/.agent/workflows/vibe:task.md" \
    "$REPO_ROOT/.agent/workflows/vibe:save.md" \
    "$REPO_ROOT/.agent/workflows/vibe:check.md" \
    "$REPO_ROOT/skills/vibe-issue/SKILL.md" \
    "$REPO_ROOT/skills/vibe-task/SKILL.md" \
    "$REPO_ROOT/skills/vibe-save/SKILL.md" \
    "$REPO_ROOT/skills/vibe-check/SKILL.md" \
    "$REPO_ROOT/skills/vibe-roadmap/SKILL.md"

  [ "$status" -eq 0 ]
}

@test "doc-text: handoff governance is defined in a standard and referenced by CLAUDE and skills" {
  run rg -nH \
    "handoff-governance-standard|task\\.md.*不是.*真源|发现.*不一致.*必须修正" \
    "$REPO_ROOT/docs/standards/handoff-governance-standard.md" \
    "$REPO_ROOT/CLAUDE.md" \
    "$REPO_ROOT/skills/vibe-save/SKILL.md" \
    "$REPO_ROOT/skills/vibe-continue/SKILL.md" \
    "$REPO_ROOT/skills/vibe-commit/SKILL.md" \
    "$REPO_ROOT/skills/vibe-integrate/SKILL.md" \
    "$REPO_ROOT/skills/vibe-done/SKILL.md"

  [ "$status" -eq 0 ]
  [[ "$output" =~ "handoff-governance-standard.md" ]]
  [[ "$output" =~ "CLAUDE.md" ]]
}

@test "doc-text: vibe-commit docs require task metadata preflight before commit grouping" {
  run rg -nH \
    "metadata preflight|current_task|runtime_branch|issue_refs|roadmap_item_ids|spec_standard|spec_ref|hard block|warning" \
    "$REPO_ROOT/.agent/workflows/vibe:commit.md"

  [ "$status" -eq 0 ]
  [[ "$output" =~ "vibe:commit.md" ]]
  [[ "$output" =~ "current_task" ]]
  [[ "$output" =~ "runtime_branch" ]]
  [[ "$output" =~ "issue_refs" ]]
  [[ "$output" =~ "roadmap_item_ids" ]]

  run rg -nH \
    "metadata preflight|current_task|runtime_branch|issue_refs|roadmap_item_ids|spec_standard|spec_ref|hard block|warning" \
    "$REPO_ROOT/skills/vibe-commit/SKILL.md"

  [ "$status" -eq 0 ]
  [[ "$output" =~ "vibe-commit/SKILL.md" ]]
  [[ "$output" =~ "current_task" ]]
  [[ "$output" =~ "runtime_branch" ]]
  [[ "$output" =~ "issue_refs" ]]
  [[ "$output" =~ "roadmap_item_ids" ]]
}

@test "doc-text: merged pr governance keeps old plans terminal and pushes new work into fresh intake" {
  run rg -n \
    "merged PR.*terminal|plan.*terminal|新需求.*repo issue|follow-up.*链接|不得.*旧 plan" \
    "$REPO_ROOT/docs/standards/git-workflow-standard.md" \
    "$REPO_ROOT/docs/standards/handoff-governance-standard.md" \
    "$REPO_ROOT/skills/vibe-integrate/SKILL.md" \
    "$REPO_ROOT/skills/vibe-done/SKILL.md"

  [ "$status" -eq 0 ]
  [[ "$output" =~ "git-workflow-standard.md" ]]
  [[ "$output" =~ "handoff-governance-standard.md" ]]
  [[ "$output" =~ "vibe-integrate/SKILL.md" ]]
  [[ "$output" =~ "vibe-done/SKILL.md" ]]
}

@test "doc-text: issue orchestration defines parent issue scope and out-of-scope split rules" {
  run rg -n \
    "主 issue|sub-issue|超出原范围|新建独立.*issue|治理母题|skill/workflow" \
    "$REPO_ROOT/skills/vibe-issue/SKILL.md" \
    "$REPO_ROOT/skills/vibe-roadmap/SKILL.md"

  [ "$status" -eq 0 ]
  [[ "$output" =~ "vibe-issue/SKILL.md" ]]
  [[ "$output" =~ "vibe-roadmap/SKILL.md" ]]
}

@test "doc-text: roadmap intake gate docs define triage ownership without shell auto intake" {
  run rg -n \
    "不是所有.*repo issue.*自动进入.*Project|候选资格|vibe-roadmap.*intake gate|vibe-roadmap.*triage|shell.*不负责.*智能.*gate|不自动进入.*GitHub Project" \
    "$REPO_ROOT/skills/vibe-roadmap/SKILL.md" \
    "$REPO_ROOT/skills/vibe-issue/SKILL.md" \
    "$REPO_ROOT/docs/standards/command-standard.md"

  [ "$status" -eq 0 ]
  [[ "$output" =~ "vibe-roadmap/SKILL.md" ]]
  [[ "$output" =~ "vibe-issue/SKILL.md" ]]
  [[ "$output" =~ "command-standard.md" ]]
}

@test "doc-text: roadmap intake view docs reject local long-term issue cache" {
  run rg -n \
    "repo issue intake 视图|运行时查询.*roadmap mirror|不维护本地长期.*issue.*cache|不维护本地长期.*issue.*registry|triage 决策快照|issue 整池真源" \
    "$REPO_ROOT/skills/vibe-roadmap/SKILL.md" \
    "$REPO_ROOT/docs/standards/command-standard.md"

  [ "$status" -eq 0 ]
  [[ "$output" =~ "vibe-roadmap/SKILL.md" ]]
  [[ "$output" =~ "command-standard.md" ]]
}
```

**Step 2: Run the new test**

Run: `bats tests/doc-text/test_workflow_constraints.bats`
Expected: All tests pass

**Step 3: Commit**

```bash
git add tests/doc-text/test_workflow_constraints.bats
git commit -m "test(doc-text): migrate workflow constraint tests

Extract workflow constraint text locks from test_skills.bats.

Doc-Text Test Entry Checklist:
- [x] 满足准入标准第 2 条 (高风险承诺文本)
- [x] 无法被行为测试替代
- [x] 无法复用现有 doc-text test
- [x] 未超出数量预算

Relates: #134"
```

---

## Task 5: Migrate Remaining Doc-Text Tests

**Files:**
- Create: `tests/doc-text/test_agent_patterns.bats`

**Step 1: Create agent patterns test file**

Create `tests/doc-text/test_agent_patterns.bats`:

```bash
#!/usr/bin/env bats

# Reason: Lock agent execution patterns and auto-confirmation conventions
# Entry Criterion: §4.1.2 - High-risk commitment text (agent behavior constraints)
# Alternative Considered: Behavior tests for pattern execution, but text
#                         defines the contract agents must follow

setup() {
  export REPO_ROOT="$BATS_TEST_DIRNAME/../.."
}

@test "doc-text: patterns define agent auto confirmation without bypassing validation" {
  run rg -n \
    "Auto Confirmation Convention|auto|--yes|过程确认|不得跳过验证|fail-fast|高风险决策" \
    "$REPO_ROOT/.agent/rules/patterns.md"

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Auto Confirmation Convention" ]]
  [[ "$output" =~ "不得跳过验证" ]]
}
```

**Step 2: Run the new test**

Run: `bats tests/doc-text/test_agent_patterns.bats`
Expected: Test passes

**Step 3: Commit**

```bash
git add tests/doc-text/test_agent_patterns.bats
git commit -m "test(doc-text): migrate agent pattern tests

Extract agent execution pattern locks from test_skills.bats.

Doc-Text Test Entry Checklist:
- [x] 满足准入标准第 2 条 (高风险承诺文本)
- [x] 无法被行为测试替代
- [x] 无法复用现有 doc-text test
- [x] 未超出数量预算

Relates: #134"
```

---

## Task 6: Clean Up Original Test File

**Files:**
- Modify: `tests/skills/test_skills.bats`

**Step 1: Remove migrated text tests**

Remove the following tests from `tests/skills/test_skills.bats`:
- Lines 63-74: "workflow and skill docs preserve github project orchestration terminology"
- Lines 76-88: "task save and check docs treat spec_standard and spec_ref as extension fields"
- Lines 90-103: "orchestration docs require reading shell output before semantic decisions"
- Lines 105-119: "handoff governance is defined in a standard and referenced by CLAUDE and skills"
- Lines 121-129: "patterns define agent auto confirmation without bypassing validation"
- Lines 131-153: "vibe-commit docs require task metadata preflight before commit grouping"
- Lines 155-168: "merged pr governance keeps old plans terminal and pushes new work into fresh intake"
- Lines 170-179: "issue orchestration defines parent issue scope and out-of-scope split rules"
- Lines 181-192: "roadmap intake gate docs define triage ownership without shell auto intake"
- Lines 194-203: "roadmap intake view docs reject local long-term issue cache"

Keep only behavior tests (tests that call `vibe` commands or test shell behavior).

**Step 2: Add comment explaining separation**

Add at the top of `tests/skills/test_skills.bats` after the setup function:

```bash
# NOTE: Doc-text regression tests have been migrated to tests/doc-text/
# See docs/standards/doc-text-test-governance.md for separation rationale
# Only behavior tests (testing shell commands and their effects) remain here
```

**Step 3: Run remaining tests**

Run: `bats tests/skills/test_skills.bats`
Expected: Remaining behavior tests pass

**Step 4: Commit**

```bash
git add tests/skills/test_skills.bats
git commit -m "refactor(tests): remove migrated doc-text tests from test_skills.bats

Doc-text regression tests moved to tests/doc-text/ per governance standard.
Only behavior tests remain in this file.

Relates: #134"
```

---

## Task 7: Update Tests README

**Files:**
- Modify: `tests/README.md` (if exists)
- Create: `tests/README.md` (if doesn't exist)

**Step 1: Create or update tests README**

```markdown
# Vibe Center Test Suite

## Test Categories

### Behavior Tests

Tests that verify shell command behavior, output, exit codes, and side effects.

**Location**: `tests/` (excluding `tests/doc-text/`)

**Run**:
```bash
bats tests/ --filter '!^tests/doc-text/'
```

### Doc-Text Regression Tests

Tests that lock critical documentation semantics and prevent concept drift.

**Location**: `tests/doc-text/`

**Run**:
```bash
bats tests/doc-text/
```

**Governance**: See [Doc-Text Test Governance Standard](../docs/standards/doc-text-test-governance.md)

## Running All Tests

```bash
# Run all tests
bats tests/

# Run only behavior tests
bats tests/ --filter '!^tests/doc-text/'

# Run only doc-text tests
bats tests/doc-text/

# Run specific test file
bats tests/skills/test_skills.bats
```

## Test Structure

```
tests/
├── contracts/          # Contract tests
├── doc-text/          # Doc-text regression tests (isolated)
│   ├── README.md
│   ├── test_terminology_locks.bats
│   ├── test_workflow_constraints.bats
│   └── test_agent_patterns.bats
├── flow/              # Flow command behavior tests
├── roadmap/           # Roadmap command behavior tests
├── skills/            # Skills behavior tests (no doc-text tests)
├── task/              # Task command behavior tests
└── test_*.bats        # Other behavior tests
```

## Writing New Tests

### Behavior Tests

Add to appropriate directory based on tested component:
- `tests/skills/` for skills-related behavior
- `tests/flow/` for flow command behavior
- `tests/roadmap/` for roadmap command behavior
- etc.

### Doc-Text Tests

**Before adding**, ensure you meet entry criteria in [Doc-Text Test Governance Standard](../docs/standards/doc-text-test-governance.md).

Add to `tests/doc-text/` with appropriate file name:
- `test_terminology_locks.bats` for terminology definitions
- `test_workflow_constraints.bats` for workflow constraint text
- `test_agent_patterns.bats` for agent execution pattern text

**Must include**:
- Reason comment
- Entry criterion citation
- Alternative considered statement