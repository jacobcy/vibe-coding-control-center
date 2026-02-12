---
description: Create a Pull Request
---

1. Analyze Changes
Generate a summary of changes between the current branch and `origin/main`.
```bash
git fetch origin main
git diff --stat origin/main...HEAD
git log origin/main..HEAD --oneline
```

2. Agent Drafting
- Based on the above analysis, draft a **Title** and **Body** for the Pull Request.
- The Title should be concise and descriptive (e.g., following Conventional Commits).
- The Body should explain *what* changed and *why*.

3. Push current branch to origin
// turbo
```bash
git push -u origin HEAD
```

4. Create Pull Request
Construct the `gh pr create` command with your drafted Title and Body.
Example:
```bash
gh pr create --title "feat: add amazing feature" --body "Detailed description..." --web
```
- **Ask the user** to confirm the command before running it.
