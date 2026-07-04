---
document_type: decision
title: 运行时加载时机契约 — Kernel/Material/Job 三层与可插拔边界
adr_id: 0003
status: accepted
decides: "可插拔边界以加载时机为物理判据：kernel 进程级（重启生效）、material dispatch-time（下个 job 生效）、job-frozen 运行中冻结；层归属由加载时机决定，不由目录决定。"
scope:
  - src/vibe3/prompts/manifest.py
  - src/vibe3/config/convention_resolver.py
  - src/vibe3/config/loader.py
  - src/vibe3/runtime/heartbeat.py
  - src/vibe3/execution/command_adapter.py
  - tests/vibe3/test_modularity/**
date: 2026-06-09
supersedes: null
superseded_by: null
related_docs:
  - docs/standards/v3/human-mirror-architecture-philosophy.md
  - src/vibe3/prompts/manifest.py
  - src/vibe3/runtime/heartbeat.py
  - src/vibe3/execution/command_adapter.py
issues:
  - 2183
  - 2166
  - 2175
  - 1896
---

# 运行时加载时机契约 — Kernel/Material/Job 三层与可插拔边界

## Context

一批 RFC（#2183 可插拔边界 / #2166 policy-material loader / #2175 版本元数据 / #1896 profile-adapter 跨项目资源）都卡在**同一个未决问题**：到底哪些模块是可替换的扩展点，判据是什么？

此前的圈定思路存在两个失败模式：

- **按功能圈**：得到一份主观的功能白名单，无法测试，边界随讨论漂移。
- **按目录圈**：在本代码库行不通——`flow` 横切 7 层（models / clients / domain / services / orchestra / commands / ui），`services/` 98 个文件混杂底座级与业务级，目录切不出干净边界。

更尖锐的是，当前材料加载时机本身就不统一，并已造成一个**可证的契约破坏**：

- `prompts/manifest.py PromptManifest.load_default` 用 `@lru_cache(maxsize=1)`（进程级永久缓存），`config/convention_resolver.py` 两处 `@cache` 同理——改材料必须重启进程才生效。
- `config/loader.load_runtime_config` 无缓存，每次调用重读——改材料下次调用即生效。
- orchestra 是 heartbeat 驱动的**长驻进程**，CLI 是**短进程**。于是同一个 plan 角色：手动 `/vibe-plan (skill)` 走短进程、材料每次新读（热生效）；orchestra 自动调走长驻进程、被 `lru_cache` 锁住（重启才生效）。
- 结果：**skill→command 与 orchestra→command 的材料语义不一致**，直接违反 #2183 验收标准第 4 条的等价要求。

约束条件：

- 不引入热重载机制（复杂、易错）。
- 运行中的 job 不得被热更新（#2175：running job keeps the versions it started with）。
- 最小变更：不做物理 kernel 目录搬迁。

## Decision

**以「加载时机」作为可插拔边界的物理判据**：一个 surface 是否可插拔，由它在 server 进程里被加载一次（kernel），还是每次 dispatch 重新解析（material）决定。判据可测试、客观，取代功能白名单与目录归属。

确立三类加载时机：

```yaml
process-once:    # kernel · 常驻 · 重启生效（Python import 缓存默认行为）
  内容: 调度骨架 / registry / queue 原语 / capacity / gate / role 契约骨架 / 状态机契约
dispatch-time:   # material · 可插拔 · 下个 job 生效（关键边界是 dispatch,不是 tick）
  内容: prompt / policy / material / backend-model / convention / adapter 资源
  缓存策略: 可配置开关 material_cache,两种工作模式（见下）
job-frozen:      # 运行中冻结 · job 起点快照 + 版本戳（满足 #2175）
  内容: 已 dispatch 的 JobEnvelope 携带的材料快照与版本
```

材料缓存采用「可配置开关 + 两种工作模式」（而非单一 dispatch-scoped），不在性能与热生效间二选一：

- **生产模式**（`material_cache` enabled，默认）：进程级缓存生效，材料在 server 生命周期内冻结，性能最优（保留 824375ac 收益），改材料需重启；运行可预测、同一 server 周期内版本一致。
- **开发模式**（`material_cache` disabled）：缓存关闭，dispatch-scoped 重读，材料热生效，便于迭代 prompt/policy。
- 两种模式都在 dispatch 时记录版本戳（#2175）：生产模式同周期版本稳定，开发模式逐 dispatch 反映当时材料。

逻辑上对应 4 层（Substrate / Orchestration-Core / Pluggable-Roles / Optional-Periphery），但**层归属由加载时机决定，不由目录决定**。

两条衍生原则：

- **接口冻结、材料插拔**：可插拔的是「角色的材料/实现」，不是「角色的契约接口」。`CommandType` 与 `JobEnvelope` 语义冻结（否则自动调度断裂），prompt/policy/backend/adapter 资源可插拔。这解开了"role 可替换 vs 禁止替换 plan/run/review"的表面矛盾。
- **边界用测试守护，不搬目录**：用一份 kernel manifest + modularity 风格守护测试圈定（判据：改某文件、不重启，下个 dispatch 该不该变？），复用 `tests/vibe3/test_modularity/` 既有机制，不移动物理文件。

关键权衡：

- ✅ 判据可测试、客观；统一 CLI/orchestra 两条路径等价；一次性解锁 #2183/#2166/#2175/#1896。
- ✅ 不需要热重载机制；天然满足 running job 不热更新。
- ✅ 缓存做成两种工作模式：默认保留进程级 cache 性能（824375ac），开发态可关、材料热生效。
- ❌ 引入配置开关 + 两条加载路径，需测试覆盖 enabled/disabled 两种模式。

## Consequences

正面影响：

- 可插拔边界从抽象/主观变为**可测试的物理判据**，杜绝边界漂移。
- 修复 CLI 与 orchestra 的材料语义不等价（#2183 验收标准第 4 条）。
- 材料热生效：改 prompt/policy 无需重启 orchestra，下个 dispatch 即生效。
- 版本可解释（#2175）：dispatch 时刻读到的材料即为该 job 的版本快照。
- #2183 / #2166 / #2175 / #1896 获得统一的实施框架。

负面影响：

- 材料加载存在两种模式，loader 与测试需覆盖 enabled/disabled 两条路径。
- 开发模式（cache disabled）下每个 dispatch 多一次材料 I/O；生产模式保留进程级 cache，无此开销。
- 需新增 kernel manifest 与守护测试，并持续维护避免清单漂移。

风险：

- 两种模式行为差异需在配置/文档中明确，避免误用（生产态误开 disabled 影响性能，开发态误用 enabled 看不到材料更新）—— 默认 enabled + 文档说明缓解。
- kernel 圈定清单可能随重构漂移 —— 用守护测试（kernel 模块不得 import-time 内联材料、不得依赖 userland 业务模块）缓解。

## How

**硬约束：本段只放链接，禁止复制实现细节。**

相关实现、清单与操作流程见：

- [Issue #2183](https://github.com/jacobcy/vibe-coding-control-center/issues/2183) — 可插拔边界根 RFC（4 层模型 + kernel 圈定清单 + 守护测试）
- [Issue #2166](https://github.com/jacobcy/vibe-coding-control-center/issues/2166) — MaterialLoader / PolicyLoader 契约（dispatch-time 加载 + dispatch-scoped 缓存）
- [Issue #2175](https://github.com/jacobcy/vibe-coding-control-center/issues/2175) — 版本元数据字段与记录位置（JobEnvelope / JobResult metadata）
- [Issue #1896](https://github.com/jacobcy/vibe-coding-control-center/issues/1896) — profile/adapter 资源解析归入 dispatch-time material 层
- [src/vibe3/prompts/manifest.py](../../src/vibe3/prompts/manifest.py) — 当前 PromptManifest lru_cache（待改 dispatch-scoped）
- [src/vibe3/config/convention_resolver.py](../../src/vibe3/config/convention_resolver.py) — 当前 convention @cache（待改 dispatch-scoped）
- [src/vibe3/runtime/heartbeat.py](../../src/vibe3/runtime/heartbeat.py) — tick loop（dispatch 加载点收口位置）
- docs/standards/v3/runtime-loading-contract.md — 落地标准（待写，ADR accepted 后补）
