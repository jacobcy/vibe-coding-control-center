# Config 治理与重构设计

> 目标：将根目录 `config/` 从“杂糅入口”收敛为清晰的配置治理层，使配置文件按运行时和模块职责分布，并让配置说明同时承担开发指引、验证指引和清理依据。

## 背景

当前仓库的根目录 `config/` 同时承载了三类不同职责：

- V2 shell 集成入口：`config/aliases.sh`、`config/loader.sh`、`config/keys.template.env`
- V3 Python 运行时配置真源：`config/settings.yaml`
- V3 prompt 模板：`config/prompts.yaml`

这种布局会带来三个直接问题：

1. 目录层级无法表达职责边界，开发者需要先读实现代码才能知道某个配置属于 shell 还是 V3。
2. 文档与真相已经漂移。仓库内仍有多处文档引用 `config/aliases/*.sh`，但 alias 真正实现已经迁移到 `lib/alias/`。
3. `config/settings.yaml` 中至少有 `github_project`、`doc_limits` 两个配置块没有进入当前 `VibeConfig` schema，存在“写在配置里，但不一定生效”的风险。

## 现状审计结论

### 当前实际文件

根目录 `config/` 当前只有五个文件：

- `config/aliases.sh`
- `config/keys.template.env`
- `config/loader.sh`
- `config/prompts.yaml`
- `config/settings.yaml`

### 当前消费方

已确认生效的配置域：

- `flow`
- `ai`
- `code_limits`
- `review_scope`
- `quality`
- `pr_scoring`
- `review`
- `plan`
- `run`
- `orchestra`
- `prompts.yaml`

疑似失效或未完整接线的配置域：

- `github_project`
- `doc_limits`

### 现状判断

当前问题的核心不是“文件太少”，而是“配置真源、配置说明、配置消费方、配置验证方式没有形成一套治理模型”。

因此本次设计采用 **B 方案：按运行时和模块职责重组 + 配置注册表 + description 升级为治理说明**。

## 设计目标

### 一级目标

1. 让 `config/` 目录结构一眼可见职责边界。
2. 每个配置文件只承载一个稳定职责域。
3. 每个重要配置项都能回答六个问题：
   - 它为什么存在
   - 谁在读取它
   - 什么时候生效
   - 调整它会影响什么
   - 如何验证它真的在发挥作用
   - 它当前是 active、partial、planned 还是 deprecated
4. 让 manager runner 可以基于文档直接执行重构，而不是二次猜测。

### 非目标

1. 本次不改变功能语义，不顺手优化无关模块。
2. 本次不把配置彻底下沉到各 Python 模块目录中。
3. 本次不引入复杂的多文件动态 include 机制作为首要目标。

## 推荐目标结构

```text
config/
  README.md

  shell/
    aliases.sh
    loader.sh
    keys.template.env

  prompts/
    prompts.yaml

  v3/
    settings.yaml
    registry.yaml
    settings/
      flow.yaml
      ai.yaml
      paths-and-limits.yaml
      review-scope.yaml
      quality.yaml
      pr-scoring.yaml
      review.yaml
      plan.yaml
      run.yaml
      orchestra.yaml
      task-bridge.yaml
```

## 结构说明

### `config/shell/`

职责：V2 shell 入口层配置与模板。

包含：

- `aliases.sh`：兼容入口，不再冒充 alias 真身
- `loader.sh`：shell 初始化入口
- `keys.template.env`：密钥模板

说明原则：

- 明确声明“实现位于 `lib/alias/` 和 `lib/config.sh`”
- 配置文件本身负责入口和兼容，不负责业务实现说明

### `config/prompts/`

职责：V3 prompt 模板配置。

包含：

- `prompts.yaml`

说明原则：

- 明确哪些命令或服务会读取 prompt 模板
- 对每个模板块标记其消费方和 fallback 行为

### `config/v3/settings/`

职责：V3 运行时配置域拆分。

拆分规则不是平均拆分，而是按稳定职责域：

- `flow.yaml`
- `ai.yaml`
- `paths-and-limits.yaml`
- `review-scope.yaml`
- `quality.yaml`
- `pr-scoring.yaml`
- `review.yaml`
- `plan.yaml`
- `run.yaml`
- `orchestra.yaml`
- `task-bridge.yaml`

其中：

- `task-bridge.yaml` 用于承接当前 `github_project` 这类“任务桥接/远端真源定位”配置
- 如果确认 `github_project` 已废弃，则该文件可以不落地，但必须在注册表中标注 `deprecated` 或 `dead`

### `config/v3/settings.yaml`

职责：V3 唯一配置加载入口。

要求：

- 对 loader 来说仍然保持单入口
- 可通过聚合方式装配各子配置文件
- 对调用方透明，避免所有消费方一起改配置路径

### `config/v3/registry.yaml`

职责：配置治理注册表。

这是本方案的关键产物，用来记录：

- 每个配置域的真源文件
- schema 对应模块
- 运行时消费方
- 当前状态
- 测试覆盖
- 迁移建议

它不是运行时配置，而是开发治理真源。

## 配置域映射

| 当前配置块 | 建议目标文件 | 说明 |
|---|---|---|
| `flow` | `config/v3/settings/flow.yaml` | flow 生命周期规则 |
| `ai` | `config/v3/settings/ai.yaml` | AI client 接入配置 |
| `code_limits` | `config/v3/settings/paths-and-limits.yaml` | 统计口径与 LOC gate |
| `review_scope` | `config/v3/settings/review-scope.yaml` | 风险识别重点路径 |
| `quality` | `config/v3/settings/quality.yaml` | 覆盖率与质量门禁 |
| `pr_scoring` | `config/v3/settings/pr-scoring.yaml` | 风险评分与 merge gate |
| `review` | `config/v3/settings/review.yaml` | review agent 配置 |
| `plan` | `config/v3/settings/plan.yaml` | plan agent 配置 |
| `run` | `config/v3/settings/run.yaml` | runner/执行配置 |
| `orchestra` | `config/v3/settings/orchestra.yaml` | 编排、webhook、governance |
| `github_project` | `config/v3/settings/task-bridge.yaml` 或移除 | 先审计再决定保留/废弃 |
| `doc_limits` | 移除或补接线 | 当前不应继续伪装为 active |

## Description 升级规则

本次设计要求 description 从“字段注释”升级为“治理说明”。

对重要配置项，不再只写一句注释，而采用统一结构：

```yaml
block_on_score_at_or_above:
  value: 10
  description:
    purpose: "定义什么时候从提示升级为阻断。"
    consumer:
      - "scripts/hooks/pre-push.sh"
      - "src/vibe3/services/pr_scoring_service.py"
    effect:
      - "score >= 阈值时阻断推送或阻断合并"
    guidance:
      - "如果误报很多，先检查 weights 和 size thresholds"
      - "不要把它当成兜底垃圾桶无限上调"
    verification:
      - "构造临界 score 样例运行 pre-push hook"
      - "检查 inspect/review 输出中的 gate 判定"
    status: "active"
```

### 统一字段规范

- `purpose`：存在原因，不写实现细节
- `consumer`：直接读取它的代码入口
- `effect`：它如何影响系统行为
- `guidance`：如何正确调整它
- `verification`：如何证明它真的生效
- `status`：当前治理状态

### 状态枚举

- `active`：已接线并有明确消费方
- `partial`：部分接线，行为不完整
- `planned`：设计存在，但尚未接线
- `deprecated`：兼容保留，准备移除
- `dead`：无消费方，应删除

## 配置注册表规范

`config/v3/registry.yaml` 建议采用如下结构：

```yaml
review:
  source_file: "config/v3/settings/review.yaml"
  schema: "src/vibe3/config/settings.py:ReviewConfig"
  consumers:
    - "src/vibe3/agents/review_prompt.py"
    - "src/vibe3/agents/review_agent.py"
  tests:
    - "tests/vibe3/agents/test_review_prompt.py"
  status: "active"
  notes:
    - "review_prompt 已接线"
```

### registry 的价值

1. agent 修改配置前先查 registry，避免盲改。
2. 审计时可以快速发现 dead config。
3. 文档更新时有统一真源，不需要在多个文档里重复解释。

## 判定规则

### 什么叫“配置是有用的”

必须同时满足以下至少两项：

1. 进入 schema 或被显式解析
2. 有运行时代码消费方
3. 有测试覆盖或至少有可执行验证路径

否则不能标记为 `active`。

### 什么叫“description 在发挥作用”

当开发者或 agent 面对一个配置项时，应该不读实现也能知道：

1. 改它之前要看哪些文件
2. 改它之后要跑哪些验证
3. 改错了会影响什么范围

如果 description 不能回答这三个问题，它就只是注释，不是开发指引。

## 迁移原则

1. **单入口兼容优先**
   - 运行时仍通过 `config/v3/settings.yaml` 进入
2. **先审计，后搬运**
   - 先区分 active/partial/dead，再做移动
3. **目录重组不等于语义变更**
   - 第一阶段只迁移结构，不顺手改策略
4. **文档跟着真源走**
   - 所有仍引用 `config/aliases/*.sh` 的文档都要修正到真实结构

## 风险与防护

### 风险 1：拆文件后 loader 复杂度上升

防护：

- 保持单聚合入口
- 在 schema 层做统一装配

### 风险 2：把未接线配置当成 active 保留下来

防护：

- 先建立 registry
- 所有配置块先做状态判定再迁移

### 风险 3：description 继续写成大段注释，没人维护

防护：

- 只对关键配置采用结构化 description
- 让 `verification` 字段直接对应测试或命令

## 验收标准

本设计落地后，应满足：

1. 任意开发者看到 `config/` 目录即可分辨 shell、V3、prompts 三类职责。
2. 任意一个重要配置项都能从 registry 找到消费方和验证方式。
3. 当前无效配置项会被明确标记为 `planned`、`deprecated` 或 `dead`，而不是继续混在 active 配置里。
4. 文档中不再把 `config/aliases.sh` 描述为 alias 真身，也不再引用不存在的 `config/aliases/*.sh`。
5. manager runner 可以直接按实施计划推进，不需要重新做结构设计。
