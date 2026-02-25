# Agent Entry (Thin)

此文件是兼容入口，供默认读取仓库根目录的 Agent 使用。

## Canonical Context
- Persona: `.agent/context/agent.md`
- Current task: `.agent/context/task.md`
- Historical memory: `.agent/context/memory.md`
- Rules: `.agent/rules/`

## Reading Order
1. `SOUL.md`
2. `CLAUDE.md`
3. `.agent/context/task.md`
4. `.agent/context/memory.md`
5. `.agent/rules/*`

如有冲突，以 `SOUL.md` 和 `CLAUDE.md` 为准。
