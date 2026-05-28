#!/usr/bin/env bats
# Test install/update lifecycle separation

setup() {
    export VIBE_ROOT="$BATS_TEST_DIRNAME/../.."
    TEST_REPO=$(mktemp -d)
    TEST_HOME=$(mktemp -d)
    export HOME="$TEST_HOME"
}

teardown() {
    rm -rf "$TEST_REPO" "$TEST_HOME"
}

@test "install.sh contains lifecycle separation comments" {
    # Check that install.sh has lifecycle separation comments
    grep -q "NOTE: install.sh only handles first-time setup" "$VIBE_ROOT/scripts/install.sh"
    grep -q "Subsequent global updates use: vibe update" "$VIBE_ROOT/scripts/install.sh"
}

@test "install.sh mentions Python environment but not editable install" {
    # Check that install.sh mentions Python environment setup
    grep -q "Python environment" "$VIBE_ROOT/scripts/install.sh" || \
    grep -q "uv environment" "$VIBE_ROOT/scripts/install.sh"

    # Check that editable install logic is removed
    ! grep -q "uv tool install --editable" "$VIBE_ROOT/scripts/install.sh"
}

@test "vibe update command exists and works" {
    # Create test file in repo
    mkdir -p "$TEST_REPO/bin" "$TEST_REPO/lib"
    echo "new" > "$TEST_REPO/bin/new.sh"
    chmod +x "$TEST_REPO/bin/new.sh"

    # Initialize TEST_REPO as a git repo so update.sh can detect it
    cd "$TEST_REPO"
    git init >/dev/null 2>&1

    # Copy necessary files for update
    cp "$VIBE_ROOT/bin/vibe" "$TEST_REPO/bin/"
    cp "$VIBE_ROOT/lib/config.sh" "$TEST_REPO/lib/"
    cp "$VIBE_ROOT/lib/utils.sh" "$TEST_REPO/lib/"
    cp "$VIBE_ROOT/lib/update.sh" "$TEST_REPO/lib/"

    export VIBE_TEST_ROOT="$TEST_REPO"

    # Create mock target directory
    mkdir -p "$HOME/.vibe"/{bin,lib,config}

    # Run update from TEST_REPO directory
    cd "$TEST_REPO"
    run "$VIBE_TEST_ROOT/bin/vibe" update run
    [ "$status" -eq 0 ]

    # Check new file synced
    [ -f "$HOME/.vibe/bin/new.sh" ]
}