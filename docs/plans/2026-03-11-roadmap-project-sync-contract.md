---
document_type: plan
title: roadmap project sync contract
status: proposed
author: Codex GPT-5
created: 2026-03-11
related_docs:
  - docs/standards/v2/roadmap-json-standard.md
  - docs/standards/v2/data-model-standard.md
  - docs/standards/v2/command-standard.md
  - docs/references/github_project.md
  - lib/roadmap.sh
  - lib/roadmap_write.sh
---

# Goal

为 `vibe roadmap sync` 确定 GitHub Project 双向同步合同：`roadmap.json` 顶层持有 `project_id`，roadmap item 作为 GitHub Project item mirror，新增本地 item 时先创建远端 item 再回填本地；`task` / `flow` 及执行桥接字段只保留本地，不参与 GitHub Project 同步。

# Non-Goals

- 本轮不直接实现 GitHub Project 双向同步代码
- 本轮不重做整个 `roadmap.json` schema
- 本轮不决定所有 GitHub 自定义字段的最终命名，只确定 official layer 与 local extension layer 的边界

# Tech Stack

- Zsh shell CLI
- GitHub GraphQL API
- `gh api graphql`
- JSON shared state (`roadmap.json`)

# Investigated Decision

## 1. Root Contract

- `roadmap.json` 当前标准根对象尚未包含 `project_id`
- 后续应在顶层新增 `project_id`
- `repo` 不写入 `roadmap.json`，运行时从当前 git 环境推导

## 2. Item Identity

- `roadmap item` 是 mirrored GitHub Project item
- 正式 item 不允许长期处于“仅本地、无远端身份”状态
- `vibe roadmap add` 的正确语义应为：
  1. 创建远端 GitHub Project item
  2. 获取 `github_project_item_id`
  3. 回填本地 `roadmap.json`

## 3. Official Layer vs Local Extension Layer

根据仓库现有标准和 GitHub 官方 Project API，边界可先收敛为：

### Official Layer

- `github_project_item_id`
- `content_type`
- `title`
- `description`
- GitHub Project 中真实存在且可通过 API 读取/更新的字段值

说明：
- GitHub 官方文档要求新增 item 后，需先 `addProjectV2ItemById`，再单独 `updateProjectV2ItemFieldValue`
- GitHub 当前公开支持通过 `updateProjectV2ItemFieldValue` 更新的字段类型是有限集合：single-select、text、number、date、iteration

### Local Extension Layer

- `spec_standard`
- `execution_record_id`
- `spec_ref`
- `linked_task_ids`
- 其他仅用于本地执行桥接、且 GitHub Project 无官方等价字段的扩展字段

说明：
- 仓库现有标准已经把 `spec_standard` / `execution_record_id` / `spec_ref` 定义为 Vibe 扩展桥
- 本轮讨论结论是：这些字段只服务本地执行计划与运行时桥接，不写回 GitHub Project
- `task` / `flow` / runtime 语义属于中间执行层，不参与 GitHub Project 同步

## 4. Sync Boundary

- `roadmap item` <-> GitHub Project item：双向同步
- `pr` <-> GitHub PR：维持各自现有同步/查询能力
- `task` / `flow` / execution bridge：只保留在本地共享真源

说明：
- 该模型是“两头同步，中间过程不同步”
- `vibe roadmap sync` 只负责规划层 mirror，不负责执行层注册、拆 task、绑定 flow 或回写执行语义到 GitHub

## 5. Bootstrap Reality

- 当前仓库历史上尚未完成 GitHub Project 正式同步
- 本地 `roadmap.json` 已有历史 roadmap items，但新建 GitHub Project 为空
- 因此第一阶段不应以“拉取远端”为主，而应先执行 bootstrap push：
  1. 以本地 roadmap items 为源
  2. 为缺失 `github_project_item_id` 的项创建远端 GitHub Project item
  3. 回填本地 `github_project_item_id` / `content_type`
  4. 之后再进入常规双向同步

## 6. Historical Data Gaps

- 本地核心执行对象仍是 `task`，但 `task` 不直接同步到 GitHub Project
- GitHub Project 同步对象仍是 `roadmap item`
- 问题在于：既有历史里存在 task 已完成、PR 已存在或已合并、但未稳定绑定到 roadmap item / task / PR 桥接字段的断层现场

处理原则：

- 不把 `task` 直接推成 GitHub Project item
- 先以 `roadmap item` 完成 Project bootstrap
- 对历史断层数据单独做补链/审计，而不是让 `roadmap sync` 隐式猜测执行事实

最小补链范围：

- 已有 `roadmap item` 但缺 `github_project_item_id`
- 已完成 `task` 缺 `execution_record_id` 桥接
- 已存在或已合并 PR，但未稳定挂回相关 `task` / `roadmap item`

该问题必须进入实现计划与测试计划，避免 bootstrap push 误把“历史执行断层”当成“当前规划同步”直接覆盖。

# Step Tasks

1. 更新 `roadmap.json` 标准，给根对象增加 `project_id`，并明确 `repo` 由运行环境推导。
2. 更新 command standard，明确 `vibe roadmap add` 是“先远端创建，再本地回填”。
3. 更新 `vibe roadmap sync` 合同，去掉 `--repo` 必填心智，改成默认从当前 git 环境推导 repo，并从 `roadmap.json.project_id` 确定 project。
4. 先实现空 Project 下的 bootstrap push：为缺失 `github_project_item_id` 的 roadmap items 创建远端 Project items 并回填本地。
5. 明确 sync 的双向边界：只同步 GitHub Project 官方镜像字段；本地执行桥接字段保留在共享真源；冲突 fail-fast。
6. 为历史断层增加审计/补链策略，避免把未绑定 task / PR 事实错误写进 GitHub Project。
7. 在实现前补合同测试，覆盖缺失 `project_id`、当前 repo 不可推导、bootstrap push 成功后本地回填、以及本地执行字段不会被写回 GitHub。

# Files To Modify

- `docs/standards/v2/roadmap-json-standard.md`
- `docs/standards/v2/command-standard.md`
- `docs/standards/v2/data-model-standard.md`
- `lib/roadmap.sh`
- `lib/roadmap_write.sh`
- `lib/roadmap_help.sh`
- `lib/task_actions.sh`
- `lib/flow_show.sh`
- `tests/contracts/test_roadmap_contract.bats`
- `tests/contracts/test_shared_state_contracts.bats`
- `tests/roadmap/test_roadmap_status_render.bats`

# Test Command

```bash
bats tests/contracts/test_roadmap_contract.bats
bats tests/contracts/test_shared_state_contracts.bats
bats tests/roadmap/test_roadmap_status_render.bats
```

# Expected Result

- `roadmap.json` 顶层具备 `project_id` 合同
- `vibe roadmap sync` 的目标从 repo issue import 明确收敛为 GitHub Project bootstrap + 双向同步
- official layer 与 local extension layer 的边界在标准和合同测试中保持一致
- `task` / `flow` 不再被误纳入 `roadmap sync` 的远端同步范围
- 历史 task / PR 断层不会被 bootstrap push 静默覆盖

# Change Summary

- Modified: 8 files
- Approximate lines: 80-180
