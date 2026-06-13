#!/usr/bin/env zsh
# vibe profiles - Profile definitions for vibe init
# Each profile defines different initialization behaviors and configurations

# ── Profile Schema ─────────────────────────────────────────────

# Profile configuration structure (generated to .vibe/config.yaml):
#
# profile: <minimal|github-flow|vibe-center>
# features:
#   agent: <true|false>          # Whether to create .agent/ directory
#   local_skills: <true|false>   # Whether to create skills/ directory
#   global_skills: <true|false>  # Whether to symlink ~/.vibe/skills → .claude/skills/
#   supervisor: <true|false>     # Whether to enable supervisor orchestration
#   github_labels: <true|false>  # Whether to create GitHub labels
#   github_orchestration: <true|false>  # Whether to enable GitHub flow/PR/issue orchestration
# conventions:
#   branches:
#     task_prefix: <string|none>   # Task branch prefix (e.g., "task/issue-")
#     dev_prefix: <string|none>    # Dev branch prefix (e.g., "dev/issue-")
#   labels:
#     state_prefix: <string|none>  # State label prefix (e.g., "state/")
#     vibe_task: <string|none>     # Vibe task tracking label (e.g., "vibe-task")
#   supervisor:
#     enabled: <true|false>
#     apply_file: <string|none>    # Supervisor apply.md path
#   agents:
#     manager_name: <string|none>  # Manager agent name (e.g., "vibe-manager-agent")
#
# paths:
#   policies_root: <string>       # Policy files root (global or repo-local)
#   prompts_root: <string>        # Prompts root (global or repo-local)
#   skills_manifest: <string>     # Skills manifest path

# ── Profile Definitions ─────────────────────────────────────────

# Minimal profile - Basic runtime without GitHub orchestration
PROFILE_MINIMAL=(
    "profile:minimal"
    "features.agent:false"
    "features.local_skills:false"
    "features.global_skills:false"
    "features.supervisor:false"
    "features.github_labels:false"
    "features.github_orchestration:false"
    "conventions.branches.task_prefix:none"
    "conventions.branches.dev_prefix:none"
    "conventions.labels.state_prefix:none"
    "conventions.labels.vibe_task:none"
    "conventions.supervisor.enabled:false"
    "conventions.supervisor.apply_file:none"
    "conventions.agents.manager_name:none"
    "paths.policies_root:\${HOME}/.vibe/assets/policies"
    "paths.prompts_root:\${HOME}/.vibe/assets/prompts"
    "paths.skills_manifest:\${HOME}/.vibe/skills.json"
)

# GitHub-flow profile - GitHub issue/PR/label orchestration
PROFILE_GITHUB_FLOW=(
    "profile:github-flow"
    "features.agent:true"
    "features.local_skills:false"
    "features.global_skills:true"
    "features.supervisor:false"
    "features.github_labels:true"
    "features.github_orchestration:true"
    "conventions.branches.task_prefix:task/issue-"
    "conventions.branches.dev_prefix:dev/issue-"
    "conventions.labels.state_prefix:state/"
    "conventions.labels.vibe_task:vibe-task"
    "conventions.supervisor.enabled:false"
    "conventions.supervisor.apply_file:none"
    "conventions.agents.manager_name:none"
    "paths.policies_root:\${HOME}/.vibe/assets/policies"
    "paths.prompts_root:\${HOME}/.vibe/assets/prompts"
    "paths.skills_manifest:\${HOME}/.vibe/skills.json"
)

# Vibe-center profile - Full Vibe Center distribution
PROFILE_VIBE_CENTER=(
    "profile:vibe-center"
    "features.agent:true"
    "features.local_skills:true"
    "features.global_skills:true"
    "features.supervisor:true"
    "features.github_labels:true"
    "features.github_orchestration:true"
    "conventions.branches.task_prefix:task/issue-"
    "conventions.branches.dev_prefix:dev/issue-"
    "conventions.labels.state_prefix:state/"
    "conventions.labels.vibe_task:vibe-task"
    "conventions.supervisor.enabled:true"
    "conventions.supervisor.apply_file:supervisor/apply.md"
    "conventions.agents.manager_name:vibe-manager-agent"
    "paths.policies_root:supervisor/policies"
    "paths.prompts_root:config/prompts"
    "paths.skills_manifest:config/v3/skills.json"
)

# ── Profile Helper Functions ────────────────────────────────────

# Get profile configuration array by name (returns array via global variable)
get_profile_config() {
    local profile_name="$1"

    case "$profile_name" in
        minimal)
            PROFILE_CONFIG_ARRAY=("${PROFILE_MINIMAL[@]}")
            ;;
        github-flow)
            PROFILE_CONFIG_ARRAY=("${PROFILE_GITHUB_FLOW[@]}")
            ;;
        vibe-center)
            PROFILE_CONFIG_ARRAY=("${PROFILE_VIBE_CENTER[@]}")
            ;;
        *)
            echo "ERROR: Unknown profile: $profile_name"
            return 1
            ;;
    esac
    return 0
}

# Get profile feature value (reads from PROFILE_CONFIG_ARRAY global)
get_profile_feature() {
    local feature_name="$1"  # e.g., "agent"

    # Search in global PROFILE_CONFIG_ARRAY
    for entry in "${PROFILE_CONFIG_ARRAY[@]}"; do
        if [[ "$entry" == "features.$feature_name:"* ]]; then
            # Extract value after colon
            echo "${entry#*:}"
            return
        fi
    done

    # Default if not found
    echo "false"
}

# Get profile convention value (reads from PROFILE_CONFIG_ARRAY global)
get_profile_convention() {
    local convention_path="$1"  # e.g., "branches.task_prefix"

    # Search in global PROFILE_CONFIG_ARRAY
    for entry in "${PROFILE_CONFIG_ARRAY[@]}"; do
        if [[ "$entry" == "conventions.$convention_path:"* ]]; then
            # Extract value after colon
            echo "${entry#*:}"
            return
        fi
    done

    # Default if not found
    echo "none"
}

# Get profile path value (reads from PROFILE_CONFIG_ARRAY global)
get_profile_path() {
    local path_name="$1"  # e.g., "policies_root"

    # Search in global PROFILE_CONFIG_ARRAY
    for entry in "${PROFILE_CONFIG_ARRAY[@]}"; do
        if [[ "$entry" == "paths.$path_name:"* ]]; then
            # Extract value after colon
            local value="${entry#*:}"
            # Expand ${HOME} safely using zsh parameter expansion
            value="${value//\$\{HOME\}/$HOME}"
            echo "$value"
            return
        fi
    done

    # Default if not found
    echo ""
}

# ── Config Generation ───────────────────────────────────────────

# Generate .vibe/config.yaml from profile configuration (uses PROFILE_CONFIG_ARRAY global)
generate_vibe_config_yaml() {
    local profile_name="$1"
    local repo_root="$2"

    # Ensure profile config is loaded in global array
    if ! get_profile_config "$profile_name"; then
        return 1
    fi

    local config_file="$repo_root/.vibe/config.yaml"

    # Generate YAML content (functions read from PROFILE_CONFIG_ARRAY global)
    cat > "$config_file" <<EOF
# Vibe Project Configuration
# Generated by: vibe init --profile $profile_name
# Date: $(date '+%Y-%m-%d %H:%M:%S')

profile: $profile_name

features:
  agent: $(get_profile_feature "agent")
  local_skills: $(get_profile_feature "local_skills")
  global_skills: $(get_profile_feature "global_skills")
  supervisor: $(get_profile_feature "supervisor")
  github_labels: $(get_profile_feature "github_labels")
  github_orchestration: $(get_profile_feature "github_orchestration")

conventions:
  branches:
    task_prefix: $(get_profile_convention "branches.task_prefix")
    dev_prefix: $(get_profile_convention "branches.dev_prefix")
  labels:
    state_prefix: $(get_profile_convention "labels.state_prefix")
    vibe_task: $(get_profile_convention "labels.vibe_task")
  supervisor:
    enabled: $(get_profile_convention "supervisor.enabled")
    apply_file: $(get_profile_convention "supervisor.apply_file")
  agents:
    manager_name: $(get_profile_convention "agents.manager_name")

paths:
  policies_root: $(get_profile_path "policies_root")
  prompts_root: $(get_profile_path "prompts_root")
  skills_manifest: $(get_profile_path "skills_manifest")
EOF

    return 0
}

# ── Profile Validation ──────────────────────────────────────────

# Validate profile name
validate_profile() {
    local profile_name="$1"

    case "$profile_name" in
        minimal|github-flow|vibe-center)
            return 0
            ;;
        *)
            echo "ERROR: Invalid profile: $profile_name"
            echo "Valid profiles: minimal, github-flow, vibe-center"
            return 1
            ;;
    esac
}

# List available profiles with descriptions
list_profiles() {
    echo "Available profiles:"
    echo ""
    echo "  ${GREEN}minimal${NC}"
    echo "    - Minimal runtime without GitHub orchestration"
    echo "    - No .agent/ directory"
    echo "    - No local skills/ or global .claude/skills/ symlinks"
    echo "    - No GitHub labels"
    echo "    - Uses global policies/prompts from ~/.vibe/assets"
    echo ""
    echo "  ${GREEN}github-flow${NC}"
    echo "    - GitHub issue/PR/label orchestration"
    echo "    - Creates .agent/ directory"
    echo "    - Creates GitHub labels (state/*)"
    echo "    - Enables GitHub flow conventions"
    echo "    - Symlinks global ~/.vibe/skills → .claude/skills/ (no local skills/ directory)"
    echo "    - Uses global policies/prompts from ~/.vibe/assets"
    echo ""
    echo "  ${GREEN}vibe-center${NC}"
    echo "    - Full Vibe Center distribution"
    echo "    - Creates .agent/ and skills/ structure"
    echo "    - Enables supervisor orchestration"
    echo "    - Creates GitHub labels (state/*)"
    echo "    - Uses repo-local policies/prompts/skills"
    echo ""
}