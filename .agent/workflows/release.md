---
description: Automated Release Workflow
---

// turbo-all

1. Pre-release Checks.
- Ensure all tests pass.
```bash
./scripts/test-all.sh
```
- Ensure `CHANGELOG.md` is updated.

2. Version Bump.
- Determine next version (patch, minor, major).
- Tag the release.
```bash
# VERSION="v0.x.x"
# git tag -a $VERSION -m "Release $VERSION"
```

3. Push Release.
```bash
# git push origin $VERSION
```
