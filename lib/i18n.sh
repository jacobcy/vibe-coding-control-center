#!/usr/bin/env zsh
# Internationalization (i18n) System for Vibe Coding Control Center

# Supported languages
declare -A SUPPORTED_LANGUAGES=(
    ["en"]="English"
    ["zh"]="中文"
    ["ja"]="日本語"
    ["ko"]="한국어"
)

# Current locale
CURRENT_LOCALE="en"

# Translation storage
declare -A TRANSLATIONS

# Load translations for a specific language
load_translations() {
    local lang="${1:-$CURRENT_LOCALE}"
    local translation_file="$VIBE_CONFIG[DOCS_DIR]/locales/${lang}.json"

    # Check if translations file exists
    if [[ -f "$translation_file" ]]; then
        # Validate path
        if ! validate_path "$translation_file" "Translation file validation failed"; then
            log_error "Invalid translation file path: $translation_file"
            return 1
        fi

        # Load translations from JSON file
        if command -v jq >/dev/null 2>&1; then
            # Use jq if available
            while IFS="=" read -r key value; do
                TRANSLATIONS["$key"]="$value"
            done < <(jq -r 'to_entries[] | "\(.key)=\(.value)"' "$translation_file" 2>/dev/null)
        else
            # Fallback: simple key-value parsing from a flat file
            if [[ -f "${translation_file%.json}.txt" ]]; then
                while IFS='=' read -r key value; do
                    # Skip comments and empty lines
                    [[ "$key" =~ ^[[:space:]]*# ]] && continue
                    [[ -z "$key" ]] && continue
                    TRANSLATIONS["$key"]="$value"
                done < "${translation_file%.json}.txt"
            fi
        fi

        log_debug "Loaded translations for language: $lang"
        return 0
    else
        log_warn "Translation file not found: $translation_file, using default English"
        return 0
    fi
}

# Translate a string
translate() {
    local key="$1"
    local default_value="${2:-$key}"  # Use key as default if translation not found

    # Validate input
    if ! validate_input "$key" "false"; then
        log_error "Invalid translation key: $key"
        echo "$default_value"
        return 1
    fi

    # Return translation if found, otherwise return default
    if [[ -n "${TRANSLATIONS[$key]+isset}" ]]; then
        echo "${TRANSLATIONS[$key]}"
    else
        echo "$default_value"
    fi
}

# Set the current locale
set_locale() {
    local lang="$1"

    # Validate language
    if [[ -z "${SUPPORTED_LANGUAGES[$lang]+isset}" ]]; then
        log_error "Unsupported language: $lang. Supported languages: ${!SUPPORTED_LANGUAGES[@]}"
        return 1
    fi

    # Update current locale
    CURRENT_LOCALE="$lang"

    # Load translations for the new locale
    load_translations "$lang"

    log_info "Locale set to: $lang"
    return 0
}

# Get current locale
get_locale() {
    echo "$CURRENT_LOCALE"
}

# Get supported languages
get_supported_languages() {
    for lang in "${!SUPPORTED_LANGUAGES[@]}"; do
        echo "$lang: ${SUPPORTED_LANGUAGES[$lang]}"
    done
}

# Format string with arguments (similar to printf but with translations)
translatef() {
    local key="$1"
    shift
    local args=("$@")

    # Get the translated format string
    local format
    format=$(translate "$key")

    # Apply arguments to the format string
    printf "$format" "${args[@]}"
}

# Initialize i18n system with default locale
initialize_i18n() {
    local default_locale="${DEFAULT_LOCALE:-en}"

    # Set and load default locale
    set_locale "$default_locale"

    log_info "i18n system initialized with locale: $CURRENT_LOCALE"
}

# Create a simple English translation file if none exists
create_default_translations() {
    local lang="${1:-en}"
    local locales_dir="$VIBE_CONFIG[DOCS_DIR]/locales"

    # Create locales directory if it doesn't exist
    if ! mkdir -p "$locales_dir" 2>/dev/null; then
        log_warn "Could not create locales directory: $locales_dir"
        return 1
    fi

    local translation_file="$locales_dir/${lang}.json"

    # Only create if it doesn't exist
    if [[ ! -f "$translation_file" ]]; then
        cat > "$translation_file" << 'EOF'
{
  "welcome_message": "Welcome to Vibe Coding Control Center!",
  "menu_option_ignition": "IGNITION (Start New Project)",
  "menu_option_equip": "EQUIP (Install/Update Tools)",
  "menu_option_diagnostics": "DIAGNOSTICS (System Check)",
  "system_status": "SYSTEM STATUS:",
  "installing_claude": "Installing Claude CLI...",
  "installing_opencode": "Installing OpenCode...",
  "configuration_complete": "Configuration complete!",
  "press_enter_continue": "Press Enter to continue...",
  "error_occurred": "An error occurred:",
  "success_message": "Operation completed successfully!"
}
EOF
        log_info "Created default translations file: $translation_file"
    fi
}

# Initialize i18n system
initialize_i18n

# Create default English translations if needed
create_default_translations "en"
