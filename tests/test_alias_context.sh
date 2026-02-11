#!/bin/bash
set -e

# Setup test environment
TEST_DIR=$(mktemp -d)
PROJECT_DIR="$TEST_DIR/project"
mkdir -p "$PROJECT_DIR/.vibe"

# Define VIBE_ROOT for aliases to work
# We assume the test is running from refactor/ root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VIBE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Create local keys.env
echo "VIBE_SESSION=local_session" > "$PROJECT_DIR/.vibe/keys.env"

# Create global fallback (optional, to prove override)
export VIBE_SESSION="global_session"

# Source aliases
# Use zsh to test because aliases.sh is zsh specific
zsh -c "
    export VIBE_ROOT='$VIBE_ROOT'
    export VIBE_HOME='$TEST_DIR' # Mock global home
    source '$VIBE_ROOT/config/aliases.sh'
    
    cd '$PROJECT_DIR'
    
    # Run vibe_load_context manually to verify (since it's internal)
    vibe_load_context
    
    if [[ \"\$VIBE_SESSION\" == 'local_session' ]]; then
        echo 'PASS: VIBE_SESSION updated to local_session'
        exit 0
    else
        echo 'FAIL: VIBE_SESSION is \$VIBE_SESSION'
        exit 1
    fi
"

# Cleanup
rm -rf "$TEST_DIR"
