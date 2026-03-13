#!/usr/bin/env zsh
# lib/roadmap_issue_dependency.sh - Remote GitHub Issue dependency helpers

_vibe_roadmap_dependency_require_gh() {
    _check_gh_available && return 0
    echo "Error: gh authentication with repo access is required for roadmap dependency commands"
    return 1
}

_vibe_roadmap_issue_node_id() { gh issue view "$2" --repo "$1" --json id --jq '.id' 2>/dev/null; }

_vibe_roadmap_dependency_graph() {
    local issue_number="$1" repo owner name response
    repo="$(_vibe_roadmap_current_repo)" || return 1
    owner="${repo%%/*}"
    name="${repo#*/}"
    [[ -n "$owner" && -n "$name" && "$owner" != "$name" ]] || return 1
    response="$(gh api graphql -f query='query($owner:String!,$repo:String!,$num:Int!){repository(owner:$owner,name:$repo){issue(number:$num){id number title blockedBy(first:20){nodes{id number title}} blocking(first:20){nodes{id number title}}}}}' -F owner="$owner" -F repo="$name" -F num="$issue_number" 2>/dev/null)" || {
        echo "Error: Failed to query GitHub issue dependency graph"
        return 1
    }
    response="$(print -r -- "$response" | jq -c '.data.repository.issue // empty')" || return 1
    [[ -n "$response" && "$response" != "null" ]] || { echo "Error: Issue not found: $issue_number"; return 1; }
    print -r -- "$response"
}

_vibe_roadmap_dependency_print_section() {
    echo "$1:"
    [[ -n "$2" ]] && print -r -- "$2" | sed 's/^/  - /' || echo "  (none)"
}

_vibe_roadmap_dependency_show() {
    local issue_number="" output_json="false" response
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --issue) issue_number="$2"; shift 2 ;;
            --json) output_json="true"; shift ;;
            *) echo "Error: Unknown option: $1"; return 1 ;;
        esac
    done
    [[ -n "$issue_number" ]] || { echo "Usage: vibe roadmap dep show --issue <issue-number> [--json]"; return 1; }
    _vibe_roadmap_dependency_require_gh || return 1
    response="$(_vibe_roadmap_dependency_graph "$issue_number")" || return 1
    [[ "$output_json" == "true" ]] && { print -r -- "$response"; return 0; }

    local title blocked_by blocking
    title="$(print -r -- "$response" | jq -r '.title')"
    blocked_by="$(print -r -- "$response" | jq -r '.blockedBy.nodes | map("#" + (.number|tostring) + " " + .title) | .[]?')"
    blocking="$(print -r -- "$response" | jq -r '.blocking.nodes | map("#" + (.number|tostring) + " " + .title) | .[]?')"
    echo "Issue: #${issue_number} ${title}"
    echo
    _vibe_roadmap_dependency_print_section "Blocked By" "$blocked_by"
    echo
    _vibe_roadmap_dependency_print_section "Blocking" "$blocking"
}

_vibe_roadmap_dependency_mutate() {
    local action="$1" issue_number="$2" blocked_by_number="$3" repo issue_id blocking_issue_id mutation response
    [[ -n "$issue_number" && -n "$blocked_by_number" ]] || { echo "Usage: vibe roadmap dep ${action} --issue <issue-number> --blocked-by <issue-number>"; return 1; }
    _vibe_roadmap_dependency_require_gh || return 1

    repo="$(_vibe_roadmap_current_repo)" || return 1
    issue_id="$(_vibe_roadmap_issue_node_id "$repo" "$issue_number")"
    blocking_issue_id="$(_vibe_roadmap_issue_node_id "$repo" "$blocked_by_number")"
    [[ -n "$issue_id" ]] || { echo "Error: Issue not found: $issue_number"; return 1; }
    [[ -n "$blocking_issue_id" ]] || { echo "Error: Blocking issue not found: $blocked_by_number"; return 1; }

    case "$action" in
        add) mutation='mutation($issueId:ID!,$blockingIssueId:ID!){addBlockedBy(input:{issueId:$issueId, blockingIssueId:$blockingIssueId}){issue{number title} blockingIssue{number title}}}' ;;
        remove) mutation='mutation($issueId:ID!,$blockingIssueId:ID!){removeBlockedBy(input:{issueId:$issueId, blockingIssueId:$blockingIssueId}){issue{number title} blockingIssue{number title}}}' ;;
        *) echo "Error: Unknown dependency action: $action"; return 1 ;;
    esac

    response="$(gh api graphql -f query="$mutation" -F issueId="$issue_id" -F blockingIssueId="$blocking_issue_id" 2>/dev/null)" || {
        echo "Error: Failed to ${action} GitHub issue dependency"
        return 1
    }
    print -r -- "$response" | jq -e ".data.${action}BlockedBy.issue.number" >/dev/null || return 1
    [[ "$action" == "add" ]] && echo "Added dependency: #${issue_number} blocked by #${blocked_by_number}" || echo "Removed dependency: #${issue_number} no longer blocked by #${blocked_by_number}"
}

_vibe_roadmap_dependency_command() {
    local action="${1:-}" issue_number="" blocked_by_number=""
    shift || true
    case "$action" in
        show) _vibe_roadmap_dependency_show "$@" ;;
        add|remove)
            while [[ $# -gt 0 ]]; do
                case "$1" in
                    --issue) issue_number="$2"; shift 2 ;;
                    --blocked-by) blocked_by_number="$2"; shift 2 ;;
                    *) echo "Error: Unknown option: $1"; return 1 ;;
                esac
            done
            _vibe_roadmap_dependency_mutate "$action" "$issue_number" "$blocked_by_number"
            ;;
        -h|--help|help|"") print -r -- $'Usage: vibe roadmap dep <show|add|remove> ...\n  show   --issue <issue-number> [--json]\n  add    --issue <issue-number> --blocked-by <issue-number>\n  remove --issue <issue-number> --blocked-by <issue-number>' ;;
        *) echo "Error: Unknown dependency subcommand: $action"; return 1 ;;
    esac
}
