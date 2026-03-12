#!/usr/bin/env bats

source "$BATS_TEST_DIRNAME/../helpers/roadmap_common.bash"

@test "roadmap dep show returns remote dependency graph as json" {
  local fixture
  fixture="$(mktemp -d)"
  make_roadmap_fixture "$fixture"

  run_roadmap_fixture_cmd "$fixture" '
    gh() {
      if [[ "$1 $2" == "auth status" ]]; then
        return 0
      fi
      if [[ "$1 $2 $3" == "api graphql -f" ]]; then
        cat <<'"'"'JSON'"'"'
{"data":{"repository":{"issue":{"id":"ISSUE_138","number":138,"title":"Issue 138","blockedBy":{"nodes":[{"id":"ISSUE_137","number":137,"title":"Issue 137"}]},"blocking":{"nodes":[]}}}}}
JSON
        return 0
      fi
      echo "unexpected gh call: $*" >&2
      return 98
    }
    vibe_roadmap dep show --issue 138 --json
  '

  [ "$status" -eq 0 ]
  [ "$(echo "$output" | jq -r '.number')" = "138" ]
  [ "$(echo "$output" | jq -r '.blockedBy.nodes[0].number')" = "137" ]
}

@test "roadmap dep add mutates remote dependency relation" {
  local fixture
  fixture="$(mktemp -d)"
  make_roadmap_fixture "$fixture"

  run_roadmap_fixture_cmd "$fixture" '
    gh() {
      if [[ "$1 $2" == "auth status" ]]; then
        return 0
      fi
      if [[ "$1 $2 $3 $4 $5 $6" == "issue view 138 --repo owner/repo --json" ]]; then
        echo "{\"id\":\"ISSUE_138\"}"
        return 0
      fi
      if [[ "$1 $2 $3 $4 $5 $6" == "issue view 137 --repo owner/repo --json" ]]; then
        echo "{\"id\":\"ISSUE_137\"}"
        return 0
      fi
      if [[ "$1 $2 $3" == "api graphql -f" ]]; then
        printf "%s" "$*" > "'"$fixture"'/gh_last_call.txt"
        cat <<'"'"'JSON'"'"'
{"data":{"addBlockedBy":{"issue":{"number":138,"title":"Issue 138"},"blockingIssue":{"number":137,"title":"Issue 137"}}}}
JSON
        return 0
      fi
      echo "unexpected gh call: $*" >&2
      return 98
    }
    vibe_roadmap dep add --issue 138 --blocked-by 137
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Added dependency: #138 blocked by #137" ]]
  grep -q 'addBlockedBy' "$fixture/gh_last_call.txt"
}

@test "roadmap dep remove mutates remote dependency relation" {
  local fixture
  fixture="$(mktemp -d)"
  make_roadmap_fixture "$fixture"

  run_roadmap_fixture_cmd "$fixture" '
    gh() {
      if [[ "$1 $2" == "auth status" ]]; then
        return 0
      fi
      if [[ "$1 $2 $3 $4 $5 $6" == "issue view 138 --repo owner/repo --json" ]]; then
        echo "{\"id\":\"ISSUE_138\"}"
        return 0
      fi
      if [[ "$1 $2 $3 $4 $5 $6" == "issue view 137 --repo owner/repo --json" ]]; then
        echo "{\"id\":\"ISSUE_137\"}"
        return 0
      fi
      if [[ "$1 $2 $3" == "api graphql -f" ]]; then
        printf "%s" "$*" > "'"$fixture"'/gh_last_call.txt"
        cat <<'"'"'JSON'"'"'
{"data":{"removeBlockedBy":{"issue":{"number":138,"title":"Issue 138"},"blockingIssue":{"number":137,"title":"Issue 137"}}}}
JSON
        return 0
      fi
      echo "unexpected gh call: $*" >&2
      return 98
    }
    vibe_roadmap dep remove --issue 138 --blocked-by 137
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Removed dependency: #138 no longer blocked by #137" ]]
  grep -q 'removeBlockedBy' "$fixture/gh_last_call.txt"
}
