#!/usr/bin/env zsh
# Example: Complete OpenClaw agent workflow with execution plane

# Scenario: OpenClaw agent automating development task "implement-api"

# Set executor mode
export EXECUTOR=openclaw

# Step 1: Prepare complete environment
echo "=== Step 1: Preparing environment ==="
skill_prepare_environment implement-api openclaw main

# Output:
# 🤖 OpenClaw Mode: Preparing complete development environment...
# 🤖 OpenClaw Mode: Creating worktree...
# ✅ Created worktree: wt-openclaw-implement-api -> implement-api (base: main)
# 👤 Identity: Agent-Opencode <agent-openclaw@vibecoding.ai>
# ✓ Execution result written: .agent/execution-results/implement-api.json
# 🤖 OpenClaw Mode: Creating tmux session...
# ✅ Created session: openclaw-implement-api
# ✅ Environment ready for task: implement-api

# Step 2: Query execution state
echo -e "\n=== Step 2: Querying execution state ==="
skill_query_task implement-api

# Output:
# {
#   "task_id": "implement-api",
#   "resolved_worktree": "wt-openclaw-implement-api",
#   "resolved_session": "openclaw-implement-api",
#   "executor": "openclaw",
#   "timestamp": "2026-03-03T06:45:00Z"
# }

# Step 3: Validate environment
echo -e "\n=== Step 3: Validating environment ==="
skill_wtvalidate wt-openclaw-implement-api

# Output:
# 🤖 OpenClaw Mode: (validation output...)

# Step 4: Simulate work completion (in real scenario, agent would do actual work)
echo -e "\n=== Step 4: Work complete, cleaning up ==="
skill_cleanup_environment implement-api openclaw

# Output:
# 🤖 OpenClaw Mode: Cleaning up development environment...
# 🤖 OpenClaw Mode: (cleanup output...)
# ✅ Environment cleaned up for task: implement-api

echo -e "\n✅ OpenClaw workflow complete!"
