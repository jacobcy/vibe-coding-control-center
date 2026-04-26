#!/usr/bin/env zsh
# lib/keys_support.sh - Provider detection and resolution helpers for vibe keys

_keys_file() {
    if [[ "$VIBE_ROOT" == "$HOME/.vibe" ]]; then
        echo "$HOME/.vibe/keys.env"
        return
    fi

    local f="$VIBE_CONFIG/keys.env"
    [[ -f "$f" ]] || f="${HOME}/.vibe/keys.env"
    echo "$f"
}

_keys_trim() {
    local value="$1"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    printf "%s" "$value"
}

_keys_is_meaningful_value() {
    local value="$1"
    [[ -z "$value" ]] && return 1
    [[ "$value" == \<* ]] && return 1
    [[ "$value" == \"\<* ]] && return 1
    return 0
}

_keys_runtime_value() {
    local env_var="$1"
    local value="${(P)env_var}"
    _keys_is_meaningful_value "$value" || return 1
    printf "%s" "$value"
}

_keys_file_value() {
    local env_var="$1"
    local kf="$(_keys_file)"
    [[ -f "$kf" ]] || return 1

    local line
    line="$(grep -E "^${env_var}=" "$kf" 2>/dev/null | head -1)"
    [[ -n "$line" ]] || return 1

    local value="${line#*=}"
    value="$(_keys_trim "$value")"
    _keys_is_meaningful_value "$value" || return 1
    printf "%s" "$value"
}

_keys_has_tool() {
    command -v "$1" >/dev/null 2>&1
}

_keys_load_plugin_cache() {
    if [[ -n "${KEYS_PLUGIN_CACHE_LOADED:-}" ]]; then
        return 0
    fi

    typeset -gA KEYS_PLUGIN_STATUS
    KEYS_PLUGIN_STATUS=()
    typeset -g KEYS_PLUGIN_CACHE_LOADED=1

    local plugin_output=""
    if ! plugin_output="$(claude plugin list 2>/dev/null)"; then
        return 0
    fi

    local current_plugin=""
    local line=""
    local trimmed=""
    local plugin_status_text=""
    while IFS= read -r line; do
        trimmed="$(_keys_trim "$line")"
        [[ -z "$trimmed" || "$trimmed" == "Installed plugins:" ]] && continue

        if [[ "$trimmed" == "❯ "* ]]; then
            current_plugin="${trimmed#❯ }"
            KEYS_PLUGIN_STATUS[$current_plugin]="unknown"
            continue
        fi

        [[ -z "$current_plugin" ]] && continue

        if [[ "$trimmed" == Status:* ]]; then
            plugin_status_text="$(_keys_trim "${trimmed#Status:}")"
            plugin_status_text="${plugin_status_text#✔ }"
            plugin_status_text="${plugin_status_text#✘ }"
            KEYS_PLUGIN_STATUS[$current_plugin]="$(_keys_trim "$plugin_status_text")"
        fi
    done <<< "$plugin_output"
}

_keys_plugin_enabled() {
    _keys_load_plugin_cache
    [[ "${KEYS_PLUGIN_STATUS[$1]-}" == "enabled" ]]
}

_keys_has_gh_auth() {
    gh auth status >/dev/null 2>&1
}

_keys_load_codex_auth_cache() {
    if [[ -n "${KEYS_CODEX_AUTH_CACHE_LOADED:-}" ]]; then
        return 0
    fi

    typeset -g KEYS_CODEX_AUTH_CACHE_LOADED=1
    typeset -g KEYS_CODEX_AUTH_STATUS=""

    local status_output=""
    if ! status_output="$(codex login status 2>&1)"; then
        return 0
    fi

    KEYS_CODEX_AUTH_STATUS="$(_keys_trim "$status_output")"
}

_keys_has_codex_auth() {
    _keys_load_codex_auth_cache
    [[ -n "$KEYS_CODEX_AUTH_STATUS" ]]
}

_keys_codex_auth_summary() {
    _keys_load_codex_auth_cache
    printf "%s" "${KEYS_CODEX_AUTH_STATUS:-Codex 登录}"
}

_keys_load_claude_auth_cache() {
    if [[ -n "${KEYS_CLAUDE_AUTH_CACHE_LOADED:-}" ]]; then
        return 0
    fi

    typeset -g KEYS_CLAUDE_AUTH_CACHE_LOADED=1
    typeset -g KEYS_CLAUDE_AUTH_LOGGED_IN=""
    typeset -g KEYS_CLAUDE_AUTH_METHOD=""
    typeset -g KEYS_CLAUDE_AUTH_PROVIDER=""

    local auth_json=""
    if ! auth_json="$(claude auth status 2>/dev/null)"; then
        return 0
    fi

    local parsed=""
    parsed="$(python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(1)
print("logged_in=" + str(bool(data.get("loggedIn", False))).lower())
print("auth_method=" + str(data.get("authMethod", "")))
print("api_provider=" + str(data.get("apiProvider", "")))
' <<< "$auth_json" 2>/dev/null)" || return 0

    local line key value
    while IFS='=' read -r key value; do
        case "$key" in
            logged_in) KEYS_CLAUDE_AUTH_LOGGED_IN="$value" ;;
            auth_method) KEYS_CLAUDE_AUTH_METHOD="$value" ;;
            api_provider) KEYS_CLAUDE_AUTH_PROVIDER="$value" ;;
        esac
    done <<< "$parsed"
}

_keys_has_claude_auth() {
    _keys_load_claude_auth_cache
    [[ "$KEYS_CLAUDE_AUTH_LOGGED_IN" == "true" ]]
}

_keys_load_claude_settings_cache() {
    if [[ -n "${KEYS_CLAUDE_SETTINGS_CACHE_LOADED:-}" ]]; then
        return 0
    fi

    typeset -g KEYS_CLAUDE_SETTINGS_CACHE_LOADED=1
    typeset -gA KEYS_CLAUDE_SETTINGS_ENV
    KEYS_CLAUDE_SETTINGS_ENV=()

    local settings_file="$HOME/.claude/settings.json"
    [[ -f "$settings_file" ]] || return 0

    local parsed=""
    parsed="$(python3 -c '
import json, sys
from pathlib import Path
try:
    data = json.loads(Path(sys.argv[1]).read_text())
except Exception:
    sys.exit(1)
env = data.get("env", {}) or {}
for key, value in env.items():
    print(str(key) + "=" + str(value))
' "$settings_file" 2>/dev/null)" || return 0

    local line key value
    while IFS='=' read -r key value; do
        [[ -n "$key" ]] && KEYS_CLAUDE_SETTINGS_ENV[$key]="$value"
    done <<< "$parsed"
}

_keys_settings_value() {
    local env_var="$1"
    _keys_load_claude_settings_cache
    local value="${KEYS_CLAUDE_SETTINGS_ENV[$env_var]-}"
    _keys_is_meaningful_value "$value" || return 1
    printf "%s" "$value"
}

_keys_cc_switch_active() {
    local base_url=""
    base_url="$(_keys_settings_value "ANTHROPIC_BASE_URL" 2>/dev/null)" || return 1

    if [[ "$base_url" != "http://127.0.0.1:15721" ]]; then
        return 1
    fi

    lsof -iTCP:15721 -sTCP:LISTEN -n -P 2>/dev/null | rg -q "127\\.0\\.0\\.1:15721"
}

_keys_cc_switch_summary() {
    local base_url=""
    base_url="$(_keys_settings_value "ANTHROPIC_BASE_URL" 2>/dev/null || printf "http://127.0.0.1:15721")"
    printf "cc-switch 本地代理 (%s)" "$base_url"
}

_keys_claude_auth_summary() {
    _keys_load_claude_auth_cache

    if [[ "$KEYS_CLAUDE_AUTH_PROVIDER" == "firstParty" ]]; then
        printf "Claude 官方登录"
        return 0
    fi

    if [[ -n "$KEYS_CLAUDE_AUTH_PROVIDER" || -n "$KEYS_CLAUDE_AUTH_METHOD" ]]; then
        printf "Claude 登录（provider=%s, method=%s）" \
            "${KEYS_CLAUDE_AUTH_PROVIDER:-unknown}" \
            "${KEYS_CLAUDE_AUTH_METHOD:-unknown}"
        return 0
    fi

    printf "Claude 登录"
}

_keys_load_gemini_auth_cache() {
    if [[ -n "${KEYS_GEMINI_AUTH_CACHE_LOADED:-}" ]]; then
        return 0
    fi

    typeset -g KEYS_GEMINI_AUTH_CACHE_LOADED=1
    typeset -g KEYS_GEMINI_AUTH_ACTIVE_ACCOUNT=""
    typeset -g KEYS_GEMINI_AUTH_HAS_OAUTH="false"

    local oauth_file="$HOME/.gemini/oauth_creds.json"
    local accounts_file="$HOME/.gemini/google_accounts.json"

    [[ -f "$oauth_file" ]] && KEYS_GEMINI_AUTH_HAS_OAUTH="true"

    if [[ -f "$accounts_file" ]]; then
        local parsed=""
        parsed="$(python3 -c '
import json, sys
from pathlib import Path
try:
    data = json.loads(Path(sys.argv[1]).read_text())
except Exception:
    sys.exit(1)
print(str(data.get("active", "")))
' "$accounts_file" 2>/dev/null)" || true
        KEYS_GEMINI_AUTH_ACTIVE_ACCOUNT="$(_keys_trim "$parsed")"
    fi
}

_keys_has_gemini_auth() {
    _keys_load_gemini_auth_cache
    [[ "$KEYS_GEMINI_AUTH_HAS_OAUTH" == "true" ]]
}

_keys_gemini_auth_summary() {
    _keys_load_gemini_auth_cache
    if [[ -n "$KEYS_GEMINI_AUTH_ACTIVE_ACCOUNT" ]]; then
        printf "Gemini 登录 (%s)" "$KEYS_GEMINI_AUTH_ACTIVE_ACCOUNT"
        return 0
    fi
    printf "Gemini 登录"
}

_keys_anthropic_env_summary() {
    local base_url=""

    base_url="$(_keys_settings_value "ANTHROPIC_BASE_URL" 2>/dev/null || _keys_runtime_value "ANTHROPIC_BASE_URL" 2>/dev/null || _keys_file_value "ANTHROPIC_BASE_URL" 2>/dev/null)"
    if [[ -n "$base_url" ]]; then
        printf "自定义 Claude provider（%s)" "$base_url"
        return 0
    fi

    printf "通过 ANTHROPIC_AUTH_TOKEN"
}

_keys_reference_state() {
    local ref="$1"
    local kind="${ref%%:*}"
    local target="${ref#*:}"

    case "$kind" in
        tool)
            if _keys_has_tool "$target"; then
                printf "active|检测到工具 %s" "$target"
            else
                printf "inactive|未检测到工具 %s" "$target"
            fi
            ;;
        plugin)
            if _keys_plugin_enabled "$target"; then
                printf "active|检测到 plugin %s" "$target"
            else
                printf "inactive|未检测到 plugin %s" "$target"
            fi
            ;;
        *)
            printf "inactive|未知依赖引用 %s" "$ref"
            ;;
    esac
}

_keys_capability_state() {
    local env_var="$1"
    local used_by_csv="$2"
    local activation="${3:-any_used}"
    local ref="" ref_state="" ref_reason=""

    case "$activation" in
        always)
            printf "active|按声明始终检查"
            return 0
            ;;
        explicit_only)
            if _keys_runtime_value "$env_var" >/dev/null || _keys_file_value "$env_var" >/dev/null; then
                printf "active|已显式配置"
            else
                printf "inactive|未检测到显式配置，跳过"
            fi
            return 0
            ;;
        any_used)
            if [[ -z "$used_by_csv" ]]; then
                printf "inactive|未声明依赖能力，跳过"
                return 0
            fi

            local refs=("${(@s:,:)used_by_csv}")
            for ref in "${refs[@]}"; do
                [[ -z "$ref" ]] && continue
                ref_state="$(_keys_reference_state "$ref")"
                if [[ "${ref_state%%|*}" == "active" ]]; then
                    printf "%s" "$ref_state"
                    return 0
                fi
                ref_reason="${ref_state#*|}"
            done

            printf "inactive|%s" "${ref_reason:-未检测到相关能力}"
            return 0
            ;;
        *)
            printf "active|按声明检查"
            ;;
    esac
}

_keys_resolve_status() {
    local env_var="$1"
    local resolution_csv="$2"
    local method=""
    local methods=("${(@s:,:)resolution_csv}")

    if _keys_settings_value "$env_var" >/dev/null; then
        if [[ "$env_var" == "ANTHROPIC_AUTH_TOKEN" ]]; then
            if _keys_cc_switch_active; then
                printf "configured|claude settings|%s" "$(_keys_cc_switch_summary)"
            else
                printf "configured|claude settings|%s" "$(_keys_anthropic_env_summary)"
            fi
        else
            printf "configured|claude settings|"
        fi
        return 0
    fi

    for method in "${methods[@]}"; do
        case "$method" in
        env)
            if _keys_runtime_value "$env_var" >/dev/null; then
                if [[ "$env_var" == "ANTHROPIC_AUTH_TOKEN" ]]; then
                    printf "configured|runtime env|%s" "$(_keys_anthropic_env_summary)"
                else
                    printf "configured|runtime env|"
                fi
                return 0
            fi

            if _keys_file_value "$env_var" >/dev/null; then
                if [[ "$env_var" == "ANTHROPIC_AUTH_TOKEN" ]]; then
                    printf "configured|project keys.env|%s" "$(_keys_anthropic_env_summary)"
                else
                    printf "configured|project keys.env|"
                fi
                return 0
            fi
            ;;
        gh_auth)
            if _keys_has_gh_auth; then
                printf "configured|gh auth|通过 gh auth login 提供"
                return 0
            fi
            ;;
        codex_auth)
            if _keys_has_codex_auth; then
                printf "configured|codex auth|%s" "$(_keys_codex_auth_summary)"
                return 0
            fi
            ;;
        gemini_auth)
            if _keys_has_gemini_auth; then
                printf "configured|gemini auth|%s" "$(_keys_gemini_auth_summary)"
                return 0
            fi
            ;;
        claude_settings)
            if [[ "$env_var" == "ANTHROPIC_AUTH_TOKEN" ]] && _keys_settings_value "$env_var" >/dev/null; then
                if _keys_cc_switch_active; then
                    printf "configured|claude settings|%s" "$(_keys_cc_switch_summary)"
                else
                    printf "configured|claude settings|%s" "$(_keys_anthropic_env_summary)"
                fi
                return 0
            fi
            ;;
        claude_auth)
            if _keys_has_claude_auth; then
                printf "configured|claude auth|%s" "$(_keys_claude_auth_summary)"
                return 0
            fi
            ;;
        esac
    done

    printf "missing||"
}

_keys_missing_recommendation() {
    local resolution_csv="$1"
    local get_from="$2"
    local methods=("${(@s:,:)resolution_csv}")
    local hints=()
    local method=""

    for method in "${methods[@]}"; do
        case "$method" in
            gh_auth) hints+=("可通过 gh auth login") ;;
            claude_auth) hints+=("可通过 claude auth login") ;;
            codex_auth) hints+=("可通过 codex login 登录") ;;
            gemini_auth) hints+=("可通过 Gemini 登录") ;;
            claude_settings) hints+=("可在 Claude settings 中配置或通过 cc-switch 托管") ;;
            env) hints+=("可手动配置 Key（$get_from）") ;;
        esac
    done

    if (( ${#hints[@]} > 0 )); then
        printf "%s" "${(j:；:)hints}"
    else
        printf "可手动配置 Key（%s）" "$get_from"
    fi
}
