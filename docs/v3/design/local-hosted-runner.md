
Self-Hosted Runner Integration Spec

⸻

1. 目标

在本地 Mac mini 上部署 GitHub self-hosted runner，使其成为：

统一执行面（Execution Plane）

用于承载：
	•	AST Gate
	•	Metrics Gate
	•	Decision Engine
	•	Local Review（主）
	•	Cloud Review（条件性）

并由 GitHub workflow 触发执行。

⸻

2. 系统定位

2.1 runner 的角色

runner 不是：
	•	❌ orchestration system
	•	❌ 决策系统
	•	❌ review engine

runner 是：

remote trigger → local execution


⸻

2.2 系统分层

[GitHub Events]
        ↓
[Workflow Trigger]
        ↓
[Self-hosted Runner]
        ↓
[Local Review System]
   ├── AST Gate
   ├── Metrics Gate
   ├── Decision Engine
   ├── Local Agent
   └── Cloud Fallback


⸻

3. Runner 部署规范

3.1 部署位置
	•	运行在：Mac mini（常驻机器）
	•	必须具备：
	•	持续在线
	•	可访问 GitHub
	•	有完整 repo checkout 权限

⸻

3.2 Runner 类型

使用：

self-hosted

推荐标签：

self-hosted
mac
review


⸻

3.3 Runner 生命周期要求

必须满足：
	•	自动启动（开机即运行）
	•	自动重连 GitHub
	•	异常退出自动恢复
	•	不依赖用户交互

⸻

3.4 并发策略

初期建议：

concurrency = 1

原因：
	•	本地 agent 非线程安全
	•	避免资源争抢
	•	避免 review 污染

⸻

4. Workflow 设计规范

⸻

4.1 触发事件

必须支持以下三类：

1️⃣ push（可选）

用于触发：
- Metrics Gate
- Local Review（L2+）


⸻

2️⃣ pull_request

用于触发：
- 完整 review pipeline


⸻

3️⃣ pull_request_target（可选）

用于：
	•	写 comment
	•	写 status

（注意安全限制）

⸻

⸻

4.2 触发粒度

建议只在以下事件触发：

pull_request:
  - opened
  - synchronize
  - ready_for_review


⸻

4.3 Workflow 职责边界

Workflow 只负责：

- checkout repo
- 准备环境
- 调用本地 review-dispatch


⸻

❗禁止在 workflow 中写：
	•	AST 分析逻辑
	•	Metrics 判断逻辑
	•	review 决策逻辑

⸻

5. 本地执行入口规范

⸻

5.1 统一入口

必须定义一个统一执行入口，例如：

review-dispatch


⸻

5.2 输入参数（最小集合）

--stage [push | pr]
--base_sha
--head_sha
--pr_number（可选）
--event_type


⸻

5.3 输入来源

来自 GitHub Actions context：
	•	github.sha
	•	github.base_ref
	•	github.head_ref
	•	github.event.pull_request.*

⸻

5.4 执行顺序（必须固定）

1. AST Gate
2. Metrics Gate
3. Decision Engine
4. Review Execution
5. Result Output


⸻

6. 本地 Review Pipeline 规范

⸻

6.1 AST Gate（强制）

必须执行：

- change_level（L0–L3）
- risk_tags
- uncertainty
- defer_hint

输出作为全流程输入。

⸻

6.2 Metrics Gate（push + PR）

执行：

- file size
- function size
- class/module size


⸻

结果处理

if FAIL:
    → BLOCK
    → exit early


⸻

6.3 Decision Engine

根据：

AST + Metrics + Stage

输出：

SKIP
LOCAL_REVIEW
CLOUD_REVIEW
LOCAL_AND_CLOUD
DEFER
BLOCK


⸻

6.4 Review Execution

本地 review（默认）

codeagent-wrapper


⸻

云 review（条件）

只在：

- L3
- 高风险
- 高不确定性

触发

⸻

fallback

cloud fail → local


⸻

7. PR 输出规范

⸻

7.1 输出形式

必须支持：
	•	PR comment
	•	summary comment
	•	状态标记（success / fail）

⸻

7.2 输出内容结构

Summary
Findings
Severity
Suggestions
Confidence


⸻

7.3 幂等性

同一个：

commit_sha + policy_version

不得重复评论

⸻

8. 缓存与复用

⸻

8.1 AST 结果复用

必须支持：

commit → push → PR

复用 AST 结果

⸻

8.2 Review 复用

push 已 review
→ PR 不重复做 local
→ 只补 cloud（如果需要）


⸻

9. 失败策略

⸻

9.1 runner 不可用

→ fallback:
    - 仅云 review（可选）
    - 或 skip


⸻

9.2 本地 review 失败

→ 标记 warning
→ 不阻断 PR


⸻

9.3 Metrics FAIL

→ 阻断流程
→ 不进入 review


⸻

10. 安全规范

⸻

10.1 权限

runner token 只允许：
	•	read repo
	•	write PR comment
	•	write status

⸻

10.2 禁止行为
	•	不允许执行任意用户输入命令
	•	不允许直接暴露 shell 接口
	•	不允许写代码（除非未来扩展）

⸻

11. 扩展点（未来）

⸻

11.1 多 runner

按 repo / team 分配


⸻

11.2 多 agent

local agent + cloud agent


⸻

11.3 review 聚合

merge multi-provider result


⸻

12. 验收标准

⸻

系统完成后必须满足：

行为
	•	PR Ready 必 review
	•	trivial 改动不触发 review
	•	结构超限在 push 阶段被拦截

⸻

架构
	•	AST 是唯一入口
	•	Metrics 在 review 前执行
	•	决策集中在本地
	•	workflow 无业务逻辑

⸻

资源
	•	本地 review 为主
	•	云 review 仅在高价值场景触发

⸻

13. 一句话定义

Self-hosted runner 是你的“执行面”，不是系统本身；真正的系统是你本地的 AST + Metrics + Decision 引擎。

