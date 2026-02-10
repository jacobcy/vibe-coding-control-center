---
description: Initialize or check project standard structure
---

// turbo-all

1. Check for existing management files and refactor if necessary.
```bash
# Refactor lowercase files if they exist
[ -f "soul.md" ] && mv soul.md SOUL.md && echo "Refactored soul.md -> SOUL.md"
[ -f "rules.md" ] && mv rules.md RULES.md && echo "Refactored rules.md -> RULES.md"
[ -f "agents.md" ] && mv agents.md AGENT.md && echo "Refactored agents.md -> AGENT.md"
[ -f "tasks.md" ] && mv tasks.md TASK.md && echo "Refactored tasks.md -> TASK.md"
```

2. Create missing standard files from templates.
```bash
[ ! -f "SOUL.md" ] && touch SOUL.md && echo "# SOUL\n\n- Principles and values." > SOUL.md
[ ! -f "MEMORY.md" ] && touch MEMORY.md && echo "# MEMORY\n\n- Key decisions and context." > MEMORY.md
[ ! -f "TASK.md" ] && touch TASK.md && echo "# TASK\n\n- [ ] Initial task." > TASK.md
[ ! -f "WORKFLOW.md" ] && touch WORKFLOW.md && echo "# WORKFLOW\n\n- Project-level workflows documentation." > WORKFLOW.md
[ ! -f "AGENT.md" ] && touch AGENT.md && echo "# AGENT\n\n- Persona and roles." > AGENT.md
```

3. Ensure directory structure.
```bash
mkdir -p .agent/workflows
mkdir -p temp
```
