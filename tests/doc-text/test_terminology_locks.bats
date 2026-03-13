#!/usr/bin/env bats

# Reason: Lock critical terminology definitions to prevent drift
# Entry Criterion: §4.1.1 - Key semantic freeze (terminology definitions)
# Alternative Considered: Behavior tests via `vibe` commands, but terminology
#                         is documentation-level contract, not command behavior

setup() {
  export REPO_ROOT="$BATS_TEST_DIRNAME/../.."
}

@test "doc-text: glossary.md locks 'repo issue' as GitHub issue term" {
  run rg -n "repo issue.*特指.*GitHub repository issue" "$REPO_ROOT/docs/standards/glossary.md"
  [ "$status" -eq 0 ]
}

@test "doc-text: glossary.md locks 'roadmap item' as mirrored GitHub Project item" {
  run rg -n "mirrored.*GitHub Project item" "$REPO_ROOT/docs/standards/glossary.md"
  [ "$status" -eq 0 ]
}

@test "doc-text: glossary.md locks 'task' as execution record" {
  run rg -n "task.*execution record" "$REPO_ROOT/docs/standards/glossary.md"
  [ "$status" -eq 0 ]
}

@test "doc-text: glossary.md locks 'flow' as logical delivery scene" {
  run rg -n "逻辑交付现场包装|execution scene" "$REPO_ROOT/docs/standards/glossary.md"
  [ "$status" -eq 0 ]
}

@test "doc-text: CLAUDE.md locks skill layer responsibilities" {
  run rg -n "负责理解上下文、调度和编排" "$REPO_ROOT/CLAUDE.md"
  [ "$status" -eq 0 ]
}
