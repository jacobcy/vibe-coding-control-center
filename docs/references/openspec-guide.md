# OpenSpec Workflow Guide: From Concept to Code

Welcome to **OpenSpec**, an artifact-driven development workflow designed to make software changes structured, thoughtful, and documented by default.

This guide walks you through the OpenSpec philosophy, installation, and the complete lifecycle of a change—using a real-world example (fixing email validation) to demonstrate.

---

## 1. What is OpenSpec?

OpenSpec treats every code change as a mini-project with a clear lifecycle. Instead of jumping straight to coding, you create **Artifacts** that define the work:

1.  **Proposal** (Why are we doing this?)
2.  **Specs** (What exactly is the requirement? - Testable scenarios)
3.  **Design** (How will we build it? - Technical decisions)
4.  **Tasks** (What are the steps? - Implementation checklist)

This "Think -> Plan -> Code" loop ensures alignment, reduces rework, and automatically documents your project's history.

---

## 2. Installation & Setup

### Install
OpenSpec is typically installed as a global CLI tool.

```bash
# Using pnpm (recommended)
pnpm install -g openspec

# Using npm
npm install -g openspec
```

### Initialize in Project
Run this once in your project root to set up the `.openspec/` structure:

```bash
openspec init
```

This creates:
- `openspec/changes/`: Active work folder.
- `openspec/specs/`: System-wide specifications.
- `openspec/config.yaml`: Configuration.

---

## 3. The Workflow Cycle

The standard OpenSpec cycle consists of 6 phases:

| Phase | Command | Purpose |
| :--- | :--- | :--- |
| **1. Explore** | `/opsx:explore` | Investigate code/problems without changing state. |
| **2. New** | `/opsx:new <name>` | Create a new change container. |
| **3. Plan** | `/opsx:continue` | Fill in Proposal, Specs, Design, Tasks. |
| **4. Apply** | `/opsx:apply` | Implement the code based on Tasks. |
| **5. Verify** | `/opsx:verify` | Run tests to confirm Specs are met. |
| **6. Archive** | `/opsx:archive` | Move completed work to history. |

---

## 4. Real-World Example: Fixing Email Validation

Let's walk through how we fixed a weak regex in `lib/email_validation.sh`.

### Step 1: Explore
We noticed the regex allowed invalid emails like `user@.com`.
- **Action**: Ran `grep` and inspected `lib/email_validation.sh`.
- **Command**: `/opsx:explore` (Thinking phase)

### Step 2: New Change
We created a container for this work.
- **Command**: `openspec new change "fix-email-validation-regex"`
- **Result**: Created folder `openspec/changes/fix-email-validation-regex/`.

### Step 3: Define Artifacts (The "Thinking" Phase)

#### A. Proposal (The "Why")
We drafted `proposal.md` stating the problem (security risk) and the goal (strict regex).

#### B. Specs (The "What")
We created `specs/validate-email/spec.md`.
*   **Requirement**: "Stricter Email Validation"
*   **Scenarios**:
    *   *WHEN* "user@example.com" *THEN* Success
    *   *WHEN* "user@.com" *THEN* Failure
    *   *WHEN* "user..name@example.com" *THEN* Failure

*This effectively wrote our test cases before we wrote code!*

#### C. Design (The "How")
We drafted `design.md` deciding to:
1.  Replace the regex.
2.  Create a new dedicated test script `tests/test_email_validation.sh` (since existing tests were just comments).

#### D. Tasks (The Plan)
We listed steps in `tasks.md`:
1.  Create test script (TDD Red).
2.  Fix regex (TDD Green).
3.  Verify.

### Step 4: Apply (The "Coding" Phase)
We followed the tasks:
1.  **Created Test**: Wrote `tests/test_email_validation.sh` with the scenarios from Specs.
2.  **Ran Test**: It failed (Red Phase).
3.  **Implemented Fix**: Updated `lib/email_validation.sh` with better regex and logic.
4.  **Verified**: Ran tests again -> All Passed (Green Phase).

### Step 5: Archive
We finished the work.
- **Command**: `openspec archive "fix-email-validation-regex"`
- **Result**: The change folder moved to `openspec/changes/archive/2026-02-22-fix-email-validation-regex/`.
- **Benefit**: Future developers can look back and see exactly *why* and *how* this change was made.

---

## 5. Superpower Tips ⚡

1.  **Fast-Forward**: For small changes, use `/opsx:ff <name>` to generate all artifacts in one go using AI.
2.  **TDD is Built-in**: The "Specs" phase naturally leads to Test-Driven Development. Write the scenarios, then the test code, then the implementation.
3.  **Context is King**: The `archive` is your project's long-term memory. Don't skip it!
4.  **Skill Integration**: Use `skill: openspec-onboard` anytime to get a guided tour (like we just did).

---

## Conclusion

OpenSpec isn't just about writing docs; it's about **thinking before coding**. By following this structured flow, you ensure every line of code has a purpose, a test, and a history.

**Ready to start?**
```bash
openspec new change "my-first-feature"
```
