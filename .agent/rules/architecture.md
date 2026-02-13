# Vibe Agent Architecture

## Core Philosophy
**"Scripts for Logic, Markdown for Orchestration."**

The Vibe ecosystem separates concerns into two distinct layers:
1.  **The Brain (Markdown Workflows)**: High-level reasoning, decision making, and step orchestration.
2.  **The Hands (Shell Scripts)**: deterministic, reusable, and testable execution units.

## Architectural Layers

### 1. Workflow Layer (`.agent/workflows/*.md`)
- **Purpose**: Guiding the AI Agent through a process.
- **Content**: Natural language instructions, decision trees, and calls to the Library Layer.
- **Rule**: Workflows **SHOULD NOT** contain complex inline code (loops, heavy logic). They should call scripts.

### 2. Library Layer (`.agent/lib/*.sh`)
- **Purpose**: The "Standard Library" of the Vibe ecosystem.
- **Content**: Pure Bash/Zsh functions.
- **Rule**: Functions must be **Idempotent** and **Atomic**.
- **Rule**: Functions must handle their own error reporting.

### 3. Rules Layer (`.agent/rules/*.md`)
- **Purpose**: The Source of Truth for patterns, style, and decisions.
- **Usage**: Workflows must explicitly read these files to "load" the context into the Agent's working memory before performing complex tasks.

## Directory Structure
```
.agent/
├── workflows/      # Human/Agent readable guides
├── lib/            # Machine executable logic
├── rules/          # Standards & Patterns
└── templates/      # Scaffolding
```
