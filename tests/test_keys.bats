#!/usr/bin/env bats

setup() {
  export PATH="$BATS_TEST_DIRNAME/../bin:$PATH"
  # Create a temp directory for safe testing without affecting actual config
  export TEMP_TEST_DIR=$(mktemp -d)
  export VIBE_ROOT="$TEMP_TEST_DIR"
  
  # Inject overriding config into VIBE_ROOT environment variables for testing
  export VIBE_CONFIG="$TEMP_TEST_DIR/config"
  mkdir -p "$VIBE_CONFIG"

  # Link bin and lib so the scripts can still be found
  ln -s "$BATS_TEST_DIRNAME/../bin" "$VIBE_ROOT/bin"
  ln -s "$BATS_TEST_DIRNAME/../lib" "$VIBE_ROOT/lib"
}

teardown() {
  rm -rf "$TEMP_TEST_DIR"
}

@test "1. vibe keys help outputs subcommands" {
  run vibe keys help
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Usage:" ]]
  [[ "$output" =~ "vibe keys" ]]
  [[ "$output" =~ "list" ]]
  [[ "$output" =~ "set" ]]
  [[ "$output" =~ "get" ]]
  [[ "$output" =~ "init" ]]
}

@test "2. vibe keys list returns success" {
  # This tests "list" regardless of keys.env existence
  run vibe keys list
  [ "$status" -eq 0 ]
  [[ "$output" =~ "API Key Status" ]]
}

@test "3. vibe keys init creates keys.env" {
  rm -f "$VIBE_CONFIG/keys.env"
  [ ! -f "$VIBE_CONFIG/keys.env" ]
  echo "# Vibe Keys Configuration" > "$VIBE_CONFIG/keys.template.env"
  run vibe keys init < /dev/null
  [ "$status" -eq 0 ]
  [ -f "$VIBE_CONFIG/keys.env" ]
  run cat "$VIBE_CONFIG/keys.env"
  [[ "$output" =~ "Vibe Keys Configuration" ]]
}
