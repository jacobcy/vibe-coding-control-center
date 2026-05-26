# Plan: Enforce bootstrap-flow in vibe-new SKILL.md

## Summary

Rewrite three sections of `skills/vibe-new/SKILL.md` to mandate `bootstrap-flow` as the sole bootstrap path, remove the misleading manual-fallback text, and add an explicit prohibition list. Pure documentation change; no code or CLI behavior changes.

## Changes

- `skills/vibe-new/SKILL.md`: Rewrite sections 1 and 3, strengthen the 限制 section. Remove the manual-fallback `git checkout -b` / `git pull origin main` block (lines 55-60). Keep section 2 (询问两件事) and sections 4-5 as-is.

## Implementation Steps

### Step 1: Expand section 1 pre-checks

Replace the current section 1 content (lines 10-23) with more explicit pre-check steps that include PR detection and existing flow handling, as specified in the issue spec:

- Add explicit `vibe3 flow show` + `git status` output interpretation
- Add condition: no active PR → safe to proceed
- Add condition: active but incomplete flow → suggest `/vibe-continue` or ask user intent
- Add condition: no issue number → route to `/vibe-issue`

**Verify**: Run `uv run pytest tests/vibe3/skills/test_vibe_new_alignment.py` — the test checks for `## 1. 先确认是否适合进入` header which will remain.

### Step 2: Rewrite section 3 (Bootstrap flow scene)

Replace lines 37-67 (the entire section 3) with mandatory bootstrap-flow language:

- Remove the manual-fallback block (lines 55-60: `git pull origin main`, `git checkout -b dev/issue-<id>`)
- Replace the "注意" note with a proper rationale block explaining *why* bootstrap-flow is mandatory (idempotency, actor attribution, baseline snapshot, consistency)
- Add an explicit ❌ prohibition list: no manual `git checkout -b`, no manual `vibe3 flow update`, no manual `vibe3 flow bind`, no manual `vibe3 snapshot save`
- Add a failure guidance: if bootstrap-flow fails, diagnose the problem; do not fall back to manual splicing
- Keep the `vibe3 internal bootstrap-flow` command examples but prefix them with ✅ markers
- The second example block (with `--related`/`--dependency` flags) can be condensed into the main example

**Verify**: Run the same test; the `## 3. Bootstrap flow scene` header must still be present. Also run `uv run ruff check skills/vibe-new/SKILL.md` (should pass on markdown).

### Step 3: Strengthen the 限制 section

Update the final 限制 section (lines 96-101) to use stronger mandatory language:

- Change "不在 skill 层手工拼接" → "禁止在 skill 层手工拼接"
- Add explicit reference back to section 3's prohibition list
- Add: "不绕过 bootstrap-flow 创建 flow"

**Verify**: Same test suite, section header checks remain valid.

### Step 4: Validate with test suite

Run the relevant tests:

```bash
uv run pytest tests/vibe3/skills/test_vibe_new_alignment.py -v
```

This test verifies:
- Section headers `## 1.`, `## 3.`, `## 停止条件` exist
- No `vibe3 new` command leaks
- No `bootstrap_full_workflow` reference
- Workflow file doesn't route to `/vibe-start`

**Verify**: All tests pass.

### Step 5: Register plan

```bash
uv run python src/vibe3/cli.py handoff plan docs/plans/issue-1021-vibe-new-bootstrap-enforcement.md
```

## Risks & Considerations

- **Risk**: None — this is a pure SKILL.md documentation change. No code paths, CLI contracts, or runtime behavior are affected.
- **Compatibility**: The test `tests/vibe3/skills/test_vibe_new_alignment.py` checks for section headers `## 1.` and `## 3.` and `## 停止条件` — these headers will be preserved as-is. The test also asserts no `vibe3 new` or `bootstrap_full_workflow` strings, which won't be introduced.
- **Short-term effect**: Agents reading the updated SKILL.md will see mandatory bootstrap-flow language and a clear prohibition list, eliminating the ambiguity that caused the manual-splicing incident in #1021's problem statement.
