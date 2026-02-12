---
description: Automated Code Review & Static Analysis
---

// turbo-all

1. Static Analysis (ShellCheck).
- Run shellcheck on all shell scripts.
```bash
find . -name "*.sh" -not -path "./lib/shunit2/*" -exec shellcheck {} + || echo "ShellCheck found issues."
```

2. Logic Review (Agent).
- Review the logic of recent changes.
- Focus on:
    - Error handling (set -e, trap).
    - Input validation (args check).
    - Security (potential injection).
    - Compliance with `SOUL.md`.

3. Report Generation.
- Generate a summary of findings.
- **Output**: `docs/audits/<date>-review.md`
