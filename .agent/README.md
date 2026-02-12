# AI Agent Workspace (.agent)

**This directory is the designated working environment for all AI agents (Claude, OpenCode, Codex, Trae, etc.).**

All AI tools interacting with this project MUST reference this directory to understand:
1.  **Context**: Current state, memory, and active tasks.
2.  **Workflows**: Standardized procedures for common tasks.
3.  **Rules**: Coding standards and behavioral guidelines.

## 🔗 Core Links
- **[AGENTS.md](../AGENTS.md)**: Global Agent Entry Point
- **[CLAUDE.md](../CLAUDE.md)**: Project Tech Stack & Context
- **[SOUL.md](../SOUL.md)**: Constitution & Principles

## 📂 Directory Structure

- **`context/`**:
  - `memory.md`: Long-term memory of decisions and architectural choices.
  - `task.md`: Current active task and todo list.
  - `agent.md`: Persona and role definitions.
- **`workflows/`**: Executable guides for specific tasks (see table below).
- **`rules/`**: Specific coding standards and project rules.
- **`templates/`**: Templates for commits, PRs, etc.

## 🤖 AI Interoperability Protocol

To ensure consistent behavior across different AI IDEs and agents:
1.  **Read Context First**: Before starting any task, read `context/task.md` and `context/memory.md`.
2.  **Follow Workflows**: If a user request matches a workflow below, FOLLOW IT step-by-step.
3.  **Update Context**: When a task is complete, update `context/task.md` and `context/memory.md` with the outcome.

---

# Agent Workflows

This directory contains workflows that the AI agent can execute to assist with various development tasks.

## Available Workflows

| Workflow | Description | Usage |
| :--- | :--- | :--- |
| **[/audit-and-cleanup](workflows/audit-and-cleanup.md)** | Document Audit & Tech Debt Cleanup | user invokes `/audit-and-cleanup` to review code and docs for staleness. |
| **[/code-review](workflows/code-review.md)** | Automated Code Review & Static Analysis | user invokes `/code-review` to run linters and analyze code quality. |
| **[/debug](workflows/debug.md)** | Systematic Debugging Workflow | user invokes `/debug` when facing complex bugs to follow a structured diagnosis process. |
| **[/feature-commit](workflows/feature-commit.md)** | Interactive Smart Commit Workflow | user invokes `/feature-commit` to stage and commit changes atomically. |
| **[/initialize](workflows/initialize.md)** | Initialize or check project standard structure | user invokes `/initialize` to set up a new project or verify structure. |
| **[/post-task](workflows/post-task.md)** | Post-task maintenance | user invokes `/post-task` to clean up keys, verify tests, and record progress. |
| **[/pull-request](workflows/pull-request.md)** | Create a Pull Request | user invokes `/pull-request` to analyze commits, draft a description, and open a PR. |
| **[/release](workflows/release.md)** | Automated Release Workflow | user invokes `/release` to build, tag, and publish a new version. |
| **[/sync-branches](workflows/sync-branches.md)** | Sync to other worktrees | user invokes `/sync-branches` to propagate current changes to other local worktrees. |
| **[/tdd](workflows/tdd.md)** | Test-Driven Development Cycle | user invokes `/tdd` to implement features using the Red-Green-Refactor cycle. |

## Common Tasks

### Syncing from Main
To update your current branch with the latest changes from `main`, you do not need a workflow. Simply run:
```bash
git pull origin main
# OR
git fetch origin && git rebase origin/main
```

### Creating workflows
To create a new workflow, add a `.md` file to `workflows/` directory with the following frontmatter:
```markdown
---
description: [Short description]
---
```
Then list the steps the agent should follow. Use `// turbo` above git commands to allow auto-execution.
