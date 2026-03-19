

Local Review Orchestration Spec

1. 目标

构建一套本地优先、AST 驱动、成本感知的代码审查与结构治理系统，用于在 commit / push / PR ready 三个阶段，对代码变更进行：
	•	结构分类
	•	风险标记
	•	可维护性约束检查
	•	审查调度
	•	本地 / 云端审查资源分配

该系统的核心目标不是“逢改必审”，而是：

在尽量低的成本下，把高价值、高风险、高不确定性的变更识别出来，并把稀缺的云端 review 资源用在最值得用的地方。

⸻

2. 已知基础设施与约束

2.1 已有能力

系统默认已有以下本地能力：
	•	Serena AST 分析能力
	•	可识别结构变化
	•	可识别 API / 类型 / 调用链 / 依赖图变化
	•	比纯 diff 更高精度
	•	本地 review agent
	•	成本低
	•	可持续运行
	•	质量低于云端模型，但可承担大部分基础审查工作
	•	云端 review API
	•	质量高
	•	额度有限
	•	不适合无差别调用
	•	本地 Mac mini review 服务
	•	可承担常驻审查任务
	•	适合作为本地 review 主执行端

2.2 系统约束

本规范必须满足以下约束：
	•	本地优先，云端稀缺
	•	不能把 review 设计成“每次都跑”
	•	不能把 hooks 当成核心系统，只能当触发器
	•	不能把复杂逻辑散落在多个 hooks 中
	•	必须以 AST 结果作为主决策依据
	•	必须在 PR 之前完成结构治理，而不是把结构问题拖到 PR

⸻

3. 非目标

本规范不负责以下事项：
	•	不规定具体编程语言实现
	•	不规定具体 hook 脚本实现
	•	不规定具体 API 调用方式
	•	不负责自动修复策略
	•	不负责具体 review prompt 设计
	•	不负责云额度计费系统

⸻

4. 核心原则

4.1 AST 是唯一主入口

所有 review 与调度决策，都必须首先经过 AST gate。
禁止用“纯行数/纯文件数”直接决定是否 review。

4.2 Metrics 是结构约束，不是质量建议

Metrics gate 的职责不是“给建议”，而是判断：

当前变更是否已经破坏了代码结构的可维护性边界。

4.3 Review 是资源调度问题，不是默认动作

Review 是否执行，不由阶段直接决定，而由以下三类信号共同决定：
	•	结构复杂度
	•	风险等级
	•	结构健康度

4.4 云端 review 由风险驱动，不由额度驱动

系统不能把“有没有额度”作为第一判断逻辑。
正确逻辑是：

先判断该变更是否值得云审，再在执行层选择云 / 本地 / fallback。

4.5 结构问题优先级高于 review

如果变更已经违反结构规模约束，则优先处理拆分与结构整理。
此时不应先做深度 review。

4.6 PR ready 必 review，但不必云 review

PR ready 阶段必须进入审查流程，但云端 review 是否参与，取决于变更价值与风险。

⸻

5. 系统总览

整体流程如下：

Trigger
  -> AST Gate
  -> Metrics Gate
  -> Decision Engine
  -> Review Execution
  -> Result Recording


⸻

6. 组件定义

6.1 AST Gate

职责

AST Gate 是系统的第一层，也是唯一强制入口。职责包括：
	•	识别变更的结构类型
	•	识别结构风险
	•	给出后续调度所需的标准化标签

输出内容

AST Gate 必须至少输出以下结果：
	•	change_level
	•	risk_tags
	•	uncertainty_hint
	•	review_recommendation
	•	defer_hint

结构分级

AST Gate 必须将变更分为以下级别之一：

L0 — Trivial
特征：
	•	注释、文案、非行为性格式调整
	•	AST 无结构变化
	•	无调用关系变化
	•	无 API 变化

L1 — Local Change
特征：
	•	仅函数/方法体内部逻辑变化
	•	不修改外部接口
	•	不影响跨模块依赖
	•	影响范围局部

L2 — Structural Change
特征：
	•	修改函数签名、类型定义、公共接口
	•	修改重要控制流
	•	可能影响调用链
	•	需要结构级关注

L3 — Systemic Change
特征：
	•	多模块联动
	•	dependency graph 变化
	•	公共 API 传播性变化
	•	可能引发系统级副作用

风险标签

AST Gate 应尽可能给出以下风险标签中的若干个：
	•	api_change
	•	type_change
	•	control_flow_change
	•	dependency_graph_change
	•	public_surface_change
	•	cross_module_impact
	•	core_path_change
	•	security_sensitive
	•	config_sensitive

不确定性提示

AST Gate 可以输出一个不确定性提示，用于帮助判断是否值得上云。示例：
	•	low
	•	medium
	•	high

其含义是：
	•	low：结构可判定，语义风险较低
	•	medium：结构可判定，但语义副作用不完全明确
	•	high：AST 无法充分覆盖语义风险，需要更强推理能力

defer_hint

AST Gate 可以对“是否值得现在 review”给出提示：
	•	none
	•	defer_to_push
	•	defer_to_pr

其目的在于避免对仍在快速 churn 的变更过早消耗 review 资源。

⸻

6.2 Metrics Gate

职责

Metrics Gate 用于检查代码结构规模是否已经突破项目维护阈值。
它不是 review，不做语义判断，只做结构约束。

输入范围

Metrics Gate 不只看“这次改了多少行”，而是可以看：
	•	变更后的文件总行数
	•	变更后的函数长度
	•	类/模块规模
	•	嵌套深度
	•	项目定义的层级规模约束

输出内容

Metrics Gate 必须输出：
	•	metrics_status
	•	violations
	•	near_limit_flags
	•	refactor_required

状态定义

PASS
未触发任何阈值问题。

WARN
接近阈值，但未超限。
此时允许继续，但应记录提醒。

FAIL
超过硬性阈值，必须先整理结构，不允许进入后续深度审查。

关键原则

Metrics Gate 的判断优先级高于 review。
当 FAIL 时，系统行为应是：

先拆分 / 重构 / 整理，再进入审查。

放置阶段

Metrics Gate 的强制执行点应在：
	•	push：强制
	•	PR ready：复核

在 commit 阶段可以做轻量提示，但不宜作为硬阻断。

⸻

6.3 Decision Engine

职责

Decision Engine 负责根据 AST 与 Metrics 的结果，决定：
	•	是否跳过 review
	•	是否只做本地 review
	•	是否做云 review
	•	是否需要 defer
	•	是否必须先拆分

决策优先级

必须严格按以下顺序判断：
	1.	Metrics 是否失败
	2.	AST 结构级别
	3.	风险标签
	4.	不确定性
	5.	当前阶段
	6.	资源选择（本地 / 云端 / fallback）

第一原则

Decision Engine 不得直接根据“当前还有没有云额度”来定义策略；
额度只影响执行层 fallback，不影响主策略。

⸻

6.4 Review Execution

职责

执行层只负责做已经确定的审查动作，不负责重新判断策略。

执行类型

Review Execution 支持以下执行模式：
	•	skip
	•	local_review
	•	cloud_review
	•	local_then_cloud
	•	defer

执行层原则
	•	本地 review 是常规主力
	•	云 review 是高价值补充
	•	云 review 失败后可以 fallback 到本地，但不能因此反向修改上层决策逻辑

⸻

6.5 Result Recording

职责

将每次 gate 与 review 的结果记录为统一的审查元数据，供后续阶段复用。

原则
	•	AST 结果应作为 single source of truth
	•	push 与 PR 应复用前序分析结果，避免重复计算
	•	对同一变更不应重复做完全等价的分析

⸻

7. 三个阶段的职责边界

⸻

7.1 Commit 阶段

目标

Commit 阶段的目标不是审查，而是快速分类和标记。

必做事项
	•	运行 AST Gate
	•	输出结构级别与风险标签
	•	给出是否值得后续 review 的建议
	•	可选输出 Metrics 预警，但不做强阻断

不应做的事
	•	不做深度 AI review
	•	不做云 review
	•	不做重型本地 review
	•	不以结构优化为由频繁打断开发

允许的结果
	•	skip
	•	mark_for_push_review
	•	mark_for_pr_review
	•	defer_to_pr

Commit 阶段核心定位

Commit 是“标记阶段”，不是“执行阶段”。

⸻

7.2 Push 阶段

目标

Push 阶段是第一个真正值得付审查成本的节点。
此阶段应承担：
	•	结构约束 enforcement
	•	第一轮本地 review 执行

必做事项
	•	运行 AST Gate
	•	强制运行 Metrics Gate
	•	根据结构级别决定是否本地 review

决策原则

当 Metrics FAIL
	•	阻止进入后续深度审查
	•	优先要求拆分/整理
	•	本次 push 不应进入深度 review 流程

当 Metrics PASS / WARN
根据 AST 结果继续：
	•	L0：跳过
	•	L1：通常可跳过，或仅轻量本地 review
	•	L2：执行本地 review
	•	L3：执行本地 review，并标记为 PR 阶段高优先级候选

Push 阶段核心定位

Push 是“结构治理 + 低成本执行”的主战场。

⸻

7.3 PR Ready 阶段

目标

PR Ready 是信息最完整、上下文最稳定的阶段。
此阶段必须完成正式审查闭环。

必做事项
	•	复用 AST 结果
	•	复核 Metrics 状态
	•	执行本地 review
	•	判断是否值得云 review

原则

所有 PR Ready 必 review
但 review 并不等于必须云审。

本地 review 始终执行
PR Ready 阶段至少要有本地 review。

云 review 是条件性增强
只有在以下情况之一成立时，才建议使用云 review：
	•	L3
	•	高风险标签明显
	•	不确定性为 high
	•	改动跨模块且传播面大
	•	本地 review 已发现可疑问题但无法稳定定性

PR 阶段核心定位

PR Ready 是“正式审查与资源升级”的阶段。

⸻

8. 统一决策矩阵

8.1 先看 Metrics

Metrics 状态	结果
PASS	允许继续
WARN	允许继续，但记录结构风险
FAIL	先拆分/整理，暂停深度审查


⸻

8.2 再看 AST Level

AST Level	Commit	Push	PR Ready
L0	标记后跳过	跳过	本地轻量 review 或跳过
L1	标记	通常跳过或轻量本地 review	本地 review
L2	标记为后续 review 候选	本地 review	本地 review，必要时云增强
L3	标记为高风险	本地 review	本地 review + 条件性云 review


⸻

8.3 云 review 推荐条件

满足以下任意条件时，PR Ready 阶段建议云 review：
	•	change_level = L3
	•	有 api_change 且影响 public surface
	•	有 dependency_graph_change
	•	有 cross_module_impact
	•	有 core_path_change
	•	uncertainty_hint = high

⸻

9. 结构治理规则

9.1 结构治理优先级

当 Metrics Gate 判定超限时：

先拆，再审。

这条规则必须高于“已经到了 PR 阶段所以先 review”。

9.2 需要治理的典型对象

项目可自行定义阈值，但至少应支持以下治理对象：
	•	过大文件
	•	过长函数
	•	过于膨胀的类/模块
	•	嵌套深度异常
	•	层级职责失衡

9.3 拆分原则

当触发结构治理时，本地 agent 应优先采用以下拆分思路：
	•	按功能边界拆分
	•	按依赖方向拆分
	•	按层级职责拆分
	•	保持高内聚、低耦合

禁止采用以下低质量拆分：
	•	仅按行数硬切
	•	随机抽取函数分文件
	•	无视调用关系的机械拆分

⸻

10. defer 机制

10.1 目的

避免对仍在频繁变动、语义尚未稳定的代码过早消耗 review 资源。

10.2 可 defer 的阶段
	•	Commit 可 defer 到 Push 或 PR
	•	Push 可标记 PR 阶段优先审查
	•	PR Ready 原则上不再 defer 正式 review

10.3 defer 条件建议

可由 AST 或历史变更信息推断：
	•	同一区域频繁 churn
	•	结构尚不稳定
	•	当前改动仍明显处于中间态

⸻

11. 资源路由原则

11.1 本地 review 的角色

本地 review 是系统主力，负责：
	•	基础结构审查
	•	低成本语义检查
	•	常规问题发现
	•	大多数 PR 的基础审查

11.2 云 review 的角色

云 review 是稀缺增强能力，只用于：
	•	高风险
	•	高传播性
	•	高不确定性
	•	本地难以稳定判断的问题

11.3 路由原则

不是“有额度就跑”，而是：

值得跑才考虑云。

⸻

12. 结果状态标准化

Decision Engine 最终必须输出统一状态之一：
	•	SKIP
	•	MARKED_FOR_PUSH
	•	MARKED_FOR_PR
	•	DEFER_TO_PR
	•	BLOCK_FOR_REFACTOR
	•	RUN_LOCAL_REVIEW
	•	RUN_CLOUD_REVIEW
	•	RUN_LOCAL_AND_CLOUD

这些状态应成为本地 agent 执行与汇报的标准接口。

⸻

13. 本地 agent 执行要求

交给本地 agent 时，应要求其按以下顺序处理：

13.1 第一阶段：整理当前系统能力
	•	明确 Serena AST 当前可输出哪些结构信号
	•	明确现有 metrics 规则有哪些
	•	明确本地 review agent 当前能力边界
	•	明确云 review 只作为 PR 阶段条件性增强

13.2 第二阶段：统一决策模型
	•	以 AST gate 为唯一入口
	•	让 Metrics gate 位于 review 前
	•	将 commit / push / PR 的职责分开
	•	统一输出标准状态

13.3 第三阶段：整理代码结构
	•	把散落的判断逻辑收敛成统一 decision engine
	•	保证 hooks 只负责触发，不负责业务判断
	•	保证 AST / Metrics / Review 三层边界清晰
	•	保证结果可复用，不重复分析

13.4 第四阶段：校验收敛性

确认系统是否满足以下条件：
	•	所有 commit 都过 AST gate
	•	所有 push 都过 Metrics gate
	•	所有 PR Ready 必 review
	•	云 review 只在高价值场景触发
	•	结构问题优先于深度 review
	•	决策逻辑集中，非分散

⸻

14. 验收标准

当本地 agent 整理完成后，系统应满足以下验收标准：

14.1 行为层
	•	trivial 改动不会触发无意义 review
	•	高结构风险改动不会漏过本地 review
	•	结构超限问题能在 push 前被拦住
	•	PR 阶段不会再首次发现明显结构失控

14.2 架构层
	•	AST gate 成为主入口
	•	Metrics gate 成为结构治理入口
	•	review 执行层不包含策略逻辑
	•	hooks 不承载复杂判断

14.3 资源层
	•	云 review 次数显著少于本地 review
	•	云 review 主要集中在 L3 / 高风险 / 高不确定性变更
	•	本地 review 成为默认路径

⸻

15. 最终一句话定义

这套系统不是一个“AI hook 集合”，而是一个：

基于 AST 的结构治理与审查资源调度系统

它的判断顺序必须永远是：

先看结构，再看风险，再决定是否审查，以及用什么资源审查。

