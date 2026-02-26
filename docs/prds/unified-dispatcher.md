# PRD: Unified Dispatcher - Multi-Framework Support

## 1. Overview

Implement an intent detection layer and dispatcher that supports multiple workflow frameworks (Superpower, OpenSpec) with user preference tracking. The dispatcher should transparently route users to their chosen framework without强制.

## 2. Goals

- **Intent Detection**: Automatically detect whether user needs dispatcher or is directly using a framework
- **Framework Routing**: Guide users to select Superpower or OpenSpec, or auto-match based on history
- **Preference Memory**: Record framework choices per feature/project for future auto-routing
- **Transparent Execution**: Users should not need to know framework details - dispatcher handles matching

## 3. Scope

### 3.1 Entry Points

| Entry | Behavior |
|-------|----------|
| `/vibe-new <feature>` | Route through dispatcher |
| `/superpower:*` | Direct Superpower flow (no dispatch) |
| `/opsx:*` or `/openspec:*` | Direct OpenSpec flow (no dispatch) |
| Natural language request | Route through dispatcher |

### 3.2 Dispatcher Flow

```
User Request
    │
    ├── Has history for this feature?
    │     │
    │     ├── Yes → Check if still valid
    │     │         │
    │     │         ├── Valid → Auto-route to framework
    │     │         └── Invalid → Prompt user to reconfirm
    │     │
    │     └── No → Prompt user to select framework
    │
    └── Direct command (/superpower/* or /opsx:*)
              → Skip dispatcher, record choice
```

### 3.3 Memory Storage

- **Location**: `.agent/context/task.md` (existing file, extended)
- **Format**: Add `framework` field to track which workflow framework each task uses

**Task.md Extended Format**:
```markdown
## Current
- unified-dispatcher (framework: openspec)
  - status: planning
  - created: 2026-02-26

## Recent
- add-login (framework: superpower)
  - status: completed
  - framework: superpower
- fix-bug-123 (framework: openspec)
  - status: review
  - framework: openspec
```

### 3.4 Framework Selection Logic

When user requests `/vibe-new <feature>`:

```
1. Look up feature in task.md
   │
   ├── Found → Use recorded framework
   │
   └── Not found → Check similar tasks
        │
        ├── Found similar → Suggest same framework
        │
        └── No history → Prompt user to select
```

### 3.5 Framework Selection Prompt

```
"I detected you want to develop a new feature. Which approach would you prefer?

1. **OpenSpec** (/opsx:*) - Structured change management, suitable for complex projects
2. **Superpower** (/superpower:*) - Quick brainstorming, suitable for fast iteration

Or just tell me your idea, and I'll help you choose."
```

## 4. Non-Goals

- Do NOT force users through dispatcher (allow direct framework usage)
- Do NOT merge Superpower and OpenSpec into one system (keep independent)
- Do NOT change existing Superpower/OpenSpec usage patterns

## 5. Technical Requirements

### 5.1 No New Files Required

- Reuse existing `.agent/context/task.md` for framework tracking
- Reuse existing `lib/` functions for file operations

### 5.2 Modified Files

- `.agent/context/task.md` - Add `framework` field to task entries
- `skills/vibe-orchestrator/SKILL.md` - Add intent detection and framework matching logic

### 5.3 Integration Points

- `/vibe-new` should trigger dispatcher
- `/opsx:*` and `/superpower:*` should bypass dispatcher but record choice
- Historical choices should auto-populate on subsequent `/vibe-new` calls

## 6. Verification

- [ ] User can directly use `/opsx:new` without going through dispatcher
- [ ] User can directly use `/superpower:*` without going through dispatcher
- [ ] `/vibe-new` correctly prompts framework selection when no history exists
- [ ] Framework choice is recorded and persists across sessions
- [ ] Subsequent `/vibe-new` for same feature auto-selects previous framework

## 7. Reference

- **Cognition-Spec-Dominion**: docs/cognition-spec-dominion.md
- **This change**: docs/plans/2026-02-26-unified-dispatcher.md (for detailed design)
