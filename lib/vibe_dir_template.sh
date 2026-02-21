#!/usr/bin/env zsh
# lib/vibe_dir_template.sh
# Directory structure template generator for Vibe environment

# Resolve script directory for sourcing dependencies
_vibe_dir_template_dir="$(cd "$(dirname "${(%):-%x}")" && pwd)"

# Source utilities if available
if [[ -f "${_vibe_dir_template_dir}/utils.sh" ]]; then
    source "${_vibe_dir_template_dir}/utils.sh"
fi

# Create the Vibe directory structure
# Usage: create_vibe_dir_structure [vibe_home_path]
# Default vibe_home: $HOME/.vibe
create_vibe_dir_structure() {
    local vibe_home="${1:-$HOME/.vibe}"

    # Validate path
    if [[ -z "$vibe_home" ]]; then
        echo "Error: vibe_home path is required" >&2
        return 1
    fi

    # Create main directories
    mkdir -p "$vibe_home"/{keys,tools/claude,tools/opencode,mcp,skills,cache}

    # Create vibe.yaml main configuration (if not exists)
    if [[ ! -f "$vibe_home/vibe.yaml" ]]; then
        cat > "$vibe_home/vibe.yaml" << 'EOF'
version: "1.0"
name: "vibe-env"

keys:
  current: anthropic

tools:
  claude:
    enabled: true
    default: true
  opencode:
    enabled: true

mcp:
  - github

defaults:
  editor: cursor
  shell: zsh
EOF
        echo "Created: vibe.yaml"
    else
        echo "Skipped: vibe.yaml (already exists)"
    fi

    # Create anthropic keys template (if not exists)
    if [[ ! -f "$vibe_home/keys/anthropic.env" ]]; then
        cat > "$vibe_home/keys/anthropic.env" << 'EOF'
# Anthropic API Keys
# Fill in your API key below
ANTHROPIC_AUTH_TOKEN=
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_MODEL=claude-sonnet-4-5
EOF
        echo "Created: keys/anthropic.env"
    else
        echo "Skipped: keys/anthropic.env (already exists)"
    fi

    # Create openai keys template (if not exists)
    if [[ ! -f "$vibe_home/keys/openai.env" ]]; then
        cat > "$vibe_home/keys/openai.env" << 'EOF'
# OpenAI API Keys
# Fill in your API key below
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com
EOF
        echo "Created: keys/openai.env"
    else
        echo "Skipped: keys/openai.env (already exists)"
    fi

    # Create current symlink if it doesn't exist or is broken
    local current_link="$vibe_home/keys/current"
    if [[ ! -L "$current_link" ]]; then
        # Use relative path for symlink (more portable)
        ln -sfn "anthropic.env" "$current_link"
        echo "Created: keys/current -> anthropic.env"
    else
        echo "Skipped: keys/current (symlink exists)"
    fi

    echo ""
    echo "Vibe directory structure created at: $vibe_home"
    echo ""
    echo "Next steps:"
    echo "  1. Edit $vibe_home/keys/anthropic.env and add your API key"
    echo "  2. Run 'vibe keys list' to see available key groups"
    echo "  3. Run 'vibe check' to verify your setup"
}

# Remove the Vibe directory structure (for testing/cleanup)
# Usage: remove_vibe_dir_structure [vibe_home_path]
remove_vibe_dir_structure() {
    local vibe_home="${1:-$HOME/.vibe}"

    if [[ -z "$vibe_home" || "$vibe_home" == "/" || "$vibe_home" == "$HOME" ]]; then
        echo "Error: Refusing to remove unsafe path: $vibe_home" >&2
        return 1
    fi

    if [[ -d "$vibe_home" ]]; then
        rm -rf "$vibe_home"
        echo "Removed: $vibe_home"
    else
        echo "Not found: $vibe_home"
    fi
}

# Verify the Vibe directory structure
# Usage: verify_vibe_dir_structure [vibe_home_path]
verify_vibe_dir_structure() {
    local vibe_home="${1:-$HOME/.vibe}"
    local issues=0

    echo "Verifying Vibe directory structure at: $vibe_home"
    echo ""

    # Check main config
    if [[ -f "$vibe_home/vibe.yaml" ]]; then
        echo "✓ vibe.yaml exists"
    else
        echo "✗ vibe.yaml missing"
        ((issues++))
    fi

    # Check directories
    for dir in keys tools mcp skills cache; do
        if [[ -d "$vibe_home/$dir" ]]; then
            echo "✓ $dir/ exists"
        else
            echo "✗ $dir/ missing"
            ((issues++))
        fi
    done

    # Check current symlink
    if [[ -L "$vibe_home/keys/current" ]]; then
        local target=$(readlink "$vibe_home/keys/current")
        if [[ -f "$vibe_home/keys/$target" ]]; then
            echo "✓ keys/current symlink valid ($target)"
        else
            echo "✗ keys/current symlink broken (points to $target)"
            ((issues++))
        fi
    else
        echo "✗ keys/current symlink missing"
        ((issues++))
    fi

    # Check at least one keys file
    local key_files=("$vibe_home/keys/"*.env(N))
    if [[ ${#key_files[@]} -gt 0 ]]; then
        echo "✓ Key files exist (${#key_files[@]} found)"
    else
        echo "✗ No key files found"
        ((issues++))
    fi

    echo ""
    if [[ $issues -eq 0 ]]; then
        echo "Verification passed!"
        return 0
    else
        echo "Verification failed with $issues issue(s)"
        return 1
    fi
}
