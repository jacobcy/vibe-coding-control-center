#!/usr/bin/env zsh
# scripts/github_project_bootstrap_sync.sh - Bootstrap cutover audit/dry-run/apply

set -e

mode=""
json_out=0
outdir="${VIBE_GITHUB_BOOTSTRAP_OUTDIR:-artifacts/github-project-bootstrap}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) mode="dry_run"; shift ;;
    --apply) mode="apply"; shift ;;
    --json) json_out=1; shift ;;
    --outdir) outdir="$2"; shift 2 ;;
    *) echo "Usage: zsh scripts/github_project_bootstrap_sync.sh [--dry-run|--apply] [--json] [--outdir <dir>]"; exit 1 ;;
  esac
done

[[ -n "$mode" ]] || mode="dry_run"

common_dir="${VIBE_GIT_COMMON_DIR:-$(git rev-parse --git-common-dir 2>/dev/null || pwd)}"
roadmap_file="${VIBE_GITHUB_ROADMAP_FILE:-$common_dir/vibe/roadmap.json}"
registry_file="${VIBE_GITHUB_REGISTRY_FILE:-$common_dir/vibe/registry.json}"
items_source="${VIBE_GITHUB_PROJECT_ITEMS_JSON:-[]}"

[[ -f "$roadmap_file" ]] || { echo "Missing roadmap file: $roadmap_file"; exit 1; }
[[ -f "$registry_file" ]] || { echo "Missing registry file: $registry_file"; exit 1; }

if [[ -f "$items_source" ]]; then
  items_json="$(cat "$items_source")"
else
  items_json="$items_source"
fi

mkdir -p "$outdir"

audit_json="$(
  jq -n \
    --slurpfile roadmap "$roadmap_file" \
    --slurpfile registry "$registry_file" \
    --argjson items "$items_json" '
      ($roadmap[0].items // []) as $roadmap_items
      | ($registry[0].tasks // []) as $tasks
      | {
          mode: "project_first",
          readiness: {
            roadmap_missing_github_project_item_id: [$roadmap_items[] | select(.github_project_item_id == null) | .roadmap_item_id],
            roadmap_missing_content_type: [$roadmap_items[] | select(.content_type == null) | .roadmap_item_id],
            roadmap_missing_execution_record_id: [$roadmap_items[] | select(.execution_record_id == null) | .roadmap_item_id],
            task_missing_spec: [$tasks[] | select((.spec_standard // "none") == "none" or .spec_ref == null) | .task_id]
          },
          github_project_items: ($items | length)
        }'
)"

proposal_json="$(
  jq -n \
    --slurpfile roadmap "$roadmap_file" \
    --slurpfile registry "$registry_file" \
    --argjson items "$items_json" '
      ($roadmap[0].items // []) as $roadmap_items
      | {
          official_layer_updates: [
            $roadmap_items[] as $local
            | ($items[]? | select(.roadmap_item_id == $local.roadmap_item_id)) as $remote
            | select($remote != null)
            | select(($local.github_project_item_id != ($remote.github_project_item_id // null)) or ($local.content_type != ($remote.content_type // null)))
            | {
                roadmap_item_id: $local.roadmap_item_id,
                before: {
                  github_project_item_id: ($local.github_project_item_id // null),
                  content_type: ($local.content_type // null)
                },
                after: {
                  github_project_item_id: ($remote.github_project_item_id // null),
                  content_type: ($remote.content_type // null)
                }
              }
          ],
          extension_layer_writeback: [
            $roadmap_items[] as $item
            | {
                roadmap_item_id: $item.roadmap_item_id,
                github_project_item_id: ($item.github_project_item_id // null),
                execution_record_id: ($item.execution_record_id // null),
                spec_standard: ($item.spec_standard // "none"),
                spec_ref: ($item.spec_ref // null)
              }
          ],
          conflicts: [
            $roadmap_items[] as $local
            | ($items[]? | select(.roadmap_item_id == $local.roadmap_item_id)) as $remote
            | select($remote != null)
            | select($local.github_project_item_id != null and $local.github_project_item_id != ($remote.github_project_item_id // null))
            | {
                roadmap_item_id: $local.roadmap_item_id,
                local_github_project_item_id: $local.github_project_item_id,
                remote_github_project_item_id: ($remote.github_project_item_id // null)
              }
          ]
        }'
)"

result_json="$(jq -n --arg mode "$mode" --arg outdir "$outdir" --argjson audit "$audit_json" --argjson proposals "$proposal_json" '{mode:$mode,outdir:$outdir,audit:$audit,proposals:$proposals}')"

if [[ "$mode" == "apply" ]]; then
  timestamp="$(date +%Y%m%dT%H%M%S)"
  snapshot_dir="$outdir/snapshots/$timestamp"
  mkdir -p "$snapshot_dir"
  cp "$roadmap_file" "$snapshot_dir/roadmap.json"
  cp "$registry_file" "$snapshot_dir/registry.json"

  tmp="$(mktemp)"
  jq --argjson items "$items_json" '
    .items |= map(
      . as $local
      | ($items[]? | select(.roadmap_item_id == $local.roadmap_item_id)) as $remote
      | if $remote != null then
          .github_project_item_id = ($remote.github_project_item_id // .github_project_item_id)
          | .content_type = ($remote.content_type // .content_type)
          | .updated_at = (now | strftime("%Y-%m-%dT%H:%M:%S%z"))
        else . end
    )' "$roadmap_file" > "$tmp"
  mv "$tmp" "$roadmap_file"

  writeback_file="$outdir/writeback-$timestamp.json"
  echo "$proposal_json" | jq '.extension_layer_writeback' > "$writeback_file"
  result_json="$(echo "$result_json" | jq --arg snapshot "$snapshot_dir" --arg writeback "$writeback_file" '. + {snapshot_dir:$snapshot, writeback_file:$writeback}')"
fi

report_file="$outdir/report-$(date +%Y%m%dT%H%M%S).json"
echo "$result_json" > "$report_file"

if [[ "$json_out" -eq 1 ]]; then
  echo "$result_json"
else
  echo "GitHub Project Bootstrap Sync"
  echo "$result_json" | jq -r '
    "Mode: \(.mode)",
    "Readiness:",
    "  roadmap missing github_project_item_id: \(.audit.readiness.roadmap_missing_github_project_item_id | length)",
    "  roadmap missing content_type: \(.audit.readiness.roadmap_missing_content_type | length)",
    "  roadmap missing execution_record_id: \(.audit.readiness.roadmap_missing_execution_record_id | length)",
    "  task missing spec: \(.audit.readiness.task_missing_spec | length)",
    "Proposals:",
    "  official layer updates: \(.proposals.official_layer_updates | length)",
    "  extension layer writeback: \(.proposals.extension_layer_writeback | length)",
    "  conflicts: \(.proposals.conflicts | length)"'
fi
