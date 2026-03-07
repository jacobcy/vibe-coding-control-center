# Goal
- ensure shell helpers used by automation never block waiting for interactive replies; operations that might prompt now fail fast and ask for explicit parameters/flags instead.

## Non-goals
- preserve the existing `read`-based UI for manual interactive sessions; allow future wrappers to re-enable it if needed (but not by default).
- do not convert every confirmation call in the repo—focus on the flows that caused the loop (`vt`, `vdown`, `vtkill`, `wt`, `wtrm`, `vup`, `vibe tool`, `vibe task remove`).

## Tech stack
- zsh scripting plus git/tmux wrappers (scripts under `alias/` and `lib/`).
- jq-based registry helpers.

## Step tasks
1. Add a non-interactive guard/helper (e.g., `vibe_confirm_auto`/`VIBE_ASSUME_YES`) so the existing `confirm_action` only runs when explicitly allowed; otherwise it bails with a message, forcing callers to supply a `--yes`-style flag.
2. Update tmux/worktree helpers (`alias/tmux.sh`, `alias/worktree.sh`) to stop prompting when multiple matches are found—list candidates and exit, asking the user to rerun with a more specific argument.
3. Turn `vdown`/`vtkill` into flag-gated operations so they refuse to kill windows/sessions unless `--yes` is provided; drop inline `confirm_action` usage.
4. Update `wtrm` and `vup` to avoid `read` prompts, require new flags for remote branch deletes, and treat ambiguous matches as errors.
5. Make `vibe tool` and `vibe task remove` accept a `--yes` flag (or environment variable) so updates/removals never prompt, and document the new flags in their help text.

## Files to modify
- `/Users/jacobcy/src/vibe-center/wt-codex-roadmap-skill/lib/utils.sh`
- `/Users/jacobcy/src/vibe-center/wt-codex-roadmap-skill/alias/tmux.sh`
- `/Users/jacobcy/src/vibe-center/wt-codex-roadmap-skill/alias/worktree.sh`
- `/Users/jacobcy/src/vibe-center/wt-codex-roadmap-skill/lib/tool.sh`
- `/Users/jacobcy/src/vibe-center/wt-codex-roadmap-skill/lib/task_actions.sh`

## Test command
- `bin/vibe tool --help` to show updated usage text.
- `bin/vibe task remove --help` to ensure the new flag is documented.

## Expected result
- The `--help` outputs mention the new `--yes` behavior and no longer hint at `confirm_action` prompts (non-interactive-friendly wording).

## Change summary
- Approx. +220/−180 lines spread across the helper and command files to add guard logic and flag parsing.
