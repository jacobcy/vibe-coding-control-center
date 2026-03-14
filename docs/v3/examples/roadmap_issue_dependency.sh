#!/usr/bin/env zsh
# docs/v3/examples/roadmap_issue_dependency.sh
# 示例目标：
# 1. 如何读取 GitHub Issue 依赖图
# 2. 如何通过 GraphQL 写入 blocked-by 关系

set -euo pipefail

current_repo() {
  gh repo view --json nameWithOwner -q '.nameWithOwner'
}

issue_node_id() {
  local repo="$1"
  local issue_number="$2"
  gh issue view "$issue_number" --repo "$repo" --json id --jq '.id'
}

show_dependency_graph() {
  local issue_number="$1"
  local repo owner name

  repo="$(current_repo)"
  owner="${repo%%/*}"
  name="${repo#*/}"

  gh api graphql \
    -f query='query($owner:String!,$repo:String!,$num:Int!){repository(owner:$owner,name:$repo){issue(number:$num){number title blockedBy(first:20){nodes{number title}} blocking(first:20){nodes{number title}}}}}' \
    -F owner="$owner" \
    -F repo="$name" \
    -F num="$issue_number" \
    --jq '.data.repository.issue'
}

mutate_blocked_by() {
  local action="$1"
  local issue_number="$2"
  local blocked_by_number="$3"
  local repo issue_id blocking_issue_id mutation_name

  repo="$(current_repo)"
  issue_id="$(issue_node_id "$repo" "$issue_number")"
  blocking_issue_id="$(issue_node_id "$repo" "$blocked_by_number")"

  case "$action" in
    add) mutation_name="addBlockedBy" ;;
    remove) mutation_name="removeBlockedBy" ;;
    *) echo "unknown action: $action" >&2; return 1 ;;
  esac

  gh api graphql \
    -f query="mutation(\$issueId:ID!,\$blockingIssueId:ID!){${mutation_name}(input:{issueId:\$issueId, blockingIssueId:\$blockingIssueId}){issue{number} blockingIssue{number}}}" \
    -F issueId="$issue_id" \
    -F blockingIssueId="$blocking_issue_id"
}

case "${1:-}" in
  show)
    show_dependency_graph "${2:?issue number required}"
    ;;
  add)
    mutate_blocked_by add "${2:?issue number required}" "${3:?blocked-by issue required}"
    ;;
  remove)
    mutate_blocked_by remove "${2:?issue number required}" "${3:?blocked-by issue required}"
    ;;
  *)
    echo "usage: $0 <show|add|remove> <issue> [blocked-by-issue]" >&2
    exit 1
    ;;
esac
