#!/usr/bin/env zsh
# vibecoding.sh
# Vibe Coding Control Center (formerly Codex)
# Combines: Claude Code, OpenCode, and Project Initialization

if [ -z "${ZSH_VERSION:-}" ]; then
    if command -v zsh >/dev/null 2>&1; then
        exec zsh -l "$0" "$@"
    fi

    echo "zsh not found. Attempting to install..." >&2
    SUDO=""
    if [ "$(id -u)" -ne 0 ]; then
        if command -v sudo >/dev/null 2>&1; then
            SUDO="sudo"
        else
            echo "sudo not available; please install zsh manually." >&2
            exit 1
        fi
    fi

    if command -v brew >/dev/null 2>&1; then
        brew install zsh
    elif command -v apt-get >/dev/null 2>&1; then
        $SUDO apt-get update && $SUDO apt-get install -y zsh
    elif command -v dnf >/dev/null 2>&1; then
        $SUDO dnf install -y zsh
    elif command -v yum >/dev/null 2>&1; then
        $SUDO yum install -y zsh
    elif command -v pacman >/dev/null 2>&1; then
        $SUDO pacman -Sy --noconfirm zsh
    elif command -v apk >/dev/null 2>&1; then
        $SUDO apk add zsh
    else
        echo "No supported package manager found to install zsh." >&2
        exit 1
    fi

    if command -v zsh >/dev/null 2>&1; then
        exec zsh -l "$0" "$@"
    fi

    echo "zsh install failed; please install zsh and re-run." >&2
    exit 1
fi

set -e

# Ensure core utilities are on PATH (non-login shells may have a minimal PATH)
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

# ================= LOAD UTILITIES =================
SCRIPT_DIR="$(cd "$(dirname "${(%):-%x}")" && pwd)"
VIBE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load all utility modules
source "$SCRIPT_DIR/../lib/utils.sh"
source "$SCRIPT_DIR/../lib/config.sh"
source "$SCRIPT_DIR/../lib/i18n.sh"
source "$SCRIPT_DIR/../lib/cache.sh"
source "$SCRIPT_DIR/../lib/error_handling.sh"
source "$SCRIPT_DIR/../lib/agents.sh"
source "$SCRIPT_DIR/../lib/init_project.sh"
source "$SCRIPT_DIR/../lib/core_commands.sh"

# Load config metadata (no env export)
load_user_config

# Re-ensure PATH after loading user config
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

ensure_oh_my_zsh || true

# ================= CLI COMMAND HANDLING =================
if [[ $# -gt 0 ]]; then
    COMMAND="$1"
    shift
    
    case "$COMMAND" in
        --help|-h)
            echo "Vibe Coding Control Center"
            echo ""
            echo "Usage: vibe [options] [command]"
            echo ""
            echo "Options:"
            echo "  -h, --help     Show this help message"
            echo ""
            echo "Commands:"
            echo "  (no args)      Launch interactive control center"
            echo "  chat           Start default AI tool chat"
            echo "  equip          Install/update AI tools"
            echo "  env            Environment and key management"
            echo "  keys           Key management"
            echo "  init           Initialize new project"
            echo "  sync           Sync workspace identity"
            echo "  diagnostics    Run system diagnostics"
            echo "  tdd            TDD feature management"
            echo ""
            echo "Run 'vibe' without arguments for interactive mode."
            exit 0
            ;;
        tdd)
            if [[ "${1:-}" == "new" ]]; then
                shift
                zsh "$SCRIPT_DIR/../scripts/tdd-init.sh" "$@"
                exit 0
            else
                log_error "Usage: vibe tdd new <feature-name>"
                exit 1
            fi
            ;;
        sync)
            do_sync_identity
            exit 0
            ;;
        keys)
            zsh "$SCRIPT_DIR/env-manager.sh" keys "$@"
            exit 0
            ;;
        env)
            zsh "$SCRIPT_DIR/env-manager.sh" "$@"
            exit 0
            ;;
        chat)
            do_chat
            exit 0
            ;;
        equip)
            do_equip
            exit 0
            ;;
        diagnostics)
            do_diagnostics
            exit 0
            ;;
        init)
            local mode="ai"
            if [[ "$1" == "--local" ]]; then
                mode="local"
                shift
            elif [[ "$1" == "--ai" ]]; then
                mode="ai"
                shift
            fi
            local preset_dir="${1:-}"
            vibe_collect_init_answers "$preset_dir" || exit 1
            vibe_init_project "$mode" || exit 1
            exit 0
            ;;
        *)
            # If command unknown, default to showing the menu but warn
            log_warn "Unknown command: $COMMAND. Entering interactive mode..."
            sleep 1
            ;;
    esac
fi

# ================= MAIN LOOP =================
while true; do
    show_header
    check_status

    echo -e "${BOLD}COMMANDS:${NC}"
    echo -e "  ${GREEN}1)${NC} ${BOLD}IGNITION${NC}    (Start New Project)"
    echo -e "  ${GREEN}2)${NC} ${BOLD}EQUIP${NC}       (Install/Update Tools)"
    echo -e "  ${GREEN}3)${NC} ${BOLD}ENV${NC}         (Environment & Keys)"
    echo -e "  ${GREEN}4)${NC} ${BOLD}SYNC${NC}        (Sync Workspace Identity)"
    echo -e "  ${GREEN}5)${NC} ${BOLD}DIAGNOSTICS${NC} (System Check)"
    echo -e "  ${RED}q)${NC} Quit"
    echo ""

    OPTION=$(prompt_user "Select command (1-5, q)" "" "")

    case $OPTION in
        1) do_ignition ;;
        2) do_equip ;;
        3) zsh "$SCRIPT_DIR/env-manager.sh" ;;
        4) do_sync_identity ;;
        5) do_diagnostics ;;
        q|Q)
            log_success "Happy Coding!"
            exit 0
            ;;
        *)
            log_warn "Invalid option: $OPTION"
            sleep 1
            ;;
    esac
done

