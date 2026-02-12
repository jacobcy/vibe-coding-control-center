---
description: Document Audit & Tech Debt Cleanup
---

// turbo-all

1. Initialize audit session.
```bash
AUDIT_ID=$(date +%Y%m%d-%H%M)
AUDIT_DIR="docs/audits/${AUDIT_ID}"
mkdir -p "$AUDIT_DIR"
echo "Initializing audit session: $AUDIT_ID"
```

2. File Structure Audit (Automated).
- Check for misplaced files in root.
```bash
echo "=== Root Directory Check ==="
find . -maxdepth 1 -type f -not -name "README.md" -not -name "LICENSE" -not -name "CLAUDE.md" -not -name "SOUL.md" -not -name "CHANGELOG.md" -not -name "CONTRIBUTING.md" -not -name "DEVELOPER.md" -not -name ".gitignore" -not -name ".gitattributes" -not -name ".gitmodules"
```
- **Action**: Move identified files to appropriate locations (`docs/`, `scripts/`, `.agent/`).

3. Tech Debt Audit (Manual + Automated).
- Scan for TODOs and FIXMEs.
```bash
grep -r "TODO" . || echo "No TODOs found."
grep -r "FIXME" . || echo "No FIXMEs found."
```
- **Action**: Create clean-up tasks in `.agent/context/task.md`.

4. Improvement Plan & Execution.
- Write `docs/audits/${AUDIT_ID}/report.md` summarizing findings.
- Execute cleanup.
- Verify system stability:
```bash
./scripts/vibecoding.sh doctor
```
