# Inspect Evidence Surface Design

**Date:** 2026-06-28
**Issue:** #3218
**Status:** Implemented; pending branch publication

## 1. Context

`vibe3 inspect` 当前把几类语义不同的数据混在一起：Git 改动事实、AST
结构、Serena 引用候选、DAG 反向扩散和任意权重的风险评分。#3219 的冻结
benchmark 已证明 AST-only 与 AST + Serena 都没有通过 PR impact 产品门槛；继续输出
`impacted_modules`、risk score 或 dead-code 结论会制造伪精确观察面。

本设计把 `inspect` 收缩为三个 evidence-only 接口：

- `inspect base`：Git-backed PR/review 观察窗口；
- `inspect files`：单个 Python 文件的 AST 事实；
- `inspect symbols`：显式 symbol 的正向引用候选。

Snapshot 退役由 #3215 负责。本设计不重新引入 baseline、持久化 index 或第二套
Git 真源。

## 2. Goals

1. 每个返回字段都能回指 Git object、当前文件内容或有效 source range。
2. 用确定性的 Kernel 命中帮助 reviewer 决定最低 review 深度。
3. 明确区分 `none`、`unknown`、`partial`、`disabled` 和 `error`。
4. CLI、PR show/create 和 review prompt 共用一个 observation model。
5. 删除无法兑现的命令、推断实现和下游消费，而不是只改文案。
6. 交付一个可用真实 fixture 与真实 CLI 初步验证的版本。

## 3. Non-goals

- 不预测运行时实际影响模块。
- 不输出 direct/transitive impact arrays。
- 不输出 numeric risk score 或 LOW/MEDIUM/HIGH/CRITICAL。
- 不判断 dead code。
- 不生成调用树。
- 不自动阻断 merge 或自动选择“受影响测试”。
- 不新增 `inspect pr`、`inspect commit` 或平行命令。
- 不实现 snapshot v2、daemon、数据库或后台索引。

## 4. Architecture

共享数据流固定为：

```text
Git exact facts ----------------------> ReviewObservationService
                                               |
Review Kernel manifest -> classifier ----------+
                                               |
                                               +-> JSON renderer
                                               +-> human renderer
                                               +-> PR/review consumers

Python file content -> PythonFileInspector ----> inspect files

file:symbol -> SymbolReferenceProviderAdapter -> inspect symbols
```

组件责任：

| Component | Responsibility | Must not do |
| --- | --- | --- |
| `ReviewObservationService` | 组装 Git facts、Kernel 命中和 review policy | 调用 DAG、Serena、snapshot 或评分器 |
| `ReviewKernelClassifier` | 对规范化路径做精确 manifest 分类 | 根据 import graph 扩散 |
| `PythonFileInspector` | 解析单个 Python 文件的 AST | 扫目录、解析 Shell、构建 reverse graph |
| `SymbolReferenceProviderAdapter` | 规范化 definition/reference positive evidence | 推导 impact、dead code 或完备性 |
| CLI renderers | 从同一个 model 生成 JSON/YAML/human output | 重新分析或补猜字段 |

公共 schema 使用独立 Pydantic model，不暴露 Serena 或 Git client 私有对象。

## 5. `inspect base` Contract

### 5.1 Comparison truth

Committed range 固定为：

```text
merge-base(resolved_base, HEAD)..HEAD
```

输出必须记录：

- current branch；
- HEAD SHA；
- 用户输入的 requested base；
- resolved base；
- exact merge-base SHA。

Working tree 分为：

- `staged`：index vs HEAD；
- `unstaged`：working tree vs index；
- `untracked`：Git status 中未跟踪路径。

同一路径可同时出现在 staged 与 unstaged；不得为了“去重”丢失状态。summary 同时提供
各分区计数和 union path count。

### 5.2 Changed file facts

每个 tracked change 包含：

```yaml
path: src/vibe3/runtime/heartbeat.py
old_path: null
status: M
additions: 12
deletions: 4
binary: false
```

规则：

- status 只允许 `A/M/D/R`；
- rename 必须同时提供 `old_path` 与 `path`；
- binary 文件的 additions/deletions 为 `null`；
- untracked 文件不伪造 Git numstat，additions/deletions 为 `null`；
- 路径统一为 repo-relative POSIX path；
- 文件不存在不等于分析失败，deleted entry 仍然是有效事实。

### 5.3 Result schema

```yaml
schema_version: 1
status: ready
comparison:
  current_branch: task/issue-3218
  head_sha: abc123
  requested_base: main
  resolved_base: origin/main
  merge_base_sha: def456
changes:
  committed: []
  staged: []
  unstaged: []
  untracked: []
  summary:
    committed: {files: 0, additions: 0, deletions: 0}
    staged: {files: 0, additions: 0, deletions: 0}
    unstaged: {files: 0, additions: 0, deletions: 0}
    untracked: {files: 0}
    unique_paths: 0
kernel:
  status: ready
  impact: none
  architecture_hits: []
  review_hits: []
review:
  minimum_depth: normal
  reasons: []
impact_analysis:
  status: disabled
  reason: benchmark_gate_failed
diagnostics: []
```

Top-level status：

- `ready`：Git facts 与 Kernel classification 都成功；
- `partial`：Git facts 成功，但可选分类能力不可用；
- `error`：无法解析 Git repository、base、HEAD 或 merge-base。

Git facts 失败时不得返回看似成功的空 changes。

## 6. Kernel Model

### 6.1 Architecture Kernel

`src/vibe3/runtime/taxonomy.py` 继续是 Architecture Kernel 顶层分类真源：

- `runtime`
- `orchestra`

命中这两个 package 下的 Python 文件意味着 `kernel.impact: large`。Infrastructure、
services、roles、agents 和 commands 不因为“重要”而自动成为 Architecture Kernel。

### 6.2 Review Kernel manifest

`config/v3/review_kernel.yaml` 是文件级 Review Kernel 真源。每个 entry 必须包含：

```yaml
- path: src/vibe3/runtime/heartbeat.py
  responsibilities: [heartbeat_timer, event_ingestion]
  reason: Drives reconciliation and event ingestion
  review_floor: repeated
```

约束：

- 只允许精确文件路径；禁止目录、glob 和 substring pattern；
- path 必须存在于仓库；
- path 不得重复；
- responsibilities、reason、review_floor 不得为空；
- review_floor 只允许 `normal/focused/repeated`；
- 所有 `runtime/`、`orchestra/` 非 `__init__.py` 文件必须出现在 manifest；
- Architecture Kernel entries 的 review_floor 固定为 `repeated`；
- 新增 Architecture Kernel 文件但未登记时，modularity test 必须失败；
- manifest 缺失或不合法时输出 `kernel.status: unavailable`，不能输出 `impact: none`。

### 6.3 Initial Architecture entries

现有 `CORE_RESPONSIBILITIES` 从测试迁移到 manifest，并保持以下映射：

| Responsibility | Modules |
| --- | --- |
| process_lifecycle | `runtime.orchestra_instance` |
| heartbeat_timer | `runtime.heartbeat`, `runtime.periodic_check_executor`, `runtime.pool_exhaustion` |
| event_ingestion | `runtime.heartbeat` |
| job_queue_lifecycle | `orchestra.queue_operations`, `orchestra.queue_entry`, `orchestra.queue_persistence_service` |
| concurrency_circuit_breaker | `runtime.circuit_breaker` |
| status_metadata | `orchestra.logging` |
| dispatch_coordination | `orchestra.global_dispatch_coordinator`, `orchestra.dispatch_coordinator_factory`, `orchestra.flow_dispatch`, `orchestra.failed_gate`, `orchestra.issue_loader`, `orchestra.remote_check` |
| protocols | `orchestra.protocols`, `runtime.protocols` |
| domain_types | `orchestra.domain_types` |
| cleanup | `runtime.cleanup_executor` |
| taxonomy | `runtime.taxonomy` |

重复 responsibility 覆盖同一文件时，manifest 只保留一个文件 entry，并将 responsibilities
表示为非空列表。例如 `runtime.heartbeat` 同时标记 `heartbeat_timer` 与
`event_ingestion`。公共 hit model 因此使用 `responsibilities: list[str]`。

### 6.4 Initial non-architecture Review Kernel entries

首版只加入以下经过现有结构文档或状态真源标准确认的文件，不迁移旧
`critical_paths` 宽目录：

| Path | Responsibility | Reason | Review floor |
| --- | --- | --- | --- |
| `src/vibe3/cli.py` | CLI command composition | Changes alter the public command surface and startup imports | focused |
| `src/vibe3/config/loader.py` | layered runtime configuration resolution | Changes alter which repository, global, and environment values win | focused |
| `src/vibe3/config/settings.py` | root configuration schema | Changes alter validation and defaults consumed across commands | focused |
| `src/vibe3/models/flow.py` | canonical flow status model | Changes alter persisted and rendered flow-state semantics | repeated |
| `src/vibe3/clients/sqlite_base.py` | shared-store connection and migration guard | Changes affect every shared-state reader and writer | repeated |
| `src/vibe3/clients/sqlite_schema.py` | shared-store canonical schema | Changes alter durable state layout and migrations | repeated |
| `src/vibe3/clients/sqlite_flow_state_repo.py` | flow state and issue-link persistence | Changes alter canonical flow and issue-link reads or writes | repeated |
| `src/vibe3/services/flow/service.py` | public flow lifecycle facade | Changes affect the service entry used across commands and roles | focused |
| `src/vibe3/services/flow/status.py` | terminal flow status transitions | Changes can break terminal-state closure across consumers | repeated |
| `src/vibe3/services/flow/transition.py` | flow state transition rules | Changes alter allowed lifecycle transitions and reactivation | repeated |
| `src/vibe3/services/flow/write_mixin.py` | flow state mutation path | Changes alter the shared write contract for flow metadata | repeated |
| `src/vibe3/services/shared/status_query.py` | cross-command flow/task status projection | Changes alter status shown by multiple public observation commands | repeated |
| `src/vibe3/services/handoff/service.py` | responsibility-chain write contract | Changes alter canonical plan/run/review handoff records | focused |

扩展 manifest 必须由独立 PR 提供责任说明与正向收益，不能为某次 PR 临时扩张。

### 6.5 Classification and review policy

对 committed、staged、unstaged、untracked 的 union paths 分类，并在每个 hit 中记录
`sources`。

- `large`：至少一个 Architecture Kernel 文件命中；
- `small`：命中 Review Kernel，但没有 Architecture Kernel 命中；
- `none`：没有 Review Kernel 命中。

新增或未登记的 `runtime/`、`orchestra/` 路径仍按 taxonomy 判定为 `large`，同时返回
`kernel.status: unavailable` 与 `missing_manifest_entry` diagnostic；不得因为 manifest
缺项降级为 small/none。

Review policy：

- `none -> normal`；
- `small -> focused`；
- `large -> repeated`；
- matched entry 的 review_floor 可以提高 minimum depth；
- public API trigger 可以提高 minimum depth，但不能改变 kernel impact。首版复用
  `review_scope.public_api_paths`，但匹配必须使用规范化后的 exact-file 或 directory-prefix
  语义，禁止当前 substring 匹配。

该 policy 是 repo-owned review rule，不是运行时 impact 预测。

## 7. `inspect files` Contract

### 7.1 Input

- 必须提供一个 repo 内或可解析到 repo 内的真实 `.py` 文件；
- 空参数、目录、Shell 和其他语言返回 `unsupported`；
- 不允许默认全仓扫描。

### 7.2 Output

```yaml
schema_version: 1
status: ready
file:
  path: src/vibe3/runtime/heartbeat.py
  language: python
  content_sha256: abc123
metrics:
  total_lines: 240
declarations:
  - kind: method
    name: on_tick
    qualified_name: Heartbeat.on_tick
    range:
      start_line: 80
      end_line: 121
imports:
  - kind: from
    module: vibe3.runtime.protocols
    names: [TickHandler]
    aliases: {}
    range:
      start_line: 12
      end_line: 12
diagnostics: []
```

声明 kind 只允许 `class/function/async_function/method/async_method/nested_function`。
range 为 1-based inclusive，并来自 Python AST `lineno/end_lineno`。

Imports 只描述直接语法：

- `import x [as y]`；
- `from x import y [as z]`；
- relative import 保留 level 和源码 module，不猜 canonical target；
- 不输出 `imported_by`、dependency 或 impact。

### 7.3 Errors

- 文件不存在：`status: error`, diagnostic `file_not_found`；
- syntax error：`status: error`, diagnostic 包含有效 source range；
- 编码错误：`status: error`, diagnostic `decode_error`；
- unsupported input：`status: unsupported`。

JSON/YAML 始终输出合法 schema；`error` 与 `unsupported` 返回非零退出码。Human
renderer 只读取同一 model。

## 8. `inspect symbols` Contract

### 8.1 Input

只支持：

```text
inspect symbols <file>:<symbol>
```

删除 file-only mode。文件 declarations 由 `inspect files` 提供。

### 8.2 Provider protocol

Provider adapter 必须按顺序：

1. 在指定文件中解析唯一 definition identity；
2. 用 definition identity 查询 references；
3. 将 provider range 规范化为 1-based inclusive；
4. 验证 path 存在、range 正数且不超出文件行数；
5. 仅把验证通过的记录放入 definitions/references。

首版使用 Serena 1.1.1 adapter 的 `find_symbol` +
`find_referencing_symbols`。公共 contract 不依赖 Serena 私有对象。

### 8.3 Output

```yaml
schema_version: 1
status: ready
query:
  file: src/vibe3/commands/inspect_base.py
  symbol: register
  content_sha256: abc123
definition:
  path: src/vibe3/commands/inspect_base.py
  range:
    start_line: 21
    end_line: 204
references:
  - path: src/vibe3/commands/inspect.py
    range:
      start_line: 16
      end_line: 16
    context: from ... import register as register_base
observation:
  observed_reference_count: 1
  complete: false
  scope: static_provider
provenance:
  provider: serena
  version: 1.1.1
unknowns: []
```

状态语义：

- `ready`：definition 与所有返回 references 都有有效 range；
- `partial`：存在有效 evidence，但部分 provider records 无效或超时；
- `not_found`：指定文件内不存在该 symbol；
- `disabled`：provider 不可用、整体超时或 contract smoke 未通过；
- `error`：输入或本地文件无法读取。

无论 status 为何，`complete` 都不得为 `true`，因为静态 provider 不覆盖动态注册和
配置路由。零 references 只表示 `observed_reference_count: 0`。

## 9. Removed Surface

删除公共命令：

- `inspect uncommit`；
- `inspect dead-code`；
- `inspect commands`。

删除实现：

- inspect DAG reverse expansion 与 `ImpactGraph` 输出；
- command analyzer 与 call-tree model/renderers；
- 自研 dead-code rules、scan 和 report models；
- inspect/PR pipeline 中基于 impacted modules 的 scoring；
- 只服务上述能力的 adapters、helpers、re-exports 和 tests。

若 `dag_service` 最终只剩直接 import extraction，则把该能力移动到命名准确的 Python
AST parser 后删除 DAG abstraction。

## 10. Downstream Migration

- `pr_quality_gates`：删除 risk gate；
- `pr show`：只展示 Git change facts、Kernel impact 和 review minimum depth；
- `pr create` AI context：只提供 changed files、numstat 和 Kernel evidence；
- review request/prompt：消费 ReviewObservation，不消费 DAG/risk/snapshot；
- pre-push selector：删除 `_find_tests_via_dag`，保留直接文件映射、目录 fallback 与
  CI 全量兜底；
- docs/skills/policies：删除已退役字段、命令和不存在的 `inspect pr/commit`。

旧 JSON schema 是非版本化且不可靠的，不提供 silent compatibility adapter。Breaking
change 通过 `schema_version: 1` 与 release note 明示。

## 11. Initial Verification Gate

### 11.1 `inspect base`

- fixture Git repo 固定 base/head/merge-base；
- committed output 与原生 `git diff --name-status`、`git diff --numstat` 一致；
- staged、unstaged、untracked 分区分别验证；
- rename、delete、binary 验证；
- Review Kernel none/small/large 与 review floor 验证；
- manifest missing/invalid 返回 partial/unavailable；
- 真实 CLI JSON 与 human smoke。

### 11.2 `inspect files`

- class、async method、nested function 与多种 imports fixture；
- range 与 Python AST 一致；
- content SHA 与读取 bytes 一致；
- syntax error、decode error、directory 和 unsupported extension；
- 真实 CLI smoke。

### 11.3 `inspect symbols`

- 有静态引用；
- symbol 存在但 observed references 为零；
- symbol not found；
- provider invalid range；
- provider partial、timeout、unavailable；
- Serena 1.1.1 真实 contract smoke。

若真实 Serena smoke 未通过，`inspect symbols` 以 `disabled` 状态交付；不能降低 range
要求或回退到 grep。

### 11.4 Removal and downstream checks

- `inspect --help` 只显示 `base/files/symbols`；
- repo search 不再存在 removed command registrations；
- PR/review/pre-push 定向 tests 证明旧 risk/DAG 数据没有消费者；
- 真实 `pr show` 或其 command-level fixture 不显示 risk/impacted modules；
- 记录删除的 production/test/doc LOC，证明复杂度下降。

## 12. Delivery Order

1. 建立 versioned models、Review Kernel manifest 与 classifier。
2. TDD 重建 `inspect base` 并迁移 PR/review consumers。
3. TDD 收缩 `inspect files`。
4. TDD 收缩 `inspect symbols`，运行真实 provider gate。
5. 删除旧 commands、DAG/risk/dead-code/call-tree 实现及下游。
6. 清理 docs/skills/policies，运行定向回归与真实 CLI smoke。

每一步必须先有失败测试，再做最小实现；不得先保留旧 pipeline 再用 feature flag 隐藏。
