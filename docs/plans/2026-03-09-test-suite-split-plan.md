# Test Suite Split Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 `tests/test_flow.bats` 与 `tests/test_roadmap.bats` 拆分为多个按主题组织的 bats 文件，并抽取共享 helper，降低单文件重量和后续冲突面。

**Architecture:** 不改生产代码，只重组测试文件。通过 `tests/helpers/*.bash` 承接 `setup()` 和 fixture，随后把现有测试块按 flow/roadmap 主题搬迁到子目录，最后删除旧的超重入口文件。

**Tech Stack:** Zsh CLI、Bats、`jq`、Markdown。

---

### Task 1: 抽取共享 helper

**Files:**
- Create: `tests/helpers/flow_common.bash`
- Create: `tests/helpers/roadmap_common.bash`

**Step 1: 复制现有 `setup()` 与 fixture helper**

- 将 `tests/test_flow.bats` 的 `setup()`、`make_flow_task_fixture()` 下沉到 `flow_common.bash`
- 将 `tests/test_roadmap.bats` 的 `setup()`、`make_roadmap_fixture()` 下沉到 `roadmap_common.bash`

**Step 2: 保持 helper 只做共享准备，不引入新逻辑**

---

### Task 2: 拆分 flow 测试

**Files:**
- Create: `tests/flow/test_flow_help_runtime.bats`
- Create: `tests/flow/test_flow_lifecycle.bats`
- Create: `tests/flow/test_flow_bind_done.bats`
- Create: `tests/flow/test_flow_pr_review.bats`
- Delete: `tests/test_flow.bats`

**Step 1: 迁移 help/runtime 相关测试**

- 包含 `help`、`status/show/list`、runtime 检测等测试

**Step 2: 迁移 lifecycle 相关测试**

- 包含 `new/switch/start/sync` 与 `vnew` 行为测试

**Step 3: 迁移 bind/done 相关测试**

- 包含 task 绑定与 flow 关闭行为测试

**Step 4: 迁移 pr/review 相关测试**

- 包含 review help、PR base 推断、bump、gh 交互相关测试

---

### Task 3: 拆分 roadmap 测试

**Files:**
- Create: `tests/roadmap/test_roadmap_status_render.bats`
- Create: `tests/roadmap/test_roadmap_query.bats`
- Create: `tests/roadmap/test_roadmap_write_audit.bats`
- Delete: `tests/test_roadmap.bats`

**Step 1: 迁移 status/render 相关测试**

- 包含状态输出、文本分组、颜色判定、show 文本渲染测试

**Step 2: 迁移 query 相关测试**

- 包含 `list --json`、`show --json` 等查询行为测试

**Step 3: 迁移 write/audit 相关测试**

- 包含 assign/classify/version/add/audit 行为测试

---

### Task 4: 回归验证

**Files:**
- Verify: `tests/flow/*.bats`
- Verify: `tests/roadmap/*.bats`

**Step 1: 跑 flow 拆分后的测试集合**

Run:

```bash
bats tests/flow/*.bats
```

**Step 2: 跑 roadmap 拆分后的测试集合**

Run:

```bash
bats tests/roadmap/*.bats
```

**Step 3: 跑合并后的相关测试集合**

Run:

```bash
bats tests/flow/*.bats tests/roadmap/*.bats
```

Expected:
- 全部通过
- 不再依赖 `tests/test_flow.bats` 与 `tests/test_roadmap.bats`