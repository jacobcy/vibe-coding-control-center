# Branch Protection Rules (Rulesets)

As defined in the [Vibe Coding Constitution](../../SOUL.md), the `main` branch is the source of truth and must be protected.

## Target Branch: `main`

The following rulesets are enforced via GitHub Repository Settings:

### 1. Require Pull Request Before Merging
- **Require a pull request before merging**: Enabled.
- **Require approvals**: At least 1.
- **Dismiss stale pull request approvals when new commits are pushed**: Enabled.
- **Resolve conversations**: Required.

### 2. Restrictions
- **Block force pushes**: Enabled (No history rewrite).
- **Block deletions**: Enabled (Cannot delete main).

## Implementation
These rules are enforced via GitHub Rulesets.
Changes to these rules require Admin access and should be reflected in this document.
