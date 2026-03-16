---
title: Fix Flow Show Message Display
type: plan
status: active
created: 2026-03-17
author: Claude Sonnet 4.6
related_docs:
  - skills/vibe-start/SKILL.md
  - lib/flow_show.sh
  - lib/flow_review.sh
---

# Fix: vibe flow show Message Display

## Issue

- GitHub Issue: gh-198
- Title: vibe flow show should display helpful message when no active flow

## Problem

When there's no active flow in the current worktree, `vibe flow show` returns exit code 1 with no output, which is confusing for users.

## Solution

Display a clear, helpful message when no active flow exists:

**Files Modified**:
- `lib/flow_show.sh` - Add friendly message and suggestions
- `lib/flow_review.sh` - Add similar improvements for consistency

## Implementation

### Changes to `lib/flow_show.sh`

Before:
```bash
[[ -n "$record" ]] || { log_error "Flow not found: $target"; return 1; }
```

After:
```bash
[[ -n "$record" ]] || {
  log_warn "当前 worktree 没有活跃的 flow"
  echo ""
  echo "💡 提示："
  echo "  • 使用 ${CYAN}vibe flow new <feature-name>${NC} 创建新的 flow"
  echo "  • 或使用 ${CYAN}/vibe-new <feature-name>${NC} 进入完整的流程规划"
  return 0
}
```

### Changes to `lib/flow_review.sh`

Similar improvements for consistency when no PR exists.

## Testing

Tested with:
```bash
$ vibe flow show
! 当前 worktree 没有活跃的 flow

💡 提示：
  • 使用 vibe flow new <feature-name> 创建新的 flow
  • 或使用 /vibe-new <feature-name> 进入完整的流程规划
```

## Acceptance Criteria

- ✅ Clear Chinese message when no active flow
- ✅ Helpful suggestions for next steps
- ✅ Exit code 0 (informational, not error)
- ✅ Similar improvements to `vibe flow review`