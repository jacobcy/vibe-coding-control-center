---
description: Resolve and Close a GitHub Issue
---

1. Resolve Issue
// turbo
```bash
if [ -f ".agent/lib/gh-ops.sh" ]; then
    source .agent/lib/gh-ops.sh
    # interactive
    issue_resolve
else
    echo "Error: .agent/lib/gh-ops.sh not found."
    exit 1
fi
```
