---
description: Post-task maintenance to cleanup and record progress
---

// turbo-all

1. Verification.
```bash
if [ -d "tests" ]; then
  ./scripts/test-all.sh || echo "⚠️  Tests failed or not found"
else
  echo "No tests directory found."
fi
```

2. Cleanup.
```bash
rm -rf temp/*
find . -name "tmpvibe*" -type d -exec rm -rf {} + 2>/dev/null || true
```

3. Update Context (CRITICAL).
- **Update `.agent/context/memory.md`**: Record key decisions, architectural changes, and lessons learned.
- **Update `.agent/context/task.md`**: Mark completed items `[x]`, add new items `[ ]`, and update backlog.
- **Update `SOUL.md`**: Only if core principles have evolved.

4. Log Completion.
```bash
echo "Maintenance complete. Context updated and temp files cleaned."
```
