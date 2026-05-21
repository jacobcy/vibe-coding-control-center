# Vibe3 Portability Decoupling Design

> 目标：让 `vibe3` 能在任意 Git 仓库中完成最小初始化与运行，同时保留 Vibe Center 当前 repo 作为一套 opinionated distribution，而不是把当前仓库的治理壳强行复制给所有项目。

## 背景

当前 `vibe3` 的核心运行时已经具备跨仓库复用的潜力，但实际使用时仍然深度依赖当前 repo 的以下资源：

- repo-local `skills/`
- repo-local `.agent/`
- repo-local `AGENTS.md` / `CLAUDE.md` / `SOUL.md` / `STRUCTURE.md`
- repo-local `config/prompts/*`、`config/v3/*`
- repo-local `supervisor/`
- repo-local 分支、label、workflow 协议

这导致当前形态更像“Vibe Center 仓库内部工具链”，而不是“可安装到其他项目的通用运行时 + 可选项目发行版”。

同时，用户希望的目标边界已经很明确：

1. 必要运行时资源复制到用户目录。
2. 项目语义和治理真源继续读取当前 repo。
3. 新项目通过 `vibe init` 接入最小能力，而不是被迫复制当前仓库全部外壳。

## 设计原则

### 1. 全局复制运行时资产，项目保留协作语义真源

- `~/.vibe/` 承载“安装后任何项目都可复用”的通用资源。
- 当前 repo 继续承载 `skills/`、`.agent/`、`AGENTS.md` 等项目特有语义。

### 2. 明确优先级，禁止全局资源静默覆盖项目真源

统一读取优先级：

1. repo-local 真源
2. repo-local `.vibe/` 初始化产物
3. user-global `~/.vibe/assets`
4. package builtin fallback

任何全局资源都只能兜底，不能反向定义项目协议。

### 3. Core 与 Distribution 分层

- `vibe3 core` 负责 flow / handoff / runtime / orchestration 能力。
- `vibe-center distribution` 负责当前仓库的 skills、policies、docs、supervisor、workflows。

### 4. Init 只生成最小骨架，不复制整套仓库外壳

`vibe init` 的职责是：

- 检测/落地最小项目适配层
- 生成 `.vibe/config.yaml`
- 选择 profile
- 建立全局资产与 repo 真源的连接规则

它不是当前 `scripts/init.sh` 的原样搬运。

## 绑定项审计

### A. 应抽到用户目录 `~/.vibe/assets/` 的资源

这些资源不应依赖具体业务仓库，可由安装包分发或首次安装时同步：

- 通用 prompt templates
- 通用 prompt recipes
- 通用 init templates
- 通用 minimal policy skeleton
- 通用 models / backend preset 模板
- 通用 skills manifest
- `vibe init` 所需模板文件

它们的特点是：

- 不要求项目采用当前 repo 的术语体系
- 不要求项目具有 `.agent/` / `skills/` / `supervisor/`
- 任何仓库都可以使用同一份默认资产

### B. 必须继续留在 repo 的真源

这些资源代表项目语义、项目治理或项目协作约定，不应默认全局化：

- `skills/`
- `.agent/`
- `AGENTS.md`
- `CLAUDE.md`
- `SOUL.md`
- `STRUCTURE.md`
- `supervisor/`
- `docs/standards/`
- repo-local `config/v3/settings.yaml`
- repo-local `config/v3/models.json`
- repo-local `config/v3/skills.json`
- repo-local label / branch / workflow 语义

### C. 应由 `vibe init` 生成到目标项目的最小骨架

这些资源既不应放在用户目录作为共享真源，也不应要求目标项目手写：

- `.vibe/config.yaml`
- `.gitignore` 追加片段
- 最小 profile 标记
- 可选的 repo-local overlay 目录
- 可选的 `.agent/` skeleton（仅在 profile 明确启用时）

## 目标分层

### Layer 1: Runtime Core

职责：

- CLI
- flow / handoff / status
- shared state
- orchestration primitives
- loader / asset resolver

约束：

- 不直接假设存在 `.agent/`
- 不直接假设存在 `skills/`
- 不直接硬编码 `supervisor/apply.md`
- 不直接把 `task/issue-*`、`state/handoff` 当成通用默认协议

### Layer 2: Global Assets

位置：`~/.vibe/assets/`

职责：

- 提供 runtime 默认资源
- 提供 init 模板
- 提供最小 profile 模板

约束：

- 只能提供 generic defaults
- 不能定义具体仓库的治理语义

建议结构：

```text
~/.vibe/
  assets/
    prompts/
      prompts.yaml
      prompt-recipes.yaml
    templates/
      init/
        minimal/
        github-flow/
        vibe-center/
    policies/
      common.md
      plan.md
      run.md
      review.md
    models/
      models.json
    manifests/
      skills.json
```

### Layer 3: Repo Adapter

职责：

- 定义当前项目是否启用 `.agent/`
- 定义当前项目是否启用 repo-local `skills/`
- 定义当前项目是否启用 GitHub label / branch / supervisor 协议
- 定义当前项目的 prompt / models / policy overlay

建议入口：

- repo-local `.vibe/config.yaml`
- profile: `minimal` / `github-flow` / `vibe-center`

### Layer 4: Vibe Center Distribution

职责：

- 继续承载当前仓库的 opinionated 协作协议
- 作为 `vibe-center` profile 的具体实现

它不是 core 本体，而是 core 的一个完整发行版。

## 资源边界矩阵

| 资源 | 去向 | 原因 |
|---|---|---|
| 通用 prompts | `~/.vibe/assets` | 任何项目可复用 |
| 通用 prompt recipes | `~/.vibe/assets` | 任何项目可复用 |
| 通用 policy skeleton | `~/.vibe/assets` | 任何项目可复用 |
| init 模板 | `~/.vibe/assets` | `vibe init` 依赖 |
| `skills/` | repo-local | 项目协作语义真源 |
| `.agent/` | repo-local | 项目 workflow / policy / template 真源 |
| `supervisor/` | repo-local | 当前发行版特有 |
| `AGENTS.md` / `CLAUDE.md` / `SOUL.md` | repo-local | 项目治理壳 |
| `.vibe/config.yaml` | repo-local generated | 项目适配入口 |
| labels / branch convention | repo-local profile | 项目协议，不应全局默认 |

## Loader 改造目标

### 当前问题

当前 loader / resolver 仍广泛依赖 repo 相对路径：

- `config/prompts/prompts.yaml`
- `config/prompts/prompt-recipes.yaml`
- `.agent/policies/*`
- `skills/<name>/SKILL.md`
- `config/v3/models.json`

### 目标行为

统一通过 `AssetResolver` 类接口按以下顺序解析：

1. repo-local explicit path
2. repo-local `.vibe/` overlay
3. `~/.vibe/assets`
4. builtin fallback

### 改造要求

- 所有 path lookup 集中在 resolver 层
- 业务层不再直接拼接 repo 相对路径
- 所有 fallback 都要可观测，可输出 provenance

## `vibe init` 目标行为

> 注：当前 `vibe init` 由 `bin/vibe` shell 脚本实现。`vibe3` Python CLI 尚未实现 `init` 子命令。

### 命令形态

```bash
vibe init --profile minimal
vibe init --profile github-flow
vibe init --profile vibe-center
```

### `minimal` profile

适用于普通 Git 仓库，仅接入最小 runtime：

- 生成 `.vibe/config.yaml`
- 指向全局 prompts / recipes / policies
- 不生成 `.agent/`
- 不要求 `skills/`
- 不启用 GitHub orchestration 协议

### `github-flow` profile

适用于希望启用 issue / PR / label 协议的项目：

- 在 `minimal` 基础上启用 GitHub 相关配置
- 生成最小 policy overlay
- 明确 labels / branch conventions 可配置
- 仍不默认复制 Vibe Center 的 skills / docs 治理壳

### `vibe-center` profile

适用于当前仓库或想完整采用当前发行版的项目：

- 允许接入 repo-local `skills/`
- 允许接入 repo-local `.agent/`
- 允许接入 `supervisor/`
- 允许接入完整 orchestration / governance 语义

## Repo 绑定项拆出策略

### 1. 硬编码路径先收口到 resolver

第一优先级不是立刻重命名所有目录，而是把这些直接路径访问收口：

- `skills/<name>/SKILL.md`
- `.agent/policies/*`
- `.agent/reports/*`
- `config/v3/models.json`
- `config/prompts/*`
- `supervisor/apply.md`

### 2. 默认 branch / label 语义改成 profile 配置

以下语义不应继续作为 universal default：

- `task/issue-*`
- `dev/issue-*`
- `state/handoff`
- `supervisor`
- `vibe-manager-agent`

这些都应转成 profile-configured conventions。

### 3. 让 Vibe Center 自己成为第一个 adapter

如果当前仓库仍然依赖“隐式默认值”才能运行，说明 core / adapter 没拆干净。

目标是：

- 当前仓库通过 `vibe-center` profile 运行
- 空仓库通过 `minimal` profile 运行
- GitHub 协作仓库通过 `github-flow` profile 运行

## 迁移阶段

### Phase 1: 定义边界与清单

- 审计所有 repo-bound path
- 定义 global assets 清单
- 定义 repo adapter 清单
- 定义 profile 模型

### Phase 2: 资产分发

- 把通用 prompts / recipes / templates / minimal policies 做成 package or installable assets
- 增加 `assets sync` 能力

### Phase 3: Loader / Resolver 收口

- 所有路径读取统一走 resolver
- 加入 provenance 输出
- 为 repo-local override 提供一致入口

### Phase 4: `vibe init`

- 落地 profile-based init
- 支持空仓库最小接入
- 支持 GitHub-flow 接入

### Phase 5: Vibe Center Adapter 化

- 把当前 repo 的 opinionated 资源显式声明成 `vibe-center` profile
- 清理 core 对 repo 特有资源的隐式依赖

### Phase 6: 验证与收口

- 空仓库 smoke test
- 现仓库回归
- 文档更新

**Validation Results**: See [Smoke Tests](../validation/smoke-tests.md)
**Contract Documentation**: See [Portability Contract](../migration/portability-contract.md)

## Issue 拆分原则

### Parent Issue

新建一个总母题 issue，职责仅限：

- 说明 portability / decoupling 的目标
- 链接本方案文档
- 跟踪子 issue

### 子 Issue 划分

按可交付边界拆成以下类型：

1. 资产分发层
2. loader / resolver 层
3. `vibe init` / profile 层
4. core 去 repo 假设层
5. Vibe Center adapter 层
6. 验证与文档层

### 依赖规则

- 资产分发先于 `init`
- loader / resolver 先于大规模去硬编码
- Vibe Center adapter 化依赖 resolver 能力
- 最终验证依赖前面全部收敛

## 建议 issue 图

```text
Parent: Portability / Decoupling program
  ├─ Issue A: package global assets
  ├─ Issue B: add asset resolver + provenance
  ├─ Issue C: implement init + profiles
  ├─ Issue D: remove repo-bound defaults from core
  ├─ Issue E: extract vibe-center adapter/profile
  └─ Issue F: end-to-end validation and docs
```

推荐依赖：

- B depends on A
- C depends on A + B
- D depends on B
- E depends on B + D
- F depends on C + D + E

## 决策

本方案选择的不是“把当前 repo 全量模板复制到其他项目”，而是：

- 全局复制 runtime assets
- repo 保留协作语义真源
- profile 决定项目接入深度
- Vibe Center 自己降级为一个显式 distribution

这是最符合当前目标、且最不容易在后续迁移中失控的路径。
