# Kiro Integration Rules

本文件定义 Kiro (AI IDE with spec workflow) 与 Vibe Center 的集成规则。

术语以 [docs/standards/glossary.md](../../docs/standards/glossary.md) 为准。

## Spec Location

Kiro specs MUST be created in `.kiro/specs/{feature-name}/` directory:
- Bugfix specs: `bugfix.md`, `design.md`, `tasks.md`
- Feature specs: `requirements.md`, `design.md`, `tasks.md`

## Vibe Task Integration

Each Kiro spec MUST have a corresponding Vibe task directory:
- Create task directory: `docs/tasks/{YYYY-MM-DD-feature-name}/`
- Create task README: `docs/tasks/{YYYY-MM-DD-feature-name}/README.md`
- Link Kiro spec in README's "文档导航" section
- The issue body is the canonical task description; task README is only the mirror/navigation surface

## Task Lifecycle

Use `vibe task` commands to manage task lifecycle:
- Register task: `vibe task add {task-id} --title "{title}" --status todo`
- Update status: `vibe task update {task-id} --status {status}`
- Bind to worktree: `vibe task update {task-id} --bind-current`
- List tasks: `vibe task list`

## Status Synchronization

Keep Kiro spec and Vibe task status in sync:
- Kiro spec execution → Update `vibe task` status
- Task completion → Update both `.kiro/specs/` and `docs/tasks/` README
- Use frontmatter `status` field as single source of truth in task README
- Long-lived findings should be recorded in the linked GitHub issue comment or PR comment

## Documentation Standards

Follow Vibe documentation standards:
- Task naming: `YYYY-MM-DD-feature-name` (kebab-case)
- Document naming: `{layer}-v{version}-{description}.md` or `{layer}-{description}.md`
- Reference: [docs/standards/doc-organization.md](../../docs/standards/doc-organization.md)

## Python Project Setup

This project uses **uv** for Python dependency management and virtual environment:

**Configuration**: `pyproject.toml` at project root

**Commands**:
- Install dependencies: `uv sync`
- Add dependencies: `uv add <package>`
- Remove dependencies: `uv remove <package>`
- Run commands: `uv run <command>`
- Run Python: `uv run python` (**DO NOT use `python` or `python3` directly**)

**Prohibited**:
- ❌ Using `python`, `python3`, `pip`, `pip3` commands
- ❌ Manual virtual environment creation (`python -m venv`)
- ❌ Using `requirements.txt` (use `pyproject.toml` only)

See [.agent/rules/python-standards.md](./python-standards.md) for complete Python coding standards.
