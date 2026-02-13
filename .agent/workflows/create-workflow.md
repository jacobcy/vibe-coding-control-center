---
description: Architect a new Agentic Workflow (Prompt Engineering)
---

# Workflow Architect

## 1. Discovery Phase (Prompt Engineering)
**INSTRUCTION**: You are the "Workflow Architect". Interview the user to design a high-quality prompt (workflow).

Ask the following questions (wait for answers):
1.  **Goal**: "What is the specific objective of this workflow?"
2.  **Context**: "What information does the agent need *before* starting? (e.g., git status, specific files)"
3.  **Pitfalls**: "What are the common mistakes or 'gotchas' in this process? I will turn these into Alerts."
4.  **Verification**: "How do we know it succeeded?"

## 2. Structural Design
Based on the answers, draft a workflow file using `_template_workflow.md` as the base.

**Key Requirements**:
- **Inject Goal**: Put the Goal in the `description` frontmatter.
- **Inject Context**: Add specific commands to "Prerequisites".
- **Inject Pitfalls**: Create `> [!IMPORTANT]` or `> [!WARNING]` blocks in relevant steps.
- **Inject Verification**: Add specific checks to "Verification".

## 3. Drafting
// turbo
```bash
echo "=== Workflow Architect ==="
read -p "Filename (e.g., deploy-prod.md): " filename

if [ -z "$filename" ]; then
    echo "Error: Filename required."
    exit 1
fi

target=".agent/workflows/$filename"
if [ -f "$target" ]; then
    echo "Error: $target already exists."
    exit 1
fi

# Create placeholder (Agent will overwrite this with the drafted content)
touch "$target"
echo "Drafting to $target..."
```

## 4. Review & Refine
**INSTRUCTION**: Present the drafted workflow content to the User in a code block.
Ask: "Does this workflow capture all the nuances? Should we add more reminders?"

## 5. Finalize
If the user approves, write the content to `$target`.
```bash
# Agent: Use 'write_to_file' tool here to save the final content.
echo "Workflow saved to $target. Run 'vibe run $filename' to test it."
```
