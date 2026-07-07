## Graphify Explore: spec 012 US4 — Planner Context Consumption

### Affected Areas

graphify query "planner spec_ref consumption handoff plan" found:

```yaml
Core pipeline:
  - execute_spec_plan_sync()  [src/vibe3/roles/plan.py L521, community=150]
  - _resolve_spec_ref()       [src/vibe3/roles/plan.py L428, community=150]
  - build_plan_prompt_body()  [src/vibe3/agents/plan_prompt.py L186, community=81]
  - SpecRefService            [src/vibe3/services/shared/spec_ref.py L24, community=107]
  - HandoffService            [src/vibe3/services/handoff/service.py L30, community=60]

Test coverage:
  - test_spec_kit_bridge.py   [tests/vibe3/extensions/, community=187]
  - test_spec_ref_service.py  [tests/vibe3/services/, community=107]
  - test_planner_commit_detection.py [tests/vibe3/execution/, community=693]

Related specs:
  - 006-handoff-protocol       [.specify/specs/006-handoff-protocol/]
  - 012-spec-handoff-bridge    [.specify/specs/012-spec-handoff-bridge/]
```

### Gap Analysis

**graphify path "handoff" "plan"** → No path found

handoff 域和 plan 域无 graph edge。US4 需要桥接。

**graphify path "spec_ref" "plan"** → 5 hops confirmed:
```
spec_ref.py → SpecRefService ← resolve_spec_plan_input → PlanRequest ← _build_plan_prompt_providers → plan()
```
链路已建成，但 SpecRefService.get_spec_content_for_prompt() 未被 plan_prompt 调用。

**graphify path "handoff" "spec_ref"** → No path found

写入端（HandoffService._record_ref）和读取端（SpecRefService.resolve_spec_ref）无直接连接。

### Key Symbols

**build_plan_prompt_body()** (degree=19)
- 19 connections: calls VibeConfig, PromptManifest, _build_plan_prompt_providers
- 被 build_plan_prompt() 和 make_plan_context_builder() 调用
- 当前 providers: policy/task/output_format — 无 spec content provider
- 修改点: 在此函数或 providers 中添加 spec.ref → spec_content 桥接

**_resolve_spec_ref()** (degree=5)
- plan.py:428, 返回 str | None
- 被 execute_spec_plan_sync() 和 execute_spec_plan_async() 调用
- 仅返回 ref 字符串，不解析内容
- 修改点: 或保留现状，在 build_plan_prompt_body 层消费

**SpecRefService** (degree=28)
- 28 connections: parse_spec_ref, get_spec_content_for_prompt, resolve_spec_ref
- get_spec_content_for_prompt() 支持 file 和 issue 两种 kind
- 已完备，缺的是调用者

### Risk Notes

- Phase 7 修改 supervisor/policies/plan.md 时需确保不 breaking 现有 test_planner_commit_detection 测试
- baseline specs 001/003/006 的 implementation truth 更新应只改 section 不新增内容
- ADR-0006 proposed→accepted 需要确认 #3311 和 #3312 已落地
