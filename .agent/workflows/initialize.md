---
description: Initialize or check project standard structure
---

# Initialize Project

## 1. Prerequisites (前置准备)
- [ ] Context gathered: Check existing structure.
- [ ] Rules loaded: `coding-standards.md`.

## 2. Standards Check (规范检查)
**CRITICAL**: 执行前请复核以下规则：
// turbo
cat .agent/rules/coding-standards.md

## 3. Execution (执行)
Create and organize the standard project structure.
> [!IMPORTANT]
> This workflow will move legacy files (MEMORY.md, etc.) to `.agent/context/`.

### 3.1 Migrate Legacy Files
// turbo
```bash
mkdir -p .agent/context
[ -f "MEMORY.md" ] && mv MEMORY.md .agent/context/memory.md && echo "Moved MEMORY.md"
[ -f "TASK.md" ] && mv TASK.md .agent/context/task.md && echo "Moved TASK.md"
[ -f "AGENT.md" ] && mv AGENT.md .agent/context/agent.md && echo "Moved AGENT.md"
[ -f "WORKFLOW.md" ] && rm WORKFLOW.md && echo "Removed redundant WORKFLOW.md"
```

### 3.2 Create Standard Structure
// turbo
```bash
# Directories
mkdir -p .agent/workflows
mkdir -p .agent/templates
mkdir -p .agent/rules/
mkdir -p temp

# Core Constitution
[ ! -f "SOUL.md" ] && echo "# SOUL\n\n- Principles and values." > SOUL.md && echo "Created SOUL.md"

# Agent Context
[ ! -f ".agent/context/memory.md" ] && echo "# MEMORY\n\n- Key decisions." > .agent/context/memory.md && echo "Created memory.md"
[ ! -f ".agent/context/task.md" ] && echo "# TASK\n\n- [ ] Initial task." > .agent/context/task.md && echo "Created task.md"
[ ! -f ".agent/context/agent.md" ] && echo "# AGENT\n\n- Persona." > .agent/context/agent.md && echo "Created agent.md"

# Gitignore
touch .gitignore
grep -q "temp/" .gitignore || echo "temp/" >> .gitignore
```

## 4. Verification (验证)
- [ ] Verify directory structure.
```bash
find .agent -maxdepth 2 -not -path '*/.*'
```

