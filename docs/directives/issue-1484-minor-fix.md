# Fix Directive: Issue #1484 — Hard Boundary Documentation

## Verdict
MINOR

## Problem
Step 6 (Epic 收口检查, line 300) queries ALL `roadmap/epic` issues regardless of assignee filter ("不受 assignee/governed 过滤限制"). This deliberately bypasses the hard boundary at line 236 ("只观察 assignee issue pool；不观察 broader repo backlog 或 supervisor issue 池").

The exception is narrow and well-defined (only for `roadmap/epic` completion checking), but the hard boundary rule should be updated to explicitly acknowledge this exception to prevent future confusion.

## Fix Required
Update hard boundary documentation in `supervisor/governance/assignee-pool.md`:

### Location 1: Line 21 (Hard Boundaries section)
Add exception note after the assignee pool boundary rule:
```markdown
**例外**：Epic 收口检查（Step 6）允许独立查询所有 `roadmap/epic` issues 以检查 sub-issues 完成状态，但仅限于建议关闭，不做 triage。
```

### Location 2: Line 236 (Boundary rule in governance_scan)
Add clarifying note:
```markdown
只观察 assignee issue pool；不观察 broader repo backlog 或 supervisor issue 池
**例外**：Step 6 (Epic 收口检查) 独立查询所有 `roadmap/epic` issues，不在此限制范围内
```

## Verification
1. Hard boundary rules at lines 21 and 236 explicitly acknowledge epic closure check exception
2. Exception is clearly scoped: "only for completion checking, no triage"
3. No functional changes required (implementation is already correct)

## Audit Reference
Full audit report: docs/reports/issue-1484-audit-report.md

## Commit Message
```
docs(governance): 明确 epic 收口检查的边界例外

- 在 Hard Boundaries 和 governance_scan 边界规则中添加例外说明
- 明确 Step 6 仅查询 epic 完成状态，不执行 triage
- 不影响现有功能实现，仅补充文档完整性
```
