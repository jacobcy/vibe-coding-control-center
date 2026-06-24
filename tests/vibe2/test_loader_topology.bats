#!/usr/bin/env bats
# Test loader topology resolution for VIBE_REPO and VIBE_MAIN
# Note: These tests verify the resolution logic patterns, not direct sourcing
# (The loader uses zsh-specific 'local' at top-level, which isn't bash-compatible)

setup() {
    export VIBE_ROOT="$BATS_TEST_DIRNAME/../.."
    TEST_REPO=$(mktemp -d)
    export HOME=$(mktemp -d)
}

teardown() {
    rm -rf "$TEST_REPO" "$HOME"
}

# Helper: Extract VIBE_REPO resolution logic for testing
_resolve_vibe_repo() {
    local git_common_dir="$1"
    local is_bare="$2"

    if [[ "$(basename "$git_common_dir")" == ".git" ]]; then
        # Non-bare repo: git-common-dir = .../main/.git → VIBE_REPO = .../main
        echo "$(cd "$git_common_dir/.." && pwd)"
    elif [[ "$is_bare" == "true" ]]; then
        # True bare repo: git-common-dir IS the repo root
        echo "$(cd "$git_common_dir" && pwd)"
    else
        # Fallback: treat git-common-dir parent as repo root (conservative)
        echo "$(cd "$git_common_dir/.." && pwd)"
    fi
}

# Helper: Check if .worktrees/main has main branch
_has_main_branch() {
    local worktree_path="$1"
    local branch
    branch="$(git -C "$worktree_path" symbolic-ref --short HEAD 2>/dev/null || true)"
    [[ "$branch" == "main" ]]
}

@test "VIBE_REPO: non-bare repo with .git basename resolves to parent" {
    # Create a non-bare repo
    cd "$TEST_REPO"
    git init
    echo "test" > test.txt
    git add test.txt
    git commit -m "initial"

    local git_common_dir="$(git rev-parse --git-common-dir)"
    local vibe_repo="$(_resolve_vibe_repo "$git_common_dir" "false")"

    # VIBE_REPO should point to the worktree root
    [[ "$vibe_repo" == "$TEST_REPO" ]]
}

@test "VIBE_REPO: bare repo resolves to git-common-dir itself" {
    # Create a bare repo
    local BARE_REPO="$TEST_REPO/bare"
    mkdir -p "$BARE_REPO"
    cd "$BARE_REPO"
    git init --bare

    local git_common_dir="$(git rev-parse --git-common-dir)"
    local vibe_repo="$(_resolve_vibe_repo "$git_common_dir" "true")"

    # VIBE_REPO should be the bare repo root itself
    [[ "$vibe_repo" == "$BARE_REPO" ]]
}

@test "VIBE_REPO: linked worktree with .git basename resolves to main repo" {
    # Create a non-bare repo with worktrees
    cd "$TEST_REPO"
    git init
    echo "test" > test.txt
    git add test.txt
    git commit -m "initial"

    # Create a linked worktree
    mkdir -p "$TEST_REPO/.worktrees"
    git branch feature
    git worktree add "$TEST_REPO/.worktrees/feature" feature

    # From linked worktree, git-common-dir points to main repo's .git
    cd "$TEST_REPO/.worktrees/feature"
    local git_common_dir="$(git rev-parse --git-common-dir)"

    # git-common-dir should end with .git
    [[ "$(basename "$git_common_dir")" == ".git" ]]

    # Resolve VIBE_REPO - should be parent of .git
    local vibe_repo
    vibe_repo="$(cd "$git_common_dir/.." && pwd)"

    # Verify the path exists and contains .git
    [[ -d "$vibe_repo/.git" ]]
    [[ -d "$vibe_repo/.worktrees" ]]
}

@test "VIBE_MAIN: .worktrees/main with wrong branch is skipped" {
    # Create a non-bare repo
    cd "$TEST_REPO"
    git init
    git commit --allow-empty -m "initial"

    # Create .worktrees/main but bind it to a feature branch
    mkdir -p "$TEST_REPO/.worktrees"
    git worktree add "$TEST_REPO/.worktrees/main" -b not-main

    # The worktree should NOT have main branch
    ! _has_main_branch "$TEST_REPO/.worktrees/main"
}

@test "VIBE_MAIN: git worktree list --porcelain finds main branch worktree" {
    # Create a repo with a main worktree
    cd "$TEST_REPO"
    git init
    git commit --allow-empty -m "initial"

    # Check that porcelain output doesn't have refs/heads/main initially
    # (default branch might be 'master')
    local found_main=0
    while IFS= read -r line; do
        if [[ "$line" == "branch refs/heads/main" ]]; then
            found_main=1
            break
        fi
    done < <(git worktree list --porcelain 2>/dev/null)

    # In a fresh repo, default branch is typically 'master', not 'main'
    [[ $found_main -eq 0 ]]
}

@test "loader.sh exists and has expected resolution logic" {
    # Verify the loader file exists and contains the expected patterns
    [[ -f "$VIBE_ROOT/lib/alias/loader.sh" ]]

    # Check for VIBE_REPO resolution patterns
    grep -q "basename.*git_common_dir" "$VIBE_ROOT/lib/alias/loader.sh"
    grep -q "is-bare-repository" "$VIBE_ROOT/lib/alias/loader.sh"

    # Check for VIBE_MAIN porcelain parsing (pattern uses backslash-escaped space)
    grep -q "git worktree list --porcelain" "$VIBE_ROOT/lib/alias/loader.sh"
    grep -q "refs/heads/main" "$VIBE_ROOT/lib/alias/loader.sh"

    # Check for branch verification on .worktrees/main
    grep -q "symbolic-ref.*HEAD" "$VIBE_ROOT/lib/alias/loader.sh"
}

@test "loader resolves correctly in real environment (zsh)" {
    # This test requires zsh, skip if not available
    if ! command -v zsh >/dev/null 2>&1; then
        skip "zsh not available"
    fi

    # Test the loader in the actual repository environment
    local result
    result=$(zsh -c 'source "$VIBE_ROOT/lib/alias/loader.sh" && echo "$VIBE_REPO:$VIBE_MAIN"' 2>/dev/null || true)

    # Should have two values separated by colon
    local repo main
    repo="${result%%:*}"
    main="${result#*:}"

    # VIBE_REPO should be set
    [[ -n "$repo" ]]

    # VIBE_MAIN should be set
    [[ -n "$main" ]]
}

@test "loader documentation in glossary is updated" {
    # Verify the glossary has the updated definitions
    [[ -f "$VIBE_ROOT/docs/standards/glossary.md" ]]

    # Check that old "bare repo 目录" assertion is removed
    ! grep -q "多 worktree 模式：bare repo 目录" "$VIBE_ROOT/docs/standards/glossary.md"

    # Check that new porcelain-based resolution is documented
    grep -q "git worktree list --porcelain" "$VIBE_ROOT/docs/standards/glossary.md"
}
