# /save Command Design

## Overview

`/save` is a session wrap-up command that preserves conversation context before ending an agent session. It prevents loss of valuable information by automatically extracting and organizing:

- Unfinished tasks
- Conversation history organized by topic
- Problem-solving solutions
- Key decisions

---

## Core Features

### 1. Topic-Based Memory Organization

Automatically identify topics from the conversation and create/update topic files.

**File Structure:**
```
.agent/
├── context/
│   ├── memory.md              # Key decisions index + summary
│   ├── memory/                # Topic detailed records (NEW)
│   │   ├── tdd-workflow.md
│   │   ├── config-system.md
│   │   └── ...
│   └── task.md                # Task tracking (existing)
└── .session-counter           # Temp file for tracking conversation rounds
```

### 2. Section-Level Update Strategy

When updating existing topic files, use **section-level replacement**:

- Read existing topic file
- Identify which sections have new content
- Replace only those sections with updated content
- Preserve unchanged sections
- Update `Last Updated` timestamp and increment `Sessions` count

**Example:**
```
Existing: config-system.md has 3 Key Decisions, 1 Problem

New conversation adds:
- 1 new Key Decision
- 1 new Problem

Result:
- Key Decisions: 3 old + 1 new = 4 total (section replaced)
- Problems & Solutions: 1 old + 1 new = 2 total (section replaced)
- Other sections: preserved
- Last Updated: updated to current date
- Sessions: incremented
```

### 3. Unfinished Task Tracking

Extract unfinished tasks from conversation and add to task.md with context.

**Task ID Format:** `<topic>-YYYYMMDD-NNN`
- Example: `config-20260221-001`
- Readable, traceable to source topic

### 4. Problem & Solution Recording

Record problems encountered and their solutions:
- **Simple problems**: 1-2 sentence summary
- **Complex problems**: Structured template (Issue, Investigation, Solution, Lesson)

### 5. Smart Stop Hook Reminder

- **PreToolUse Hook**: Count user messages (stored in temp file)
- **Stop Hook**: If rounds > 8, remind user to run `/save`

### 6. Learn Suggestion

After saving context, analyze if content has reusable patterns worth extracting:

- **Pattern types to suggest**: error_resolution, debugging_techniques, workarounds, project_specific
- **Analysis criteria**:
  - Repeated patterns across sessions
  - User corrections that reveal best practices
  - Solutions to specific problems
  - Project conventions worth documenting

**Suggestion Flow:**
```
After /save completes:
  ↓
Analyze saved content for reusable patterns
  ↓
If patterns found:
  → Suggest: "发现 X 个可复用模式，是否运行 /learn 提取为 skill？"
  → List pattern types found
  ↓
User confirms:
  → Run /learn to extract patterns
```

**Decision Factors:**
- Session frequency with same topic → Higher learn value
- User corrections present → Learn the corrected approach
- Problem solutions documented → Learn the solution pattern

---

## Relationship with continuous-learning

| Aspect | `/save` | continuous-learning |
|--------|---------|---------------------|
| **Purpose** | Save project context | Extract reusable patterns |
| **Storage** | Project-level `.agent/context/memory/` | Global `~/.claude/skills/learned/` |
| **Trigger** | Manual `/save` + Hook reminder | Stop Hook (auto, needs config) |
| **Content** | Topics, tasks, decisions, solutions | Patterns, techniques, best practices |

**Integration with /learn:**
- `/save` stores project-specific knowledge in `memory/`
- After saving, `/save` analyzes content for reusable patterns
- If patterns found, suggests running `/learn` to extract as global skill
- `/learn` reads from `memory/` and creates skills in `~/.claude/skills/learned/`
- They are complementary: `/save` = project context, `/learn` = global patterns

---

## File Format Specifications

### memory.md (Updated)

```markdown
# MEMORY

## Active Context
（保持现有格式）

## Key Decisions
（保持现有格式）

## Topic Index
| Topic | Last Updated | Summary |
|-------|--------------|---------|
| [tdd-workflow](memory/tdd-workflow.md) | 2026-02-21 | TDD 工作流优化与测试策略 |
| [config-system](memory/config-system.md) | 2026-02-20 | 配置系统重构，keys.env 管理策略 |

## Incidents & Lessons Learned
（保持现有格式）

## Execution Log
（保持现有格式）
```

### memory/<topic>.md

```markdown
# <Topic Name>

## Summary
<!-- 1-2 句主题概述 -->

## Key Decisions
<!-- 关于此主题的关键决策 -->

## Problems & Solutions
### <Problem 1>
- **Issue**: ...
- **Solution**: ...
- **Lesson**: ...（可选，复杂问题才有）

## Related Tasks
- [ ] <topic>-20260221-001: Task description
- [x] <topic>-20260220-001: Completed task

## References
- 相关文件、链接等

---
Created: YYYY-MM-DD
Last Updated: YYYY-MM-DD
Sessions: 3
```

### task.md (Updated)

```markdown
# TASK

## Current Sprint
<!-- 当前正在进行的任务 -->
- [ ] [<topic>-YYYYMMDD-NNN] Task description (in progress)
- [ ] [<topic>-YYYYMMDD-NNN] Task description (blocked by #XXX)

## Backlog
<!-- 待办任务，按优先级排序 -->
- [ ] [<topic>-YYYYMMDD-NNN] Task description
  - Context: 来自 [memory/<topic>.md](memory/<topic>.md)
  - Created: YYYY-MM-DD
  - Blocked by: 需要先完成 TASK-XXX（可选）

## Completed
- [x] [<topic>-YYYYMMDD-NNN] Completed task description
```

---

## /save Skill Workflow

```
1. Analyze conversation content
   ↓
2. Identify topics (1-N topics)
   ↓
3. For each topic:
   a. Check if memory/<topic>.md exists
   b. If exists: Read current content
   c. Identify sections with new/changed content
   d. Update only those sections (section-level replacement)
   e. Update Last Updated timestamp
   f. Increment Sessions count
   ↓
4. Update memory.md index
   - Add new topics to table
   - Update Last Updated for modified topics
   ↓
5. Update task.md
   - Generate task IDs: <topic>-YYYYMMDD-NNN
   - Append new unfinished tasks to Backlog
   - Mark completed tasks
   ↓
6. Output summary report to user
   ↓
7. Analyze for learnable patterns
   - Check for reusable patterns across saved content
   - If found, suggest running /learn
   - Optionally call /learn with user confirmation
```

---

## Section-Level Update Algorithm

```
For each identified topic:
  existing_file = read memory/<topic>.md

  if existing_file exists:
    new_content = analyze conversation for this topic

    for each section in [Summary, Key Decisions, Problems, Tasks, References]:
      if new_content has updates for section:
        replace section in existing_file
      else:
        preserve existing section

    update Last Updated = today
    increment Sessions count
  else:
    create new memory/<topic>.md with all sections
```

---

## Stop Hook Implementation

### PreToolUse Hook (session-counter)

```bash
# Track user messages
COUNTER_FILE="/tmp/vibe-session-counter-$$"

# Increment on each user message (detected via tool use pattern)
if [[ ! -f "$COUNTER_FILE" ]]; then
    echo "0" > "$COUNTER_FILE"
fi

count=$(cat "$COUNTER_FILE")
echo $((count + 1)) > "$COUNTER_FILE"
```

### Stop Hook (save-reminder)

```bash
COUNTER_FILE="/tmp/vibe-session-counter-$$"
THRESHOLD=8

if [[ -f "$COUNTER_FILE" ]]; then
    rounds=$(cat "$COUNTER_FILE")
    if [[ $rounds -gt $THRESHOLD ]]; then
        echo "💡 本次对话已进行 $rounds 轮，建议运行 /save 保存上下文"
    fi
    rm "$COUNTER_FILE"
fi
```

---

## Task Types to Identify

| Type | Example | Handling |
|------|---------|----------|
| **Explicit** | "帮我实现用户登录功能" | Extract directly |
| **Implicit** | "这个问题以后再处理" | Identify as pending |
| **Partial** | "先做 A，B 以后再说" | Mark A done, B pending |
| **Blocked** | "等 XXX 完成后才能继续" | Record blocking reason |

---

## Output Example

```
📋 Session Summary

📁 Topics: 2
  • save-command (new)
  • config-system (updated)

✅ Tasks Added: 3
  • save-20260221-001: Implement Stop Hook mechanism
  • save-20260221-002: Add session counter
  • config-20260221-001: Fix env loading edge case

💡 Key Decisions: 2
  • Topic-based organization over date-based
  • Task ID format: <topic>-YYYYMMDD-NNN

🔧 Problems Solved: 1
  • How to detect conversation value → User message count threshold

📂 Files Updated:
  • .agent/context/memory/save-command.md (created)
  • .agent/context/memory/config-system.md (updated)
  • .agent/context/memory.md (index updated)
  • .agent/context/task.md (3 tasks added)

---

🎓 Learn Suggestion
发现 2 个可复用模式：
  • error_resolution: env loading edge case
  • project_specific: task ID naming convention

是否运行 /learn 提取为 skill？[y/N]
```

---

## Design Decisions

1. **Naming: `/save`** - Describes action (saving context), not farewell
2. **Topic-based organization** - Better than date-based for future retrieval
3. **Section-level update** - Replace only changed sections, practical and reliable
4. **Auto-identify topics** - Agent analyzes and names topics automatically
5. **Task + context dual tracking** - Tasks in task.md, context in topic files, bidirectional reference
6. **Problem complexity-based recording** - Simple = brief, Complex = structured
7. **Skill + Hook dual trigger** - Manual `/save` + automatic reminder for > 8 rounds
8. **Topic-prefix task IDs** - `<topic>-YYYYMMDD-NNN` format for readability and traceability
9. **Independent from continuous-learning** - `/save` for project context, `/learn` for global patterns

---

## Implementation Priority

1. **P0**: `/save` Skill core logic with section-level update
2. **P0**: memory/ directory structure and file formats
3. **P1**: Stop Hook reminder mechanism
4. **P2**: Integration with `/learn` for pattern extraction from memory/

---

*Created: 2026-02-21*
*Updated: 2026-02-21*
*Status: Design Approved*
