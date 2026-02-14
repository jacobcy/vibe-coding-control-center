#!/usr/bin/env zsh
# tests/test_integrity.sh
# 用途: 检查核心脚本的依赖引用 (source) 是否正确

SCRIPT_DIR="$(cd "$(dirname "${(%):-%x}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR/.."
source "$ROOT_DIR/lib/utils.sh"

log_step "Running Integrity Tests..."

check_source_paths() {
    local file="$1"
    local base_dir=$(dirname "$file")
    echo "Checking dependencies in $file..."
    
    # Extract source lines and check paths
    grep -E "^\s*source\s+" "$file" | while read -r line; do
        # Extract path: remove 'source', ' ', and quotes
        local src_path="${line#*source }"
        # Remove leading/trailing spaces and quotes using shell expansion
        src_path="${src_path#"${src_path%%[![:space:]]*}"}"
        src_path="${src_path%"${src_path##*[![:space:]]}"}"
        src_path="${src_path//\"/}"
        src_path="${src_path//\'/}"
        
        # Ignore lines that source dynamic variables (containing $ but not the ones we know)
        if [[ "$src_path" == *"\$"* && "$src_path" != *"\$SCRIPT_DIR"* && "$src_path" != *"\$VIBE_ROOT"* ]]; then
            echo "  [SKIP] $src_path (Dynamic variable)"
            continue
        fi

        # Resolve variables
        local actual_path="$src_path"
        actual_path="${actual_path//\$SCRIPT_DIR/$base_dir}"
        actual_path="${actual_path//\$VIBE_ROOT/$ROOT_DIR}"
        
        if [[ -f "$actual_path" ]]; then
            echo "  [OK] $src_path"
        else
            echo "  [FAIL] $src_path (Resolved to: $actual_path)"
            EXIT_CODE=1
        fi
    done
}

EXIT_CODE=0

check_source_paths "$ROOT_DIR/scripts/install.sh"
check_source_paths "$ROOT_DIR/scripts/vibecoding.sh"
check_source_paths "$ROOT_DIR/config/aliases.sh"
check_source_paths "$ROOT_DIR/install/init-project.sh"

# bin entrypoints (should not have unresolved source lines)
check_source_paths "$ROOT_DIR/bin/vibe"
check_source_paths "$ROOT_DIR/bin/vibe-chat"
check_source_paths "$ROOT_DIR/bin/vibe-init"
check_source_paths "$ROOT_DIR/bin/vibe-equip"
check_source_paths "$ROOT_DIR/bin/vibe-check"
check_source_paths "$ROOT_DIR/bin/vibe-env"
check_source_paths "$ROOT_DIR/bin/vibe-flow"
check_source_paths "$ROOT_DIR/bin/vibe-config"
check_source_paths "$ROOT_DIR/bin/vibe-alias"

if [[ $EXIT_CODE -eq 0 ]]; then
    log_success "Integrity test PASSED!"
else
    log_error "Integrity test FAILED!"
fi

exit $EXIT_CODE
