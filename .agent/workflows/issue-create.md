---
description: Create a new GitHub Issue
---

1. Create Issue
// turbo
```bash
if [ -f ".agent/lib/gh-ops.sh" ]; then
    source .agent/lib/gh-ops.sh
    issue_create
else
    echo "Error: .agent/lib/gh-ops.sh not found."
    exit 1
fi
```
