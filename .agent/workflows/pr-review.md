---
description: Pull Request Review Workflow
trigger: Manual or on PR assignment
---

# PR Review Workflow

This workflow guides the agent through reviewing a GitHub Pull Request for the Vibe Coding Control Center.

## 1. Setup & Context
- Ensure `gh` CLI is authenticated.
- Identify the PR number to review.

```bash
# List open PRs if number not provided
gh pr list
```

## 2. Checkout & Inspect
- Checkout the PR branch to a detached state or temporary branch.
```bash
gh pr checkout <PR_NUMBER>
```
- Fetch the PR description and checks status.
```bash
gh pr view <PR_NUMBER>
gh pr checks <PR_NUMBER>
```

## 3. Automated Validation
- **Static Analysis**: Run ShellCheck.
```bash
find . -name "*.sh" -not -path "./lib/shunit2/*" -exec shellcheck {} +
```
- **Test Suite**: Run project tests.
```bash
./scripts/vibecoding.sh --doctor
# OR specific tests
./tests/test_all.sh
```

## 4. Code & Logic Review
- **Diff Analysis**: Read the changes.
```bash
gh pr diff <PR_NUMBER>
```
- **Criteria Checklist**:
  - [ ] **Architecture**: Does it follow "Orchestrate, don't reimplement"?
  - [ ] **Security**: Are inputs validated? Are paths safe?
  - [ ] **Standards**: Does it follow `SOUL.md` (Chinese response, English thought)?
  - [ ] **Documentation**: Are `docs/` updated? Is `CHANGELOG.md` updated?
  - [ ] **Cleanliness**: No temp files committed?

## 5. Submit Feedback
- Construct constructive feedback.
- If changes are needed:
```bash
gh pr review <PR_NUMBER> --request-changes --body "Review comments..."
```
- If approved:
```bash
gh pr review <PR_NUMBER> --approve --body "LGTM! Verified tests pass and standards are met."
```

## 6. Merge (Optional)
- If authorized and approved:
```bash
gh pr merge <PR_NUMBER> --merge --delete-branch
```
