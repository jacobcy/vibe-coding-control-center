---
description: Interactive Smart Commit Workflow
---

// turbo-all

1. Analyze changes and propose grouping.
```bash
# This is a placeholder for the actual logic which would likely involve a script
# For now, we will list the changes and ask the user to commit them manually or via the IDE
# In a real implementation, this would call a python script or complex shell script to group files.

echo "Analyzing changes..."
git status -s

echo "\n--- Suggested Grouping ---"
echo "1. Documentation: docs/"
echo "2. Core Logic: lib/"
echo "3. Tests: tests/"
echo "4. Workflow Config: .agent/workflows/"
```

2. Interactive Commit Loop (Simulated).
```bash
# In a fully autonomous agent environment, we might use a script to actually perform the commits.
# For this workflow, we will guide the user or the agent to perform the commits.
# We'll use a simple loop to commit by pathspec.

# Example: Commit documentation
# git add docs/ && git commit -m "docs: update documentation" || echo "No docs changes"

# Example: Commit workflows
# git add .agent/workflows/ && git commit -m "feat: update workflows" || echo "No workflow changes"

echo "To commit features, run git add <path> && git commit -m '...'"
```

3. Verification.
```bash
git log --oneline -n 5
```
