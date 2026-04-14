#!/usr/bin/env zsh
# lib/doctor_plugins.sh - Claude plugin diagnostics support for vibe doctor

_doctor_trim() {
    local value="$1"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    printf "%s" "$value"
}

_doctor_plugin_install_hint() {
    local plugin_name="$1"
    printf "claude plugin install %s" "$plugin_name"
}

_doctor_plugin_scope_hint() {
    local plugin_name="$1"
    local expected_scope="$2"
    local install_hint
    install_hint="$(_doctor_plugin_install_hint "$plugin_name")"

    if [[ -n "$expected_scope" ]]; then
        printf "%s --scope %s" "$install_hint" "$expected_scope"
    else
        printf "%s" "$install_hint"
    fi
}

_doctor_collect_installed_plugins() {
    typeset -gA DOCTOR_PLUGIN_VERSION
    typeset -gA DOCTOR_PLUGIN_SCOPE
    typeset -gA DOCTOR_PLUGIN_STATUS

    DOCTOR_PLUGIN_VERSION=()
    DOCTOR_PLUGIN_SCOPE=()
    DOCTOR_PLUGIN_STATUS=()

    local plugin_output=""
    if ! plugin_output="$(claude plugin list 2>&1)"; then
        DOCTOR_PLUGIN_LIST_ERROR="$plugin_output"
        return 1
    fi

    DOCTOR_PLUGIN_LIST_ERROR=""

    local current_plugin=""
    local line=""
    local trimmed=""
    local plugin_status_text=""
    while IFS= read -r line; do
        trimmed="$(_doctor_trim "$line")"
        [[ -z "$trimmed" || "$trimmed" == "Installed plugins:" ]] && continue

        if [[ "$trimmed" == "❯ "* ]]; then
            current_plugin="${trimmed#❯ }"
            DOCTOR_PLUGIN_STATUS[$current_plugin]="unknown"
            continue
        fi

        [[ -z "$current_plugin" ]] && continue

        if [[ "$trimmed" == Version:* ]]; then
            DOCTOR_PLUGIN_VERSION[$current_plugin]="$(_doctor_trim "${trimmed#Version:}")"
        elif [[ "$trimmed" == Scope:* ]]; then
            DOCTOR_PLUGIN_SCOPE[$current_plugin]="$(_doctor_trim "${trimmed#Scope:}")"
        elif [[ "$trimmed" == Status:* ]]; then
            plugin_status_text="$(_doctor_trim "${trimmed#Status:}")"
            plugin_status_text="${plugin_status_text#✔ }"
            plugin_status_text="${plugin_status_text#✘ }"
            DOCTOR_PLUGIN_STATUS[$current_plugin]="$(_doctor_trim "$plugin_status_text")"
        fi
    done <<< "$plugin_output"

    return 0
}

_doctor_print_plugin_status() {
    local plugin_name="$1"
    local expected_scope="$2"
    local description="$3"
    local severity="${4:-optional}"
    local plugin_status="${DOCTOR_PLUGIN_STATUS[$plugin_name]-}"
    local scope="${DOCTOR_PLUGIN_SCOPE[$plugin_name]-}"
    local version="${DOCTOR_PLUGIN_VERSION[$plugin_name]-}"
    local details=()
    local missing_return=2

    case "$severity" in
        required) missing_return=1 ;;
        recommended) missing_return=3 ;;
        optional) missing_return=2 ;;
    esac

    [[ -n "$description" ]] && echo "      $description"

    if [[ -z "$plugin_status" ]]; then
        printf "  ${YELLOW}!${NC} %-36s 未安装\n" "$plugin_name"
        echo "      安装建议: $(_doctor_plugin_scope_hint "$plugin_name" "$expected_scope")"
        return "$missing_return"
    fi

    [[ -n "$scope" ]] && details+=("$scope")
    [[ -n "$plugin_status" ]] && details+=("$plugin_status")
    [[ -n "$version" && "$version" != "unknown" ]] && details+=("$version")

    local detail_text="installed"
    if (( ${#details[@]} > 0 )); then
        detail_text="${(j:, :)details}"
    fi

    if [[ -n "$expected_scope" && "$scope" != "$expected_scope" ]]; then
        printf "  ${YELLOW}!${NC} %-36s scope 不符合预期\n" "$plugin_name"
        echo "      当前状态: ${detail_text}"
        echo "      期望 scope: ${expected_scope}"
        echo "      安装建议: $(_doctor_plugin_scope_hint "$plugin_name" "$expected_scope")"
        return "$missing_return"
    fi

    if [[ "$plugin_status" == "enabled" ]]; then
        printf "  ${GREEN}✓${NC} %-36s %s\n" "$plugin_name" "$detail_text"
        return 0
    fi

    printf "  ${YELLOW}!${NC} %-36s 已安装但未启用\n" "$plugin_name"
    echo "      当前状态: ${detail_text}"
    echo "      建议：先在 Claude CLI 中启用该 plugin"
    return "$missing_return"
}

_doctor_check_plugins() {
    local config_output="$1"
    local required_missing=0
    local recommended_missing=0
    local optional_missing=0
    local line=""
    local name=""
    local expected_scope=""
    local description=""

    DOCTOR_PLUGIN_REQUIRED_MISSING=0
    DOCTOR_PLUGIN_RECOMMENDED_MISSING=0
    DOCTOR_PLUGIN_OPTIONAL_MISSING=0

    echo "${BOLD}Claude Plugins:${NC}"
    echo ""

    if ! _doctor_collect_installed_plugins; then
        log_warn "无法获取 plugin 列表（claude plugin list 失败）"
        echo "  建议：确保 Claude CLI 正确安装并配置"
        [[ -n "$DOCTOR_PLUGIN_LIST_ERROR" ]] && echo "  详情: $DOCTOR_PLUGIN_LIST_ERROR"
        return 1
    fi

    echo "  ${CYAN}必要 plugins:${NC}"
    local in_required=false
    while IFS= read -r line; do
        if [[ "$line" == "# REQUIRED_PLUGINS" ]]; then
            in_required=true
            continue
        fi
        if [[ "$line" =~ "^#" ]]; then
            in_required=false
            continue
        fi
        if $in_required && [[ -n "$line" ]]; then
            IFS='|' read -r name expected_scope description <<< "$line"
            _doctor_print_plugin_status "$name" "$expected_scope" "$description" required
            case $? in
                1) ((required_missing+=1)) ;;
            esac
        fi
    done <<< "$config_output"

    echo ""
    echo "  ${CYAN}建议 plugins:${NC}"
    local in_recommended=false
    while IFS= read -r line; do
        if [[ "$line" == "# RECOMMENDED_PLUGINS" ]]; then
            in_recommended=true
            continue
        fi
        if [[ "$line" =~ "^#" ]]; then
            in_recommended=false
            continue
        fi
        if $in_recommended && [[ -n "$line" ]]; then
            IFS='|' read -r name expected_scope description <<< "$line"
            _doctor_print_plugin_status "$name" "$expected_scope" "$description" recommended
            case $? in
                3) ((recommended_missing+=1)) ;;
            esac
        fi
    done <<< "$config_output"

    echo ""
    echo "  ${CYAN}可选 plugins:${NC}"
    local in_optional=false
    while IFS= read -r line; do
        if [[ "$line" == "# OPTIONAL_PLUGINS" ]]; then
            in_optional=true
            continue
        fi
        if [[ "$line" =~ "^#" ]]; then
            in_optional=false
            continue
        fi
        if $in_optional && [[ -n "$line" ]]; then
            IFS='|' read -r name expected_scope description <<< "$line"
            _doctor_print_plugin_status "$name" "$expected_scope" "$description" optional
            case $? in
                2) ((optional_missing+=1)) ;;
            esac
        fi
    done <<< "$config_output"

    echo ""
    if (( required_missing == 0 )); then
        log_success "必要 plugins 已满足"
    else
        log_warn "必要 plugins 缺失 $required_missing 个"
    fi

    if (( recommended_missing > 0 )); then
        log_warn "建议 plugins 缺失 $recommended_missing 个（推荐补齐）"
    fi

    if (( optional_missing > 0 )); then
        log_warn "可选 plugins 缺失 $optional_missing 个（按需安装）"
    fi

    DOCTOR_PLUGIN_REQUIRED_MISSING=$required_missing
    DOCTOR_PLUGIN_RECOMMENDED_MISSING=$recommended_missing
    DOCTOR_PLUGIN_OPTIONAL_MISSING=$optional_missing

    (( required_missing == 0 ))
}
