---
document_type: usage-guide
title: CI Simulation Mode 使用指南
status: active
author: Claude Sonnet 4.5
created: 2026-05-16
last_updated: 2026-05-16
related_docs:
  - docs/standards/quality-control-standard.md
  - scripts/hooks/pre-push.sh
  - tests/vibe3/integration/test_ci_parity.py
purpose: 帮助用户理解何时以及如何使用 VIBE_CI_SIMULATE、VIBE_CI_PARITY 和 GITHUB_ACTIONS 环境变量
---

# CI Simulation Mode 使用指南

> **背景**: PR #805 添加了 CI 模拟模式，帮助开发者在本地发现 CI 环境特有的问题。
>
> **适用场景**: 涉及 subprocess、git 操作、环境变量依赖的测试

---

## 一、VIBE_CI_SIMULATE=1 — 完整 CI 环境模拟

**功能**: 在整个 pre-push hook 中模拟完整的 CI 环境

**实现**: 自动设置以下环境变量
- `GITHUB_ACTIONS=true`
- `CI=true`

**使用时机**:
- 推送前验证改动在 CI 环境下的行为
- 修改了 subprocess 密集型代码
- 修改了 git 操作逻辑
- 修改了环境敏感的逻辑

**使用方式**:
```bash
VIBE_CI_SIMULATE=1 bash scripts/hooks/pre-push.sh
```

**特点**:
- ✅ 覆盖整个 pre-push 流程（compile、type check、test、LOC checks）
- ✅ 提供与 CI 完全一致的环境变量
- ✅ 适合端到端验证

**示例场景**:
```bash
# 修改了 subprocess 调用逻辑后，验证 CI 环境下行为一致
VIBE_CI_SIMULATE=1 bash scripts/hooks/pre-push.sh

# 修改了 git 操作代码后，验证 CI bare repository 场景
VIBE_CI_SIMULATE=1 bash scripts/hooks/pre-push.sh
```

---

## 二、VIBE_CI_PARITY=1 — 双重测试验证

**功能**: 在正常测试通过后，使用 CI 环境变量重新运行测试

**实现**:
1. 正常模式运行测试
2. 设置 `GITHUB_ACTIONS=true` 重新运行相同测试
3. 对比两次结果，发出警告（不阻断）

**使用时机**:
- 作为轻量级的 CI 一致性检查
- 怀疑测试依赖本地环境时
- 需要提前发现 CI-only 失败

**使用方式**:
```bash
VIBE_CI_PARITY=1 bash scripts/hooks/pre-push.sh
```

**特点**:
- ✅ 非阻断性：仅发出警告，不阻止推送
- ✅ 轻量级：仅在测试阶段额外运行一次
- ✅ 自动检测：捕获本地通过但 CI 失败的问题

**示例场景**:
```bash
# 作为日常推送前的 CI 一致性检查
VIBE_CI_PARITY=1 bash scripts/hooks/pre-push.sh

# 发现测试可能依赖环境变量时
VIBE_CI_PARITY=1 bash scripts/hooks/pre-push.sh
```

**输出示例**:
```
  -> Running test suite (incremental): changed files in src/vibe3/services/
  [test output...]
  -> CI parity check (simulating CI environment)...
  [test output...]
  WARNING: Tests passed locally but failed in CI simulation
  This may indicate environment-dependent test behavior
```

---

## 三、GITHUB_ACTIONS=true — 直接环境变量

**功能**: 直接设置 CI 环境变量，用于 pytest 直接调用

**使用时机**:
- 直接运行特定测试文件
- 调试 CI-specific 测试失败
- 开发新的 CI 敏感测试

**使用方式**:
```bash
# 直接运行测试
GITHUB_ACTIONS=true uv run pytest tests/vibe3/services/test_git.py

# 运行整个测试套件
GITHUB_ACTIONS=true uv run pytest tests/vibe3
```

**特点**:
- ✅ 灵活：可以针对特定测试文件或目录
- ✅ 直接：不经过 pre-push hook 逻辑
- ✅ 适合开发调试

**示例场景**:
```bash
# 调试特定的 git 测试失败
GITHUB_ACTIONS=true uv run pytest tests/vibe3/services/test_git.py -v

# 验证新写的 subprocess 测试
GITHUB_ACTIONS=true uv run pytest tests/vibe3/services/test_subprocess.py
```

---

## 四、三种模式对比

| 模式 | 覆盖范围 | 阻断性 | 典型用途 |
|------|----------|--------|----------|
| `VIBE_CI_SIMULATE=1` | 整个 pre-push hook | ✅ 阻断 | 端到端 CI 环境验证 |
| `VIBE_CI_PARITY=1` | 仅测试阶段 | ⚠️ 警告 | 轻量级 CI 一致性检查 |
| `GITHUB_ACTIONS=true` | 仅当前命令 | ✅ 阻断 | 直接测试调试 |

---

## 五、推荐使用场景

### 场景矩阵

| 场景 | 推荐模式 | 理由 |
|------|----------|------|
| **修改 subprocess 密集代码** | `VIBE_CI_SIMULATE=1` | 需要完整环境验证 |
| **修改 git 操作逻辑** | `VIBE_CI_SIMULATE=1` | 需要验证 bare repository 场景 |
| **日常推送前检查** | `VIBE_CI_PARITY=1` | 轻量级，不阻断 |
| **调试 CI 测试失败** | `GITHUB_ACTIONS=true` | 直接定位问题 |
| **开发新测试** | `GITHUB_ACTIONS=true` | 快速迭代验证 |
| **高风险变更推送前** | `VIBE_CI_SIMULATE=1` | 最严格的验证 |

### 快速参考

```bash
# 完整 CI 环境验证（推荐用于高风险变更）
VIBE_CI_SIMULATE=1 bash scripts/hooks/pre-push.sh

# 轻量级 CI 一致性检查（推荐用于日常开发）
VIBE_CI_PARITY=1 bash scripts/hooks/pre-push.sh

# 直接调试特定测试
GITHUB_ACTIONS=true uv run pytest tests/vibe3/services/test_git.py -v
```

---

## 六、常见问题

### Q1: 为什么我的测试在本地通过但在 CI 失败？

**可能原因**:
- 测试依赖特定工作目录（CI 在根目录运行）
- 测试依赖特定 git 状态（CI 在 bare repository 运行）
- 测试依赖未 mock 的环境变量

**验证方法**:
```bash
# 方式一：完整模拟
VIBE_CI_SIMULATE=1 bash scripts/hooks/pre-push.sh

# 方式二：直接运行失败的测试
GITHUB_ACTIONS=true uv run pytest tests/vibe3/path/to/failing_test.py -v
```

### Q2: VIBE_CI_PARITY 和 VIBE_CI_SIMULATE 的区别？

| 特性 | VIBE_CI_PARITY | VIBE_CI_SIMULATE |
|------|----------------|------------------|
| **环境变量覆盖范围** | 仅测试阶段 | 整个 pre-push |
| **阻断性** | ⚠️ 警告 | ✅ 阻断 |
| **测试运行次数** | 2 次（正常 + CI） | 1 次（CI 模式） |
| **推荐使用频率** | 每次推送 | 高风险变更前 |

### Q3: 何时使用 GITHUB_ACTIONS=true 而不是 VIBE_CI_SIMULATE？

**使用 `GITHUB_ACTIONS=true`**:
- 直接运行特定测试文件
- 快速迭代调试
- 不需要完整 pre-push 流程

**使用 `VIBE_CI_SIMULATE=1`**:
- 需要端到端验证
- 需要模拟完整的 CI 环境（包括 CI=true）
- 推送前的最终验证

---

## 七、相关资源

- **质量检查标准**: [quality-control-standard.md](../../standards/quality-control-standard.md) §2.8
- **实现代码**: [scripts/hooks/pre-push.sh](../../../scripts/hooks/pre-push.sh)
- **测试验证**: [tests/vibe3/integration/test_ci_parity.py](../../../tests/vibe3/integration/test_ci_parity.py)
- **PR #805**: feat(ci): add CI-like environment verification for executor workflow
- **Issue #608**: 系统改进：executor 应在 CI-like 环境验证测试

---

**维护者**: Vibe Team
**最后更新**: 2026-05-16
**相关阶段**: Phase 1 - Infrastructure
