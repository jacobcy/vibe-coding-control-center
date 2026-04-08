# Architecture Review Decisions

**Plan**: `docs/plans/2026-04-09-issue-pr-cache-unification-plan.md`
**Reviewer**: plan-eng-review
**Date**: 2026-04-09

---

## Decision #1: pr_number Storage Location

**Question**: Should `pr_number` be stored in `flow_state` table or cache table?

**Context**:
- Schema has no `pr_number` field in `flow_state` table
- But code assumes it exists (`flow_data.get("pr_number")`)
- Design doc proposes cache table only

**Decision**: ✅ **Cache table only**

**Rationale**:
- Cache is for optimization (issue/PR titles, PR numbers)
- `flow_state` is for truth (branch metadata, actor, status)
- PR number is bridge data (hint for GitHub lookup), belongs to cache

**Migration**:
- Remove all `flow_data.get("pr_number")` reads
- Replace with `cache_service.get_pr_number(branch)` or direct GitHub lookup
- No schema migration needed (field never existed)

---

## Decision #2: Issue Title Fetch Unification

**Question**: Should issue title fetch be unified under cache service?

**Context**:
- `FlowProjectionService.get_issue_titles()` - batch fetch
- `SpecRefService._fetch_issue_data()` - single fetch
- Both call `gh` API directly without cache

**Decision**: ✅ **Migrate to FlowContextCacheService**

**Rationale**:
- Eliminates duplicate API calls
- Single source for issue/PR context
- Consistent TTL management

**Migration**:
- `FlowProjectionService` → use `cache_service.get_issue_titles()`
- `SpecRefService` → use `cache_service.get_issue_title()`
- Cache service handles UPSERT + staleness

---

## Decision #3: Sync Trigger Points

**Question**: Where should `cache_service.maybe_sync()` be called?

**Decision**: ✅ **After commands that modify flow/PR state**

**Trigger Points**:
1. **Flow commands**:
   - `flow update` (after `ensure_flow_for_branch`)
   - `flow bind` (after `link_issue`)

2. **PR commands**:
   - `pr create` (after PR creation)
   - `pr ready` (after lifecycle change)

3. **Service methods**:
   - `FlowService.create_flow()` (after flow creation)
   - `FlowService.ensure_flow_for_branch()` (after flow registration)

**Implementation**:
```python
# In command handler
cache_service = FlowContextCacheService()
cache_service.maybe_sync()  # Check staleness + command counter

# In service method
def create_flow(...):
    # ... create flow logic
    cache_service = FlowContextCacheService()
    cache_service.maybe_sync()
```

---

## Decision #4: Cache vs Truth Boundaries

**Question**: What belongs to cache vs truth?

**Decision**: ✅ **Strict separation**

**Truth** (never deleted):
- `flow_state` - branch metadata, actor, status
- `flow_issue_links` - issue relationships
- `flow_events` - audit log

**Cache** (can be stale/deleted):
- Issue title/body
- PR number/title/state
- Milestone data

**Degradation**:
- If cache is stale → fetch from GitHub
- If cache is missing → lazy populate on first access
- If GitHub unavailable → graceful degradation (show issue number only)

---

## Next Steps

1. Fix schema-code inconsistency (remove `flow_data.get("pr_number")`)
2. Implement `FlowContextCacheService` with lazy initialization
3. Migrate issue title fetch paths to cache service
4. Add `maybe_sync()` calls to trigger points
5. Update design doc with architecture decisions