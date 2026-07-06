#!/usr/bin/env bash
# Spec-kit -> Vibe handoff bridge adapter (spec 012 US3).
#
# Resolves a generated spec-kit artifact under .specify/specs/<NNN>/ and
# publishes it through the PUBLIC `vibe3 handoff` surface. The adapter NEVER
# writes shared state directly and makes no label/state decisions (G7).
# Re-publishing the same artifact is safe because `vibe3 handoff` dedups the
# ref value.
#
# Usage:
#   publish-artifact.sh <kind> [--spec-dir <dir>] [--branch <branch>] [--artifact <path>]
#
#   kind        spec | plan | report | audit
#   --spec-dir  spec-kit spec directory (default: latest .specify/specs/<NNN-*>/)
#   --artifact  explicit artifact path (overrides resolution)
#   --branch    target Vibe flow branch (defaults to current branch)
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: publish-artifact.sh <spec|plan|report|audit> [--spec-dir <dir>] [--branch <branch>] [--artifact <path>]" >&2
  exit 64
fi

KIND="$1"; shift

case "$KIND" in
  spec)   REL="spec.md" ;;
  plan)   REL="plan.md" ;;
  report) REL="analysis/report.md" ;;
  audit)  REL="analysis/audit.md" ;;
  *) echo "Error: unknown kind '$KIND' (expected: spec|plan|report|audit)" >&2; exit 64 ;;
esac

SPEC_DIR=""
BRANCH=""
ARTIFACT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --spec-dir) SPEC_DIR="${2:?--spec-dir requires a value}"; shift 2 ;;
    --branch)   BRANCH="${2:?--branch requires a value}"; shift 2 ;;
    --artifact) ARTIFACT="${2:?--artifact requires a value}"; shift 2 ;;
    *) echo "Error: unknown option '$1'" >&2; exit 64 ;;
  esac
done

if [[ -n "$ARTIFACT" ]]; then
  RESOLVED="$ARTIFACT"
else
  # Resolve spec-dir: explicit > greatest NNN/name > error. Directory mtime is
  # unrelated to feature identity and can change when an older spec is edited.
  if [[ -z "$SPEC_DIR" ]]; then
    SPEC_DIR=$(find .specify/specs -mindepth 1 -maxdepth 1 -type d -print \
      2>/dev/null | LC_ALL=C sort -r | head -n1 || true)
  fi
  if [[ -z "$SPEC_DIR" ]]; then
    echo "Error: no spec directory found under .specify/specs/" >&2
    exit 66
  fi
  RESOLVED="${SPEC_DIR%/}/${REL}"
fi
if [[ ! -f "$RESOLVED" ]]; then
  echo "Error: artifact not found: $RESOLVED" >&2
  exit 66
fi

# Normalize to a repo-relative canonical path (strip a leading ./).
RESOLVED="${RESOLVED#./}"

# Publish through the PUBLIC Vibe handoff surface only.
CMD=(vibe3 handoff "$KIND" "$RESOLVED")
if [[ -n "$BRANCH" ]]; then
  CMD+=(--branch "$BRANCH")
fi
exec "${CMD[@]}"
