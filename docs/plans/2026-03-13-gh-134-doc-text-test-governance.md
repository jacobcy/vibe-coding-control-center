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

See content in the actual file created.

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

See content in the actual file created.

**Step 3: Commit**

```bash
git add tests/doc-text/
git commit -m "test(doc-text): create dedicated test directory structure

Prepare isolated test suite for doc-text regression tests.

Relates: #134"
```

---

## Task 3: Migrate Existing Doc-Text Tests (Part 1 - Terminology)

**Files:**
- Create: `tests/doc-text/test_terminology_locks.bats`
- Modify: `tests/skills/test_skills.bats` (extract tests)

**Step 1: Analyze existing text tests**

Run: `grep -n "@test" tests/skills/test_skills.bats | grep -E "(docs|terminology|workflow|standard|skill.*SKILL)"`

Expected: List of 13 text-based tests

**Step 2: Create terminology locks test file**

Create `tests/doc-text/test_terminology_locks.bats` with 5 tests for terminology definitions.

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

## Task 4: Migrate Existing Doc-Text Tests (Part 2 - Workflow Constraints)

**Files:**
- Create: `tests/doc-text/test_workflow_constraints.bats`

**Step 1: Create workflow constraints test file**

Create `tests/doc-text/test_workflow_constraints.bats` with 9 tests for workflow constraints.

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

## Task 5: Migrate Remaining Doc-Text Tests (Agent Patterns)

**Files:**
- Create: `tests/doc-text/test_agent_patterns.bats`

**Step 1: Create agent patterns test file**

Create `tests/doc-text/test_agent_patterns.bats` with 1 test for agent patterns.

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

Remove all doc-text tests from `tests/skills/test_skills.bats`, keeping only behavior tests.

**Step 2: Add comment explaining separation**

Add at the top after setup function:

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
- Modify or Create: `tests/README.md`

**Step 1: Create or update tests README**

Document test categories, structure, and how to run tests.

**Step 2: Commit**

```bash
git add tests/README.md
git commit -m "docs(tests): add test suite README with category separation

Document behavior tests vs doc-text tests separation and run commands.

Relates: #134"
```

---

## Task 8: Update CLAUDE.md Reference

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Add doc-text test governance reference**

Add to the "参考" section:

```markdown
- **[docs/standards/doc-text-test-governance.md](docs/standards/doc-text-test-governance.md)** — 文档文本回归测试治理标准（权威）
```

**Step 2: Add to HARD RULES**

Add new rule #10 about doc-text tests.

**Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(CLAUDE): add doc-text test governance to hard rules

Reference new standard and enforce test separation.

Relates: #134"
```

---

## Task 9: Verification

**Files:**
- None (verification only)

**Step 1: Verify doc-text tests run independently**

Run: `bats tests/doc-text/`
Expected: All migrated tests pass

**Step 2: Verify behavior tests still pass**

Run: `bats tests/skills/test_skills.bats`
Expected: Remaining behavior tests pass

**Step 3: Verify test count**

Run: `find tests/doc-text -name "*.bats" -exec grep -c "@test" {} \; | awk '{sum+=$1} END {print sum}'`
Expected: 15 (all migrated tests)

Run: `grep -c "@test" tests/skills/test_skills.bats`
Expected: 3 (only behavior tests remain)

**Step 4: Verify budget compliance**

Run: `ls tests/doc-text/*.bats | wc -l`
Expected: 3 files (within budget of 10)

Run: `for f in tests/doc-text/*.bats; do echo "$f: $(grep -c '@test' "$f")"; done`
Expected: Each file under 20 tests

**Step 5: Document verification results**

Document in commit message or PR description:

```
Verification Results:
- [x] Doc-text tests run independently: PASS
- [x] Behavior tests still pass: PASS
- [x] Test count matches: 15 migrated, 3 remain
- [x] Budget compliance: 3 files, all under 20 tests each
```

---

## Task 10: Create Migration Summary Document

**Files:**
- Create: `docs/reports/2026-03-13-doc-text-test-migration.md`

**Step 1: Create migration report**

Document the migration process, changes made, verification results, and lessons learned.

**Step 2: Commit**

```bash
git add docs/reports/2026-03-13-doc-text-test-migration.md
git commit -m "docs(report): add doc-text test migration report

Document migration process, verification, and lessons learned.

Relates: #134"
```

---

## Success Criteria

- [ ] Governance standard created with entry criteria and budget
- [ ] Doc-text test directory structure established
- [ ] All 15 text tests migrated to `tests/doc-text/`
- [ ] Original `test_skills.bats` cleaned to only behavior tests
- [ ] Tests README updated with category separation
- [ ] CLAUDE.md updated with new hard rule
- [ ] All tests pass independently
- [ ] Budget compliance verified (3 files, under limit)
- [ ] Migration report documented

## Non-Goals

- Not deleting all existing text tests
- Not converting text tests to behavior tests
- Not changing test execution infrastructure
- Not creating new text tests beyond migration