#!/usr/bin/env bats

setup() {
  export REPO_ROOT="$BATS_TEST_DIRNAME/.."
}

@test "metrics uses current repo root even when VIBE_ROOT points elsewhere" {
  local expected_total expected_max reported_total reported_max

  expected_total=$(bash -lc '
    cd "'"$REPO_ROOT"'"
    total=0
    while IFS= read -r f; do
      n=$(wc -l < "$f")
      total=$((total + n))
    done < <(find lib lib3 -name "*.sh" -type f | sort; echo bin/vibe)
    echo "$total"
  ')

  expected_max=$(bash -lc '
    cd "'"$REPO_ROOT"'"
    max=0
    while IFS= read -r f; do
      n=$(wc -l < "$f")
      [ "$n" -gt "$max" ] && max="$n"
    done < <(find lib lib3 -name "*.sh" -type f | sort; echo bin/vibe)
    echo "$max"
  ')

  run env VIBE_ROOT="$BATS_TEST_TMPDIR/not-a-repo" bash -lc \
    'cd "'"$REPO_ROOT"'" && bash scripts/metrics.sh'

  [ "$status" -eq 0 ]

  # Parse YAML output for v2_shell metrics
  reported_total=$(echo "$output" | awk '/v2_shell:/,/v3_python:/' | awk '/total_loc:/,/max_file_loc:/' | grep "current:" | head -1 | awk '{print $2}')
  [ "$reported_total" -eq "$expected_total" ]

  reported_max=$(echo "$output" | awk '/v2_shell:/,/v3_python:/' | awk '/max_file_loc:/,/tests:/' | grep "current:" | head -1 | awk '{print $2}')
  [ "$reported_max" -eq "$expected_max" ]
}

@test "shell files stay within the 300-line CI ceiling" {
  run bash -lc '
    cd "'"$REPO_ROOT"'"
    failed=0
    for f in lib/*.sh bin/vibe; do
      lines=$(wc -l < "$f")
      if [ "$lines" -gt 300 ]; then
        echo "$f:$lines"
        failed=1
      fi
    done
    exit "$failed"
  '

  [ "$status" -eq 0 ]
}
