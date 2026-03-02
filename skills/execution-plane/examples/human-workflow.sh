#!/usr/bin/env zsh
# Example: Complete human workflow with execution plane

# Scenario: Developer starting a new feature "add-user-authentication"

# Step 1: Create worktree
echo "=== Step 1: Creating worktree ==="
wtnew add-user-auth claude main

# Output:
# ✅ Created worktree: wt-claude-add-user-auth -> add-user-auth (base: main)
# 👤 Identity: Agent-Claude <agent-claude@vibecoding.ai>
# ✓ Execution result written: .agent/execution-results/add-user-auth.json

# Step 2: Create tmux session
echo -e "\n=== Step 2: Creating tmux session ==="
tmnew add-user-auth claude

# Output:
# ✅ Created session: claude-add-user-auth

# Step 3: List worktrees to verify
echo -e "\n=== Step 3: Listing worktrees ==="
wtlist claude

# Output:
# Worktrees:
# -----------
#   wt-claude-add-user-auth
#     Owner: claude
#     Task: add-user-auth
#     Branch: add-user-auth
#     Path: /path/to/wt-claude-add-user-auth
# -----------
# Total: 1 worktree(s)

# Step 4: List sessions to verify
echo -e "\n=== Step 4: Listing sessions ==="
tmlist

# Output:
# 📋 Tmux Sessions:
#   - claude-add-user-auth (1 windows) ✓ attached
#     Agent: claude
#     Task: add-user-auth
#     Worktree: wt-claude-add-user-auth

# Step 5: Validate worktree
echo -e "\n=== Step 5: Validating worktree ==="
wtvalidate wt-claude-add-user-auth

# Output:
# 🔍 Validating worktree: wt-claude-add-user-auth
# --------------------------------
# ✓ Checking naming convention...
#   ✅ Naming valid
# ✓ Checking git status...
#   Branch: add-user-auth
#   Tracking: origin/add-user-auth
#   ✅ Working directory clean
#   ✅ Git repository integrity OK
# --------------------------------
# ✅ Validation complete

# Step 6: Simulate session loss (for demo)
echo -e "\n=== Step 6: Simulating session loss ==="
tmkill claude-add-user-auth --force

# Output:
# ✅ Killed: claude-add-user-auth

# Step 7: Recover session
echo -e "\n=== Step 7: Recovering session ==="
wtrecover --task-id add-user-auth

# Output:
# 🔍 Recovering session...
#   Task ID: add-user-auth
#   Worktree: wt-claude-add-user-auth
#   Session: claude-add-user-auth
# ✓ Switching to worktree: wt-claude-add-user-auth
# ⚠️  Session lost: claude-add-user-auth
#    Recreating session...
# ✓ Session recreated: claude-add-user-auth
# ✓ Attaching to session...
# 
# ✅ Recovery complete (2s)

# Step 8: Cleanup when done
echo -e "\n=== Step 8: Cleaning up ==="
wtrm wt-claude-add-user-auth --force
tmkill claude-add-user-auth --force

# Output:
# ✅ Removed: wt-claude-add-user-auth
# 🗑️  Deleted local branch: add-user-auth
# ✅ Killed: claude-add-user-auth

echo -e "\n✅ Workflow complete!"
