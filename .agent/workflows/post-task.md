---
description: Post-task maintenance to cleanup and record progress
---

// turbo-all

1. Run verification tests to ensure the system is stable.
```bash
if [ -d "tests" ]; then
  ./tests/test_new_features.sh || echo "Warning: Tests failed or not found"
fi
```

2. Cleanup temporary files and artifacts.
```bash
rm -rf temp/*
find . -name "tmpvibe*" -type d -exec rm -rf {} +
```

3. Record the necessary information to management files.
- Update `MEMORY.md` with key decisions and new context.
- Update `TASK.md` by marking completed items and adding new ones.
- Update `SOUL.md` if any core principles were evolved.

4. Log the completion.
```bash
echo "Maintenance complete. Files cleaned and progress recorded."
```
