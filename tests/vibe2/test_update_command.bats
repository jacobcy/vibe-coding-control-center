#!/usr/bin/env bats
# Test vibe update command

setup() {
    export VIBE_ROOT="$BATS_TEST_DIRNAME/../.."

    # Create temp directories
    TEST_REPO=$(mktemp -d)
    TEST_HOME=$(mktemp -d)
    EXTERNAL_REPO=$(mktemp -d)

    # Mock minimal Vibe repo structure
    mkdir -p "$TEST_REPO"/{bin,lib,lib3,config,config/shell,scripts,src,skills}
    mkdir -p "$TEST_HOME/.vibe"/{bin,lib,config}
    mkdir -p "$EXTERNAL_REPO/.git"

    # Copy necessary files from real repo
    cp "$VIBE_ROOT/bin/vibe" "$TEST_REPO/bin/"
    cp "$VIBE_ROOT/lib/config.sh" "$TEST_REPO/lib/"
    cp "$VIBE_ROOT/lib/utils.sh" "$TEST_REPO/lib/"
    cp "$VIBE_ROOT/lib/update.sh" "$TEST_REPO/lib/"
    cp "$VIBE_ROOT/lib/install_utils.sh" "$TEST_REPO/lib/"
    cp -R "$VIBE_ROOT/config/shell" "$TEST_REPO/config/"

    # Create mock files to sync
    echo "# test bin" > "$TEST_REPO/bin/test_script.sh"
    chmod +x "$TEST_REPO/bin/test_script.sh"
    echo "# test lib" > "$TEST_REPO/lib/test_lib.sh"

    # Create mock keys.env in target to test preservation
    echo "API_KEY=test123" > "$TEST_HOME/.vibe/config/keys.env"

    export VIBE_TEST_ROOT="$TEST_REPO"
    export HOME="$TEST_HOME"
}

teardown() {
    rm -rf "$TEST_REPO" "$TEST_HOME" "$EXTERNAL_REPO"
}

@test "vibe update help shows usage" {
    run "$VIBE_TEST_ROOT/bin/vibe" update help
    [ "$status" -eq 0 ]
    [[ "$output" =~ "Global distribution sync" ]]
    [[ "$output" =~ "--dry-run" ]]
    [[ "$output" =~ "--verbose" ]]
}

@test "vibe update run syncs files" {
    # Run update
    run env HOME="$TEST_HOME" zsh -lc 'cd "'"$VIBE_TEST_ROOT"'" && ./bin/vibe update run'
    [ "$status" -eq 0 ]

    # Check files were synced
    [ -f "$TEST_HOME/.vibe/bin/test_script.sh" ]
    [ -f "$TEST_HOME/.vibe/lib/test_lib.sh" ]
}

@test "vibe update syncs config/keys.env from source to target" {
    # Create old keys.env in target (should be overwritten)
    echo "API_KEY=old_value" > "$TEST_HOME/.vibe/config/keys.env"

    # Create new keys.env in source (should overwrite target)
    echo "API_KEY=new_value" > "$TEST_REPO/config/keys.env"

    # Run update
    run env HOME="$TEST_HOME" zsh -lc 'cd "'"$VIBE_TEST_ROOT"'" && ./bin/vibe update run'
    [ "$status" -eq 0 ]

    # Check keys.env was overwritten from source
    [ -f "$TEST_HOME/.vibe/config/keys.env" ]
    grep -q "API_KEY=new_value" "$TEST_HOME/.vibe/config/keys.env"
    ! grep -q "API_KEY=old_value" "$TEST_HOME/.vibe/config/keys.env"
}

@test "vibe update --dry-run does not modify files" {
    # Run dry-run
    run env HOME="$TEST_HOME" zsh -lc 'cd "'"$VIBE_TEST_ROOT"'" && ./bin/vibe update run --dry-run'
    [ "$status" -eq 0 ]

    # Check no files created
    [ ! -f "$TEST_HOME/.vibe/bin/test_script.sh" ]
    [[ "$output" =~ "DRY-RUN" ]]
}

@test "vibe update cleans stale files" {
    # Create stale file in target
    mkdir -p "$TEST_HOME/.vibe/lib"
    echo "stale" > "$TEST_HOME/.vibe/lib/stale_file.sh"

    # Run update
    run env HOME="$TEST_HOME" zsh -lc 'cd "'"$VIBE_TEST_ROOT"'" && ./bin/vibe update run'
    [ "$status" -eq 0 ]

    # Check stale file removed
    [ ! -f "$TEST_HOME/.vibe/lib/stale_file.sh" ]
}

@test "global vibe update from external repo fails before self-syncing ~/.vibe" {
    cp "$VIBE_ROOT/bin/vibe" "$TEST_HOME/.vibe/bin/"
    cp "$VIBE_ROOT/lib/config.sh" "$VIBE_ROOT/lib/utils.sh" "$VIBE_ROOT/lib/update.sh" \
        "$VIBE_ROOT/lib/install_utils.sh" "$TEST_HOME/.vibe/lib/"

    run env HOME="$TEST_HOME" zsh -lc 'cd "'"$EXTERNAL_REPO"'" && "$HOME/.vibe/bin/vibe" update run'
    [ "$status" -eq 1 ]
    [[ "$output" == *"not a Vibe Center repository"* ]] || \
        [[ "$output" == *"must run from a Vibe Center repository or worktree"* ]]
    [[ ! "$output" =~ "Pre-flight checks passed" ]]
    [[ ! "$output" =~ "Failed to sync: bin" ]]
}
