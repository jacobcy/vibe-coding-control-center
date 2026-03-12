#!/usr/bin/env zsh
# lib/roadmap_github_api.sh - GitHub Project GraphQL/API interaction helpers

_vibe_roadmap_create_github_draft_issue() {
    local project_id="$1" title="$2" body="${3:-}" response item_id
    response="$(gh api graphql -f query='
      mutation($project: ID!, $title: String!, $body: String!) {
        addProjectV2DraftIssue(input: {projectId: $project, title: $title, body: $body}) {
          projectItem {
            id
          }
        }
      }' -F project="$project_id" -f title="$title" -f body="$body" 2>/dev/null)" || {
        echo "Failed to create GitHub Project draft item. Make sure gh is authenticated and project_id is valid."
        return 1
    }
    item_id="$(print -r -- "$response" | jq -r '.data.addProjectV2DraftIssue.projectItem.id // empty')"
    [[ -n "$item_id" ]] || {
        echo "Failed to parse GitHub Project item id from GraphQL response."
        return 1
    }
    print -r -- "$item_id"
}

_vibe_roadmap_parse_source_ref() {
    local ref="$1" repo="" number="" content_type=""
    case "$ref" in
        gh:*#*)
            repo="${ref#gh:}"
            repo="${repo%%#*}"
            number="${ref##*#}"
            content_type="issue"
            ;;
        https://github.com/*/issues/*)
            repo="${ref#https://github.com/}"
            repo="${repo%%/issues/*}"
            number="${ref##*/issues/}"
            content_type="issue"
            ;;
        https://github.com/*/pull/*)
            repo="${ref#https://github.com/}"
            repo="${repo%%/pull/*}"
            number="${ref##*/pull/}"
            content_type="pull_request"
            ;;
    esac

    [[ -n "$repo" && -n "$number" && -n "$content_type" ]] || return 1
    print -r -- "$repo|$number|$content_type"
}

_vibe_roadmap_resolve_content_node_id() {
    local repo="$1" number="$2" content_type="$3"
    case "$content_type" in
        issue)
            gh issue view "$number" --repo "$repo" --json id --jq '.id' 2>/dev/null
            ;;
        pull_request)
            gh pr view "$number" --repo "$repo" --json id --jq '.id' 2>/dev/null
            ;;
        *)
            return 1
            ;;
    esac
}

_vibe_roadmap_add_project_item_from_content() {
    local project_id="$1" content_id="$2" response item_id
    response="$(gh api graphql -f query='
      mutation($project: ID!, $content: ID!) {
        addProjectV2ItemById(input: {projectId: $project, contentId: $content}) {
          item {
            id
          }
        }
      }' -F project="$project_id" -F content="$content_id" 2>/dev/null)" || return 1
    item_id="$(print -r -- "$response" | jq -r '.data.addProjectV2ItemById.item.id // empty')"
    [[ -n "$item_id" ]] || return 1
    print -r -- "$item_id"
}

_vibe_roadmap_bootstrap_remote_item() {
    local project_id="$1" item_json="$2"
    local source_type title description source_ref parsed repo number content_type content_id item_id

    source_type="$(printf '%s' "$item_json" | jq -r '.source_type // "local"')"
    title="$(printf '%s' "$item_json" | jq -r '.title // "Imported Project Item"')"
    description="$(printf '%s' "$item_json" | jq -r '.description // empty')"

    if [[ "$source_type" == "github" ]]; then
        while IFS= read -r source_ref; do
            [[ -n "$source_ref" ]] || continue
            parsed="$(_vibe_roadmap_parse_source_ref "$source_ref" 2>/dev/null || true)"
            [[ -n "$parsed" ]] || continue
            repo="${parsed%%|*}"
            parsed="${parsed#*|}"
            number="${parsed%%|*}"
            content_type="${parsed##*|}"
            content_id="$(_vibe_roadmap_resolve_content_node_id "$repo" "$number" "$content_type" 2>/dev/null || true)"
            [[ -n "$content_id" ]] || continue
            item_id="$(_vibe_roadmap_add_project_item_from_content "$project_id" "$content_id" 2>/dev/null || true)"
            [[ -n "$item_id" ]] || continue
            print -r -- "${item_id}|${content_type}"
            return 0
        done < <(printf '%s' "$item_json" | jq -r '.source_refs[]?')
    fi

    item_id="$(_vibe_roadmap_create_github_draft_issue "$project_id" "$title" "$description")" || return 1
    print -r -- "${item_id}|draft_issue"
}

_vibe_roadmap_fetch_github_project_items() {
    local project_id="$1"
    local after="" response nodes has_next end_cursor results='[]'
    while true; do
        response="$(gh api graphql -f query='
          query($project: ID!, $after: String) {
            node(id: $project) {
              ... on ProjectV2 {
                items(first: 100, after: $after) {
                  nodes {
                    id
                    content {
                      __typename
                      ... on Issue {
                        title
                        body
                        number
                        url
                        repository { nameWithOwner }
                      }
                      ... on PullRequest {
                        title
                        body
                        number
                        url
                        repository { nameWithOwner }
                      }
                      ... on DraftIssue {
                        title
                        body
                      }
                    }
                  }
                  pageInfo {
                    hasNextPage
                    endCursor
                  }
                }
              }
            }
          }' -F project="$project_id" -F after="$after" 2>/dev/null)" || return 1

        nodes="$(print -r -- "$response" | jq -c '
          [.data.node.items.nodes[]?
            | {
                github_project_item_id: .id,
                title: (.content.title // null),
                description: (.content.body // null),
                content_type: (
                  if .content.__typename == "Issue" then "issue"
                  elif .content.__typename == "PullRequest" then "pull_request"
                  else "draft_issue"
                  end
                ),
                source_type: (
                  if .content.__typename == "DraftIssue" then "local" else "github" end
                ),
                source_refs: (
                  if (.content.__typename == "Issue" or .content.__typename == "PullRequest") then
                    [
                      ("gh:" + .content.repository.nameWithOwner + "#" + (.content.number | tostring)),
                      .content.url
                    ]
                  else
                    []
                  end
                ),
                issue_refs: (
                  if (.content.__typename == "Issue" or .content.__typename == "PullRequest") then
                    [("gh-" + (.content.number | tostring))]
                  else
                    []
                  end
                ),
                remote_number: (.content.number // null)
              }
          ]')"
        results="$(print -r -- "$results" "$nodes" | jq -sc 'add')" || return 1

        has_next="$(print -r -- "$response" | jq -r '.data.node.items.pageInfo.hasNextPage')"
        end_cursor="$(print -r -- "$response" | jq -r '.data.node.items.pageInfo.endCursor // empty')"
        [[ "$has_next" == "true" && -n "$end_cursor" ]] || break
        after="$end_cursor"
    done

    print -r -- "$results"
}
