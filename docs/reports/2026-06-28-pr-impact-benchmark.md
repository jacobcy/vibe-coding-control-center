# PR Impact Analysis Benchmark Report

Date: 2026-06-28
Issue: #3219
Decision: `interface_only`

Artifact status: the failed AST/Hybrid implementation, scorer, and gold set were
discarded after the decision. This report is retained as architecture evidence;
its aggregate measurements and confidence limits are the durable output.

## Executive decision

Neither deterministic AST-only nor AST plus Serena 1.1.1 passes the fixed
reliability gate. `inspect base` may retain the Git-backed change-set interface,
but runtime impact output must remain `disabled` with reason
`benchmark_gate_failed`. No result from this experiment should feed review
prompts, PR bodies, risk scores, CI gates, or automatic test selection.

Serena 1.1.1 is worth retaining behind a research/provider interface. The
correct `find_symbol` then `find_referencing_symbols` path returns real
definition and reference locations and materially improves recall. It is not a
complete PR observation surface: it does not identify configuration/dynamic
unknowns, cannot by itself define impact semantics, and pushed cold p95 above
the gate.

## Research setup

- Corpus: 20 merged PRs with frozen requested-base and head object IDs.
- Diff truth: `merge-base(requested_base_sha, head_sha)..head_sha`.
- Source truth: Git objects read through a single `git archive` per revision;
  no checkout or persisted snapshot.
- Runtime/test separation: changed tests are not runtime impact seeds.
- Serena: isolated `uvx --from serena-agent==1.1.1` worker; each historical head
  is extracted into a temporary directory. The worker does not modify the
  repository `.serena` configuration.
- Serena tools: `find_symbol(name_path_pattern, relative_path)` followed by
  `find_referencing_symbols(name_path, relative_path)`. `get_symbols_overview`
  is not used for locations.
- Timing: cold included Git reads, AST indexing, provider startup, and queries;
  warm reused the in-process revision index/provider result.

The original corpus annotations are intentionally not retained as a canonical
fixture because post-run adjudication found conflicting definitions of direct
impact. Reusing them would reproduce the measurement but not a reliable truth
set.

## Aggregate results

| Metric | Gate | AST-only | Hybrid (AST + Serena 1.1.1) |
| --- | ---: | ---: | ---: |
| Critical direct misses | 0 | 6 | 1 |
| Direct precision | >= 85% | 52.27% | 33.05% |
| Direct recall | >= 85% | 56.10% | 95.12% |
| Direct TP / FP / FN | observation | 23 / 21 / 18 | 39 / 79 / 2 |
| Transitive top-10 precision | >= 70% | 5.33% | 2.67% |
| Evidence coverage | 100% | 100% | 100% |
| Negative-control false positives | 0 | 0 | 0 |
| Silent dynamic unknown misses | 0 | 6 | 6 |
| Ready-case ratio | >= 80% | 50% | 50% |
| Cold p95 | <= 10s | 4.21s | 12.71s |
| Warm p95 | <= 3s | < 0.01s | < 0.01s |

AST-only fails six gates. Hybrid improves direct recall by 39.02 percentage
points and reduces critical misses from six to one, but it still fails six
gates. The required Hybrid acceptance condition is therefore not met.

Git-only and the old pipeline are recorded as `disabled` comparison surfaces.
They return no impact arrays, miss all 41 labeled direct impacts and all six
dynamic unknowns, and have a ready ratio of zero. Their nominal empty-set
precision is not a success metric.

## What Serena 1.1.1 proved

The upgraded provider has a real, bounded capability:

- PR #3213: six queried symbols, two accepted cross-module edges, 6.78s cold;
  it located `vibe3.orchestra.remote_check` as a caller of
  `collect_label_anomalies` with an exact source line.
- PR #3117: it recovered both reviewed callers of `echo_dry_run_header`.
- PR #3042: it recovered the `GitHubClient` inheritance/mixin dependency.
- PR #3095: it crossed lazy re-export boundaries and found final callers that a
  module import graph sees only as transitive.
- PR #3076: 29 queried symbols produced 119 reference edges in 10.88s cold;
  after module dedupe the candidate still returned 31 direct modules.

Provider-only elapsed time stayed below 10 seconds in this run (maximum 9.26s),
but end-to-end Hybrid cold p95 was 12.71s. More importantly, semantic references
increase candidate count without solving dynamic/configuration uncertainty.

## Annotation audit and confidence boundary

The benchmark exposed two gold-set defects after the labels were frozen:

- PR #3136 had three additional source-confirmed direct callers of
  `_extract_imports` that the first manual pass omitted.
- PR #3095 shows a semantic-definition conflict: the import graph classifies a
  caller behind a lazy re-export as transitive, while Serena supplies a direct
  symbol-reference edge.

For traceability, the preregistered labels and scores were not rewritten after
seeing candidate output. Therefore the exact Hybrid precision value must be
treated as conservative, not as a publication-quality estimate. This does not
change the no-go verdict: even if precision were ignored entirely, Hybrid still
fails critical-miss, transitive precision, dynamic-unknown, ready-ratio, and
cold-latency gates.

This audit also means a future experiment must define `direct` as either
import-hop distance or semantic caller distance before annotation, then use an
independent/blinded second reviewer. Mixing the two definitions invalidates
precision comparisons.

## Root causes

1. Module-scope ambiguity remains expensive. Restricting `<module>` changes to
   module imports removed hundreds of false positives, but assignment/export
   changes still need symbol-specific base/head semantics.
2. Static transitive reach is not a useful assertion surface. It mostly
   describes dependency possibility, not modules that need PR review.
3. Serena is a reference engine, not an impact policy. It can locate callers;
   it cannot decide whether a reference represents changed behavior.
4. Dependency injection, string-based error classification, runtime protocol
   wiring, and configuration-selected backends require explicit detectors or
   explicit unknowns. Neither AST import expansion nor Serena reports them.
5. Large shared changes return too many direct candidates for a stable prompt
   surface even when every item has a source location.

## Product boundary

The safe product contract is:

```yaml
runtime_impacts:
  status: disabled
  reason: benchmark_gate_failed
```

The Git change set, changed files, diff hunks, and separate changed-test list
remain available. Empty direct/transitive arrays must not be emitted while
impact analysis is disabled.

## Future research direction

A later experiment can reuse the interfaces and Serena worker, but should not
extend this graph:

1. Define semantic callers as direct; remove transitive module expansion from
   the user-facing contract.
2. Query both base and head for changed/deleted definitions.
3. Use AST only for hunk-to-symbol mapping, literal module imports, and explicit
   dynamic/config unknown detectors.
4. Use Serena only for located symbol references and inheritance.
5. Rebuild a blinded, independently adjudicated corpus with the direct
   definition fixed before candidate output.
6. Reapply the same absolute gates. Until all pass, keep the command as a
   design/research interface rather than an observation product.
