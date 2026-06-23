# Project-Specific Roadmap Intake Extensions

This file demonstrates the `.vibe/governance/` overlay mechanism.

## Purpose

Project-specific governance extensions that are automatically appended to the
default governance materials (e.g., `supervisor/governance/roadmap-intake.md`).

## Usage

1. Create `.vibe/governance/<material-name>.md` matching the base material name
2. Add project-specific rules, checks, or extensions
3. Content is automatically appended when governance scans use that material

## Example: Custom Intake Checks

You can add project-specific intake rules here:

```markdown
### Project-Specific Intake Rules

1. **Custom Label Check**: Verify issues have required project labels
2. **Project Convention Check**: Ensure issues follow project-specific conventions
3. **Milestone Alignment**: Check alignment with project roadmap milestones
```

## Note

This overlay mechanism follows the same pattern as `.vibe/policies/`:

- `.vibe/policies/plan.md` → appends to `supervisor/policies/plan.md`
- `.vibe/governance/roadmap-intake.md` → appends to `supervisor/governance/roadmap-intake.md`

Both are automatically discovered and applied during prompt assembly.
