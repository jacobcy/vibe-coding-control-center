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

  reported_total=$(echo "$output" | awk -F'|' '/\| Shell 总 LOC \(v2\) \|/{gsub(/ /,"",$4); print $4; exit}')
  [ "$reported_total" -eq "$expected_total" ]

  reported_max=$(echo "$output" | sed -n 's/.*| Shell 最大文件行数 (v2) | 300 | *\([0-9][0-9]*\).*/\1/p' | head -1)
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
