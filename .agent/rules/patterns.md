# Engineering Patterns

## 1. Idempotency
All scripts and workflows must be **safe to run multiple times**.
- **Bad**: `mkdir foo` (Fails if exists)
- **Good**: `mkdir -p foo` (Succeeds if exists)
- **Context**: If an agent gets stuck and retries a step, it shouldn't destroy data.

## 2. "Turbo" Mode (Auto-Run)
- Workflows can be annotated with `// turbo` to deterimine safe-to-autorun blocks.
- **Pattern**: If a block is purely read-only or strictly idempotent, mark it `// turbo`.
- **Pattern**: Destructive or high-risk actions (e.g., `git push --force`) must **NEVER** be auto-run.

## 3. Context First
Agents have no persistent memory between sessions.
- **Pattern**: Every workflow starts by gathering context.
- **Action**: `git status`, `git log`, `cat .agent/rules/*`.
- **Why**: You cannot make good decisions without knowing the current state.

## 4. Structured Reporting
Output must be predictable and parseable.
- **Pattern**: Use Markdown headers for sections.
- **Pattern**: Use checkboxes `[ ]` for actionable items.
- **Pattern**: Explicitly state "Next Steps".

## 5. Fail Fast
- **Shell**: Use `set -e`.
- **Workflow**: If a prerequisite fails (e.g., "Clean git status"), stop immediately. Do not proceed to complex logic.
