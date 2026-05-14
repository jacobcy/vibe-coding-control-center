"""Event handlers for flow lifecycle events.

Handlers for agent execution events (planner, executor, reviewer).

Note: Worker ref validation and no-op blocking now live in
codeagent_runner.CodeagentExecutionService, which owns the unified sync shell
for command-mode, orchestra sync, and tmux-child execution. Domain event
handlers only provide visibility and failure/block side effects; they do NOT
perform proactive state advancement because the domain event path lacks the
full execution context.
"""
