# Vibe3 Architecture Convergence Standard

状态：Active

## 1. 目的

本标准定义 Vibe3 的目标架构收敛方向，回答三类问题：

- 最终代码结构应该分成哪些层
- `domain-first` 为什么存在、解决什么问题
- 为什么当前代码会膨胀，以及后续应如何收敛

本标准是 Vibe3 结构收敛的总纲，不替代现有分项标准。

本标准不定义：

- 具体事件类型与 payload 字段
- `state/*` 业务状态细节
- worktree 参数和 ownership 细节
- 某一条 agent 链路的 prompt 文案
- 具体实施顺序与施工计划

这些内容分别以其他标准或计划文档为准。

## 2. 背景判断

Vibe3 当前已经形成以下稳定方向：

- `environment` 负责 worktree / tmux / session 等环境原语
- `agents` 负责 prompt/backend/pipeline 封装
- `runtime` 负责 heartbeat、transport 与事件入口
- `domain` 负责事件驱动的业务编排

但当前仓库仍处于“新旧并存”的迁移态：

- 旧的 `orchestra/services` 仍保留较多编排权
- `manager` 仍承担了部分执行控制面
- 多条角色链路仍各自拼装启动流程
- 共用能力已经抽出，但主控入口还没有完全唯一化

因此，当前问题不是“有没有分层”，而是“是否已经完成收权”。

## 3. 核心判断

### 3.1 代码膨胀的真实原因

Vibe3 的代码膨胀，主要不是因为功能绝对数量过多，而是因为同一类职责同时存在于多层：

- 业务编排同时存在于 `domain`、`orchestra`、`manager`
- 执行启动同时存在于 `manager`、`domain handlers`、部分 `orchestra services`
- lifecycle / capacity / session 组件虽已抽出，但调用入口仍然分散

结果是：

- 共享组件存在
- 旧调用链没有完全退役
- 新层叠加到旧层之上
- 同一种事情出现多个“半合法入口”

这会导致代码量增加、调试困难、职责漂移和认知负担失控。

### 3.2 之前抽象过什么

Vibe3 并不是“完全没有抽象”，而是已经抽出过一批共性基础设施：

- `ExecutionRolePolicyService`：统一角色执行配置解析
- `ExecutionLifecycleService`：统一 started/completed/failed 记账
- `CapacityService`：统一容量控制
- `SessionRegistryService`：统一 session 真相记录
- `WorktreeManager`：统一 worktree 原语
- `agent_resolver`：统一 manager / governance / supervisor 配置真源
- `OrchestrationFacade`：统一 runtime observation 到 domain event 的翻译入口

问题在于：这些更多是共享组件，还不是唯一主线。

## 4. 为什么要 Domain-First

### 4.1 domain-first 的定义

`domain-first` 指的是：

- runtime / server 只负责 transport 与事件进入系统
- 业务语义只在 domain 层做判断
- role 之间的推进关系由 domain event 明确定义
- 角色执行只是 domain 决策后的副作用，不再是多处散落的脚本式编排

### 4.2 好处

采用 `domain-first` 的目标收益有四个：

1. 同一事实入口统一  
   heartbeat、webhook、人工恢复等不同入口，最终都能收敛成同一套业务事件，而不是各自维护一套“如果这样就 dispatch 那样”的脚本。

2. 业务判断可测试  
   以前很多逻辑藏在 tick service 或 manager 启动路径里，测试只能靠集成链路。进入 domain 后，状态推进和事件反应可以做更清晰的单测。

3. 生命周期更可审计  
   当“发生了什么”由事件显式表达时，manager、plan、run、review、governance、supervisor 的推进链更容易记录、复盘和调试。

4. transport 与业务解耦  
   server/runtime 不再需要理解所有角色细节。后续无论是 webhook、CLI、定时器还是别的 transport，接入成本都会更低。

### 4.3 代价

`domain-first` 也有明显成本：

- 事件层、handler、transport adapter 会引入额外文件和抽象
- 如果旧的 orchestration 逻辑不及时退休，就会出现双轨系统
- 如果只抽“事件定义”，不收拢“执行入口”，会变成更多胶水代码而不是更少

所以 `domain-first` 不是天然减少代码量，它减少的是耦合；只有在边界真正收敛后，才会开始减少总复杂度。

## 5. 目标结构

Vibe3 最终应收敛为六层。

### 5.1 Server

`server/` 只负责：

- HTTP / webhook / health / status 暴露
- 进程级 driver 装配
- runtime 启停

`server/` 不负责：

- 角色业务判断
- role-specific dispatch 规则
- prompt / backend / capacity 选择

### 5.2 Runtime

`runtime/` 只负责：

- heartbeat
- queue / tick / event routing
- 将外部 observation 交给 domain facade

`runtime/` 不负责：

- 业务状态推进
- 直接启动某个具体角色
- 持有 role-specific orchestration 逻辑

### 5.3 Domain

`domain/` 是业务编排真源，只负责：

- 定义领域事件
- 把 runtime observation 翻译成业务事件
- 决定“下一步应该发生什么”
- 驱动状态机与角色推进关系

`domain/` 不负责：

- 直接管理 tmux / worktree 细节
- 自己拼 shell 命令
- 成为资源管理器

### 5.4 Execution

`execution` 是统一执行控制面，负责：

- 角色执行策略解析
- capacity gate
- lifecycle 记录
- session truth 写入
- launch sync/async agent
- 绑定 `tmux_session`、`log_path`、`cwd` 等 runtime refs

这是当前最需要显式收敛出来的一层。

`execution` 不是新的业务层，而是 domain 的执行器。

### 5.5 Environment

`environment/` 只负责资源原语：

- worktree 创建、复用、回收
- tmux/session 探活与登记
- 环境现场隔离

`environment/` 不负责：

- 判断何时 dispatch
- 决定哪个角色该执行
- 写业务状态机

### 5.6 Role Adapters

以下目录最终都应薄化为角色适配器，而不是通用编排器：

- `manager/`
- `orchestra/`
- `agents/plan`
- `agents/run`
- `agents/review`
- governance / supervisor 相关 role service

它们应只保留：

- 角色特有输入组装
- 角色特有 prompt / material 渲染
- 角色特有结果解释

它们不应继续各自实现一套通用 dispatch 骨架。

## 6. 模块边界要求

### 6.1 唯一合法入口原则

以下事情必须只有一个合法入口：

- 业务编排：只能经过 `domain`
- 执行启动：只能经过 `execution`
- 环境资源变更：只能经过 `environment`
- 共享状态记账：只能写入统一真源，不得由角色链各自维护影子状态

### 6.2 已有共享组件的正确位置

以下组件不应再继续被当作“随处可直接拼装”的工具箱，而应逐步挂到 execution 主线：

- `ExecutionRolePolicyService`
- `ExecutionLifecycleService`
- `CapacityService`
- `SessionRegistryService`
- `WorktreeManager`
- `CodeagentBackend`

### 6.3 manager 的最终定位

`manager` 是状态控制角色，不是通用执行引擎。

它负责：

- flow 映射
- issue scene 审计
- manager 角色决策

它不负责：

- 复写 planner/executor/reviewer 的通用 dispatch 骨架
- 持有独立的 capacity / lifecycle / session 控制面

### 6.4 governance / supervisor 的最终定位

`governance` 与 `supervisor` 都属于业务角色，不属于 runtime 内核。

它们负责：

- 各自的治理/监督判断
- 角色专属材料组装

它们不负责：

- 自己维护一套独立的 async 启动与 session 管理语义
- 绕过 execution 直接起 agent

## 7. 当前代码收缩方向

当前仓库后续收敛时，应优先做以下事情：

1. 先收拢 execution 主线  
   不再让 `manager`、`domain handlers`、`orchestra services` 分别拼启动流程。

2. 再瘦 manager / governance / supervisor  
   把它们收回到“角色逻辑”而不是“半执行框架”。

3. 最后退役旧 orchestra 编排逻辑  
   让 `orchestra` 保留 adapter、read model、兼容壳，而不是继续承担业务真相。

## 8. 判断一段代码是否放错层

出现以下信号时，应优先怀疑边界错误：

- 一个模块既决定“要不要执行”，又决定“怎么启动执行”
- 一个模块既持有业务状态推进，又直接操作 tmux/worktree
- 多个角色链各自调用 lifecycle/capacity/session，而没有统一入口
- 为了让新设计工作，不得不在旧 service 上继续打补丁
- 同一份 role policy 需要被多个上层手工拼接

## 9. 与其他标准的关系

- 事件语义与处理规则：见 [vibe3-event-driven-standard.md](vibe3-event-driven-standard.md)
- runtime driver / tick / async child：见 [vibe3-orchestra-runtime-standard.md](vibe3-orchestra-runtime-standard.md)
- 状态机与 authoritative refs：见 [v3/command-standard.md](v3/command-standard.md)
- worktree ownership：见 [vibe3-worktree-ownership-standard.md](vibe3-worktree-ownership-standard.md)

本文件负责回答“整体最后该长成什么样”，上述文件负责回答各分层内部的细节语义。

## 10. 标准结论

Vibe3 后续收敛的核心不是继续增加抽象，而是收回主控权。

最终应形成的结构是：

- `server/runtime` 只做 transport
- `domain` 只做业务编排
- `execution` 只做统一执行控制面
- `environment` 只做资源原语
- `manager/governance/supervisor/plan/run/review` 只做角色逻辑
- `orchestra` 退回 adapter 与兼容层

若没有完成这一步，`domain-first` 只会让系统多一层；  
完成这一步后，`domain-first` 才会真正降低耦合并压住代码膨胀。
