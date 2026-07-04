# Data Model: Low-Code ADR Recall

## ADR metadata

```yaml
decides: "<decision object + binding constraint, one concise sentence>"
scope:
  - "<repository-relative path or glob>"
```

`status` remains authoritative for lifecycle. Only `accepted` ADR files constrain plans. `proposed` is optional context; `superseded` remains historical.

## Recall inputs

| Field | Plan stage | Review stage |
|---|---|---|
| baseline | current branch + commit | reviewed head + merge base |
| semantic input | issue + spec + plan summary | plan + PR purpose |
| paths | planned repository-relative paths | actual merge-base diff paths |
| ADR snapshot | accepted files at planning baseline | accepted files at review baseline |

## ADR Consideration

| Field | Meaning |
|---|---|
| `baseline` | branch/commit and stage |
| `accepted_snapshot` | accepted ADR IDs discovered from files |
| `paths` | planned or actual paths, explicitly tagged |
| `candidates` | ADR ID plus semantic/scope/metadata trigger |
| `applicable` | binding constraints and compliance evidence |
| `dismissed_candidates` | candidate ID and concrete non-applicability reason |
| `metadata_flags` | missing/weak decides, invalid/stale scope, lifecycle/index mismatch |
| `adr_change_proposals` | RFC/ADR proposal and carry/replace/retire scope dispositions |
| `review_reconciliation` | actual-diff changes to the plan-stage assessment |

## Invariants

- `applicable` and `dismissed_candidates` are subsets of `candidates`.
- Every candidate is resolved or explicitly left as an open conflict.
- A zero-candidate result has scan evidence and metadata flags but no fabricated exhaustive dismissal list.
- Review reconciliation preserves the plan-stage record and appends actual-diff evidence.
