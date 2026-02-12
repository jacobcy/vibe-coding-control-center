---
description: Systematic Debugging Workflow
---

// turbo-all

1. Reproduce Issue.
- Create a minimal reproduction script.
```bash
# touch tests/repro_issue_XXX.sh
# chmod +x tests/repro_issue_XXX.sh
```

2. Collect Environment Info.
```bash
vibe doctor
echo "=== Git Status ==="
git status
echo "=== Last Commit ==="
git log -1
```

3. Analyze Logs.
- Check execution logs if available.
- Run with `set -x` for verbose output.

4. Propose Fix.
- Create a fix plan.
- Implement fix using TDD cycle.
