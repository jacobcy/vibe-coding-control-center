---
description: Interactive Smart Commit Workflow
---

// turbo-all

1. Analyze Smart Groups
Analyze all uncommitted changes to identify logical functional groups.
```bash
echo "=== Git Status Analysis ==="
git status -s

echo -e "\n=== Change Summary ==="
# Group files by directory
git status -s | awk '{print $2}' | cut -d/ -f1 | sort | uniq -c | sort -nr
```

2. Generate Commit Plan
- Review the `git status` output above.
- **Goal**: Cover ALL uncommitted changes by grouping them into atomic commits.
- **Strategy**: Group related files (e.g., tests with code, docs with features).
- **Format**: Each commit must follow Conventional Commits (feat, fix, docs, style, refactor, test, chore).

3. Execute Smart Commits
- Iterate through your plan group by group.
- Use `git add <files>` and `git commit -m "<message>"` for each logical group.
- **Constraint**: Do not use `git add .` unless all changes belong to a single atomic feature.
- Continue until `git status` is clean (or user decides to stash remaining).

4. Verify History.
```bash
git log --oneline -n 5
```
