#!/usr/bin/env zsh
# lib/skill_manager.sh
# Skill management library for Vibe environment

# Resolve script directory for sourcing dependencies
_skill_manager_dir="$(cd "$(dirname "${(%):-%x}")" && pwd)"

# Source dependencies
if [[ -f "${_skill_manager_dir}/utils.sh" ]]; then
    source "${_skill_manager_dir}/utils.sh"
fi
if [[ -f "${_skill_manager_dir}/config.sh" ]]; then
    source "${_skill_manager_dir}/config.sh"
fi

# Skills directory location
VIBE_SKILLS_DIR="${VIBE_HOME:-$HOME/.vibe}/skills"

# List all skills
# Usage: vibe_skill_list
vibe_skill_list() {
    echo "Available skills:"

    if [[ ! -d "$VIBE_SKILLS_DIR" ]]; then
        log_warn "Skills directory not found: $VIBE_SKILLS_DIR"
        echo ""
        log_info "Run 'vibe init' to create the directory structure"
        return 1
    fi

    local found=0
    local count=0

    for skill_file in "$VIBE_SKILLS_DIR"/*.skill.yaml(N); do
        local name=$(basename "$skill_file" .skill.yaml)
        local desc=""

        # Try to extract description from file
        if [[ -f "$skill_file" ]]; then
            desc=$(grep -m1 "^description:" "$skill_file" 2>/dev/null | sed 's/description:[[:space:]]*//')
        fi

        echo "  $name"
        if [[ -n "$desc" ]]; then
            echo "    └─ $desc"
        fi

        found=1
        ((count++))
    done

    if [[ $found -eq 0 ]]; then
        echo "  No skills found"
        echo ""
        log_info "Add a skill with: vibe skill add <path>"
    else
        echo ""
        echo "Total: $count skill(s)"
    fi
}

# Add a skill
# Usage: vibe_skill_add <path_or_url>
vibe_skill_add() {
    local source="$1"
    local name="$2"

    if [[ -z "$source" ]]; then
        log_error "Skill source required"
        echo "Usage: vibe skill add <path> [name]"
        echo "       vibe skill add <url> [name]"
        return 1
    fi

    mkdir -p "$VIBE_SKILLS_DIR"

    # Determine name from source if not provided
    if [[ -z "$name" ]]; then
        name=$(basename "$source" .skill.yaml)
        name=$(basename "$name" .yaml)
    fi

    local target="$VIBE_SKILLS_DIR/${name}.skill.yaml"

    if [[ -f "$target" ]]; then
        log_warn "Skill already exists: $name"
        log_info "Remove it first if you want to update"
        return 0
    fi

    # Handle different source types
    if [[ "$source" =~ ^https?:// ]]; then
        # URL source
        log_info "Downloading skill from: $source"
        if command -v curl >/dev/null 2>&1; then
            curl -fsSL "$source" -o "$target"
        elif command -v wget >/dev/null 2>&1; then
            wget -q "$source" -O "$target"
        else
            log_error "curl or wget required to download from URL"
            return 1
        fi
    elif [[ -f "$source" ]]; then
        # Local file
        if [[ "$source" == *.yaml || "$source" == *.yml ]]; then
            cp "$source" "$target"
        else
            log_error "Skill file must be a YAML file"
            return 1
        fi
    elif [[ -d "$source" ]]; then
        # Directory - look for skill.yaml
        if [[ -f "$source/skill.yaml" ]]; then
            cp "$source/skill.yaml" "$target"
        else
            log_error "No skill.yaml found in directory: $source"
            return 1
        fi
    else
        log_error "Source not found: $source"
        return 1
    fi

    log_success "Added skill: $name"
    echo "File: $target"
}

# Remove a skill
# Usage: vibe_skill_remove <name>
vibe_skill_remove() {
    local name="$1"

    if [[ -z "$name" ]]; then
        log_error "Skill name required"
        echo "Usage: vibe skill remove <name>"
        return 1
    fi

    local target="$VIBE_SKILLS_DIR/${name}.skill.yaml"

    if [[ ! -f "$target" ]]; then
        log_error "Skill not found: $name"
        return 1
    fi

    rm -f "$target"
    log_success "Removed skill: $name"
}

# Show skill details
# Usage: vibe_skill_show <name>
vibe_skill_show() {
    local name="$1"

    if [[ -z "$name" ]]; then
        log_error "Skill name required"
        echo "Usage: vibe skill show <name>"
        return 1
    fi

    local target="$VIBE_SKILLS_DIR/${name}.skill.yaml"

    if [[ ! -f "$target" ]]; then
        log_error "Skill not found: $name"
        return 1
    fi

    echo "Skill: $name"
    echo "File: $target"
    echo ""
    cat "$target"
}

# Create a new skill template
# Usage: vibe_skill_create <name>
vibe_skill_create() {
    local name="$1"

    if [[ -z "$name" ]]; then
        log_error "Skill name required"
        echo "Usage: vibe skill create <name>"
        return 1
    fi

    mkdir -p "$VIBE_SKILLS_DIR"

    local target="$VIBE_SKILLS_DIR/${name}.skill.yaml"

    if [[ -f "$target" ]]; then
        log_error "Skill already exists: $name"
        return 1
    fi

    cat > "$target" << EOF
# $name skill
name: $name
description: ""
version: "1.0"

# Trigger patterns (optional)
triggers:
  - ""

# Instructions
instructions: |
  Add your instructions here.

# Examples (optional)
examples:
  - input: ""
    output: ""
EOF

    log_success "Created skill template: $name"
    echo "File: $target"
    echo ""
    log_info "Edit the file to add your skill content"
}

# Edit a skill
# Usage: vibe_skill_edit <name>
vibe_skill_edit() {
    local name="$1"

    if [[ -z "$name" ]]; then
        log_error "Skill name required"
        echo "Usage: vibe skill edit <name>"
        return 1
    fi

    local target="$VIBE_SKILLS_DIR/${name}.skill.yaml"

    if [[ ! -f "$target" ]]; then
        log_error "Skill not found: $name"
        return 1
    fi

    # Use open_editor if available
    if type open_editor >/dev/null 2>&1; then
        open_editor "$target"
    else
        local editor="${EDITOR:-vim}"
        "$editor" "$target"
    fi
}
