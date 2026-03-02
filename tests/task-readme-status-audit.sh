#!/usr/bin/env bash
# Bug Condition Exploration Test for Task README Status Field Conflicts
# Property 1: Fault Condition - Task README 双头真源检测
#
# CRITICAL: This test MUST FAIL on unfixed code - failure confirms the bug exists
# EXPECTED OUTCOME: Test FAILS with counterexamples showing status conflicts/redundancy

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=== Task README Status Field Audit ==="
echo "Testing for dual status field bug condition..."
echo ""

# Track results
declare -a conflicts=()
declare -a redundancies=()
declare -a clean_files=()
total_files=0
bug_found=0

# Function to extract frontmatter status
get_frontmatter_status() {
    local file="$1"
    # Extract status from YAML frontmatter (between first two --- markers)
    sed -n '/^---$/,/^---$/p' "$file" | grep '^status:' | head -1 | sed 's/^status: *"\?\([^"]*\)"\?/\1/'
}

# Function to extract body status (after frontmatter)
get_body_status() {
    local file="$1"
    # Skip frontmatter, then look for: - **状态**: <value>
    # Use sed to skip first two --- markers, then grep for status line
    sed '1,/^---$/d; /^---$/,/^---$/d' "$file" | grep -m1 '^\s*-\s*\*\*状态\*\*:' | sed 's/^\s*-\s*\*\*状态\*\*:\s*//' || true
}

# Function to check if body status is a reference (not a value)
is_reference_text() {
    local text="$1"
    [[ "$text" =~ "frontmatter" ]] || [[ "$text" =~ "见" ]]
}

# Scan all Task README files
for readme in docs/tasks/*/README.md; do
    if [[ ! -f "$readme" ]]; then
        continue
    fi
    
    total_files=$((total_files + 1))
    task_dir=$(basename "$(dirname "$readme")")
    
    frontmatter_status=$(get_frontmatter_status "$readme")
    body_status=$(get_body_status "$readme")
    
    # Check if file has both status fields
    if [[ -n "$frontmatter_status" && -n "$body_status" ]]; then
        # Check if body status is a reference text (correct format)
        if is_reference_text "$body_status"; then
            clean_files+=("$task_dir: Uses reference text (correct)")
        else
            # Check if values conflict
            frontmatter_lower=$(echo "$frontmatter_status" | tr '[:upper:]' '[:lower:]' | tr '_' ' ' | tr '-' ' ')
            body_lower=$(echo "$body_status" | tr '[:upper:]' '[:lower:]' | tr '_' ' ' | tr '-' ' ')
            
            # Normalize status values for comparison
            frontmatter_normalized=$(echo "$frontmatter_lower" | sed 's/in progress/in_progress/; s/todo/todo/; s/completed/completed/; s/archived/archived/')
            body_normalized=$(echo "$body_lower" | sed 's/in progress/in_progress/; s/todo/todo/; s/completed/completed/; s/archived/archived/')
            
            if [[ "$frontmatter_normalized" != "$body_normalized" ]]; then
                conflicts+=("$task_dir: frontmatter='$frontmatter_status' vs body='$body_status' (CONFLICT)")
                bug_found=1
            else
                redundancies+=("$task_dir: frontmatter='$frontmatter_status' vs body='$body_status' (REDUNDANT)")
                bug_found=1
            fi
        fi
    elif [[ -n "$frontmatter_status" && -z "$body_status" ]]; then
        clean_files+=("$task_dir: No body status field (clean)")
    fi
done

# Report results
echo "Scanned $total_files Task README files"
echo ""

if [[ ${#conflicts[@]} -gt 0 ]]; then
    echo -e "${RED}HIGH PRIORITY CONFLICTS (status values differ):${NC}"
    for conflict in "${conflicts[@]}"; do
        echo -e "  ${RED}✗${NC} $conflict"
    done
    echo ""
fi

if [[ ${#redundancies[@]} -gt 0 ]]; then
    echo -e "${YELLOW}MEDIUM PRIORITY REDUNDANCIES (status values match but dual fields exist):${NC}"
    for redundancy in "${redundancies[@]}"; do
        echo -e "  ${YELLOW}⚠${NC} $redundancy"
    done
    echo ""
fi

if [[ ${#clean_files[@]} -gt 0 ]]; then
    echo -e "${GREEN}CLEAN FILES (no bug condition):${NC}"
    for clean in "${clean_files[@]}"; do
        echo -e "  ${GREEN}✓${NC} $clean"
    done
    echo ""
fi

# Test result
echo "=== Test Result ==="
if [[ $bug_found -eq 1 ]]; then
    echo -e "${RED}TEST FAILED (EXPECTED)${NC}"
    echo "Bug condition detected: Task README files have dual status fields"
    echo "Conflicts found: ${#conflicts[@]}"
    echo "Redundancies found: ${#redundancies[@]}"
    echo ""
    echo "This confirms the bug exists. Counterexamples documented above."
    exit 1
else
    echo -e "${GREEN}TEST PASSED${NC}"
    echo "No bug condition detected: All files use single source of truth"
    echo "All files either:"
    echo "  - Use frontmatter status only (no body status field)"
    echo "  - Use reference text in body (points to frontmatter)"
    exit 0
fi
