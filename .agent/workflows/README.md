# Agent Workflows

This directory contains workflows that the AI agent can execute to assist with various development tasks.

## Available Workflows

| Workflow | Description | Usage |
| :--- | :--- | :--- |
| **[/audit-and-cleanup](audit-and-cleanup.md)** | Document Audit & Tech Debt Cleanup | user invokes `/audit-and-cleanup` to review code and docs for staleness. |
| **[/code-review](code-review.md)** | Automated Code Review & Static Analysis | user invokes `/code-review` to run linters and analyze code quality. |
| **[/debug](debug.md)** | Systematic Debugging Workflow | user invokes `/debug` when facing complex bugs to follow a structured diagnosis process. |
| **[/feature-commit](feature-commit.md)** | Interactive Smart Commit Workflow | user invokes `/feature-commit` to stage and commit changes atomically. |
| **[/initialize](initialize.md)** | Initialize or check project standard structure | user invokes `/initialize` to set up a new project or verify structure. |
| **[/post-task](post-task.md)** | Post-task maintenance | user invokes `/post-task` to clean up keys, verify tests, and record progress. |
| **[/pull-request](pull-request.md)** | Create a Pull Request | user invokes `/pull-request` to analyze commits, draft a description, and open a PR. |
| **[/release](release.md)** | Automated Release Workflow | user invokes `/release` to build, tag, and publish a new version. |
| **[/sync-branches](sync-branches.md)** | Sync to other worktrees | user invokes `/sync-branches` to propagate current changes to other local worktrees. |
| **[/tdd](tdd.md)** | Test-Driven Development Cycle | user invokes `/tdd` to implement features using the Red-Green-Refactor cycle. |

## Common Tasks

### Syncing from Main
To update your current branch with the latest changes from `main`, you do not need a workflow. Simply run:
```bash
git pull origin main
# OR
git fetch origin && git rebase origin/main
```

### Creating workflows
To create a new workflow, add a `.md` file to this directory with the following frontmatter:
```markdown
---
description: [Short description]
---
```
Then list the steps the agent should follow. Use `// turbo` above git commands to allow auto-execution.
