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

# Load config metadata (no env export)
load_user_config

# Re-ensure PATH after loading user config
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

ensure_oh_my_zsh || true

# Show main header
show_header() {
    clear
    echo -e "${PURPLE}"
    echo "   ______           __          "
    echo "  / ____/____  ____/ /__  _  __"
    echo " / /    / __ \/ __  / _ \| |/_/"
    echo "/ /___ / /_/ / /_/ /  __/>  <  "
    echo "\____/ \____/\__,_/\___/_/|_|  "
    echo -e "${NC}"
    echo -e "${CYAN}    VIBE CODING CONTROL CENTER${NC}"
    echo -e "${CYAN}             v${VIBE_VERSION}${NC}"
    echo -e "${BLUE}====================================${NC}"
}

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
             echo "  config         Manage Vibe Coding configuration"
             echo "  equip          Install/update AI tools"
             echo "  env            Environment and key management"
             echo "  keys           Key management"
             echo "  init           Initialize new project"
             echo "  doctor         System health check (includes diagnostics)"
             echo "  flow           Feature development workflow"
             echo ""
             echo "Run 'vibe' without arguments for interactive mode."
             exit 0
            ;;
        flow)
            zsh "${VIBE_ROOT}/bin/vibe-flow" "$@"
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
            zsh "${VIBE_ROOT}/bin/vibe-chat"
            exit 0
            ;;
        config)
            exec zsh "${VIBE_ROOT}/bin/vibe-config" "$@"
            ;;
        equip)
            zsh "${VIBE_ROOT}/bin/vibe-equip"
            exit 0
            ;;
        doctor)
            zsh "${VIBE_ROOT}/bin/vibe-check"
            exit 0
            ;;
        init)
            zsh "${VIBE_ROOT}/bin/vibe-init" "$@"
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
    # check_status replaced by vibe-check
    zsh "${VIBE_ROOT}/bin/vibe-check"

    echo -e "${BOLD}COMMANDS:${NC}"
    echo -e "  ${GREEN}1)${NC} ${BOLD}CHAT${NC}        (AI Tool Chat)"
    echo -e "  ${GREEN}2)${NC} ${BOLD}CONFIG${NC}      (Manage Configuration)"
    echo -e "  ${GREEN}3)${NC} ${BOLD}DOCTOR${NC}      (System Health & Diagnostics)"
    echo -e "  ${GREEN}4)${NC} ${BOLD}ENV${NC}         (Environment & Keys)"
    echo -e "  ${GREEN}5)${NC} ${BOLD}EQUIP${NC}       (Install/Update Tools)"
    echo -e "  ${GREEN}6)${NC} ${BOLD}FLOW${NC}        (Feature Development Workflow)"
    echo -e "  ${GREEN}7)${NC} ${BOLD}INIT${NC}        (Start New Project)"
    echo -e "  ${GREEN}8)${NC} ${BOLD}SIGN${NC}        (Git Identity Signature)"
    echo -e "  ${RED}q)${NC} Quit"
    echo ""

    OPTION=$(prompt_user "Select command (1-8, q)" "" "")

    case $OPTION in
        1) 
            zsh "${VIBE_ROOT}/bin/vibe-chat" 
            ;;
        2) 
            # Config command - launch the config manager
            zsh "${VIBE_ROOT}/bin/vibe-config" 
            ;;
        3) 
            # vibe-check --diagnostics
            zsh "${VIBE_ROOT}/bin/vibe-check" --diagnostics
            press_enter "Press Enter to return..."
            ;;
        4) 
            zsh "$SCRIPT_DIR/env-manager.sh" 
            ;;
        5) 
            zsh "${VIBE_ROOT}/bin/vibe-equip" 
            ;;
        6) 
            # Flow command - feature development workflow
            zsh "${VIBE_ROOT}/bin/vibe-flow"
            press_enter "Press Enter to continue..."
            ;;
        7) 
            zsh "${VIBE_ROOT}/bin/vibe-init"
            press_enter "Press Enter to continue..."
            ;;
        8) 
            zsh "${VIBE_ROOT}/bin/vibe-sign"
            press_enter "Press Enter to continue..."
            ;;
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
