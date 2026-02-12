---
description: Interactive Smart Commit Workflow
---

// turbo-all

1. Analyze changes to identify logical groups.
```bash
echo "=== Git Status Analysis ==="
git status -s

echo -e "\n=== Change Summary ==="
# Group files by directory
git status -s | awk '{print $2}' | cut -d/ -f1 | sort | uniq -c | sort -nr
```

2. Generate commit plan.
- Review the `git status` output above.
- Propose a logical grouping for commits based on the changed files.
- Each commit should be atomic and follow Conventional Commits (feat, fix, docs, style, refactor, test, chore).

3. Execute Commits (Interactive Loop).
- Use `git add <files>` and `git commit -m "<message>"` for each group.
- **Rule**: Do not use `git add .` unless all changes are strictly related to a single feature.

4. Verify History.
```bash
git log --oneline -n 5
```
