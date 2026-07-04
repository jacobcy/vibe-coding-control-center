# Feature Specification: Client Layer Baseline

**Feature Branch**: `dev/issue-3299`
**Created**: 2026-07-03
**Corrected**: 2026-07-04
**Status**: Baseline / Reverse Specification

## Purpose and truth sources

`src/vibe3/clients/` contains concrete adapters for Git, GitHub, SQLite, AI/model services, and Serena, plus caches, runtime-asset helpers, sync rules, and narrow Protocol definitions. It is a mixed infrastructure package, not a guarantee that every class has identical construction or lifecycle semantics.

## User Scenarios & Testing

### Scenario 1 - Concrete adapter use

Callers use `GitClient`, `GitHubClient`, `SQLiteClient`, `AIClient`, and `SerenaClient` for external I/O. Constructors differ: some have defaults, while caches such as `MergedPRCache` and `RecentPRCache` require a repository path. The baseline MUST NOT claim all clients are zero-argument constructible.

### Scenario 2 - Narrow ports

`clients/protocols/` defines narrow structural interfaces for selected consumers. These protocols are useful typing boundaries but do not mean every concrete client implements one universal client interface.

### Scenario 3 - Lazy public barrel

`clients.__init__` uses a lazy name-to-module map to reduce import cycles. Most names resolve inside the client layer, but the current barrel also lazily re-exports label helpers from `services.shared`; this is a real upward dependency and contradicts a strict “clients never depend on services” architecture claim.

### Scenario 4 - Repository-local caches and runtime assets

PR caches are repository-scoped and require root context. Runtime-asset helpers resolve bundled/project material locations. Their failure and fallback behavior is specific to each helper and is not interchangeable with external API clients.

## Requirements

- **FR-001**: concrete adapter constructors MUST be documented individually; no global no-argument constructor invariant exists.
- **FR-002**: SQLite path resolution MUST use the repository-aware helpers where a repo path is available.
- **FR-003**: Protocols MUST stay narrow and consumer-driven; they MUST NOT be presented as a complete substitute for concrete client APIs.
- **FR-004**: the public barrel MUST resolve every name listed in `__all__` and MUST preserve lazy imports required to avoid cycles.
- **FR-005**: current service-layer re-exports from the clients barrel MUST be recorded as an architecture gap, not normalized as the desired dependency direction.
- **FR-006**: repository caches MUST retain repository identity/path input and MUST NOT be documented as process-global clients.
- **FR-007**: transient Git error helpers only identify retry-safe message patterns; they do not classify Git failures into the full exception taxonomy.

## Key implementation PRs

| PR | Contribution |
|---|---|
| [#3265](https://github.com/jacobcy/vibe-coding-control-center/pull/3265) | Removed dead client/adapter/environment code and unused exports. |
| [#3256](https://github.com/jacobcy/vibe-coding-control-center/pull/3256) | Unified duplicated GitHub label I/O and state-priority handling. |
| [#2481](https://github.com/jacobcy/vibe-coding-control-center/pull/2481) | Broke the config-to-clients dependency cycle. |
| [#3247](https://github.com/jacobcy/vibe-coding-control-center/pull/3247) | Extended SQLite/client primitives used by blocked dependency reconciliation. |

## Known gaps and tracking

| Gap | Coverage |
|---|---|
| Broken/dead protocol-package re-exports and misleading protocol documentation. | [#3035](https://github.com/jacobcy/vibe-coding-control-center/issues/3035) covers this bounded protocol cleanup. |
| `clients.__init__` resolves multiple public names from `vibe3.services.shared`, reversing the intended lower-layer dependency direction. | [#3304](https://github.com/jacobcy/vibe-coding-control-center/issues/3304) |

## Success Criteria

- Constructor and cache requirements match concrete code.
- Protocol claims remain narrow and structural.
- The clients-to-services barrel dependency is visible and tracked rather than hidden by lazy loading.

## Non-goals

- Performing the barrel refactor in this archive pass.
- Designing one universal client interface.
- Replacing concrete adapters with protocols everywhere.
