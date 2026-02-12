---
description: Initialize or check project standard structure
---

// turbo-all

1. Check and Move Legacy Context Files.
```bash
mkdir -p .agent/context
[ -f "MEMORY.md" ] && mv MEMORY.md .agent/context/memory.md && echo "Moved MEMORY.md"
[ -f "TASK.md" ] && mv TASK.md .agent/context/task.md && echo "Moved TASK.md"
[ -f "AGENT.md" ] && mv AGENT.md .agent/context/agent.md && echo "Moved AGENT.md"
[ -f "WORKFLOW.md" ] && rm WORKFLOW.md && echo "Removed redundant WORKFLOW.md"
```

2. Ensure Mandatory Files Exist.
```bash
# Core Constitution
[ ! -f "SOUL.md" ] && echo "# SOUL\n\n- Principles and values." > SOUL.md && echo "Created SOUL.md"

# Agent Context
[ ! -f ".agent/context/memory.md" ] && echo "# MEMORY\n\n- Key decisions." > .agent/context/memory.md && echo "Created memory.md"
[ ! -f ".agent/context/task.md" ] && echo "# TASK\n\n- [ ] Initial task." > .agent/context/task.md && echo "Created task.md"
[ ! -f ".agent/context/agent.md" ] && echo "# AGENT\n\n- Persona." > .agent/context/agent.md && echo "Created agent.md"

# Vibe/Claude Spec
[ ! -f "CLAUDE.md" ] && echo "# Project Context\n\n- See .agent/context/ for details." > CLAUDE.md && echo "Created CLAUDE.md"
```

3. Ensure Directory Structure.
```bash
mkdir -p .agent/workflows
mkdir -p .agent/templates
mkdir -p .agent/rules
mkdir -p temp
touch .gitignore
grep -q "temp/" .gitignore || echo "temp/" >> .gitignore
```
