# Vibe Doctor Basic Shell Check Plan

> **For agentic workers:** REQUIRED: Use superpowers:test-driven-development and superpowers:verification-before-completion during implementation. Steps use checkbox syntax for tracking.

**Goal:** 扩展 `vibe doctor`，在保持轻量的前提下，检查关键命令在当前环境以及 login `bash` / `zsh` 中是否可用；只输出最小诊断和最小修复建议，不自动修改配置。

**Architecture:** 保持 V2 shell 层实现，以 `lib/doctor.sh` 为唯一入口。当前 shell 的工具检查与 shell-specific login probe 分开报告，避免把 PATH diff、项目依赖扫描和自动修复混入 doctor。

**Tech Stack:** Zsh, Bash, existing `bin/vibe`, `lib/utils.sh`, Bats

---

## Scope

### In scope

- 当前环境检查：`vibe`, `vibe3`, `uv`, `rg`
- 信息级附加检查：`gh`, `gemini`, `codeagent-wrapper`
- 显示命令绝对路径；核心命令继续显示版本/可用性
- login `bash` / login `zsh` command availability 检查
- 缺失时输出最小 hint

### Out of scope

- 自动修复 shell dotfiles
- 全量 PATH diff
- 环境变量全文输出
- 全项目依赖审计或自动执行 `uv sync`
- 对 `nvm/rbenv/sdkman` 等环境管理器做专门适配

## Chunk 1: Refine Current-Shell Tool Output

### Task 1: Add core tool/path reporting

**Files:**
- Modify: `lib/doctor.sh`
- Optional Modify: `lib/utils.sh`
- Test: `tests/vibe2/contracts/test_vibe_doctor_contract.bats` (new) or extend `tests/vibe2/contracts/test_vibe_contract.bats`

- [ ] Add a dedicated core tool table for `vibe`, `vibe3`, `uv`, `rg`
- [ ] Show absolute path for each detected tool; keep version when cheap and stable
- [ ] Keep optional tools (`gh`, `gemini`, `codeagent-wrapper`) as warn/info only
- [ ] Preserve existing help/summary shape unless a minimal wording update is required

**Acceptance:**
- `vibe doctor` clearly shows whether core commands are found in the current shell
- Output remains short and stable enough for contract tests

## Chunk 2: Add Login Shell Availability Probes

### Task 2: Check bash/zsh command resolution

**Files:**
- Modify: `lib/doctor.sh`
- Optional Modify: `lib/utils.sh`
- Test: `tests/vibe2/contracts/test_vibe_doctor_contract.bats`

- [ ] Implement a small helper that runs login shell probes via absolute shell paths when available
- [ ] Probe `command -v` for `vibe`, `vibe3`, `uv`, `rg`
- [ ] Report results under a dedicated `Shell command availability` section
- [ ] Only print hints when at least one core command is missing in one shell

**Implementation notes:**
- Prefer `/opt/homebrew/bin/bash` or `bash`, and `/bin/zsh` or `zsh`
- Avoid full PATH diff; only compare command resolution results
- Keep output to one or two actionable hint lines per failing shell
- Hints:
  - bash missing -> check `~/.bash_profile` / `~/.profile`
  - zsh missing -> check `~/.zprofile` / `~/.zshrc`
  - both missing -> check install location and whether `~/.vibe/bin` / Homebrew bin is on PATH

**Acceptance:**
- If bash misses `rg` but zsh has it, doctor reports that exact mismatch
- If both shells resolve all core commands, doctor prints a compact aligned message or stays quiet

## Chunk 3: Lock Behavior with Focused Bats Coverage

### Task 3: Add contract tests for doctor output

**Files:**
- Create: `tests/vibe2/contracts/test_vibe_doctor_contract.bats` or extend existing contract file

- [ ] Add a help smoke test for `vibe doctor --help`
- [ ] Add a current-shell output test asserting the core tool section/header exists
- [ ] Add a shell availability output test using temporary HOME, fixture dotfiles, or controlled PATH to verify mismatch messaging
- [ ] Keep tests deterministic; do not depend on the developer machine having every optional tool installed

**Test strategy:**
- Prefer fixture-controlled PATH and temporary dotfiles over asserting the real host PATH
- Scope tests to contract-level strings, not full formatted output snapshots

## Verification

- [ ] Run: `bats tests/vibe2/contracts/test_vibe_doctor_contract.bats`
- [ ] Run: `bats tests/vibe2/contracts/test_vibe_contract.bats`
- [ ] Manual smoke: `bin/vibe doctor`
- [ ] Manual smoke: `bin/vibe doctor --help`

## Rollout Notes

- Keep this as a single-file behavior enhancement plus focused tests; do not widen into environment repair
- Do not claim shells are fully consistent; only report command availability
- If optional tools create noisy failures, downgrade them to informational status instead of blocking the summary

