# Config Governance Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将仓库根目录 `config/` 重构为清晰的配置治理层，按职责拆分 V2 shell、V3 settings、prompts，并补齐配置注册表与开发指引说明。

**Architecture:** 保持 `config/v3/settings.yaml` 作为 V3 运行时单入口，在其背后重组子配置文件；新增 `config/v3/registry.yaml` 作为治理真源；shell 与 prompts 分别独立成域。先做审计和兼容迁移，再修正文档和测试。

**Tech Stack:** YAML, Python 3.10+, Pydantic, shell loader, GitHub issue/PR workflow

---

### Task 1: 建立配置审计基线

**Files:**
- Modify: `docs/plans/2026-04-02-config-governance-design.md`
- Create: `temp/config-audit-notes.md`

**Step 1: 列出现有配置文件与配置块**

Run:

```bash
find config -maxdepth 3 -type f | sort
rg -n "^flow:|^ai:|^code_limits:|^review_scope:|^quality:|^pr_scoring:|^review:|^plan:|^run:|^orchestra:|^github_project:|^doc_limits:" config/settings.yaml
```

Expected: 能完整列出当前 `config/` 文件和 `settings.yaml` 顶层配置块。

**Step 2: 审计每个配置块的消费方**

Run:

```bash
rg -n "config\\.(flow|ai|code_limits|review_scope|quality|pr_scoring|review|plan|run|orchestra)|get_config\\(\\)\\." src scripts tests -S
```

Expected: 形成“配置块 -> 消费方”对照表。

**Step 3: 记录 active/partial/dead 初判**

Write `temp/config-audit-notes.md`，至少包含：

- 配置块名称
- schema 是否存在
- 直接消费方
- 测试覆盖
- 初始状态判断

**Step 4: 运行最小验证**

Run:

```bash
uv run pytest tests/vibe3/services/test_pr_scoring_service.py tests/vibe3/agents/test_review_prompt.py tests/vibe3/orchestra/test_serve.py -q
```

Expected: 当前配置相关核心测试通过，作为迁移前基线。

### Task 2: 重组目录结构并保持单入口

**Files:**
- Create: `config/README.md`
- Create: `config/shell/aliases.sh`
- Create: `config/shell/loader.sh`
- Create: `config/shell/keys.template.env`
- Create: `config/prompts/prompts.yaml`
- Create: `config/v3/settings.yaml`
- Create: `config/v3/settings/flow.yaml`
- Create: `config/v3/settings/ai.yaml`
- Create: `config/v3/settings/paths-and-limits.yaml`
- Create: `config/v3/settings/review-scope.yaml`
- Create: `config/v3/settings/quality.yaml`
- Create: `config/v3/settings/pr-scoring.yaml`
- Create: `config/v3/settings/review.yaml`
- Create: `config/v3/settings/plan.yaml`
- Create: `config/v3/settings/run.yaml`
- Create: `config/v3/settings/orchestra.yaml`
- Optional: `config/v3/settings/task-bridge.yaml`
- Keep compatibility or remove old files after cutover

**Step 1: 建立新目录骨架**

Use `apply_patch` 创建目标目录中的说明和配置文件占位结构。

Expected: 新结构存在，但旧入口暂不删除。

**Step 2: 将现有配置按职责迁移到对应文件**

规则：

- shell 文件只迁移入口与模板
- prompts 单独迁移
- V3 settings 按职责域拆分

Expected: 每个配置域只出现在一个目标文件中。

**Step 3: 保持 `config/v3/settings.yaml` 为聚合入口**

Implementation note:

- 若当前 loader 不支持 include，则可先生成聚合文件
- 允许第一阶段用代码装配子文件，不要求纯 YAML include

Expected: 运行时仍然只需要一个入口文件。

**Step 4: 保留迁移兼容层**

Expected:

- 旧路径在短期内仍可工作，或有明确失败提示
- 不直接破坏现有调用方

### Task 3: 建立配置注册表和 description 规范

**Files:**
- Create: `config/v3/registry.yaml`
- Modify: `config/v3/settings/*.yaml`
- Modify: `docs/standards/configuration-standard.md`

**Step 1: 为每个配置域登记 registry**

每个域至少包含：

- `source_file`
- `schema`
- `consumers`
- `tests`
- `status`
- `notes`

**Step 2: 将关键配置项 description 升级为治理说明**

至少覆盖：

- `code_limits`
- `review_scope`
- `pr_scoring.merge_gate`
- `review.agent_config`
- `plan.agent_config`
- `run.agent_config`
- `orchestra.governance`

**Step 3: 标记可疑配置域状态**

对 `github_project`、`doc_limits` 给出明确状态：

- `active`
- `partial`
- `planned`
- `deprecated`
- `dead`

Expected: 不再存在“看起来像生效，其实没人读”的配置块。

### Task 4: 更新 loader、schema 与消费方

**Files:**
- Modify: `src/vibe3/config/loader.py`
- Modify: `src/vibe3/config/settings.py`
- Modify: `src/vibe3/prompts/template_loader.py`
- Modify: `src/vibe3/services/pr_create_usecase.py`
- Modify any tests referencing `config/settings.yaml` or `config/prompts.yaml`

**Step 1: 调整 V3 loader 到新入口**

Run:

```bash
sed -n '1,220p' src/vibe3/config/loader.py
```

Implementation:

- 将默认入口切到 `config/v3/settings.yaml`
- 如需兼容旧入口，添加迁移期 fallback

**Step 2: 调整 prompts 默认路径**

Implementation:

- 将默认路径切到 `config/prompts/prompts.yaml`
- 保留旧路径 fallback，直到文档和测试一起切完

**Step 3: 调整直接硬编码旧路径的调用方**

重点检查：

- `src/vibe3/services/pr_create_usecase.py`
- `src/vibe3/prompts/template_loader.py`
- tests 中硬编码路径的用例

**Step 4: 运行定向测试**

Run:

```bash
uv run pytest tests/vibe3/services/test_ai_service.py tests/vibe3/prompts/test_models.py tests/vibe3/orchestra/test_serve.py tests/vibe3/agents/test_review_prompt.py -q
```

Expected: 新路径不破坏现有行为。

### Task 5: 清理文档漂移并补齐开发指引

**Files:**
- Modify: `AGENTS.md`
- Modify: `STRUCTURE.md`
- Modify: `CLAUDE.md`
- Modify: `skills/vibe-instruction/SKILL.md`
- Modify: `docs/standards/configuration-standard.md`
- Modify any docs still referencing `config/aliases/*.sh`

**Step 1: 搜索过时路径引用**

Run:

```bash
rg -n "config/aliases/|config/settings.yaml|config/prompts.yaml" AGENTS.md STRUCTURE.md CLAUDE.md skills docs tests -S
```

**Step 2: 修正文档为新结构与新语义**

要求：

- 明确 alias 真身在 `lib/alias/`
- 明确 V3 配置入口与 registry 的职责
- 明确 description 是开发指引，不只是注释

**Step 3: 运行文档相关最小验证**

Run:

```bash
rg -n "config/aliases/" AGENTS.md STRUCTURE.md CLAUDE.md skills docs -S
```

Expected: 不再引用不存在的 `config/aliases/*.sh`。

### Task 6: 验收与收口

**Files:**
- Modify: `docs/plans/2026-04-02-config-governance-design.md`
- Modify: `config/v3/registry.yaml`

**Step 1: 验收目录结构**

Run:

```bash
find config -maxdepth 3 -type f | sort
```

Expected: shell、prompts、v3 三层结构清晰。

**Step 2: 验收 registry 完整性**

Run:

```bash
sed -n '1,260p' config/v3/registry.yaml
```

Expected: 所有重要配置域都有 consumer、status、tests。

**Step 3: 验收配置行为**

Run:

```bash
uv run pytest tests/vibe3/services/test_pr_scoring_service.py tests/vibe3/analysis/test_coverage_service.py tests/vibe3/orchestra/test_serve.py tests/vibe3/services/test_ai_service.py -q
```

Expected: 关键配置消费路径全部通过。

**Step 4: 提交与 PR**

Run:

```bash
git add config src/vibe3 docs AGENTS.md STRUCTURE.md CLAUDE.md skills
git commit -m "refactor: reorganize config governance"
```

Expected: 提交只包含配置治理相关改动。
