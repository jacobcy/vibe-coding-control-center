# Feature Specification: Analysis Intelligence Baseline

**Feature Branch**: `dev/issue-3299`
**Created**: 2026-07-03
**Corrected**: 2026-07-04
**Status**: Baseline / Reverse Specification

## Purpose and truth sources

The analysis package exposes direct, validated evidence: changed-file scope, diff summaries, Python syntax facts, symbol-reference evidence, local review observations, coverage helpers, and deterministic Review Kernel classification. It does not promise whole-program semantic inference.

## User Scenarios & Testing

### Scenario 1 - Exact git/file evidence

Change-scope and diff-summary helpers report repository-relative paths and A/M/D classifications from git evidence. Pre-push selectors and local review reports derive bounded test/review inputs from those facts.

### Scenario 2 - Python and symbol inspection

`inspect_python_file()` returns syntax-derived file evidence. Symbol inspection reports provider results and completeness metadata; an empty or incomplete provider result is not proof that no references exist.

### Scenario 3 - Review Kernel classification

`config/v3/review-kernel.yaml` entries are exact existing files. Globs, directories, absolute paths, duplicate entries, and missing files are rejected. The classifier combines exact hits with architecture-package membership to return an observation and minimum review depth.

### Scenario 4 - Public evidence API

`src/vibe3/analysis/__init__.py` lazily exports the supported evidence types/functions. Internal command analysis, selectors, or helpers not listed in `__all__` are not promised as package-level APIs.

## Requirements

- **FR-001**: changed-path evidence MUST remain repository-relative and based on actual git state.
- **FR-002**: A/M/D classification MUST preserve deletion as a first-class change type.
- **FR-003**: symbol evidence MUST expose incompleteness/availability rather than upgrading a provider miss into a global “unused” conclusion.
- **FR-004**: Review Kernel manifest entries MUST be exact existing files and MUST reject glob syntax.
- **FR-005**: architecture-package changes missing from the manifest MUST produce an unavailable observation/diagnostic and repeated review floor.
- **FR-006**: a Review Kernel `review_floor` is classifier output consumed by review guidance; this baseline does not claim an independent runtime gate enforces it automatically.
- **FR-007**: the public analysis barrel MUST contain only the direct validated-evidence APIs explicitly listed in `__all__`.
- **FR-008**: retired snapshot/baseline/risk-scoring capabilities MUST NOT be described as current analysis behavior.

## Key implementation PRs

| PR | Contribution |
|---|---|
| [#3235](https://github.com/jacobcy/vibe-coding-control-center/pull/3235) | Retired unsupported inspect promises and retained evidence-only interfaces. |
| [#3231](https://github.com/jacobcy/vibe-coding-control-center/pull/3231) | Retired the snapshot subsystem and its stale analysis surface. |
| [#3031](https://github.com/jacobcy/vibe-coding-control-center/pull/3031) | Added A/M/D file classification to structure-change evidence. |
| [#3019](https://github.com/jacobcy/vibe-coding-control-center/pull/3019) | Pushed code-path filtering into exact git pathspec handling. |

## Known gaps and tracking

Review adoption and value of the bounded files/symbols evidence surface is intentionally measured through [#3236](https://github.com/jacobcy/vibe-coding-control-center/issues/3236). That RFC is not an unimplemented baseline requirement.

## Success Criteria

- Review Kernel paths are described as exact, never as globs.
- Incomplete symbol results retain their uncertainty.
- Retired snapshot functionality is absent from the baseline.

## Non-goals

- Whole-program impact inference.
- Reintroducing snapshots or risk scoring.
- Automating review decisions from analysis observations.
