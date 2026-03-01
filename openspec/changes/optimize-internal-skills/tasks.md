## 1. Skill Metadata Examples (input_examples)

- [x] 1.1 Add `input_examples` to `skills/vibe-orchestrator/SKILL.md` (Gate parameters usage examples).
- [x] 1.2 Add `input_examples` to `skills/vibe-audit/SKILL.md` (Track A vs B usage examples).

## 2. vibe-commit Anti-Pollution Refactor

- [x] 2.1 Update `skills/vibe-commit/SKILL.md` documentation to rely on generated digest logs instead of naked `git diff`.
- [x] 2.2 Re-architect the `vibe-commit` shell execution layer to pipe `git diff` through a `head -n X` truncation hook or strictly generate summary text.

## 3. Review and Verify

- [ ] 3.1 Invoke a mock `vibe-commit` on a large codebase diff to verify context token length stays below target.
- [ ] 3.2 Let Agent successfully read the metadata `input_examples` inside newly updated skills to ensure correct routing behavior.
