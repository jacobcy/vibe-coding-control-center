#!/usr/bin/env zsh
# utils.sh
# Enhanced secure utilities for Vibe Coding scripts

# Avoid re-sourcing side effects (readonly redefinition, strict mode flip).
if [[ -n "${VIBE_UTILS_LOADED:-}" ]]; then
    return 0 2>/dev/null || exit 0
fi
readonly VIBE_UTILS_LOADED=1

# Ensure core utilities are on PATH (non-login shells may have a minimal PATH)
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

is_sourced=false
if [[ -n "${ZSH_VERSION:-}" ]]; then
    # Zsh: Check ZSH_EVAL_CONTEXT to see if we are being sourced
    # If it contains "file", we are sourced. If it's just "toplevel" or "cmdarg", we are main.
    if [[ $ZSH_EVAL_CONTEXT == *file* ]]; then
        is_sourced=true
    fi
elif [[ -n "${BASH_VERSION:-}" ]]; then
    [[ "${BASH_SOURCE[0]}" != "$0" ]] && is_sourced=true
fi

# Strict mode for non-interactive, non-sourced shells; avoid nounset in interactive shells.
if [[ "${VIBE_UTILS_STRICT:-}" == "true" ]]; then
    set -euo pipefail  # Exit on error, undefined vars, and pipe failures
elif [[ -o interactive || "$is_sourced" == "true" ]]; then
    :
else
    set -euo pipefail  # Exit on error, undefined vars, and pipe failures
fi

# ================= SECURITY CONSTANTS =================
readonly MAX_PATH_LENGTH=4096
readonly MAX_INPUT_LENGTH=10000
readonly ALLOWED_FILE_MODES="600 640 644 664 755"

# ================= COLORS =================
readonly RED=$'\033[0;31m'
readonly GREEN=$'\033[0;32m'
readonly YELLOW=$'\033[1;33m'
readonly BLUE=$'\033[0;34m'
readonly PURPLE=$'\033[0;35m'
readonly CYAN=$'\033[0;36m'
readonly BOLD=$'\033[1m'
readonly NC=$'\033[0m'  # No Color

# ================= ENHANCED LOGGING =================
# Defined early so other modules can use them
log_debug() {
    local message="$1"
    if [[ "${DEBUG:-false}" == "true" ]]; then
        echo -e "${CYAN}DBG: $message${NC}" >&2
    fi
}

log_info() {
    local message="$1"
    echo -e "${GREEN}✓ $message${NC}"
}

log_warn() {
    local message="$1"
    echo -e "${YELLOW}! $message${NC}" >&2
}

log_error() {
    local message="$1"
    echo -e "${RED}✗ $message${NC}" >&2
}

log_success() {
    local message="$1"
    echo -e "${GREEN}★ $message${NC}"
}

log_step() {
    local message="$1"
    echo -e "${BLUE}>> $message...${NC}"
}

log_critical() {
    local message="$1"
    echo -e "${RED}★★★ CRITICAL: $message${NC}" >&2
}

# ================= CORE HELPERS =================
vibe_mkdir_p() {
    local dir="$1"
    local mkdir_bin
    mkdir_bin=$(command -v mkdir 2>/dev/null || true)
    [[ -z "$mkdir_bin" ]] && mkdir_bin="/bin/mkdir"
    "$mkdir_bin" -p "$dir"
}

vibe_chmod() {
    local mode="$1"
    local path="$2"
    local chmod_bin
    chmod_bin=$(command -v chmod 2>/dev/null || true)
    [[ -z "$chmod_bin" ]] && chmod_bin="/bin/chmod"
    "$chmod_bin" "$mode" "$path"
}

# ================= VALIDATION FUNCTIONS =================
validate_path() {
    local path="$1"
    local error_msg="${2:-Invalid path provided}"

    # Check if path is empty
    if [[ -z "$path" ]]; then
        log_error "$error_msg: Path is empty"
        return 1
    fi

    # Check path length
    if [[ ${#path} -gt $MAX_PATH_LENGTH ]]; then
        log_error "$error_msg: Path too long (${#path} > $MAX_PATH_LENGTH)"
        return 1
    fi

    # Prevent path traversal
    if [[ "$path" == *"../"* || "$path" == *"..\\"* ]]; then
        log_error "$error_msg: Path traversal detected"
        return 1
    fi

    # Check for null bytes
    if [[ "$path" == *$'\0'* ]]; then
        log_error "$error_msg: Null byte detected in path"
        return 1
    fi

    # Basic path format validation (doesn't guarantee existence)
    if [[ "$path" =~ [[:cntrl:]] ]]; then
        log_error "$error_msg: Control characters detected in path"
        return 1
    fi

    return 0
}

validate_input() {
    local input="$1"
    local allow_empty="${2:-false}"

    # Check input length
    if [[ ${#input} -gt $MAX_INPUT_LENGTH ]]; then
        log_error "Input too long (${#input} > $MAX_INPUT_LENGTH)"
        return 1
    fi

    # Check for null bytes
    if [[ "$input" == *$'\0'* ]]; then
        log_error "Null byte detected in input"
        return 1
    fi

    # Check for control characters (excluding newlines and tabs)
    if [[ "$input" =~ [[:cntrl:]] ]]; then
        if [[ "$input" != *$'\n'* && "$input" != *$'\t'* ]]; then
            log_error "Control characters detected in input"
            return 1
        fi
    fi

    # Check for potential command injection patterns
    if [[ "$input" == *'$('* || "$input" == *'`'* || "$input" == *'&&'* || "$input" == *'||'* || "$input" == *';'* || "$input" == *'>'* || "$input" == *'<'* ]]; then
        log_error "Potential command injection detected in input"
        return 1
    fi

    if [[ "$allow_empty" != "true" && -z "$input" ]]; then
        log_error "Input cannot be empty"
        return 1
    fi

    return 0
}

validate_content() {
    local content="$1"
    local allow_empty="${2:-true}"

    # Check content length
    if [[ ${#content} -gt $MAX_INPUT_LENGTH ]]; then
        log_error "Content too long (${#content} > $MAX_INPUT_LENGTH)"
        return 1
    fi

    # Check for null bytes
    if [[ "$content" == *$'\0'* ]]; then
        log_error "Null byte detected in content"
        return 1
    fi

    # Check for control characters (excluding newlines and tabs)
    if [[ "$content" =~ [[:cntrl:]] ]]; then
        if [[ "$content" != *$'\n'* && "$content" != *$'\t'* ]]; then
            log_error "Control characters detected in content"
            return 1
        fi
    fi

    if [[ "$allow_empty" != "true" && -z "$content" ]]; then
        log_error "Content cannot be empty"
        return 1
    fi

    return 0
}

validate_filename() {
    local filename="$1"

    # Validate input first
    if ! validate_input "$filename" "false"; then
        return 1
    fi

    # Check for invalid characters in filename
    if [[ "$filename" =~ [/\0] ]]; then
        log_error "Invalid characters in filename"
        return 1
    fi

    # Check for suspicious patterns
    if [[ "$filename" == .* || "$filename" == /* || "$filename" == *"/.."* || "$filename" == *"\\.."* ]]; then
        log_error "Suspicious filename pattern detected"
        return 1
    fi

    return 0
}

validate_secure_path() {
    local path="$1"
    local error_msg="${2:-Invalid path provided}"

    # Check if path is empty
    if [[ -z "$path" ]]; then
        log_error "$error_msg: Path is empty"
        return 1
    fi

    # Check path length
    if [[ ${#path} -gt $MAX_PATH_LENGTH ]]; then
        log_error "$error_msg: Path too long (${#path} > $MAX_PATH_LENGTH)"
        return 1
    fi

    # Prevent path traversal
    if [[ "$path" == *"../"* || "$path" == *"..\\"* ]]; then
        log_error "$error_msg: Path traversal detected"
        return 1
    fi

    # Check for null bytes
    if [[ "$path" == *$'\0'* ]]; then
        log_error "$error_msg: Null byte detected in path"
        return 1
    fi

    # Basic path format validation (doesn't guarantee existence)
    if [[ "$path" =~ [[:cntrl:]] ]]; then
        log_error "$error_msg: Control characters detected in path"
        return 1
    fi

    # Additional security check: ensure path is within allowed directories
    local abs_path
    if command -v realpath >/dev/null 2>&1; then
        abs_path=$(realpath -q "$path" 2>/dev/null) || {
            # If realpath fails, use a simple canonicalization approach
            case "$path" in
                /*) abs_path="$path" ;;
                *) abs_path="$(pwd)/$path" ;;
            esac
        }
    else
        # Fallback without realpath
        case "$path" in
            /*) abs_path="$path" ;;
            *) abs_path="$(pwd)/$path" ;;
        esac
    fi

    # Define allowed directories
    # Use Zsh modifiers for directory path to avoid external dependency on dirname
    local script_path="${(%):-%x}"
    local script_dir="${script_path:h}"
    local project_root="${script_dir:h}"
    
    local raw_allowed_dirs=("$HOME/.vibe" "$(pwd)/config" "$(pwd)" "$project_root")
    local allowed_dirs=()
    
    # Canonicalize allowed directories
    for d in "${raw_allowed_dirs[@]}"; do
        if command -v realpath >/dev/null 2>&1; then
            allowed_dirs+=("$(realpath -q "$d" 2>/dev/null || echo "$d")")
        else
            allowed_dirs+=("$d")
        fi
    done

    local is_allowed=false

    for allowed_dir in "${allowed_dirs[@]}"; do
        if [[ "$abs_path" == "$allowed_dir"* ]]; then
            is_allowed=true
            break
        fi
    done

    if [[ "$is_allowed" == false ]]; then
        log_error "$error_msg: Path outside allowed directories: $path"
        return 1
    fi

    return 0
}

# ================= ENVIRONMENT VALIDATION =================
check_command_exists() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        log_error "Command not found: $cmd"
        return 1
    fi
    return 0
}

check_directory_writable() {
    local dir="$1"

    # Validate path first
    if ! validate_path "$dir" "Directory path validation failed"; then
        return 1
    fi

    # Get absolute path
    dir="${dir:A}"

    if [[ ! -d "$dir" ]]; then
        log_error "Directory does not exist: $dir"
        return 1
    fi

    if [[ ! -w "$dir" ]]; then
        log_error "Directory not writable: $dir"
        return 1
    fi

    return 0
}

# ================= SECURE FILE OPERATIONS =================
secure_copy() {
    local src="$1"
    local dest="$2"
    local preserve_perms="${3:-false}"

    # Validate paths
    if ! validate_path "$src" "Source path validation failed"; then
        return 1
    fi
    if ! validate_path "$dest" "Destination path validation failed"; then
        return 1
    fi

    # Check if source exists
    if [[ ! -e "$src" ]]; then
        log_error "Source file does not exist: $src"
        return 1
    fi

    # Get absolute paths to prevent path traversal
    src="${src:A}"
    dest_dir="${dest:h}"
    dest_dir="${dest_dir:A}"
    dest="$dest_dir/${dest:t}"

    # Ensure destination directory exists
    if ! vibe_mkdir_p "$dest_dir" 2>/dev/null; then
        log_error "Cannot create destination directory: $dest_dir"
        return 1
    fi

    # Perform copy with appropriate flags
    if [[ "$preserve_perms" == "true" ]]; then
        cp -p "$src" "$dest"
    else
        cp "$src" "$dest"
    fi

    if [[ $? -eq 0 ]]; then
        log_info "Successfully copied $src to $dest"
        return 0
    else
        log_error "Failed to copy $src to $dest"
        return 1
    fi
}

secure_write_file() {
    local filepath="$1"
    local content="$2"
    local perms="${3:-600}"  # Default to read/write for owner only

    # Validate path
    if ! validate_path "$filepath" "File path validation failed"; then
        return 1
    fi

    # Validate content (allow common template characters)
    if ! validate_content "$content" "true"; then
        return 1
    fi

    # Validate permissions format
    if ! [[ "$perms" =~ ^[0-7]{3}$ ]]; then
        log_error "Invalid permission format: $perms (must be 3-digit octal)"
        return 1
    fi

    # Check if the permission is in allowed list
    case " $ALLOWED_FILE_MODES " in
        *" $perms "*)
            ;;
        *)
            log_warn "Unusual file permission: $perms"
            ;;
    esac

    # Get directory and ensure it exists
    local dirpath="${filepath:h}"
    dirpath="${dirpath:A}"

    if ! vibe_mkdir_p "$dirpath"; then
        log_error "Cannot create directory: $dirpath"
        return 1
    fi

    # Write the file
    if printf '%s' "$content" > "$filepath"; then
        vibe_chmod "$perms" "$filepath"
        log_info "Successfully wrote file: $filepath with permissions $perms"
        return 0
    else
        log_error "Failed to write file: $filepath"
        return 1
    fi
}

secure_append_file() {
    local filepath="$1"
    local content="$2"

    # Validate path
    if ! validate_path "$filepath" "File path validation failed"; then
        return 1
    fi

    # Validate content (allow common template characters)
    if ! validate_content "$content" "true"; then
        return 1
    fi

    # Get absolute path
    filepath="${filepath:A}"

    # Append the content
    if printf '%s' "$content" >> "$filepath"; then
        log_info "Successfully appended to file: $filepath"
        return 0
    else
        log_error "Failed to append to file: $filepath"
        return 1
    fi
}

# ================= INPUT PROMPTS WITH VALIDATION =================
prompt_user() {
    local prompt_text="$1"
    local default_value="${2:-}"
    local validator="${3:-}"

    while true; do
        printf "%s? %s%s %s%s%s: " "$YELLOW" "$prompt_text" "$NC" "$BLUE" "${default_value:+[default: $default_value]}" "$NC" >&2
        if read -r input; then
            :
        else
            input=""
        fi

        # Use default if input is empty and default is provided
        if [[ -z "$input" && -n "$default_value" ]]; then
            input="$default_value"
        fi

        # Validate input if validator is provided
        if [[ -n "$validator" ]]; then
            # Use a safe approach instead of eval to prevent command injection
            case "$validator" in
                "validate_input")
                    if validate_input "$input" "false"; then
                        echo "$input"
                        return 0
                    fi
                    ;;
                "validate_input_allow_empty")
                    if validate_input "$input" "true"; then
                        echo "$input"
                        return 0
                    fi
                    ;;
                "validate_path")
                    if validate_path "$input" "Invalid path provided"; then
                        echo "$input"
                        return 0
                    fi
                    ;;
                "validate_filename")
                    if validate_filename "$input"; then
                        echo "$input"
                        return 0
                    fi
                    ;;
                "validate_content")
                    if validate_content "$input" "true"; then
                        echo "$input"
                        return 0
                    fi
                    ;;
                *)
                    log_error "Unknown validator: $validator"
                    return 1
                    ;;
            esac
            log_error "Invalid input, please try again."
            continue
        else
            # Basic validation for non-empty input
            if [[ -n "$input" ]]; then
                echo "$input"
                return 0
            else
                log_error "Input cannot be empty, please try again."
            fi
        fi
    done
}

# ================= SIMPLE PROMPTS =================
press_enter() {
    local message="${1:-Press Enter to continue...}"
    if [[ -t 0 ]]; then
        printf "%s" "$message" >&2
        read -r _input
    fi
}

confirm_action() {
    local prompt="${1:-Are you sure?}"
    local default_response="${2:-n}"
    local response

    while true; do
        # Zsh-specific prompt syntax
        local yn_hint="[Y/n]"
        if [[ "$default_response" == "n" || "$default_response" == "N" ]]; then
            yn_hint="[y/N]"
        fi
        echo -n "${YELLOW}? $prompt ${yn_hint}${NC} ${BLUE}[default: $default_response]${NC}: "
        read -r response
        response=${response:-$default_response}

        case $response in
            [yY][eE][sS]|[yY])
                return 0
                ;;
            [nN][oO]|[nN])
                return 1
                ;;
            *)
                log_error "Please answer yes or no."
                ;;
        esac
    done
}

# ================= SHELL CONFIG =================
get_shell_rc() {
    echo "$HOME/.zshrc"
}

install_zsh() {
    local sudo_cmd=""
    if [[ $EUID -ne 0 ]]; then
        if command -v sudo &> /dev/null; then
            sudo_cmd="sudo"
        else
            log_error "sudo not available; please install zsh manually"
            return 1
        fi
    fi

    if command -v brew &> /dev/null; then
        $sudo_cmd brew install zsh
    elif command -v apt-get &> /dev/null; then
        $sudo_cmd apt-get update
        $sudo_cmd apt-get install -y zsh
    elif command -v dnf &> /dev/null; then
        $sudo_cmd dnf install -y zsh
    elif command -v yum &> /dev/null; then
        $sudo_cmd yum install -y zsh
    elif command -v pacman &> /dev/null; then
        $sudo_cmd pacman -Sy --noconfirm zsh
    elif command -v apk &> /dev/null; then
        $sudo_cmd apk add zsh
    else
        log_error "No supported package manager found to install zsh"
        return 1
    fi
}

ensure_zsh_installed() {
    if command -v zsh &> /dev/null; then
        return 0
    fi

    log_warn "zsh not found, attempting to install..."
    install_zsh || return 1

    if ! command -v zsh &> /dev/null; then
        log_error "zsh installation failed"
        return 1
    fi
    return 0
}

ensure_oh_my_zsh() {
    if [[ -d "$HOME/.oh-my-zsh" ]]; then
        log_info "Oh My Zsh already installed"
        return 0
    fi

    if ! command -v zsh &> /dev/null; then
        log_error "zsh is required to install Oh My Zsh"
        return 1
    fi

    local installer_url="https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh"
    if command -v curl &> /dev/null; then
        RUNZSH=no CHSH=no KEEP_ZSHRC=yes sh -c "$(curl -fsSL "$installer_url")"
    elif command -v wget &> /dev/null; then
        RUNZSH=no CHSH=no KEEP_ZSHRC=yes sh -c "$(wget -qO- "$installer_url")"
    else
        log_error "curl or wget required to install Oh My Zsh"
        return 1
    fi

    if [[ -d "$HOME/.oh-my-zsh" ]]; then
        log_success "Oh My Zsh installed"
        return 0
    fi

    log_error "Oh My Zsh installation failed"
    return 1
}

append_to_rc() {
    local rc_file="$1"
    local content="$2"
    local marker="$3"

    # Validate marker only (content is shell config, should contain variables/commands)
    if ! validate_input "$marker" "false"; then
        return 1
    fi
    if ! validate_path "$rc_file" "RC file path validation failed"; then
        return 1
    fi

    # Get absolute path
    rc_file="${rc_file:A}"

    if [[ -f "$rc_file" ]]; then
        if grep -qF "$marker" "$rc_file" 2>/dev/null; then
            log_info "Configuration already present in $rc_file ($marker)"
        else
            # Use printf instead of echo for better security (handles backslashes properly)
            printf '%s\n' "$content" >> "$rc_file"
            log_info "Added configuration to $rc_file"
            log_warn "Please run: source $rc_file"
        fi
    else
        # Create the file with secure permissions if it doesn't exist
        secure_write_file "$rc_file" "$content" "644"
        log_info "Created new configuration file: $rc_file"
        log_warn "Please run: source $rc_file"
    fi
}

# ================= ERROR HANDLING =================
handle_error() {
    local exit_code=$?
    local func_name="${funcstack[2]:-${funcstack[1]:-unknown}}"
    local file_trace="${funcfiletrace[2]:-${funcfiletrace[1]:-unknown}}"

    log_error "Error occurred in function '$func_name' at $file_trace (exit code: $exit_code)"

    # Log stack trace if debugging is enabled
    if [[ "${DEBUG:-false}" == "true" ]]; then
        log_debug "Stack trace:"
        for i in {1..${#funcstack[@]}}; do
            log_debug "  ${funcfiletrace[$i]} ${funcstack[$i]}"
        done
    fi

    exit $exit_code
}

# Set up error trap only for non-interactive, non-sourced shells.
if [[ ! -o interactive && "$is_sourced" != "true" ]]; then
    trap 'handle_error' ERR
fi

# ================= TEMPORARY FILES =================
create_temp_file() {
    local suffix="${1:-}"
    local temp_dir="${TMPDIR:-/tmp}"

    # Validate temp directory
    if ! check_directory_writable "$temp_dir"; then
        log_error "Cannot create temporary files in: $temp_dir"
        return 1
    fi

    local temp_file
    temp_file=$(mktemp "${temp_dir}/temp.XXXXXX$suffix") || {
        log_error "Failed to create temporary file"
        return 1
    }

    log_debug "Created temporary file: $temp_file"
    echo "$temp_file"
    return 0
}

cleanup_temp_file() {
    local temp_file="$1"
    if [[ -n "${temp_file:-}" && -f "$temp_file" ]]; then
        rm -f "$temp_file" 2>/dev/null
        log_debug "Cleaned up temporary file: $temp_file"
    fi
}

# ================= SANITIZATION =================
sanitize_filename() {
    local filename="$1"

    # Remove dangerous characters and patterns
    filename=$(printf '%s\n' "$filename" | sed 's/[\/;&|$()`{}<>]//g')

    # Replace spaces with underscores
    filename=$(printf '%s\n' "$filename" | sed 's/ /_/g')

    # Limit length
    if [[ ${#filename} -gt 255 ]]; then
        filename="${filename:0:255}"
    fi

    echo "$filename"
}

# ================= VERSION MANAGEMENT =================

# Get version of a command (Safe version)
get_command_version() {
    local cmd="$1"
    local version_flag="${2:---version}"

    if ! command -v "$cmd" &> /dev/null; then
        echo ""
        return 0
    fi

    local version_output
    # Use || true to prevent set -e from exiting on non-zero exit of version flag
    version_output=$("$cmd" "$version_flag" 2>&1 | head -n 1) || true

    if [[ -z "$version_output" ]]; then
        echo ""
        return 0
    fi

    # Extract version number with || true to prevent grep exit code 1 from crashing
    local version
    version=$(echo "$version_output" | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?([a-zA-Z0-9_-]*)?' | head -n 1) || true

    echo "$version"
}

# Compare two semantic versions
# Usage: if version_greater_than "2.0.0" "1.9.9"; then ... fi
version_greater_than() {
    local v1="$1"
    local v2="$2"

    if [[ "$v1" == "$v2" ]]; then
        return 1  # Equal, not greater
    fi

    # Use a more robust version comparison that handles prerelease tags
    local result
    result=$(printf '%s\n%s' "$v1" "$v2" | sort -V | head -n 1)

    if [[ "$result" == "$v2" ]]; then
        # v2 is "smaller" in version order, so v1 > v2
        return 0
    else
        # v1 is "smaller" or equal, so v1 is not greater than v2
        return 1
    fi
}

# Compare two semantic versions for equality
version_equal() {
    [[ "$1" == "$2" ]]
}

# Compare two semantic versions (v1 < v2)
version_less_than() {
    local v1="$1"
    local v2="$2"

    if [[ "$v1" == "$v2" ]]; then
        return 1  # Equal, not less
    fi

    # If v1 is not greater than v2 and not equal, then it's less
    if ! version_greater_than "$v1" "$v2"; then
        return 0
    fi

    return 1
}

# Normalize version string for comparison
normalize_version() {
    local version="$1"

    # Remove prefixes like 'v', 'V', etc.
    version=$(echo "$version" | sed 's/^[vV]//')

    # Ensure version has at least 3 components (major.minor.patch)
    local parts
    parts=("${(@s:.:)version}")
    while [[ ${#parts[@]} -lt 3 ]]; do
        parts+=("0")
    done

    echo "${parts[1]}.${parts[2]}.${parts[3]}"
}

# Get the greatest version from a list
get_greatest_version() {
    local versions=("$@")
    local greatest=""

    for version in "${versions[@]}"; do
        if [[ -z "$greatest" ]] || version_greater_than "$version" "$greatest"; then
            greatest="$version"
        fi
    done

    echo "$greatest"
}

# Update package via brew
update_via_brew() {
    local package="$1"

    if ! check_command_exists "brew"; then
        log_error "Homebrew not found"
        return 1
    fi

    log_info "Updating $package via Homebrew..."
    if brew upgrade "$package" 2>&1 | grep -q "already installed"; then
        log_info "$package is already up to date"
        return 0
    fi

    log_success "$package updated successfully"
    return 0
}

# Update package via npm
update_via_npm() {
    local package="$1"

    if ! check_command_exists "npm"; then
        log_error "npm not found"
        return 1
    fi

    log_info "Updating $package via npm..."
    if npm update -g "$package" 2>&1; then
        log_success "$package updated successfully"
        return 0
    else
        log_error "Failed to update $package"
        return 1
    fi
}

# Merge JSON configurations (simple merge for MCP config)
merge_json_configs() {
    local existing_file="$1"
    local new_config="$2"
    local output_file="$3"

    # Validate paths
    if ! validate_path "$existing_file" "Existing config file validation failed"; then
        return 1
    fi

    if ! validate_path "$output_file" "Output config file validation failed"; then
        return 1
    fi

    # Check if jq is available for proper JSON merging
    if command -v jq &> /dev/null; then
        # Use jq for proper JSON merging
        local merged
        merged=$(jq -s '.[0] * .[1]' "$existing_file" <(echo "$new_config") 2>/dev/null)

        if [[ $? -eq 0 && -n "$merged" ]]; then
            echo "$merged" > "$output_file"
            log_info "Merged JSON configurations using jq"
            return 0
        fi
    fi

    # Fallback: simple backup and replace
    log_warn "jq not available, backing up existing config and replacing"
    local backup_file="${existing_file}.backup.$(date +%Y%m%d_%H%M%S)"

    if ! secure_copy "$existing_file" "$backup_file" "false"; then
        log_error "Failed to backup existing config"
        return 1
    fi

    log_info "Backed up existing config to: $backup_file"
    echo "$new_config" > "$output_file"

    return 0
}

# ================= EXPORTS =================
# Functions are available when sourced in zsh; export -f is not supported.
