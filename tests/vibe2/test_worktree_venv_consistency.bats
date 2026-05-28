#!/usr/bin/env bats
# Test cross-worktree venv consistency (deps-only model)

setup() {
    export VIBE_ROOT="$BATS_TEST_DIRNAME/../.."
    TEST_HOME=$(mktemp -d)
    export HOME="$TEST_HOME"
}

teardown() {
    rm -rf "$TEST_HOME"
}

@test "shared venv does not contain editable .pth file" {
    # Skip if venv doesn't exist (CI environment)
    if [[ ! -d "$HOME/.venvs/vibe-center" ]]; then
        skip "Global venv not found (expected in CI environment)"
    fi

    # Check that no editable .pth file exists
    ! ls "$HOME/.venvs/vibe-center/lib/python"*/site-packages/__editable__.vibe3*.pth 2>/dev/null
}

@test "pyproject.toml has package=false" {
    grep -q 'package = false' "$VIBE_ROOT/pyproject.toml"
}

@test "pyproject.toml has pytest pythonpath" {
    grep -q 'pythonpath = \["src"\]' "$VIBE_ROOT/pyproject.toml"
}

@test ".envrc is committed to repo" {
    # .envrc should be tracked by git
    git -C "$VIBE_ROOT" ls-files .envrc | grep -q '.envrc'

    # .envrc should have correct content
    grep -q 'UV_PROJECT_ENVIRONMENT.*vibe-center' "$VIBE_ROOT/.envrc"
    grep -q 'PYTHONPATH.*PWD/src' "$VIBE_ROOT/.envrc"
}

@test ".gitignore tracks .envrc and ignores .envrc.local" {
    # .envrc should NOT be in gitignore
    ! grep -q '^\.envrc$' "$VIBE_ROOT/.gitignore"

    # .envrc.local SHOULD be in gitignore
    grep -q '^\.envrc\.local$' "$VIBE_ROOT/.gitignore"
}

@test "cli.py has src bootstrap code" {
    # Check that cli.py has bootstrap before imports
    grep -q 'import sys' "$VIBE_ROOT/src/vibe3/cli.py"
    grep -q 'from pathlib import Path' "$VIBE_ROOT/src/vibe3/cli.py"
    grep -q 'sys.path.insert(0, _SRC)' "$VIBE_ROOT/src/vibe3/cli.py"
}

@test "install.sh does not write .envrc" {
    # install.sh should NOT contain _write_file_if_changed for .envrc
    ! grep -q 'envrc_content.*UV_PROJECT_ENVIRONMENT' "$VIBE_ROOT/scripts/install.sh"
    ! grep -q '_write_file_if_changed.*\.envrc' "$VIBE_ROOT/scripts/install.sh"
}

@test "update.sh calls uv sync" {
    grep -q 'uv sync --all-extras' "$VIBE_ROOT/lib/update.sh"
}

@test "init.sh does not warn about UV_PROJECT_ENVIRONMENT" {
    # init.sh should NOT contain UV_PROJECT_ENVIRONMENT warning
    ! grep -q 'UV_PROJECT_ENVIRONMENT is not set' "$VIBE_ROOT/scripts/init.sh"
    ! grep -q 'UV_PROJECT_ENVIRONMENT directory does not exist' "$VIBE_ROOT/scripts/init.sh"
}
