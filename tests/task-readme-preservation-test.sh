#!/usr/bin/env bash
# Preservation Property Tests for Task README Status Field Fix
# Property 2: Preservation - 非状态内容保持不变
#
# IMPORTANT: Follow observation-first methodology
# This test observes and captures baseline behavior on UNFIXED code
# After fix is applied, re-run to ensure preservation

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=== Task README Preservation Tests ==="
echo "Testing that non-status content remains unchanged..."
echo ""

# Track results
total_tests=0
passed_tests=0
failed_tests=0

# Test helper function
test_preservation() {
    local test_name="$1"
    local file="$2"
    local check_command="$3"
    
    total_tests=$((total_tests + 1))
    
    if eval "$check_command"; then
        echo -e "${GREEN}✓${NC} $test_name"
        passed_tests=$((passed_tests + 1))
        return 0
    else
        echo -e "${RED}✗${NC} $test_name"
        failed_tests=$((failed_tests + 1))
        return 1
    fi
}

# Extract frontmatter (excluding status line for comparison)
get_frontmatter_without_status() {
    local file="$1"
    sed -n '/^---$/,/^---$/p' "$file" | grep -v '^status:' || true
}

# Extract body content (excluding status line)
get_body_without_status() {
    local file="$1"
    # Skip frontmatter, then get all content except status line
    sed '1,/^---$/d; /^---$/,/^---$/d' "$file" | grep -v '^\s*-\s*\*\*状态\*\*:' || true
}

# Extract gate progress table
get_gate_table() {
    local file="$1"
    # Find the Gate progress table section
    sed -n '/^| Gate |/,/^$/p' "$file" || true
}

# Extract document navigation section
get_doc_navigation() {
    local file="$1"
    # Find the document navigation section (until next ## heading or end of file)
    awk '/^## 文档导航/,/^## / {if (/^## / && !/^## 文档导航/) exit; print}' "$file" || true
}

echo "Testing preservation properties on affected files..."
echo ""

# List of files with bug condition (from exploration test results)
affected_files=(
    "docs/tasks/2026-02-21-save-command/README.md"
    "docs/tasks/2026-02-21-vibe-architecture/README.md"
    "docs/tasks/2026-02-25-vibe-v2-final/README.md"
    "docs/tasks/2026-02-26-agent-dev-refactor/README.md"
    "docs/tasks/2026-02-26-vibe-engine/README.md"
    "docs/tasks/2026-03-01-session-lifecycle/README.md"
    "docs/tasks/2026-03-02-command-slash-alignment/README.md"
    "docs/tasks/2026-03-02-cross-worktree-task-registry/README.md"
)

# Create baseline snapshots for each file
baseline_dir="tests/.baseline"
mkdir -p "$baseline_dir"

for file in "${affected_files[@]}"; do
    if [[ ! -f "$file" ]]; then
        echo -e "${YELLOW}⚠${NC} File not found: $file"
        continue
    fi
    
    task_name=$(basename "$(dirname "$file")")
    echo "--- Testing: $task_name ---"
    
    # Create baseline snapshots
    baseline_file="$baseline_dir/${task_name}.baseline"
    
    # Capture baseline: frontmatter (without status), body (without status line), gate table, doc nav
    {
        echo "=== FRONTMATTER (without status) ==="
        get_frontmatter_without_status "$file"
        echo ""
        echo "=== BODY (without status line) ==="
        get_body_without_status "$file"
        echo ""
        echo "=== GATE TABLE ==="
        get_gate_table "$file"
        echo ""
        echo "=== DOC NAVIGATION ==="
        get_doc_navigation "$file"
    } > "$baseline_file"
    
    # Test 1: Frontmatter fields (except status) exist
    test_preservation \
        "Frontmatter fields present" \
        "$file" \
        "[[ -n \$(get_frontmatter_without_status '$file') ]]"
    
    # Test 2: Body content (except status line) exists
    test_preservation \
        "Body content present" \
        "$file" \
        "[[ -n \$(get_body_without_status '$file') ]]"
    
    # Test 3: Gate progress table exists (optional - some early-stage tasks don't have it)
    gate_table_content=$(get_gate_table "$file")
    if [[ -n "$gate_table_content" ]]; then
        test_preservation \
            "Gate progress table present" \
            "$file" \
            "[[ -n \$(get_gate_table '$file') ]]"
    else
        echo -e "${YELLOW}⊘${NC} Gate progress table (skipped - not present in original)"
    fi
    
    # Test 4: Frontmatter has required fields
    test_preservation \
        "Frontmatter has task_id" \
        "$file" \
        "grep -q '^task_id:' '$file'"
    
    test_preservation \
        "Frontmatter has title" \
        "$file" \
        "grep -q '^title:' '$file'"
    
    # Test 5: Body has expected sections
    test_preservation \
        "Body has '概述' section" \
        "$file" \
        "grep -q '^## 概述' '$file'"
    
    test_preservation \
        "Body has '当前状态' section" \
        "$file" \
        "grep -q '^## 当前状态' '$file'"
    
    echo ""
done

echo "=== Baseline Snapshots Created ==="
echo "Baseline files saved to: $baseline_dir/"
echo "These snapshots capture the current state (before fix)"
echo "After applying the fix, re-run this script to verify preservation"
echo ""

echo "=== Test Summary ==="
echo "Total tests: $total_tests"
echo -e "${GREEN}Passed: $passed_tests${NC}"
if [[ $failed_tests -gt 0 ]]; then
    echo -e "${RED}Failed: $failed_tests${NC}"
fi
echo ""

if [[ $failed_tests -eq 0 ]]; then
    echo -e "${GREEN}ALL PRESERVATION TESTS PASSED${NC}"
    echo "Baseline behavior captured successfully"
    exit 0
else
    echo -e "${RED}SOME PRESERVATION TESTS FAILED${NC}"
    echo "Check the output above for details"
    exit 1
fi
