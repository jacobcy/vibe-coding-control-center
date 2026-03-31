# Prompt Assembly Unification Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 plan / run / review / orchestra / manager 的 prompt 组装方式统一为同一套可配置 recipe 和可验证 renderer，让模板、变量来源、dry run 展示、缺失变量检测都走同一个入口。

**Architecture:** 在命令层和 codeagent 执行层之间新增 Prompt Assembly 层。该层用 recipe 描述模板、变量和来源，通过统一 assembler 拉取 skill、文件、命令输出、provider 返回值并渲染最终 prompt；执行层只消费已经 materialize 的 prompt 和 provenance。先迁移 orchestra governance 与 assignee dispatch，再迁移 plan / run / review。

**Tech Stack:** Python, Pydantic, Typer, YAML, pytest, ruff, black, codeagent-wrapper

---

## Scope And Non-Goals

- In scope:
  - 统一 prompt recipe 数据模型
  - 统一模板解析、变量来源解析、变量校验、dry run 预览
  - orchestra governance 与 assignee dispatch 首批迁移
  - run / plan / review 接入统一 assembler
  - 新增 prompt check / render 验证命令或等价 usecase
- Out of scope:
  - 本轮不重写所有 skill 内容
  - 本轮不优化各业务 prompt 的文案质量
  - 本轮不改 codeagent-wrapper 本身

## File Map

### Create

- `src/vibe3/prompts/models.py`
- `src/vibe3/prompts/assembler.py`
- `src/vibe3/prompts/provider_registry.py`
- `src/vibe3/prompts/builtin_providers.py`
- `src/vibe3/prompts/exceptions.py`
- `src/vibe3/services/prompt_recipe_service.py`
- `tests/vibe3/prompts/test_models.py`
- `tests/vibe3/prompts/test_assembler.py`
- `tests/vibe3/prompts/test_provider_registry.py`
- `tests/vibe3/prompts/test_prompt_recipe_service.py`

### Modify

- `config/prompts.yaml`
- `config/settings.yaml`
- `src/vibe3/config/settings.py`
- `src/vibe3/services/prompt_template_service.py`
- `src/vibe3/services/codeagent_models.py`
- `src/vibe3/services/execution_pipeline.py`
- `src/vibe3/commands/run.py`
- `src/vibe3/commands/plan.py`
- `src/vibe3/commands/review.py`
- `src/vibe3/services/run_context_builder.py`
- `src/vibe3/services/plan_context_builder.py`
- `src/vibe3/services/context_builder.py`
- `src/vibe3/services/review_usecase.py`
- `src/vibe3/orchestra/config.py`
- `src/vibe3/orchestra/dispatcher.py`
- `src/vibe3/orchestra/services/governance_service.py`
- `src/vibe3/orchestra/services/assignee_dispatch.py`
- `tests/vibe3/orchestra/test_governance_service.py`
- `tests/vibe3/orchestra/test_dispatcher.py`
- `tests/vibe3/orchestra/test_assignee_dispatch.py`
- `tests/vibe3/commands/test_run.py`
- `tests/vibe3/commands/test_plan.py`
- `tests/vibe3/commands/test_review.py`

---

## Chunk 1: Core Prompt Assembly Layer

### Task 1: Define recipe and provenance models

**Files:**
- Create: `src/vibe3/prompts/models.py`
- Create: `src/vibe3/prompts/exceptions.py`
- Test: `tests/vibe3/prompts/test_models.py`

- [ ] Step 1: Write failing tests for recipe parsing and validation
- [ ] Step 2: Run `uv run pytest tests/vibe3/prompts/test_models.py -q` and verify FAIL
- [ ] Step 3: Implement `PromptRecipe`, `PromptVariableSource`, `PromptRenderResult`, `PromptVariableProvenance`
- [ ] Step 4: Add explicit errors for missing variables and unused variables
- [ ] Step 5: Run tests and lint
- [ ] Step 6: Commit

### Task 2: Build provider registry and variable resolvers

**Files:**
- Create: `src/vibe3/prompts/provider_registry.py`
- Create: `src/vibe3/prompts/builtin_providers.py`
- Test: `tests/vibe3/prompts/test_provider_registry.py`

- [ ] Step 1: Write failing tests for `literal`, `skill`, `file`, `command`, `provider`
- [ ] Step 2: Run `uv run pytest tests/vibe3/prompts/test_provider_registry.py -q` and verify FAIL
- [ ] Step 3: Implement provider registry and builtin resolvers
- [ ] Step 4: Reuse `RunUsecase.find_skill_file()` for skill lookup
- [ ] Step 5: Run tests and lint
- [ ] Step 6: Commit

### Task 3: Implement the assembler and validation engine

**Files:**
- Create: `src/vibe3/prompts/assembler.py`
- Create: `src/vibe3/services/prompt_recipe_service.py`
- Modify: `src/vibe3/services/prompt_template_service.py`
- Test: `tests/vibe3/prompts/test_assembler.py`
- Test: `tests/vibe3/prompts/test_prompt_recipe_service.py`

- [ ] Step 1: Write failing tests for render success, missing variables, unused variables, and provenance output
- [ ] Step 2: Run `uv run pytest tests/vibe3/prompts/test_assembler.py tests/vibe3/prompts/test_prompt_recipe_service.py -q` and verify FAIL
- [ ] Step 3: Implement `PromptAssembler.render(recipe_key, runtime_context)`
- [ ] Step 4: Extract template variable names before formatting and validate contract
- [ ] Step 5: Keep template lookup and source resolution in separate modules
- [ ] Step 6: Run tests and lint
- [ ] Step 7: Commit

---

## Chunk 2: Orchestra Migration

Parallel note: Chunk 2 and Chunk 3 can proceed in parallel after Chunk 1 lands because they consume the new assembler but touch different entrypoints.

### Task 4: Migrate governance to recipe-based prompt assembly

**Files:**
- Modify: `src/vibe3/orchestra/config.py`
- Modify: `src/vibe3/orchestra/services/governance_service.py`
- Modify: `config/prompts.yaml`
- Modify: `config/settings.yaml`
- Test: `tests/vibe3/orchestra/test_governance_service.py`

- [ ] Step 1: Write failing tests asserting governance uses recipe-driven rendering and dry-run provenance
- [ ] Step 2: Run `uv run pytest tests/vibe3/orchestra/test_governance_service.py -q` and verify FAIL
- [ ] Step 3: Replace governance-specific inline render logic with assembler invocation
- [ ] Step 4: Keep runtime issue summary providers in orchestra layer, not in generic prompt service
- [ ] Step 5: Ensure dry run prints template key, template file, skill source, provider keys, final rendered prompt path
- [ ] Step 6: Move governance recipe declaration into config rather than hardcoded Python branches
- [ ] Step 7: Run tests and lint
- [ ] Step 8: Commit

### Task 5: Migrate assignee dispatch to the same assembly mechanism

**Files:**
- Modify: `src/vibe3/orchestra/dispatcher.py`
- Modify: `src/vibe3/orchestra/services/assignee_dispatch.py`
- Modify: `config/prompts.yaml`
- Modify: `config/settings.yaml`
- Test: `tests/vibe3/orchestra/test_dispatcher.py`
- Test: `tests/vibe3/orchestra/test_assignee_dispatch.py`

- [ ] Step 1: Write failing tests asserting manager dispatch no longer hardcodes a single `Implement issue #...` prompt
- [ ] Step 2: Run `uv run pytest tests/vibe3/orchestra/test_dispatcher.py tests/vibe3/orchestra/test_assignee_dispatch.py -q` and verify FAIL
- [ ] Step 3: Add assignee-dispatch recipe config with default `vibe-manager` skill and no global runtime section
- [ ] Step 4: Reuse the same assembler as governance but pass only issue-local runtime context
- [ ] Step 5: Keep assignee dispatch responsible only for trigger timing and flow/worktree resolution
- [ ] Step 6: Ensure dry run shows the exact manager prompt that would be sent
- [ ] Step 7: Run tests and lint
- [ ] Step 8: Commit

---

## Chunk 3: Plan / Run / Review Migration

Parallel note: Chunk 3 can start once Chunk 1 is merged; it does not depend on Chunk 2 except for shared conventions.

### Task 6: Normalize run/plan/review around recipe-backed prompt materialization

**Files:**
- Modify: `src/vibe3/commands/run.py`
- Modify: `src/vibe3/commands/plan.py`
- Modify: `src/vibe3/commands/review.py`
- Modify: `src/vibe3/services/run_context_builder.py`
- Modify: `src/vibe3/services/plan_context_builder.py`
- Modify: `src/vibe3/services/context_builder.py`
- Modify: `src/vibe3/services/review_usecase.py`
- Modify: `src/vibe3/services/codeagent_models.py`
- Modify: `src/vibe3/services/execution_pipeline.py`
- Test: `tests/vibe3/commands/test_run.py`
- Test: `tests/vibe3/commands/test_plan.py`
- Test: `tests/vibe3/commands/test_review.py`

- [ ] Step 1: Write failing tests proving commands can resolve a recipe and dry-run it consistently
- [ ] Step 2: Run `uv run pytest tests/vibe3/commands/test_run.py tests/vibe3/commands/test_plan.py tests/vibe3/commands/test_review.py -q` and verify FAIL
- [ ] Step 3: Convert context builders from final-string builders into provider helpers or recipe-fed sections
- [ ] Step 4: Extend execution models to carry prompt provenance summary without mixing it into business metadata
- [ ] Step 5: Make dry-run output uniform across plan / run / review
- [ ] Step 6: Preserve backward compatibility for `--skill` and `--plan` CLI surfaces while changing internals
- [ ] Step 7: Run tests and lint
- [ ] Step 8: Commit

---

## Chunk 4: Validation And Operator Tooling

### Task 7: Add unified prompt validation and rendering entrypoints

**Files:**
- Modify: `src/vibe3/config/settings.py`
- Modify: `config/settings.yaml`
- Modify: `config/prompts.yaml`
- Create or modify command surface under `src/vibe3/commands/`
- Test: dedicated tests under `tests/vibe3/prompts/` and `tests/vibe3/commands/`

- [ ] Step 1: Write failing tests for a prompt validation command or usecase
- [ ] Step 2: Run targeted tests and verify FAIL
- [ ] Step 3: Add a command or usecase that can validate recipe contracts, render a recipe with sample runtime input, and output JSON provenance
- [ ] Step 4: Add clear operator-facing errors for missing template keys, missing providers, missing files, and command failures
- [ ] Step 5: Run tests and lint
- [ ] Step 6: Commit

### Task 8: Documentation and migration notes

**Files:**
- Modify: `config/prompts.yaml`
- Modify: `config/settings.yaml`
- Modify docs under `docs/` if operator instructions already exist

- [ ] Step 1: Document the recipe schema, variable source kinds, and dry-run expectations
- [ ] Step 2: Add one governance example and one assignee-dispatch example
- [ ] Step 3: Add migration notes for legacy context builders and direct string prompts
- [ ] Step 4: Run docs smoke checks if present
- [ ] Step 5: Commit

---

## Parallel Execution Guide

- Phase order:
  - Chunk 1 must land first.
  - After Chunk 1, Chunk 2 and Chunk 3 can run in parallel.
  - Chunk 4 depends on the stable public shape from Chunk 2 and Chunk 3.
- Safe parallel boundaries:
  - Orchestra migration and command migration are independent after assembler contracts settle.
  - Governance and assignee dispatch inside Chunk 2 should stay sequential because both touch orchestra config.
  - Run / plan / review inside Chunk 3 can be split by entrypoint only after shared execution model changes are merged.

## Acceptance Criteria

- Every execution path that sends prompt text to codeagent goes through one assembler contract.
- Template names live in config, not hardcoded in consumer services.
- Variable sources are declared and inspectable.
- Dry run can show recipe key, template source, each variable source, final rendered prompt, and task text.
- Missing variables and unused variables fail fast with actionable errors.
- Governance and assignee dispatch share the same assembly mechanism.
- Run / plan / review no longer each maintain their own implicit prompt composition contract.

## Risks

- Over-generalizing too early could create a second abstraction that only wraps existing builders without removing duplication.
- Provider registry can become a service locator if provider boundaries are not kept narrow and typed.
- Async execution and dry-run logging may diverge if prompt provenance is not propagated through one model.
- Orchestra and command migrations may conflict on config shape if recipe schema is not frozen in Chunk 1.

## Verification Matrix

- Core assembler:
  - `uv run pytest tests/vibe3/prompts -q`
- Orchestra migration:
  - `uv run pytest tests/vibe3/orchestra/test_governance_service.py tests/vibe3/orchestra/test_dispatcher.py tests/vibe3/orchestra/test_assignee_dispatch.py -q`
- Command migration:
  - `uv run pytest tests/vibe3/commands/test_run.py tests/vibe3/commands/test_plan.py tests/vibe3/commands/test_review.py -q`
- Static checks:
  - `uv run ruff check src/vibe3 tests/vibe3`
  - `uv run black --check src/vibe3 tests/vibe3`
