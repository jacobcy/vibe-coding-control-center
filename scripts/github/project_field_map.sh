#!/usr/bin/env zsh
# scripts/github/project_field_map.sh - GitHub Project custom field readiness check

set -e

json_out=0
check_mode=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check) check_mode=1; shift ;;
    --json) json_out=1; shift ;;
    *) echo "Usage: zsh scripts/github/project_field_map.sh --check [--json]"; exit 1 ;;
  esac
done

[[ "$check_mode" -eq 1 ]] || { echo "Usage: zsh scripts/github/project_field_map.sh --check [--json]"; exit 1; }

fields_source="${VIBE_GITHUB_PROJECT_FIELDS_JSON:-[]}"
if [[ -f "$fields_source" ]]; then
  fields_json="$(cat "$fields_source")"
else
  fields_json="$fields_source"
fi

required_json='[
  {"name":"execution_record_id","type":"text"},
  {"name":"spec_standard","type":"single_select"},
  {"name":"spec_ref","type":"text"}
]'

field_names_json="$(echo "$fields_json" | jq -c 'map(.name)')"

result_json="$(
  jq -n \
    --argjson field_names "$field_names_json" \
    --argjson required "$required_json" '
      [ $required[] as $field | select(($field_names | index($field.name)) == null) | $field ] as $missing
      | {
          official_fields: ["github_project_item_id", "content_type"],
          extension_fields: $required,
          missing_fields: $missing,
          status: (if ($missing | length) == 0 then "pass" else "fail" end)
        }'
)"

if [[ "$json_out" -eq 1 ]]; then
  echo "$result_json"
else
  echo "GitHub Project Field Readiness"
  echo "$result_json" | jq -r '.extension_fields[] | "  - \(.name) [\(.type)]"'
  if [[ "$(echo "$result_json" | jq -r '.missing_fields | length')" -eq 0 ]]; then
    echo "Status: pass"
  else
    echo "Status: fail"
    echo "$result_json" | jq -r '.missing_fields[] | "Missing: \(.name) [\(.type)]"'
  fi
fi

[[ "$(echo "$result_json" | jq -r '.status')" == "pass" ]]
