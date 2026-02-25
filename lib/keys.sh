#!/usr/bin/env zsh
# v2/lib/keys.sh - API Key Management for Vibe 2.0
# Target: ~60 lines | Read/write/list keys from keys.env

# ── Keys File Location ──────────────────────────────────
_keys_file() {
    local f="$VIBE_CONFIG/keys.env"
    [[ -f "$f" ]] || f="${HOME}/.vibe/keys.env"
    echo "$f"
}

# ── List Keys ───────────────────────────────────────────
_keys_list() {
    local kf="$(_keys_file)"
    echo "${BOLD}API Key Status${NC} ($kf)"
    echo ""

    if [[ ! -f "$kf" ]]; then
        log_warn "No keys.env found"
        echo "💡 Create from template: ${CYAN}vibe keys init${NC}"
        return 0
    fi

    while IFS='=' read -r key value; do
        [[ "$key" =~ ^[[:space:]]*# ]] && continue
        [[ -z "$key" ]] && continue
        if [[ "$value" == *"<"*">"* || -z "$value" ]]; then
            echo "  ${YELLOW}!${NC} ${key}"
        else
            echo "  ${GREEN}✓${NC} ${key}"
        fi
    done < "$kf"
}

# ── Set a Key ───────────────────────────────────────────
_keys_set() {
    local key="$1" value="$2"
    [[ -z "$key" || -z "$value" ]] && { log_error "Usage: vibe keys set <KEY_NAME> <value>"; return 1; }

    local kf="$(_keys_file)"
    [[ ! -f "$kf" ]] && { log_error "No keys.env found. Run: vibe keys init"; return 1; }

    if grep -q "^${key}=" "$kf" 2>/dev/null; then
        # Update existing key
        sed -i '' "s|^${key}=.*|${key}=${value}|" "$kf"
        log_success "Updated: $key"
    else
        # Append new key
        echo "${key}=${value}" >> "$kf"
        log_success "Added: $key"
    fi
}

# ── Get a Key ───────────────────────────────────────────
_keys_get() {
    local key="$1"
    [[ -z "$key" ]] && { log_error "Usage: vibe keys get <KEY_NAME>"; return 1; }

    local kf="$(_keys_file)"
    grep "^${key}=" "$kf" 2>/dev/null | head -1 | cut -d'=' -f2- || \
        { log_warn "Key not found: $key"; return 1; }
}

# ── Init from Template ──────────────────────────────────
_keys_init() {
    local kf="$VIBE_CONFIG/keys.env"
    local tpl="$VIBE_CONFIG/keys.template.env"

    if [[ -f "$kf" ]]; then
        log_warn "keys.env already exists: $kf"
        confirm_action "Overwrite?" || return 0
    fi

    if [[ -f "$tpl" ]]; then
        cp "$tpl" "$kf"
        log_success "Created keys.env from template"
        echo "💡 Edit: ${CYAN}\${EDITOR:-vim} $kf${NC}"
    else
        log_error "Template not found: $tpl"
        return 1
    fi
}

# ── Dispatcher ──────────────────────────────────────────
vibe_keys() {
    local subcmd="${1:-list}"
    shift 2>/dev/null || true

    case "$subcmd" in
        list|ls)   _keys_list ;;
        set)       _keys_set "$@" ;;
        get)       _keys_get "$@" ;;
        init)      _keys_init ;;
        *)         log_error "Unknown: vibe keys $subcmd"
                   echo "Usage: vibe keys {list|set|get|init}" ;;
    esac
}
