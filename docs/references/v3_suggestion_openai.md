

1. 系统目标

该工具是一个 GitHub workflow wrapper CLI。

它解决的问题：

在 Git + GitHub Project + Issue + PR 的开发模式下，开发者通常会同时推进多条开发线，但 GitHub 本身无法很好回答：
	•	当前有哪些开发线正在进行
	•	每条线处于 plan / execute / review 哪个阶段
	•	每条线最近发生了什么 handoff
	•	每条线遇到了哪些 bug 或阻塞
	•	多条 flow 的整体进度

该工具通过：

Flow + Handoff

实现一个 本地开发流程记录层。

关键原则：

GitHub = 数据源
flow wrapper = 流程记录


⸻

2. 核心设计原则

2.1 GitHub 是唯一事实来源

本工具 不会复制 GitHub 数据。

以下信息永远通过 gh 实时获取：

GitHub issue
task
branch
PR
merge 状态
review 状态
GitHub project

工具不会存储：

PR metadata
issue metadata
branch metadata
project state

原因：

避免状态漂移
避免同步复杂度
避免维护 API schema


⸻

2.2 本地只记录两类数据

本地只保存：

Flow metadata
Handoff event

Flow metadata 是极小数据。

Handoff 是流程日志。

⸻

2.3 Flow 是开发线

Flow 表示一条开发线。

关系如下：

GitHub Issue
   ↓
Task
   ↓
Flow
   ↓
Branch
   ↓
PR

规则：

1 task = 1 flow
1 flow = 1 main branch
1 flow = 1 main PR

但工具不会保存 branch / PR 状态，只保存引用。

⸻

3. Flow 概念

Flow 是一条开发线。

它记录：

任务来源
当前阶段
关联 branch
关联 PR
handoff 历史

Flow 示例：

flow:
  id: flow-124
  repo: owner/repo

  repo_issue: 120
  task_issue: 124

  title: "Implement flow state sync"

  branch: "flow/124-state-sync"

  pr: 245

  stage: execute
  status: in_progress

  created_at: 2026-03-15T08:00:00Z
  updated_at: 2026-03-15T09:20:00Z

注意：

branch/pr 只是引用

真实状态来自：

gh pr view
gh issue view
git branch


⸻

4. 阶段模型

Flow 生命周期固定为三阶段：

plan
execute
review

终态：

done
blocked
cancelled

阶段含义：

阶段	含义
plan	任务定义与方案规划
execute	实现进行中
review	实现完成，等待审查
done	PR 已 merge


⸻

5. 阶段与 GitHub 的关系

阶段不是 GitHub 状态，而是流程状态。

推荐关系：

Flow Stage	GitHub 状态
plan	task 已创建
execute	branch 存在 + draft PR
review	PR open
done	PR merged

但系统不会强制同步。

doctor 命令只做检测。

⸻

6. Handoff

handoff 是核心。

它表示：

流程阶段交接

典型 handoff：

plan → execute
execute → review
review → done


⸻

Handoff 记录结构

handoff:
  id: hf_20260315_001

  flow: flow-124

  from_stage: plan
  to_stage: execute

  actor: jacob

  timestamp: 2026-03-15T08:10:00Z

  summary: "Plan approved, branch created"

  notes:
    - "Need sync command"

handoff 只记录流程信息。

不会记录 GitHub 状态。

⸻

7. 本地存储

V3 使用 SQLite 数据库存储：

位置：

.git/vibe3/handoff.db (位于主仓库 git common dir)

主要表：

- flow_state: flow 元数据和状态
- flow_issue_links: flow 与 issue 的关系
- flow_events: 事件和 handoff 记录

注意：这是历史建议文档，描述的是 V2 文件存储方案。
当前 V3 实现使用 SQLite，详见 docs/standards/v3/data-model-standard.md。


⸻

Flow 数据 (历史建议)

注意：以下为 V2 风格的文件存储建议，已被 V3 SQLite 实现取代。

.flow/flows/flow-124.yaml 示例：

version: 1

flow:
  id: flow-124

  repo: owner/repo

  repo_issue: 120
  task_issue: 124

  title: "Implement flow state sync"

  branch: flow/124-state-sync

  pr: 245

  stage: execute
  status: in_progress

  created_at: 2026-03-15T08:00:00Z
  updated_at: 2026-03-15T09:20:00Z


⸻

Handoff 事件 (历史建议)

V2 风格：

.flow/events/handoffs.jsonl

每行：

{
  "flow": "flow-124",
  "action": "enter_execute",
  "from_stage": "plan",
  "to_stage": "execute",
  "actor": "jacob",
  "timestamp": "2026-03-15T08:10:00Z",
  "summary": "Branch created"
}


⸻

8. CLI 设计 (历史建议)

命令统一围绕 flow。

主命令：

flow

注意：以下为 V2 风格的命令建议，已被 V3 现行命令取代。
当前 V3 命令标准见 docs/standards/v3/command-standard.md。


⸻

创建 Flow (历史建议)

flow create --task 124 --repo owner/repo

行为：
	•	创建 flow 文件
	•	stage = plan
	•	写 handoff

V3 现行方式：使用 `vibe3 flow update` 注册 flow，然后 `vibe3 flow bind` 绑定 issue。

⸻

开始执行 (历史建议)

flow start 124

行为：
	•	stage → execute
	•	写 handoff

V3 现行方式：flow 状态由 Orchestra 自动管理，或通过 `vibe3 task resume` 恢复。

⸻

创建 Draft PR (历史建议)

flow pr draft 124

行为：

gh pr create --draft

然后记录 PR number。

V3 现行方式：直接使用 `gh pr create --draft`，flow 自动关联 PR。

⸻

进入 Review (历史建议)

flow handoff 124 --to review

行为：
	•	stage → review
	•	写 handoff

V3 现行方式：通过 `vibe3 handoff` 记录阶段交接，flow 状态由 Orchestra 管理。

⸻

完成 Flow (历史建议)

flow done 124

行为：
	•	调用

gh pr merge

	•	stage → done

V3 现行方式：直接使用 `gh pr merge`，flow 自动进入 done 状态。

⸻

9. 查询命令 (历史建议)

flow list

查看所有 flow。

示例：

FLOW   STAGE    TASK   BRANCH                 PR
124    execute  124    flow/124-state-sync    245
125    review   125    flow/125-doctor        246
126    plan     126    -                      -

V3 现行方式：使用 `vibe3 flow status` 查看 flow 总览，`vibe3 task status` 查看任务总览。

PR 和 branch 状态来自：

gh
git


⸻

flow show

flow show 124

输出：

Flow 124
Stage: execute

Task: #124
GitHub Issue: #120

Branch: flow/124-state-sync
PR: #245

Recent Handoffs
---------------
plan → execute


⸻

flow board

按阶段展示：

PLAN
  flow-130 Task #130

EXECUTE
  flow-124 Task #124
  flow-127 Task #127

REVIEW
  flow-125 Task #125


⸻

10. Doctor

doctor 用于检测流程异常。

flow doctor

检查：

flow execute but branch missing
flow review but PR missing
flow done but PR not merged
flow plan but branch exists

它不会修复，只提示。

⸻

11. gh 集成原则

系统优先使用：

gh

而不是直接 API。

优点：

避免 token 管理
避免 GraphQL schema
复用 gh 配置

只有在 gh 无法完成时才使用 API。

⸻

12. 推荐依赖

因为系统非常轻量。

建议：

typer
rich
pyyaml

可选：

pydantic

不建议：

数据库
ORM
复杂 API SDK


⸻

13. 推荐项目结构

flowctl/

  pyproject.toml

  flowctl/

    cli.py

    commands/
      create.py
      start.py
      pr.py
      handoff.py
      done.py
      list.py
      show.py
      board.py
      doctor.py

    model/
      flow.py
      handoff.py

    storage/
      flow_store.py
      event_store.py

    gh/
      gh_wrapper.py

    ui/
      table.py


⸻

14. 最小 MVP

第一版只需要：

flow create
flow start
flow pr draft
flow handoff
flow done
flow list
flow show
flow board
flow doctor

就足够实用。

⸻

15. 一个完整流程示例

创建 flow：

flow create --repo owner/repo --task 124

开始执行：

flow start 124

创建 PR：

flow pr draft 124

进入 review：

flow handoff 124 --to review

合并：

flow done 124


⸻

最核心的设计思想

这套系统不是：

GitHub automation

而是：

GitHub workflow journaling

你不是管理 GitHub。

你是在 记录开发流程的历史与状态。

