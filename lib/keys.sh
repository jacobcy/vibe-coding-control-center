#!/usr/bin/env zsh
# lib/keys.sh - API Key Management for Vibe 2.0
# 目标：成为唯一密钥检查入口，从配置驱动生成检查结果
# 职责：只检查密钥状态，不检查工具（工具检查交给 vibe doctor）

# ── 配置读取 ─────────────────────────────────────────────
_keys_read_config() {
    uv run python "$VIBE_ROOT/scripts/vibe-read-dependencies.py" --format shell
}

if [[ "${VIBE_KEYS_SUPPORT_LOADED:-}" != "$VIBE_LIB/keys_support.sh" ]]; then
    source "$VIBE_LIB/keys_support.sh"
    VIBE_KEYS_SUPPORT_LOADED="$VIBE_LIB/keys_support.sh"
fi

_keys_print_entry() {
    local level="$1"
    local name="$2"
    local env_var="$3"
    local description="$4"
    local get_from="$5"
    local note="$6"
    local used_by_csv="$7"
    local resolution_csv="$8"
    local activation="$9"
    local capability_state capability_reason resolve_result
    local state="" reason="" source="" extra=""

    capability_state="$(_keys_capability_state "$env_var" "$used_by_csv" "$activation")"
    state="${capability_state%%|*}"
    reason="${capability_state#*|}"

    if [[ "$state" == "inactive" && "$level" == "optional" ]]; then
        printf "  ${CYAN}-${NC} %-20s 跳过\n" "$name"
        echo "      $reason"
        return 0
    fi

    resolve_result="$(_keys_resolve_status "$env_var" "$resolution_csv")"
    state="${resolve_result%%|*}"
    local remainder="${resolve_result#*|}"
    source="${remainder%%|*}"
    extra="${remainder#*|}"

    case "$state" in
        configured)
            if [[ -n "$extra" ]]; then
                printf "  ${GREEN}✓${NC} %-20s %s (%s)\n" "$name" "${source:-configured}" "$extra"
            else
                printf "  ${GREEN}✓${NC} %-20s %s\n" "$name" "${source:-configured}"
            fi
            ;;
        alternative)
            printf "  ${CYAN}~${NC} %-20s %s\n" "$name" "${source:-alternative}"
            echo "      $description"
            [[ -n "$reason" ]] && echo "      激活原因: $reason"
            [[ -n "$extra" ]] && echo "      当前方案: $extra"
            [[ -n "$note" ]] && echo "      备注: $note"
            ;;
        missing)
            if [[ "$level" == "required" ]]; then
                printf "  ${RED}✗${NC} %-20s 缺失\n" "$name"
            else
                printf "  ${YELLOW}!${NC} %-20s 缺失\n" "$name"
            fi
            echo "      $description"
            [[ -n "$reason" ]] && echo "      激活原因: $reason"
            echo "      建议: $(_keys_missing_recommendation "$resolution_csv" "$get_from")"
            [[ -n "$note" ]] && echo "      备注: $note"
            ;;
    esac
}

# ── Check Keys ──────────────────────────────────────────
_keys_check() {
    local config_output
    config_output="$(_keys_read_config)"

    echo "${BOLD}密钥检查${NC}"
    echo "$(printf '%.0s─' {1..50})"
    echo ""

    # 必要密钥
    echo "${BOLD}必要密钥:${NC}"
    local in_required=false
    local line="" name="" env_var="" description="" get_from="" note="" used_by_csv="" resolution_csv="" activation=""
    while IFS= read -r line; do
        if [[ "$line" == "# REQUIRED_KEYS" ]]; then
            in_required=true
            continue
        fi
        if [[ "$line" =~ "^#" ]]; then
            in_required=false
            continue
        fi
        if $in_required && [[ -n "$line" ]]; then
            IFS='|' read -r name env_var description get_from note used_by_csv resolution_csv activation <<< "$line"
            _keys_print_entry "required" "$name" "$env_var" "$description" "$get_from" "$note" "$used_by_csv" "$resolution_csv" "$activation"
        fi
    done <<< "$config_output"
    echo ""

    # 可选密钥
    echo "${BOLD}可选密钥:${NC}"
    local in_optional=false
    while IFS= read -r line; do
        if [[ "$line" == "# OPTIONAL_KEYS" ]]; then
            in_optional=true
            continue
        fi
        if [[ "$line" =~ "^#" ]]; then
            in_optional=false
            continue
        fi
        if $in_optional && [[ -n "$line" ]]; then
            IFS='|' read -r name env_var description get_from note used_by_csv resolution_csv activation <<< "$line"
            _keys_print_entry "optional" "$name" "$env_var" "$description" "$get_from" "$note" "$used_by_csv" "$resolution_csv" "$activation"
        fi
    done <<< "$config_output"
    echo ""

    # 自定义配置（扫描 keys.env 中的 VIBE_* 变量）
    _keys_print_custom_vars

    echo ""
    echo "${BOLD}配置文件:${NC} ${CYAN}$(_keys_file)${NC}"
    echo ""
    echo "${BOLD}如何设置:${NC}"
    echo "  1. 编辑文件: ${CYAN}\${EDITOR:-vim} $(_keys_file)${NC}"
    echo "  2. 添加变量: KEY=VALUE (每行一个)"
    echo "  3. 保存后重新打开终端，或运行: ${CYAN}source $(_keys_file)${NC}"
    echo ""
    echo "${BOLD}Agent 配置覆盖 (覆盖 config/models.json):${NC}"
    echo "  VIBE_BACKEND_<ROLE>   如 VIBE_BACKEND_PLANNER=opencode"
    echo "  VIBE_MODEL_<ROLE>     如 VIBE_MODEL_PLANNER=deepseek/deepseek-v4-pro"
    echo "  VIBE_DEFAULT_BACKEND  全局默认 backend"
    echo "  VIBE_DEFAULT_MODEL    全局默认 model"
}

# ── Scan Custom VIBE_* Variables ───────────────────────────────
_keys_print_custom_vars() {
    local kf="$(_keys_file)"
    [[ -f "$kf" ]] || return 0

    local defined_vars
    defined_vars="$(_keys_read_config | grep -E "^[^#]" | cut -d'|' -f2 | sort -u)"

    local file_vars=()
    local line="" var_name="" file_value=""
    while IFS= read -r line; do
        [[ "$line" =~ "^#" ]] && continue
        [[ "$line" =~ "^VIBE_" ]] || continue
        [[ -z "$line" ]] && continue

        var_name="${line%%=*}"
        file_value="${line#*=}"

        echo "$defined_vars" | grep -qx "$var_name" && continue
        [[ -z "$file_value" || "$file_value" =~ "^<.*>$" ]] && continue

        file_vars+=("$var_name|$file_value")
    done < "$kf"

    if (( ${#file_vars[@]} == 0 )); then
        return 0
    fi

    echo "${BOLD}自定义配置 (来自 $(_keys_file_short)):${NC}"
    for entry in "${file_vars[@]}"; do
        var_name="${entry%%|*}"
        file_value="${entry#*|}"
        if [[ -n "${(P)var_name:-}" ]]; then
            printf "  ${GREEN}✓${NC} %-25s %s\n" "$var_name" "${(P)var_name}"
        else
            printf "  ${YELLOW}!${NC} %-25s %s ${YELLOW}(未加载)${NC}\n" "$var_name" "$file_value"
        fi
    done
}

_keys_file_short() {
    local path="$(_keys_file)"
    path="${path/#$HOME/~}"
    local max_len=40
    if (( ${#path} > max_len )); then
        path="...${path: -$max_len}"
    fi
    echo "$path"
}

# ── Get a Key ───────────────────────────────────────────
_keys_get() {
    local key="$1"
    [[ -z "$key" ]] && { log_error "Usage: vibe keys get <KEY_NAME>"; return 1; }

    local kf="$(_keys_file)"
    if [[ ! -f "$kf" ]]; then
        log_warn "No keys.env found"
        echo "💡 Create: ${CYAN}vibe keys init${NC}"
        return 1
    fi

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
    local subcmd="${1:-check}"
    shift 2>/dev/null || true

    case "$subcmd" in
        check|list|ls) _keys_check ;;
        get)           _keys_get "$@" ;;
        init)          _keys_init ;;
        help|-h|--help)
                       echo "${BOLD}Vibe 密钥管理${NC}"
                       echo ""
                       echo "Usage: ${CYAN}vibe keys <subcommand>${NC}"
                       echo ""
                       echo "Subcommands:"
                       echo "  ${GREEN}check${NC}          检查密钥状态（从配置驱动）"
                       echo "  ${GREEN}get${NC} <k>        获取特定密钥明文"
                       echo "  ${GREEN}init${NC}           从模板初始化 keys.env 配置文件"
                       echo ""
                       echo "职责：检查密钥状态（不检查工具）"
                       echo "工具检查：请使用 ${CYAN}vibe doctor${NC}"
                       ;;
        *)             log_error "Unknown: vibe keys $subcmd"
                       echo "Usage: vibe keys <subcommand> (check, get, init)"
                       return 1
                       ;;
    esac
}
