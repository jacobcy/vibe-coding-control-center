---
description: Document Audit & Tech Debt Cleanup
---

// turbo-all

1. Initialize audit session and directory.
```bash
AUDIT_ID=$(date +%Y%m%d-%H%M)
AUDIT_DIR="docs/audits/${AUDIT_ID}"
mkdir -p "$AUDIT_DIR"
echo "Initializing audit session: $AUDIT_ID"
```

2. Phase 1: Document Audit.
- Audit root uppercase files (AI context) vs. `docs/` (Human context).
- Identify obsolete or unsynced files.
- **Action**: Think about the mapping and write `docs/audits/${AUDIT_ID}/doc-audit-report.md`.

3. Phase 2: Tech Debt Audit.
- Audit codebase for patterns, complexity, and security gaps.
- **Action**: Perform analysis and write `docs/audits/${AUDIT_ID}/code-audit-report.md`.

4. Phase 3: Improvement Plan.
- Based on reports, draft a prioritized cleanup plan.
- **Action**: Write `docs/audits/${AUDIT_ID}/cleanup-plan.md`.

5. Phase 4: Execution & Final Report.
- Execute the cleanup steps (requires confirmation if not turbo).
- **Action**: Generate `docs/audits/${AUDIT_ID}/execution-report.md` after work is done.
